"""Покращення №1: управління виходом (base RR2 vs breakeven vs partial).
Чесно IS/OOS, 4 монети, одна-на-монету. Приймаємо лише те, що тримається на OOS."""
import numpy as np, pandas as pd
import lib_data as L, strategies as ST, engine as E
FEE, SLIP = 0.0005, 0.0003
BASE = {"BTC": ST.resample(L.load_btc_15m(), "4h"),
        "ETH": L.load_any("quant/data/eth_4h.csv"),
        "SOL": L.load_any("quant/data/sol_4h.csv"),
        "BNB": L.load_any("quant/data/bnb_4h.csv")}
ENG = {"BTC": "KF", "ETH": "KF", "SOL": "KF", "BNB": "F"}   # BNB лише FVG

def adxv(d):
    h, l = d["high"], d["low"]; up = h.diff(); dn = -l.diff()
    pdm = ((up > dn) & (up > 0)) * up; mdm = ((dn > up) & (dn > 0)) * dn
    tr = E.true_range(d); a = tr.ewm(alpha=1/14, adjust=False).mean()
    pdi = 100*pdm.ewm(alpha=1/14, adjust=False).mean()/a
    mdi = 100*mdm.ewm(alpha=1/14, adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)).ewm(alpha=1/14, adjust=False).mean().to_numpy()

def kc_setups(d):
    cl = d["close"]; mid = E.ema(cl, 20); band = 2*E.atr(d, 10)
    up = ((cl > mid+band) & (cl > E.ema(cl, 200))).to_numpy()
    dn = ((cl < mid-band) & (cl < E.ema(cl, 200))).to_numpy()
    ax = adxv(d)
    o, h, l, c = [d[x].to_numpy() for x in ["open", "high", "low", "close"]]
    atr = E.atr(d, 14).to_numpy(); n = len(c); out = []
    for i in range(1, n-1):
        if not np.isfinite(atr[i]) or ax[i] < 20: continue
        for si, sig in ((1, up), (-1, dn)):
            if sig[i] and not sig[i-1]:
                D = 2*atr[i]; eb = i+1
                en = o[eb]*(1+SLIP) if si > 0 else o[eb]*(1-SLIP)
                out.append((eb, si, en, en-si*D, en+si*2*D, D))
    return out

def fvg_setups(d, la=20, af=0.5):
    o, h, l, c = [d[x].to_numpy() for x in ["open", "high", "low", "close"]]
    em = E.ema(d["close"], 200).to_numpy(); atr = E.atr(d, 14).to_numpy(); n = len(c); out = []
    for k in range(2, n-1):
        if h[k-2] < l[k] and c[k] > em[k]:
            zt, zb = l[k], h[k-2]
            for j in range(k+1, min(k+1+la, n)):
                if l[j] <= zt and c[j] > em[j]:
                    en = zt*(1+SLIP); D = max(en-zb, af*atr[j])
                    out.append((j, 1, en, en-D, en+2*D, D)); break
        if l[k-2] > h[k] and c[k] < em[k]:
            zt, zb = h[k], l[k-2]
            for j in range(k+1, min(k+1+la, n)):
                if h[j] >= zt and c[j] < em[j]:
                    en = zt*(1-SLIP); D = max(zb-en, af*atr[j])
                    out.append((j, -1, en, en+D, en-2*D, D)); break
    return out

def sim_exit(h, l, c, n, eb, si, en, st, tg, D, mode):
    cur = st; reached = False; j = eb
    while j < n:
        hit_st = (l[j] <= cur) if si > 0 else (h[j] >= cur)
        hit_tg = (h[j] >= tg) if si > 0 else (l[j] <= tg)
        if hit_st:                                   # песимістично: стоп перший
            if mode == "partial" and reached: return j, 0.5 - 2*FEE*(en/D)
            return j, si*(cur-en)/D - 2*FEE*(en/D)   # base:-1R  be:0R(якщо BE)
        if hit_tg:
            return j, (1.5 if mode == "partial" else 2) - 2*FEE*(en/D)
        hit1 = (h[j] >= en+D) if si > 0 else (l[j] <= en-D)
        if hit1 and not reached:
            reached = True
            if mode in ("be", "partial"): cur = en
        j += 1
    return n-1, si*(c[-1]-en)/D

def run(d, eng, mode):
    setups = []
    if "K" in eng: setups += kc_setups(d)
    if "F" in eng: setups += fvg_setups(d)
    setups.sort(key=lambda x: x[0])
    h, l, c = [d[x].to_numpy() for x in ["high", "low", "close"]]; n = len(c); idx = d.index
    out = []; ou = -1
    for eb, si, en, st, tg, D in setups:
        if eb <= ou: continue
        xb, r = sim_exit(h, l, c, n, eb, si, en, st, tg, D, mode)
        out.append((pd.Timestamp(idx[eb]).tz_localize(None) if pd.Timestamp(idx[eb]).tzinfo else pd.Timestamp(idx[eb]), r))
        ou = xb
    return out

def split_rows(mode):
    isr, oosr, allrows = [], [], []
    for coin, d in BASE.items():
        cut = pd.Timestamp(d.index[int(len(d)*0.6)]); cut = cut.tz_localize(None) if cut.tzinfo else cut
        for ts, r in run(d, ENG[coin], mode):
            allrows.append((ts, r)); (oosr if ts >= cut else isr).append(r)
    return np.array(isr), np.array(oosr), pd.DataFrame(allrows, columns=["t", "r"]).sort_values("t")

def monthly(T, risk=0.015):
    Toos = T[T["t"] >= T["t"].iloc[int(len(T)*0)]]  # full T already; compute on OOS separately below
    r = T["r"].values; eq = np.cumprod(1+risk*r)
    me = pd.Series(eq, index=pd.DatetimeIndex(T["t"])).resample("ME").last().dropna()
    mret = me.pct_change().dropna(); mret = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mret])
    dd = ((eq/np.maximum.accumulate(eq))-1).min()*100
    return mret.median()*100, (mret > 0).mean()*100, dd

print("Управління виходом — 4 монети, одна-на-монету, IS/OOS:\n")
print(f"{'режим':9s} | {'IS exp':>7} {'OOS exp':>7} | {'OOS медіана/міс':>15} {'+міс':>5} {'DD':>5}")
print("-"*60)
for mode in ["base", "be", "partial"]:
    isr, oosr, T = split_rows(mode)
    Toos = T[T["t"] >= pd.Timestamp("2022-12-10")]
    med, pos, dd = monthly(Toos)
    print(f"{mode:9s} | {isr.mean():+7.3f} {oosr.mean():+7.3f} | {med:+13.2f}% {pos:4.0f}% {dd:4.0f}%")
print("\nПриймаємо зміну ЛИШЕ якщо OOS exp і OOS-медіана не гірші за base.")
print("(BE/partial зазвичай ріжуть exp, але можуть знижувати просадку — дивимось баланс.)")
