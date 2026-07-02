"""15m-ІСТИНА ПО ВСІХ МОНЕТАХ: повна конфігурація (BTC/ETH/SOL=KC+FVG, BNB=FVG)
під реальною послідовністю 15m-барів. Порівнюємо БАЗУ (FVG край) і ПАКЕТ
(mid50 + wait>2 + ADX>=20 лише для FVG; KC незмінний).
Сигнали — з тих САМИХ 4h-даних, що всі попередні тести; 15m лише для розв'язки
послідовності (філ -> стоп/тейк). Монети без 15m-файлу пропускаються з попередженням.
ЗАПУСК НА VPS: venv/bin/python quant/78_truth_all_coins.py   (спершу fetch_15m_all.py)"""
import os
import numpy as np, pandas as pd
import lib_data as L, strategies as ST, engine as E

FEE, ES, SS = 0.0005, 0.0005, 0.0010

def naive(t): ts = pd.Timestamp(t); return ts.tz_localize(None) if ts.tzinfo else ts
def adxv(d):
    h, l = d["high"], d["low"]; up = h.diff(); dn = -l.diff()
    pdm = ((up > dn) & (up > 0))*up; mdm = ((dn > up) & (dn > 0))*dn
    tr = E.true_range(d); a = tr.ewm(alpha=1/14, adjust=False).mean()
    pdi = 100*pdm.ewm(alpha=1/14, adjust=False).mean()/a; mdi = 100*mdm.ewm(alpha=1/14, adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)).ewm(alpha=1/14, adjust=False).mean().to_numpy()

def kc_setups(d):
    cl = d["close"]; o = d["open"].to_numpy()
    atr = E.atr(d, 14).to_numpy(); ax = adxv(d); n = len(cl); S = []
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

def fvg_setups(d, mid50, min_wait, adx_min):
    o, h, l, c = [d[x].to_numpy() for x in ["open", "high", "low", "close"]]
    atr = E.atr(d, 14).to_numpy(); em = E.ema(d["close"], 200).to_numpy(); ax = adxv(d)
    n = len(c); S = []
    for k in range(2, n-1):
        for si in (1, -1):
            if si > 0 and not (h[k-2] < l[k] and c[k] > em[k]): continue
            if si < 0 and not (l[k-2] > h[k] and c[k] < em[k]): continue
            zt = l[k] if si > 0 else h[k]; zb = h[k-2] if si > 0 else l[k-2]
            entry = (zt + zb)/2 if mid50 else zt
            for j in range(k+1, min(k+21, n)):
                hit = l[j] <= entry if si > 0 else h[j] >= entry
                if not hit: continue
                if j - k <= min_wait: break
                trok = c[j] > em[j] if si > 0 else c[j] < em[j]
                if not trok: break
                if adx_min > 0 and not (np.isfinite(ax[j]) and ax[j] >= adx_min): break
                D = max(abs(entry - zb), 0.5*atr[j])
                S.append((j, si, entry, entry - si*D, entry + si*2*D, D, "FVG")); break
    return S

def R_of(si, en, exlvl, D, extype):
    enf = en*(1 + si*ES); exf = exlvl*(1 - si*SS) if extype == "stop" else exlvl
    return si*(exf - enf)/D - 2*FEE*(enf/D)

def coin_truth(d4, m15, engines, pkg):
    m15_ts = np.array([naive(t).value for t in m15.index])
    h15, l15 = m15["high"].to_numpy(), m15["low"].to_numpy()
    d4_ts = np.array([naive(t).value for t in d4.index])
    S = (kc_setups(d4) if "K" in engines else [])
    S += fvg_setups(d4, *( (True, 2, 20) if pkg else (False, 0, 0) ))
    S.sort(key=lambda x: x[0])
    cut = naive(d4.index[int(len(d4)*0.6)])
    out = []; ou_b = -1; n15 = len(m15_ts)
    for j4, si, en, sp, tg, D, tag in S:
        b = np.searchsorted(m15_ts, d4_ts[j4], "left")
        if b <= ou_b or b >= n15: continue
        filled = (tag == "KC"); ext = None
        while b < n15:
            lo, hi = l15[b], h15[b]
            if not filled:
                if (lo <= en) if si > 0 else (hi >= en):
                    filled = True
                    if (lo <= sp) if si > 0 else (hi >= sp): ext = ("stop", sp); break
                    if (hi >= tg) if si > 0 else (lo <= tg): ext = ("tgt", tg); break
            else:
                if (lo <= sp) if si > 0 else (hi >= sp): ext = ("stop", sp); break
                if (hi >= tg) if si > 0 else (lo <= tg): ext = ("tgt", tg); break
            b += 1
        if not filled: continue                                  # лімітку так і не зачепило
        if ext is None: ext = ("eod", float(m15["close"].iloc[-1])); b = n15-1
        ts = naive(m15.index[min(b, n15-1)])
        out.append(dict(ts=ts, tag=tag, R=R_of(si, en, ext[1], D, ext[0]),
                        seg="OOS" if naive(d4.index[j4]) >= cut else "IS"))
        ou_b = b
    return pd.DataFrame(out)

