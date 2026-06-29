"""Чи ширший стоп зменшує залежність від стоп-слипу і дає вищий РЕАЛЬНИЙ прибуток?
Грід стоп-ширини, оцінка ОДНОЧАСНО: чистий бектест і реалістичний (стоп-слип 0.10%).
Чесно IS/OOS, 4 монети, BNB лише FVG."""
import numpy as np, pandas as pd
import lib_data as L, strategies as ST, engine as E
BASE = {"BTC": ST.resample(L.load_btc_15m(), "4h"), "ETH": L.load_any("quant/data/eth_4h.csv"),
        "SOL": L.load_any("quant/data/sol_4h.csv"), "BNB": L.load_any("quant/data/bnb_4h.csv")}
ENG = {"BTC": "KF", "ETH": "KF", "SOL": "KF", "BNB": "F"}
CUT = pd.Timestamp("2022-12-10")

def adxv(d):
    h, l = d["high"], d["low"]; up = h.diff(); dn = -l.diff()
    pdm = ((up > dn) & (up > 0))*up; mdm = ((dn > up) & (dn > 0))*dn
    tr = E.true_range(d); a = tr.ewm(alpha=1/14, adjust=False).mean()
    pdi = 100*pdm.ewm(alpha=1/14, adjust=False).mean()/a; mdi = 100*mdm.ewm(alpha=1/14, adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)).ewm(alpha=1/14, adjust=False).mean().to_numpy()

def setups(d, eng, kc_mult, fvg_floor):
    cl = d["close"]; o, h, l, c = [d[x].to_numpy() for x in ["open", "high", "low", "close"]]
    atr = E.atr(d, 14).to_numpy(); em = E.ema(cl, 200).to_numpy(); n = len(c); out = []
    if "K" in eng:
        mid = E.ema(cl, 20); band = 2*E.atr(d, 10)
        up = ((cl > mid+band) & (cl > E.ema(cl, 200))).to_numpy()
        dn = ((cl < mid-band) & (cl < E.ema(cl, 200))).to_numpy(); ax = adxv(d)
        for i in range(1, n-1):
            if not np.isfinite(atr[i]) or ax[i] < 20: continue
            for si, sig in ((1, up), (-1, dn)):
                if sig[i] and not sig[i-1]: out.append((i+1, si, o[i+1], kc_mult*atr[i]))
    if "F" in eng:
        for k in range(2, n-1):
            if h[k-2] < l[k] and c[k] > em[k]:
                zt, zb = l[k], h[k-2]
                for j in range(k+1, min(k+21, n)):
                    if l[j] <= zt and c[j] > em[j]: out.append((j, 1, zt, max(zt-zb, fvg_floor*atr[j]))); break
            if l[k-2] > h[k] and c[k] < em[k]:
                zt, zb = h[k], l[k-2]
                for j in range(k+1, min(k+21, n)):
                    if h[j] >= zt and c[j] < em[j]: out.append((j, -1, zt, max(zb-zt, fvg_floor*atr[j]))); break
    return out

def taken(d, eng, kc_mult, fvg_floor):
    s = sorted(setups(d, eng, kc_mult, fvg_floor), key=lambda x: x[0])
    h, l, c = [d[x].to_numpy() for x in ["high", "low", "close"]]; n = len(c); idx = d.index; out = []; ou = -1
    for eb, si, raw, D in s:
        if eb <= ou: continue
        stop = raw - si*D; tgt = raw + si*2*D; j = eb; ex = None
        while j < n:
            if (l[j] <= stop) if si > 0 else (h[j] >= stop): ex = ("stop", stop, j); break
            if (h[j] >= tgt) if si > 0 else (l[j] <= tgt): ex = ("tgt", tgt, j); break
            j += 1
        if ex is None: ex = ("eod", c[-1], n-1)
        ts = pd.Timestamp(idx[eb]); ts = ts.tz_localize(None) if ts.tzinfo else ts
        out.append((ts, si, raw, D, ex[0], ex[1])); ou = ex[2]
    return out

def R_of(rec, fee, e_slip, stop_slip):
    ts, si, raw, D, extype, exlvl = rec
    en = raw*(1 + si*e_slip)
    exfill = exlvl*(1 - si*stop_slip) if extype == "stop" else exlvl
    return ts, si*(exfill-en)/D - 2*fee*(en/D)

def evaluate(kc_mult, fvg_floor):
    ALL = []
    for coin, d in BASE.items(): ALL += taken(d, ENG[coin], kc_mult, fvg_floor)
    def stats(fee, es, ss):
        rows = [R_of(r, fee, es, ss) for r in ALL]
        T = pd.DataFrame(rows, columns=["t", "r"]).sort_values("t")
        iso = T[T["t"] < CUT]["r"].values; oo = T[T["t"] >= CUT]
        eq = np.cumprod(1+0.01*oo["r"].values)
        me = pd.Series(eq, index=pd.DatetimeIndex(oo["t"])).resample("ME").last().dropna()
        mr = me.pct_change().dropna(); mr = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mr])
        dd = ((eq/np.maximum.accumulate(eq))-1).min()*100
        return iso.mean(), oo["r"].mean(), mr.median()*100, dd
    isc, oc, _, _ = stats(0.0005, 0.0003, 0.0)             # чисто
    _, orr, mrr, ddr = stats(0.0005, 0.0005, 0.0010)        # реалістично (стоп-слип 0.10%)
    return len(ALL), isc, oc, orr, mrr, ddr

print("Стоп-ширина: чистий vs РЕАЛІСТИЧНИЙ (стоп-слип 0.10%). OOS, risk1%.\n")
print(f"{'KCxATR / FVGfloor':18s} | {'n':>5} {'IS чист':>7} {'OOS чист':>8} | {'OOS реал':>8} {'реал мед/міс':>12} {'DD':>5}")
print("-"*78)
for kc in [2.0, 2.5, 3.0]:
    for ff in [0.5, 1.0]:
        n, isc, oc, orr, mrr, ddr = evaluate(kc, ff)
        tag = f"{kc}x / {ff}" + ("  (база)" if (kc == 2.0 and ff == 0.5) else "")
        print(f"{tag:18s} | {n:5d} {isc:+7.3f} {oc:+8.3f} | {orr:+8.3f} {mrr:+10.2f}% {ddr:4.0f}%")
print("\nШукаємо вищий 'OOS реал' за базу (+0.102R / +5.4%). Приймаємо лише якщо тримає OOS.")
