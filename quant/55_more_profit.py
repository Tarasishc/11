"""Покращення №2: БІЛЬШИЙ прибуток — дати виграшам бігти.
Варіанти тейка RR 1.5/2/2.5/3 + трейлінг-стоп (без стелі). Чесно IS/OOS, 4 монети."""
import numpy as np, pandas as pd
import lib_data as L, strategies as ST, engine as E
FEE, SLIP = 0.0005, 0.0003
BASE = {"BTC": ST.resample(L.load_btc_15m(), "4h"),
        "ETH": L.load_any("quant/data/eth_4h.csv"),
        "SOL": L.load_any("quant/data/sol_4h.csv"),
        "BNB": L.load_any("quant/data/bnb_4h.csv")}
ENG = {"BTC": "KF", "ETH": "KF", "SOL": "KF", "BNB": "F"}

def adxv(d):
    h, l = d["high"], d["low"]; up = h.diff(); dn = -l.diff()
    pdm = ((up > dn) & (up > 0))*up; mdm = ((dn > up) & (dn > 0))*dn
    tr = E.true_range(d); a = tr.ewm(alpha=1/14, adjust=False).mean()
    pdi = 100*pdm.ewm(alpha=1/14, adjust=False).mean()/a
    mdi = 100*mdm.ewm(alpha=1/14, adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)).ewm(alpha=1/14, adjust=False).mean().to_numpy()

def kc_setups(d):
    cl = d["close"]; mid = E.ema(cl, 20); band = 2*E.atr(d, 10)
    up = ((cl > mid+band) & (cl > E.ema(cl, 200))).to_numpy()
    dn = ((cl < mid-band) & (cl < E.ema(cl, 200))).to_numpy(); ax = adxv(d)
    o, h, l, c = [d[x].to_numpy() for x in ["open", "high", "low", "close"]]
    atr = E.atr(d, 14).to_numpy(); n = len(c); out = []
    for i in range(1, n-1):
        if not np.isfinite(atr[i]) or ax[i] < 20: continue
        for si, sig in ((1, up), (-1, dn)):
            if sig[i] and not sig[i-1]:
                D = 2*atr[i]; eb = i+1; en = o[eb]*(1+SLIP) if si > 0 else o[eb]*(1-SLIP)
                out.append((eb, si, en, en-si*D, D))
    return out

def fvg_setups(d, la=20, af=0.5):
    o, h, l, c = [d[x].to_numpy() for x in ["open", "high", "low", "close"]]
    em = E.ema(d["close"], 200).to_numpy(); atr = E.atr(d, 14).to_numpy(); n = len(c); out = []
    for k in range(2, n-1):
        if h[k-2] < l[k] and c[k] > em[k]:
            zt, zb = l[k], h[k-2]
            for j in range(k+1, min(k+1+la, n)):
                if l[j] <= zt and c[j] > em[j]:
                    en = zt*(1+SLIP); D = max(en-zb, af*atr[j]); out.append((j, 1, en, en-D, D)); break
        if l[k-2] > h[k] and c[k] < em[k]:
            zt, zb = h[k], l[k-2]
            for j in range(k+1, min(k+1+la, n)):
                if h[j] >= zt and c[j] < em[j]:
                    en = zt*(1-SLIP); D = max(zb-en, af*atr[j]); out.append((j, -1, en, en+D, D)); break
    return out

def sim_exit(h, l, c, n, eb, si, en, st, D, mode):
    cur = st; reached = False; peak = en; j = eb
    rr = {"rr1.5": 1.5, "rr2": 2.0, "rr2.5": 2.5, "rr3": 3.0}.get(mode)
    tg = en + si*rr*D if rr else None
    while j < n:
        peak = max(peak, h[j]) if si > 0 else min(peak, l[j])
        hit_st = (l[j] <= cur) if si > 0 else (h[j] >= cur)
        if hit_st: return j, si*(cur-en)/D - 2*FEE*(en/D)
        if rr:
            if (h[j] >= tg) if si > 0 else (l[j] <= tg): return j, si*(tg-en)/D - 2*FEE*(en/D)
        else:  # trail: після +1R тягнемо стоп на (пік - 1R), стелі немає
            hit1 = (h[j] >= en+D) if si > 0 else (l[j] <= en-D)
            if hit1 or reached:
                reached = True
                ns = peak - D if si > 0 else peak + D
                cur = max(cur, ns) if si > 0 else min(cur, ns)
        j += 1
    return n-1, si*(c[-1]-en)/D

def run(d, eng, mode):
    setups = (kc_setups(d) if "K" in eng else []) + (fvg_setups(d) if "F" in eng else [])
    setups.sort(key=lambda x: x[0])
    h, l, c = [d[x].to_numpy() for x in ["high", "low", "close"]]; n = len(c); idx = d.index
    out = []; ou = -1
    for eb, si, en, st, D in setups:
        if eb <= ou: continue
        xb, r = sim_exit(h, l, c, n, eb, si, en, st, D, mode)
        ts = pd.Timestamp(idx[eb]); ts = ts.tz_localize(None) if ts.tzinfo else ts
        out.append((ts, r)); ou = xb
    return out

def evalrows(mode):
    isr, oosr, rows = [], [], []
    for coin, d in BASE.items():
        cut = pd.Timestamp(d.index[int(len(d)*0.6)]); cut = cut.tz_localize(None) if cut.tzinfo else cut
        for ts, r in run(d, ENG[coin], mode):
            rows.append((ts, r)); (oosr if ts >= cut else isr).append(r)
    T = pd.DataFrame(rows, columns=["t", "r"]).sort_values("t")
    Toos = T[T["t"] >= pd.Timestamp("2022-12-10")]
    r = Toos["r"].values; eq = np.cumprod(1+0.015*r)
    me = pd.Series(eq, index=pd.DatetimeIndex(Toos["t"])).resample("ME").last().dropna()
    mret = me.pct_change().dropna(); mret = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mret])
    dd = ((eq/np.maximum.accumulate(eq))-1).min()*100
    return np.array(isr), np.array(oosr), mret.median()*100, (mret > 0).mean()*100, dd

print("Більший прибуток — тейк/трейлінг, 4 монети одна-на-монету, IS/OOS (risk1.5%):\n")
print(f"{'режим':8s} | {'IS exp':>7} {'OOS exp':>7} {'OOS WR':>6} | {'медіана/міс':>11} {'+міс':>5} {'DD':>5} {'×eq':>6}")
print("-"*72)
for mode in ["rr1.5", "rr2", "rr2.5", "rr3", "trail"]:
    isr, oosr, med, pos, dd = evalrows(mode)
    wr = (oosr > 0).mean()*100
    eqx = np.prod(1+0.015*oosr)
    print(f"{mode:8s} | {isr.mean():+7.3f} {oosr.mean():+7.3f} {wr:5.0f}% | {med:+9.2f}% {pos:4.0f}% {dd:4.0f}% {eqx:6.1f}")
print("\nПриймаємо ЛИШЕ якщо OOS exp/дохід кращі за rr2 І не ламають DD.")
