"""Більше тестів на базі ТРЕЙЛІНГУ (бот не чіпаємо): робастність трейл-дистанції
+ фільтри зверху (денний тренд MTF, сильніший ADX). Чесно IS/OOS, 4 монети."""
import importlib.util, builtins, numpy as np, pandas as pd
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c55", "quant/55_more_profit.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print = _p
import engine as E
BASE, ENG, kc_setups, fvg_setups, adxv, FEE = m.BASE, m.ENG, m.kc_setups, m.fvg_setups, m.adxv, m.FEE

def sim_trail(h, l, c, n, eb, si, en, st, D, tm, peak_src="close"):
    # peak_src="high" -> по екстремуму бара (оптимістично, ловить шпильки);
    # peak_src="close" -> по закриттю (реалістично, стоп не опиняється вище ринку)
    cur = st; reached = False; peak = en; j = eb
    while j < n:
        pv = (h[j] if si > 0 else l[j]) if peak_src == "high" else c[j]
        peak = max(peak, pv) if si > 0 else min(peak, pv)
        if (l[j] <= cur) if si > 0 else (h[j] >= cur):
            return j, si*(cur-en)/D - 2*FEE*(en/D)
        if ((h[j] >= en+D) if si > 0 else (l[j] <= en-D)) or reached:
            reached = True
            ns = peak - tm*D if si > 0 else peak + tm*D
            cur = max(cur, ns) if si > 0 else min(cur, ns)
        j += 1
    return n-1, si*(c[-1]-en)/D

def daily_sign(d):
    dc = d["close"].resample("1D").last(); de = E.ema(dc, 200)
    s = pd.Series(np.where(dc > de, 1, -1), index=dc.index).shift(1)
    return s.reindex(d.index, method="ffill").to_numpy()

def run(d, eng, tm=1.0, filt="none", peak_src="close"):
    setups = (kc_setups(d) if "K" in eng else []) + (fvg_setups(d) if "F" in eng else [])
    setups.sort(key=lambda x: x[0])
    h, l, c = [d[x].to_numpy() for x in ["high", "low", "close"]]; n = len(c); idx = d.index
    ds = daily_sign(d) if filt == "mtf" else None
    ax = adxv(d) if filt == "adx25" else None
    out = []; ou = -1
    for eb, si, en, st, D in setups:
        if eb <= ou: continue
        if filt == "mtf" and ds[eb] != si: continue
        if filt == "adx25" and not (np.isfinite(ax[eb]) and ax[eb] >= 25): continue
        xb, r = sim_trail(h, l, c, n, eb, si, en, st, D, tm, peak_src)
        ts = pd.Timestamp(idx[eb]); ts = ts.tz_localize(None) if ts.tzinfo else ts
        out.append((ts, r)); ou = xb
    return out

def evaluate(tm=1.0, filt="none", peak_src="close"):
    isr, oosr, rows = [], [], []
    for coin, d in BASE.items():
        cut = pd.Timestamp(d.index[int(len(d)*0.6)]); cut = cut.tz_localize(None) if cut.tzinfo else cut
        for ts, r in run(d, ENG[coin], tm, filt, peak_src):
            rows.append((ts, r)); (oosr if ts >= cut else isr).append(r)
    T = pd.DataFrame(rows, columns=["t", "r"]).sort_values("t")
    To = T[T["t"] >= pd.Timestamp("2022-12-10")]
    r = To["r"].values; eq = np.cumprod(1+0.015*r)
    me = pd.Series(eq, index=pd.DatetimeIndex(To["t"])).resample("ME").last().dropna()
    mret = me.pct_change().dropna(); mret = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mret])
    dd = ((eq/np.maximum.accumulate(eq))-1).min()*100
    return np.array(isr), np.array(oosr), mret.median()*100, (mret > 0).mean()*100, dd

print("Усе IS/OOS, risk1.5%, 4 монети одна-на-монету.\n")
print("A) Трейл-дистанція: HIGH-пік (оптимістично, шпильки) vs CLOSE-пік (реалістично)")
print(f"{'tm':>5} | {'OOS exp HIGH':>12} {'мед/міс':>8} | {'OOS exp CLOSE':>13} {'мед/міс':>8} {'DD':>5}")
print("-"*60)
for tm in [0.5, 0.75, 1.0, 1.25, 1.5]:
    _, oh, mh, _, _ = evaluate(tm, "none", "high")
    _, oc, mc, pc, dc = evaluate(tm, "none", "close")
    print(f"{tm:5.2f} | {oh.mean():+12.3f} {mh:+7.2f}% | {oc.mean():+13.3f} {mc:+7.2f}% {dc:4.0f}%")

print("\nB) Фільтри зверху (реалістичний CLOSE-трейл 1.0R):")
print(f"{'варіант':22s} | {'IS exp':>7} {'OOS exp':>7} {'nOOS':>5} | {'мед/міс':>8} {'+міс':>5} {'DD':>5}")
print("-"*70)
for name, tm, filt in [("trail 1.0R (база)", 1.0, "none"),
                       ("trail + денний тренд", 1.0, "mtf"),
                       ("trail + ADX>=25", 1.0, "adx25")]:
    isr, oosr, med, pos, dd = evaluate(tm, filt, "close")
    print(f"{name:22s} | {isr.mean():+7.3f} {oosr.mean():+7.3f} {len(oosr):5d} | {med:+7.2f}% {pos:4.0f}% {dd:4.0f}%")
print("\nЯкщо CLOSE-крива НЕ монотонна (має пік) — трейл реальний. Якщо HIGH>>CLOSE на тісних")
print("трейлах — підтверджує артефакт шпильок. Чесний орієнтир — CLOSE-колонка.")
