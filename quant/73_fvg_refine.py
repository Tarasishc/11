"""ГЛИБОКА ВАЛІДАЦІЯ двох кандидатів з 72 (обидва — виконання FVG):
  A) wait>2: НЕ брати ретест у перші 2 бари після формування (пізній ретест кращий)
     - виконувано в боті: лімітку активуємо лише з 3-го бару; якщо зона зачеплена раніше - скіп
  B) mid: лімітка на 50% зони замість краю (краща ціна, тонший стоп)
Перевірки: грід варіантів (+ADX20) -> вибір на IS -> OOS; по монетах; по роках;
інтегрований портфель (KC незмінний). Приймаємо лише широку OOS-стійкість."""
import importlib.util, builtins, numpy as np, pandas as pd
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c72", "quant/72_avoid_losers.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print = _p
BASE, ENG, naive, adxv = m.BASE, m.ENG, m.naive, m.adxv
FEE, ES, SS = m.FEE, m.ES, m.SS
import engine as E

def collect2(d, eng, fvg_adx=0.0, fvg_mid=False, min_wait=0):
    """як m.collect, але з min_wait: ретест у перші min_wait барів = сетап ЗГОРІВ (skip)."""
    cl = d["close"]; o, h, l, c = [d[x].to_numpy() for x in ["open", "high", "low", "close"]]
    atr = E.atr(d, 14).to_numpy(); em = E.ema(cl, 200).to_numpy(); ax = adxv(d); n = len(c); S = []
    if "K" in eng:
        mid_ = E.ema(cl, 20); band = 2*E.atr(d, 10)
        up = ((cl > mid_+band) & (cl > E.ema(cl, 200))).to_numpy()
        dn = ((cl < mid_-band) & (cl < E.ema(cl, 200))).to_numpy()
        for i in range(1, n-1):
            if not np.isfinite(atr[i]) or ax[i] < 20: continue
            for si, sig in ((1, up), (-1, dn)):
                if sig[i] and not sig[i-1]: S.append((i+1, si, o[i+1], 2.0*atr[i], "KC"))
    if "F" in eng:
        for k in range(2, n-1):
            for si in (1, -1):
                if si > 0 and not (h[k-2] < l[k] and c[k] > em[k]): continue
                if si < 0 and not (l[k-2] > h[k] and c[k] < em[k]): continue
                zt = l[k] if si > 0 else h[k]; zb = h[k-2] if si > 0 else l[k-2]
                entry = (zt + zb)/2 if fvg_mid else zt
                for j in range(k+1, min(k+21, n)):
                    hit = l[j] <= entry if si > 0 else h[j] >= entry
                    if not hit: continue
                    if j - k <= min_wait: break          # ранній ретест -> сетап згорів
                    trok = c[j] > em[j] if si > 0 else c[j] < em[j]
                    if not trok: break                    # торкнулись без тренду -> зона спожита
                    if fvg_adx > 0 and not (np.isfinite(ax[j]) and ax[j] >= fvg_adx): break
                    D = max(abs(entry - zb), 0.5*atr[j])
                    S.append((j, si, entry, D, "FVG")); break
    S.sort(key=lambda x: x[0]); out = []; ou = -1
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
        out.append(dict(ts=naive(d.index[eb]), eng=tag, R=R)); ou = ex[2]
    return out

def portfolio(**kw):
    rows = []
    for coin, d in BASE.items():
        cut = naive(d.index[int(len(d)*0.6)])
        for t in collect2(d, ENG[coin], **kw):
            t["coin"] = coin; t["seg"] = "OOS" if t["ts"] >= cut else "IS"; rows.append(t)
    return pd.DataFrame(rows)

def pstats(T, seg, risk=0.01):
    s = T[T.seg == seg].sort_values("ts"); r = s["R"].values
    eq = np.cumprod(1 + risk*r)
    me = pd.Series(eq, index=pd.DatetimeIndex(s["ts"])).resample("ME").last().dropna()
    mr = me.pct_change().dropna(); mr = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mr])*100
    dd = ((eq/np.maximum.accumulate(eq))-1).min()*100
    span = (s["ts"].max()-s["ts"].min()).days/30.44
    return dict(n=len(r), exp=r.mean(), tpm=len(r)/span, avg=mr.mean(), med=mr.median(),
                pos=(mr > 0).mean()*100, dd=dd)

GRID = [("база (край, все)",            dict()),
        ("A wait>2",                    dict(min_wait=2)),
        ("B mid 50%",                   dict(fvg_mid=True)),
        ("A+B mid+wait>2",              dict(fvg_mid=True, min_wait=2)),
        ("ADX20-FVG (відома)",          dict(fvg_adx=20)),
        ("B+ADX20",                     dict(fvg_mid=True, fvg_adx=20)),
        ("A+B+ADX20",                   dict(fvg_mid=True, min_wait=2, fvg_adx=20))]
print("ПОРТФЕЛЬ (KC незмінний + FVG-варіант), одна-на-монету, реалістично, risk 1%\n")
print(f"{'варіант':22s} {'сег':4s} | {'n':>5} {'exp':>7} {'уг/міс':>6} | {'сер/міс':>8} {'мед':>6} {'+міс':>5} {'DD':>5}")
print("-"*88)
RES = {}
for name, kw in GRID:
    T = portfolio(**kw); RES[name] = T
    for seg in ["IS", "OOS"]:
        x = pstats(T, seg)
        print(f"{name:22s} {seg:4s} | {x['n']:5d} {x['exp']:+7.3f} {x['tpm']:6.1f} | "
              f"{x['avg']:+7.2f}% {x['med']:+5.2f}% {x['pos']:4.0f}% {x['dd']:4.0f}%")
    print()

best = max(GRID, key=lambda g: pstats(RES[g[0]], "IS")["exp"])[0]
print(f"ОБРАНО на IS (найвищий exp): {best}\n")

T = RES[best]
print(f"Стійкість «{best}» ПО МОНЕТАХ (порівн. з базою, exp OOS):")
B = RES["база (край, все)"]
for coin in ["BTC", "ETH", "SOL", "BNB"]:
    b = B[(B.seg == "OOS") & (B.coin == coin)]["R"]; v = T[(T.seg == "OOS") & (T.coin == coin)]["R"]
    print(f"  {coin}: база {b.mean():+.3f} (n={len(b)}) -> варіант {v.mean():+.3f} (n={len(v)})")
print(f"\nСтійкість ПО РОКАХ (exp OOS, база -> варіант):")
for yr in sorted(T[T.seg == "OOS"]["ts"].dt.year.unique()):
    b = B[(B.seg == "OOS") & (B["ts"].dt.year == yr)]["R"]; v = T[(T.seg == "OOS") & (T["ts"].dt.year == yr)]["R"]
    print(f"  {yr}: {b.mean():+.3f} (n={len(b)}) -> {v.mean():+.3f} (n={len(v)})")
