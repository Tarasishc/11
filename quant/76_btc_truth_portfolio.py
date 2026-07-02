"""ЧЕСНИЙ ПІДСУМОК ПО BTC: повна конфігурація (KC + FVG) під 15m-ІСТИНОЮ.
KC: вхід маркетом на open наступного бара (філ негайний) -> стоп/тейк по 15m.
FVG: як у 75. Порівнюємо: база vs покращення (mid50+wait>2+ADX20 лише для FVG).
Це нижня чесна планка по BTC; по інших монетах 15m нема — приймаємо ту саму фізику."""
import importlib.util, builtins, numpy as np, pandas as pd
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c75", "quant/75_intrabar_truth.py")
c75 = importlib.util.module_from_spec(spec); spec.loader.exec_module(c75); builtins.print = _p
import engine as E
naive, adxv = c75.naive, c75.adxv
FEE, ES, SS = c75.FEE, c75.ES, c75.SS
D4, M15 = c75.D4, c75.M15
m15_ts, h15, l15 = c75.m15_ts, c75.h15, c75.l15
d4_ts = c75.d4_ts

def kc_setups(d):
    cl = d["close"]; o, h, l, c = [d[x].to_numpy() for x in ["open", "high", "low", "close"]]
    atr = E.atr(d, 14).to_numpy(); ax = adxv(d); n = len(c); S = []
    mid = E.ema(cl, 20); band = 2*E.atr(d, 10)
    up = ((cl > mid+band) & (cl > E.ema(cl, 200))).to_numpy()
    dn = ((cl < mid-band) & (cl < E.ema(cl, 200))).to_numpy()
    for i in range(1, n-1):
        if not np.isfinite(atr[i]) or ax[i] < 20: continue
        for si, sig in ((1, up), (-1, dn)):
            if sig[i] and not sig[i-1]:
                en = o[i+1]; D = 2.0*atr[i]
                S.append((i+1, si, en, en - si*D, en + si*2*D, D, "KC"))
    return S

def truth_exit(j4, si, en, sp, tg, pre_filled):
    """15m-прохід від початку 4h-бара j4. pre_filled=True для KC (філ на open)."""
    b = np.searchsorted(m15_ts, d4_ts[j4], "left")
    filled = pre_filled
    while b < len(m15_ts):
        lo, hi = l15[b], h15[b]
        if not filled:
            if (lo <= en) if si > 0 else (hi >= en):
                filled = True
                if (lo <= sp) if si > 0 else (hi >= sp): return "stop", sp, b
                if (hi >= tg) if si > 0 else (lo <= tg): return "tgt", tg, b
        else:
            if (lo <= sp) if si > 0 else (hi >= sp): return "stop", sp, b
            if (hi >= tg) if si > 0 else (lo <= tg): return "tgt", tg, b
        b += 1
    return "eod", float(M15["close"].iloc[-1]), len(m15_ts)-1

def R_of(si, en, exlvl, D, extype):
    enf = en*(1 + si*ES); exf = exlvl*(1 - si*SS) if extype == "stop" else exlvl
    return si*(exf - enf)/D - 2*FEE*(enf/D)

def btc_portfolio_truth(fvg_kw):
    fv = [(j, si, en, sp, tg, D, "FVG") for j, si, en, sp, tg, D in
          [(t[0], t[1], t[2], t[3], t[4], t[5]) for t in raw_fvg(fvg_kw)]]
    S = sorted(kc_setups(D4) + fv, key=lambda x: x[0])
    out = []; ou_b15 = -1
    for j4, si, en, sp, tg, D, tag in S:
        b_start = np.searchsorted(m15_ts, d4_ts[j4], "left")
        if b_start <= ou_b15: continue                     # одна позиція за раз (по 15m-часу)
        ext, lvl, b_end = truth_exit(j4, si, en, sp, tg, pre_filled=(tag == "KC"))
        if ext == "eod" and b_end == len(m15_ts)-1 and tag == "FVG":
            # можливо, філа взагалі не було -> перевіримо: якщо ціна так і не торкнулась entry
            seg_lo = l15[b_start:]; seg_hi = h15[b_start:]
            touched = (seg_lo.min() <= en) if si > 0 else (seg_hi.max() >= en)
            if not touched: continue
        out.append((naive(M15.index[min(b_end, len(m15_ts)-1)]), tag, R_of(si, en, lvl, D, ext)))
        ou_b15 = b_end
    return pd.DataFrame(out, columns=["ts", "tag", "R"])