def mstats(T, risk=0.01):
    T = T.sort_values("ts"); r = T["R"].values
    eq = np.cumprod(1 + risk*r)
    me = pd.Series(eq, index=pd.DatetimeIndex(T["ts"])).resample("ME").last().dropna()
    mr = me.pct_change().dropna(); mr = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mr])*100
    dd = ((eq/np.maximum.accumulate(eq))-1).min()*100
    span = max((T["ts"].max()-T["ts"].min()).days/30.44, 1e-9)
    return len(r), r.mean(), len(r)/span, mr.mean(), mr.median(), (mr > 0).mean()*100, dd

CFG = [("BTC", "KF", None, "quant/data/btc_15m.csv"),
       ("ETH", "KF", "quant/data/eth_4h.csv", "quant/data/eth_15m.csv"),
       ("SOL", "KF", "quant/data/sol_4h.csv", "quant/data/sol_15m.csv"),
       ("BNB", "F",  "quant/data/bnb_4h.csv", "quant/data/bnb_15m.csv")]
print("15m-ІСТИНА по монетах: БАЗА vs ПАКЕТ (mid50+wait>2+ADX20), реалістичні витрати\n")
print(f"{'мон':4s} {'варіант':7s} | {'n':>5} {'exp':>7} | {'KC exp':>7} {'FVG exp':>8} | {'OOS n':>5} {'OOS exp':>8}")
print("-"*74)
PORT = {"база": [], "пакет": []}
for coin, eng, f4, f15 in CFG:
    if not os.path.exists(f15):
        print(f"{coin:4s} — НЕМАЄ {f15} (спершу запусти quant/data/fetch_15m_all.py)"); continue
    m15 = L.load_any(f15)
    d4 = ST.resample(m15, "4h") if f4 is None else L.load_any(f4)
    if coin == "BTC": m15 = L.load_btc_15m(); d4 = ST.resample(m15, "4h")
    for lbl, pkg in [("база", False), ("пакет", True)]:
        T = coin_truth(d4, m15, eng, pkg); PORT[lbl].append(T)
        k_ = T[T.tag == "KC"]["R"]; f_ = T[T.tag == "FVG"]["R"]; o_ = T[T.seg == "OOS"]["R"]
        print(f"{coin:4s} {lbl:7s} | {len(T):5d} {T['R'].mean():+7.3f} | "
              f"{(k_.mean() if len(k_) else float('nan')):+7.3f} {(f_.mean() if len(f_) else float('nan')):+8.3f} | "
              f"{len(o_):5d} {o_.mean() if len(o_) else float('nan'):+8.3f}")
    print()

if all(len(v) == 4 for v in PORT.values()):
    print("ПОРТФЕЛЬ 4 МОНЕТИ ПІД ІСТИНОЮ (одна-на-монету, risk 1%):")
    print(f"{'варіант':7s} {'сег':5s} | {'n':>5} {'exp':>7} {'уг/міс':>6} | {'сер/міс':>8} {'мед':>6} {'+міс':>5} {'DD':>5}")
    print("-"*76)
    for lbl in ["база", "пакет"]:
        A = pd.concat(PORT[lbl], ignore_index=True)
        for seg, sub in [("ВСЕ", A), ("OOS", A[A.seg == "OOS"])]:
            n, e, tpm, avg, med, pos, dd = mstats(sub)
            print(f"{lbl:7s} {seg:5s} | {n:5d} {e:+7.3f} {tpm:6.1f} | {avg:+7.2f}% {med:+5.2f}% {pos:4.0f}% {dd:4.0f}%")
        print()
