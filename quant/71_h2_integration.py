"""Чи ДОДАЄ H2 (Брукс, варіант V3: закр>hi попер.) щось нашому портфелю?
Чесне злиття: KC + FVG + H2 сетапи однією чергою, одна-позиція-на-монету
(двигуни конкурують за слот, як буде в боті). Порівнюємо OOS: база vs база+H2.
Також: перекриття входів H2 з базовими (чи це взагалі нові угоди?)."""
import importlib.util, builtins, numpy as np, pandas as pd
import lib_data as L, strategies as ST, engine as E
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c70", "quant/70_brooks_h2.py")
m70 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m70); builtins.print = _p

BASE, naive, adxv = m70.BASE, m70.naive, m70.adxv
FEE, ES, SS = m70.FEE, m70.ES, m70.SS
ENG = {"BTC": "KF", "ETH": "KF", "SOL": "KF", "BNB": "F"}
H2CFG = {"cAbove": 1}                       # обраний на IS варіант V3

def base_setups(d, eng):
    """KC (маркет на open i+1) + FVG (лімітка на ретесті) -> (entry_bar, side, entry_px, D, tag)."""
    cl = d["close"]; o, h, l, c = [d[x].to_numpy() for x in ["open", "high", "low", "close"]]
    atr = E.atr(d, 14).to_numpy(); em = E.ema(cl, 200).to_numpy(); ax = adxv(d); n = len(c); S = []
    if "K" in eng:
        mid = E.ema(cl, 20); band = 2*E.atr(d, 10)
        up = ((cl > mid+band) & (cl > E.ema(cl, 200))).to_numpy()
        dn = ((cl < mid-band) & (cl < E.ema(cl, 200))).to_numpy()
        for i in range(1, n-1):
            if not np.isfinite(atr[i]) or ax[i] < 20: continue
            for si, sig in ((1, up), (-1, dn)):
                if sig[i] and not sig[i-1]: S.append((i+1, si, o[i+1], 2.0*atr[i], "KC"))
    if "F" in eng:
        for k in range(2, n-1):
            if h[k-2] < l[k] and c[k] > em[k]:
                zt, zb = l[k], h[k-2]
                for j in range(k+1, min(k+21, n)):
                    if l[j] <= zt and c[j] > em[j]: S.append((j, 1, zt, max(zt-zb, 0.5*atr[j]), "FVG")); break
            if l[k-2] > h[k] and c[k] < em[k]:
                zt, zb = h[k], l[k-2]
                for j in range(k+1, min(k+21, n)):
                    if h[j] >= zt and c[j] < em[j]: S.append((j, -1, zt, max(zb-zt, 0.5*atr[j]), "FVG")); break
    return S

def h2_setups(d):
    """H2-сигнали з РОЗВ'ЯЗАНИМ стоп-тригером -> (entry_bar, side, entry_px, D, 'H2')."""
    h, l = d["high"].to_numpy(), d["low"].to_numpy(); n = len(h); S = []
    for sb, side, entry, D in m70.signals(d, H2CFG):
        for j in range(sb+1, min(sb+1+m70.LA_ENTRY, n)):
            if (h[j] > entry) if side > 0 else (l[j] < entry):
                S.append((j, side, entry, D, "H2")); break
    return S

def run_portfolio(with_h2):
    rows = []
    for coin, d in BASE.items():
        h, l, c = [d[x].to_numpy() for x in ["high", "low", "close"]]; n = len(c); idx = d.index
        S = base_setups(d, ENG[coin]) + (h2_setups(d) if with_h2 else [])
        S.sort(key=lambda x: x[0]); ou = -1
        cut = naive(idx[int(len(d)*0.6)])
        for eb, si, raw, D, tag in S:
            if eb <= ou: continue
            stop = raw - si*D; tgt = raw + si*2.0*D; j = eb; ex = None
            while j < n:
                if (l[j] <= stop) if si > 0 else (h[j] >= stop): ex = ("stop", stop, j); break
                if (h[j] >= tgt) if si > 0 else (l[j] <= tgt): ex = ("tgt", tgt, j); break
                j += 1
            if ex is None: ex = ("eod", c[-1], n-1)
            en = raw*(1 + si*ES); exf = ex[1]*(1 - si*SS) if ex[0] == "stop" else ex[1]
            R = si*(exf-en)/D - 2*FEE*(en/D)
            ts = naive(idx[eb])
            rows.append(("OOS" if ts >= cut else "IS", ts, tag, R)); ou = ex[2]
    return pd.DataFrame(rows, columns=["seg", "ts", "tag", "R"])

def stats(T, seg):
    s = T[T.seg == seg].sort_values("ts"); r = s["R"].values
    eq = np.cumprod(1 + 0.01*r)
    me = pd.Series(eq, index=pd.DatetimeIndex(s["ts"])).resample("ME").last().dropna()
    mr = me.pct_change().dropna(); mr = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mr])*100
    dd = ((eq/np.maximum.accumulate(eq))-1).min()*100
    span = (s["ts"].max()-s["ts"].min()).days/30.44
    return len(r), r.mean(), len(r)/span, mr.mean(), mr.median(), (mr > 0).mean()*100, dd

print("ІНТЕГРАЦІЯ H2 у портфель (KC+FVG [+H2], одна-на-монету, реалістично, risk 1%)\n")
print(f"{'портфель':16s} {'сег':4s} | {'n':>5} {'exp':>7} {'уг/міс':>6} | {'сер/міс':>8} {'медіан':>7} {'+міс':>5} {'DD':>5}")
print("-"*84)
for lbl, w in [("база KC+FVG", False), ("база + H2", True)]:
    T = run_portfolio(w)
    for seg in ["IS", "OOS"]:
        n, e, tpm, avg, med, pos, dd = stats(T, seg)
        print(f"{lbl:16s} {seg:4s} | {n:5d} {e:+7.3f} {tpm:6.1f} | {avg:+7.2f}% {med:+6.2f}% {pos:4.0f}% {dd:4.0f}%")

# внесок H2 у злитому портфелі + скільки слотів він забрав
T = run_portfolio(True)
for seg in ["IS", "OOS"]:
    s = T[T.seg == seg]
    h2 = s[s.tag == "H2"]
    print(f"\n{seg}: H2-угод у злитому портфелі {len(h2)} ({len(h2)/len(s)*100:.0f}% всіх), exp(H2) {h2['R'].mean():+.3f}R, "
          f"exp(KC+FVG у злитті) {s[s.tag != 'H2']['R'].mean():+.3f}R")

# перекриття: скільки H2-входів поруч (±2 бари) з базовими входами
print("\nПерекриття входів H2 з базовими (та сама монета, ±2 бари):")
tot = near = 0
for coin, d in BASE.items():
    bs = {eb for eb, *_ in base_setups(d, ENG[coin])}
    for eb, si, raw, D, tag in h2_setups(d):
        tot += 1
        if any(abs(eb-b) <= 2 for b in bs): near += 1
print(f"  H2-входів {tot}, з них поруч із базовим сетапом {near} ({near/tot*100:.0f}%) — решта справді НОВІ угоди")