def raw_fvg(kw):
    return [(j, si, en, sp, tg, D) for j, si, en, sp, tg, D, *_ in
            [t for t in c75_fvg(kw)]]

def c75_fvg(kw):
    # ті самі сетапи, що в 75 (без внутрішньої одна-за-раз — послідовність робимо тут по 15m)
    d = D4
    o, h, l, c = [d[x].to_numpy() for x in ["open", "high", "low", "close"]]
    atr = E.atr(d, 14).to_numpy(); em = E.ema(d["close"], 200).to_numpy(); ax = adxv(d)
    n = len(c); S = []
    for k in range(2, n-1):
        for si in (1, -1):
            if si > 0 and not (h[k-2] < l[k] and c[k] > em[k]): continue
            if si < 0 and not (l[k-2] > h[k] and c[k] < em[k]): continue
            zt = l[k] if si > 0 else h[k]; zb = h[k-2] if si > 0 else l[k-2]
            entry = (zt + zb)/2 if kw.get("fvg_mid") else zt
            for j in range(k+1, min(k+21, n)):
                hit = l[j] <= entry if si > 0 else h[j] >= entry
                if not hit: continue
                if j - k <= kw.get("min_wait", 0): break
                trok = c[j] > em[j] if si > 0 else c[j] < em[j]
                if not trok: break
                fa = kw.get("fvg_adx", 0)
                if fa > 0 and not (np.isfinite(ax[j]) and ax[j] >= fa): break
                D = max(abs(entry - zb), 0.5*atr[j])
                S.append((j, si, entry, entry - si*D, entry + si*2*D, D)); break
    return S

def mstats(T, risk=0.01):
    T = T.sort_values("ts"); r = T["R"].values
    eq = np.cumprod(1 + risk*r)
    me = pd.Series(eq, index=pd.DatetimeIndex(T["ts"])).resample("ME").last().dropna()
    mr = me.pct_change().dropna(); mr = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mr])*100
    dd = ((eq/np.maximum.accumulate(eq))-1).min()*100
    span = (T["ts"].max()-T["ts"].min()).days/30.44
    return len(r), r.mean(), len(r)/span, mr.mean(), mr.median(), (mr > 0).mean()*100, dd

print("BTC, ПОВНА конфігурація KC+FVG під 15m-ІСТИНОЮ (вся історія, risk 1%)\n")
print(f"{'варіант':26s} | {'n':>4} {'exp':>7} {'уг/міс':>6} | {'сер/міс':>8} {'мед':>6} {'+міс':>5} {'DD':>5}")
print("-"*82)
for name, kw in [("база (FVG край)", {}),
                 ("покращ. (mid+wait>2+ADX20)", dict(fvg_mid=True, min_wait=2, fvg_adx=20))]:
    T = btc_portfolio_truth(kw)
    n, e, tpm, avg, med, pos, dd = mstats(T)
    print(f"{name:26s} | {n:4d} {e:+7.3f} {tpm:6.1f} | {avg:+7.2f}% {med:+5.2f}% {pos:4.0f}% {dd:4.0f}%")
    k_ = T[T.tag == "KC"]; f_ = T[T.tag == "FVG"]
    print(f"    KC exp {k_['R'].mean():+.3f} (n={len(k_)}) | FVG exp {f_['R'].mean():+.3f} (n={len(f_)})")
print("\n(KC філ на open -> ambiguity нема на вході; вихід теж по 15m-істині.)")
