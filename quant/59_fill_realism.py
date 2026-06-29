"""Стрес-тест ВИКОНАННЯ на робочій конфігурації (4 монети, BNB лише FVG, RR2).
Моделюємо: гірший філ входу, ДОДАТКОВЕ прослизання на стопі (обвал), вищі комісії.
Стоп = stop-market (тейкер, проскакує); тейк = лімітка (філ точний). Чесно OOS."""
import numpy as np, pandas as pd
import lib_data as L, strategies as ST, engine as E
BASE = {"BTC": ST.resample(L.load_btc_15m(), "4h"), "ETH": L.load_any("quant/data/eth_4h.csv"),
        "SOL": L.load_any("quant/data/sol_4h.csv"), "BNB": L.load_any("quant/data/bnb_4h.csv")}
ENG = {"BTC": "KF", "ETH": "KF", "SOL": "KF", "BNB": "F"}

def adxv(d):
    h, l = d["high"], d["low"]; up = h.diff(); dn = -l.diff()
    pdm = ((up > dn) & (up > 0))*up; mdm = ((dn > up) & (dn > 0))*dn
    tr = E.true_range(d); a = tr.ewm(alpha=1/14, adjust=False).mean()
    pdi = 100*pdm.ewm(alpha=1/14, adjust=False).mean()/a; mdi = 100*mdm.ewm(alpha=1/14, adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)).ewm(alpha=1/14, adjust=False).mean().to_numpy()

def setups(d, eng):                       # raw входи без слипеджу: (eb, si, raw_entry, D, typ)
    cl = d["close"]; o, h, l, c = [d[x].to_numpy() for x in ["open", "high", "low", "close"]]
    atr = E.atr(d, 14).to_numpy(); em = E.ema(cl, 200).to_numpy(); n = len(c); out = []
    if "K" in eng:
        mid = E.ema(cl, 20); band = 2*E.atr(d, 10)
        up = ((cl > mid+band) & (cl > E.ema(cl, 200))).to_numpy()
        dn = ((cl < mid-band) & (cl < E.ema(cl, 200))).to_numpy(); ax = adxv(d)
        for i in range(1, n-1):
            if not np.isfinite(atr[i]) or ax[i] < 20: continue
            for si, sig in ((1, up), (-1, dn)):
                if sig[i] and not sig[i-1]:
                    out.append((i+1, si, o[i+1], 2*atr[i], "mkt"))
    if "F" in eng:
        for k in range(2, n-1):
            if h[k-2] < l[k] and c[k] > em[k]:
                zt, zb = l[k], h[k-2]
                for j in range(k+1, min(k+21, n)):
                    if l[j] <= zt and c[j] > em[j]:
                        out.append((j, 1, zt, max(zt-zb, 0.5*atr[j]), "lim")); break
            if l[k-2] > h[k] and c[k] < em[k]:
                zt, zb = h[k], l[k-2]
                for j in range(k+1, min(k+21, n)):
                    if h[j] >= zt and c[j] < em[j]:
                        out.append((j, -1, zt, max(zb-zt, 0.5*atr[j]), "lim")); break
    return out

def taken(d, eng):                        # одна-на-монету: фіксуємо вихід-бар і тип
    s = sorted(setups(d, eng), key=lambda x: x[0]); h, l, c = [d[x].to_numpy() for x in ["high","low","close"]]
    n = len(c); idx = d.index; out = []; ou = -1
    for eb, si, raw, D, typ in s:
        if eb <= ou: continue
        stop = raw - si*D; tgt = raw + si*2*D; j = eb; ex = None
        while j < n:
            if (l[j] <= stop) if si > 0 else (h[j] >= stop): ex = ("stop", stop, j); break
            if (h[j] >= tgt) if si > 0 else (l[j] <= tgt): ex = ("tgt", tgt, j); break
            j += 1
        if ex is None: ex = ("eod", c[-1], n-1)
        ts = pd.Timestamp(idx[eb]); ts = ts.tz_localize(None) if ts.tzinfo else ts
        out.append((ts, si, raw, D, typ, ex[0], ex[1])); ou = ex[2]
    return out

ALL = []
for coin, d in BASE.items():
    for t in taken(d, ENG[coin]): ALL.append((coin,)+t)
cut = pd.Timestamp("2022-12-10")

def R_of(rec, fee, e_slip, stop_slip):
    coin, ts, si, raw, D, typ, extype, exlvl = rec
    en = raw*(1 + si*e_slip)               # гірший вхід
    if extype == "stop": exfill = exlvl*(1 - si*stop_slip)   # стоп проскакує
    else: exfill = exlvl                                     # тейк лімітка / eod
    r = si*(exfill-en)/D - 2*fee*(en/D)
    return ts, r

def evalsc(fee, e_slip, stop_slip):
    rows = [R_of(r, fee, e_slip, stop_slip) for r in ALL]
    T = pd.DataFrame(rows, columns=["t", "r"]).sort_values("t"); To = T[T["t"] >= cut]
    r = To["r"].values; eq = np.cumprod(1+0.01*r)
    me = pd.Series(eq, index=pd.DatetimeIndex(To["t"])).resample("ME").last().dropna()
    mret = me.pct_change().dropna(); mret = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mret])
    dd = ((eq/np.maximum.accumulate(eq))-1).min()*100
    return r.mean(), mret.median()*100, (mret > 0).mean()*100, dd

stopfrac = sum(1 for r in ALL if r[6] == "stop")/len(ALL)*100
print(f"Угод усього: {len(ALL)} | стоп-виходів: {stopfrac:.0f}% (саме вони ловлять прослизання)\n")
print(f"{'сценарій':34s} | {'OOS exp':>7} {'мед/міс':>8} {'+міс':>5} {'DD':>5}")
print("-"*64)
SC = [("База (комісія .05%, вхід .03%)",         0.0005, 0.0003, 0.0000),
      ("Реалістично (стоп +0.10% слип)",         0.0005, 0.0005, 0.0010),
      ("Песимістично (стоп +0.20%, комісія .07%)",0.0007, 0.0010, 0.0020),
      ("Жорстко (стоп +0.30%, комісія .10%)",     0.0010, 0.0015, 0.0030),
      ("Крах-сценарій (стоп +0.50%)",             0.0007, 0.0010, 0.0050)]
for name, fee, es, ss in SC:
    exp, med, pos, dd = evalsc(fee, es, ss)
    print(f"{name:34s} | {exp:+7.3f} {med:+7.2f}% {pos:4.0f}% {dd:4.0f}%  {'OK' if exp>0 else 'ЗБИТОК'}")
print("\nСтоп=тейкер і проскакує в обвалі; тейк=лімітка (точний філ). Дивимось, де edge гине.")
