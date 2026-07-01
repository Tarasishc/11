"""Чи є ЗАКОНОМІРНІСТЬ у стопових сетапах, яку можна прибрати фільтром?
Гіпотеза користувача: % відхилення від EMA200 (розтягнутість). Також перевіряю
ADX і ATR%. ДИСЦИПЛІНА: патерн шукаю ЛИШЕ на IS (перші 60%), приймаю тільки якщо
тримається на OOS (останні 40%) і має сенс. Інакше — чесно відхиляю (не оверфіт).
Детекція 1:1 з 60_stop_width, реалістичне виконання (комісія+слип стопа 0.10%)."""
import numpy as np, pandas as pd
import lib_data as L, strategies as ST, engine as E

BASE = {"BTC": ST.resample(L.load_btc_15m(), "4h"), "ETH": L.load_any("quant/data/eth_4h.csv"),
        "SOL": L.load_any("quant/data/sol_4h.csv"), "BNB": L.load_any("quant/data/bnb_4h.csv")}
ENG = {"BTC": "KF", "ETH": "KF", "SOL": "KF", "BNB": "F"}
FEE, ES, SS = 0.0005, 0.0005, 0.0010            # реалістичне виконання

def naive(t): ts = pd.Timestamp(t); return ts.tz_localize(None) if ts.tzinfo else ts
def adxv(d):
    h, l = d["high"], d["low"]; up = h.diff(); dn = -l.diff()
    pdm = ((up > dn) & (up > 0))*up; mdm = ((dn > up) & (dn > 0))*dn
    tr = E.true_range(d); a = tr.ewm(alpha=1/14, adjust=False).mean()
    pdi = 100*pdm.ewm(alpha=1/14, adjust=False).mean()/a; mdi = 100*mdm.ewm(alpha=1/14, adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)).ewm(alpha=1/14, adjust=False).mean().to_numpy()

def features(d, eng, fvg_adx=0.0):
    """кожна взята угода (одна-на-монету) -> фічі на вході + результат.
    fvg_adx>0 -> FVG-вхід беремо лише якщо ADX на барі ретесту ≥ порога (як у KC)."""
    cl = d["close"]; o, h, l, c = [d[x].to_numpy() for x in ["open", "high", "low", "close"]]
    atr = E.atr(d, 14).to_numpy(); em = E.ema(cl, 200).to_numpy(); ax = adxv(d); n = len(c)
    S = []                                       # (eb, si, raw, D, engine)
    if "K" in eng:
        mid = E.ema(cl, 20); band = 2*E.atr(d, 10)
        up = ((cl > mid+band) & (cl > E.ema(cl, 200))).to_numpy(); dn = ((cl < mid-band) & (cl < E.ema(cl, 200))).to_numpy()
        for i in range(1, n-1):
            if not np.isfinite(atr[i]) or ax[i] < 20: continue
            for si, sig in ((1, up), (-1, dn)):
                if sig[i] and not sig[i-1]: S.append((i+1, si, o[i+1]*(1+si*0), 2.0*atr[i], "K"))
    if "F" in eng:
        for k in range(2, n-1):
            if h[k-2] < l[k] and c[k] > em[k]:
                zt, zb = l[k], h[k-2]
                for j in range(k+1, min(k+21, n)):
                    if l[j] <= zt and c[j] > em[j]:
                        if fvg_adx <= 0 or (np.isfinite(ax[j]) and ax[j] >= fvg_adx):
                            S.append((j, 1, zt, max(zt-zb, 0.5*atr[j]), "F"))
                        break
            if l[k-2] > h[k] and c[k] < em[k]:
                zt, zb = h[k], l[k-2]
                for j in range(k+1, min(k+21, n)):
                    if h[j] >= zt and c[j] < em[j]:
                        if fvg_adx <= 0 or (np.isfinite(ax[j]) and ax[j] >= fvg_adx):
                            S.append((j, -1, zt, max(zb-zt, 0.5*atr[j]), "F"))
                        break
    S.sort(key=lambda x: x[0]); out = []; ou = -1
    for eb, si, raw, D, engn in S:
        if eb <= ou: continue
        stop = raw - si*D; tgt = raw + si*2*D; j = eb; ex = None
        while j < n:
            if (l[j] <= stop) if si > 0 else (h[j] >= stop): ex = ("stop", stop, j); break
            if (h[j] >= tgt) if si > 0 else (l[j] <= tgt): ex = ("tgt", tgt, j); break
            j += 1
        if ex is None: ex = ("eod", c[-1], n-1)
        en = raw*(1 + si*ES); exf = ex[1]*(1 - si*SS) if ex[0] == "stop" else ex[1]
        R = si*(exf-en)/D - 2*FEE*(en/D)
        dist = si*(raw - em[eb])/em[eb]*100          # % відхилення від EMA200 у бік тренду
        out.append((naive(d.index[eb]), si, engn, dist, ax[eb], atr[eb]/raw*100, R, ex[0]))
        ou = ex[2]
    return out

ALL = []
for coin, d in BASE.items():
    cut = naive(d.index[int(len(d)*0.6)])
    for f in features(d, ENG[coin]):
        ALL.append((coin, "OOS" if f[0] >= cut else "IS") + f)
DF = pd.DataFrame(ALL, columns=["coin", "seg", "ts", "side", "eng", "dist", "adx", "atrp", "R", "ex"])
IS, OOS = DF[DF.seg == "IS"], DF[DF.seg == "OOS"]

def exp(x): return x["R"].mean()
print(f"Усього угод {len(DF)} | IS {len(IS)} | OOS {len(OOS)} | база exp: IS {exp(IS):+.3f}R  OOS {exp(OOS):+.3f}R\n")

# 1) стопи vs тейки — середні фічі (IS)
st = IS[IS.ex == "stop"]; tg = IS[IS.ex == "tgt"]
print("СЕРЕДНІ ФІЧІ на IS (стоп vs тейк):")
for col, lbl in [("dist", "відх.EMA%"), ("adx", "ADX"), ("atrp", "ATR%")]:
    print(f"  {lbl:10s}: стоп {st[col].mean():6.2f} | тейк {tg[col].mean():6.2f} | різниця {tg[col].mean()-st[col].mean():+.2f}")

# 2) біни по кожній фічі (IS): expectancy — шукаємо монотонний зв'язок
def bins_report(name, col):
    q = IS[col].quantile([0, .2, .4, .6, .8, 1.0]).to_numpy().copy()
    q[0] -= 1e-9
    print(f"\nБІНИ по {name} (IS), expectancy та OOS-перевірка того ж порогу:")
    print(f"  {'квінтиль':22s} {'n':>5} {'IS exp':>8} {'WR':>5}")
    edges = np.unique(q)
    for a, b in zip(edges[:-1], edges[1:]):
        sub = IS[(IS[col] > a) & (IS[col] <= b)]
        if len(sub): print(f"  ({a:7.2f}..{b:7.2f}] {len(sub):5d} {sub['R'].mean():+8.3f} {(sub['R']>0).mean()*100:4.0f}%")
    return edges

for name, col in [("відх.EMA%", "dist"), ("ADX", "adx"), ("ATR%", "atrp")]:
    bins_report(name, col)

# 3) ТЕСТ ФІЛЬТРІВ IS -> OOS. Приймаємо лише якщо викинуте від'ємне НА ОБОХ і лишок росте.
print("\n" + "="*72)
print("ТЕСТ ФІЛЬТРІВ (IS -> OOS). Хочемо: викинуте <0 і на IS, і на OOS + лишок росте.\n")
def test_filter(name, col, thresholds, keep_high):
    print(f"{name} ({'лишаємо ≥ поріг, викидаємо низькі' if keep_high else 'лишаємо ≤ поріг, викидаємо високі'}):")
    for thr in thresholds:
        parts = []
        for seg, D in [("IS", IS), ("OOS", OOS)]:
            keep = D[D[col] >= thr] if keep_high else D[D[col] <= thr]
            drop = D[D[col] < thr] if keep_high else D[D[col] > thr]
            de = drop["R"].mean() if len(drop) else float("nan")
            parts.append(f"{seg}: викид {len(drop):4d} (exp{de:+.3f}) → лишок exp {keep['R'].mean():+.3f} (баз {D['R'].mean():+.3f})")
        print(f"  поріг={thr:6.2f} | " + " | ".join(parts))
    print()

test_filter("відх.EMA% (гіпотеза юзера)", "dist", [16.0, 23.0, 30.0], keep_high=False)
test_filter("ADX", "adx", [18.0, 20.0, 22.0], keep_high=True)
test_filter("ATR%", "atrp", [1.5, 1.75, 2.0], keep_high=True)

# 4) комбо: FVG-угоди з низьким ADX (KC вже має ADX≥20, а FVG — ні)
print("="*72)
print("FVG-угоди окремо за ADX (KC вже фільтрує ADX≥20, FVG — НІ):")
fv = DF[DF.eng == "F"]
for seg in ["IS", "OOS"]:
    s = fv[fv.seg == seg]
    lo = s[s.adx < 20]; hi = s[s.adx >= 20]
    print(f"  {seg}: ADX<20 -> {len(lo):4d} угод exp {lo['R'].mean():+.3f}R | "
          f"ADX≥20 -> {len(hi):4d} угод exp {hi['R'].mean():+.3f}R")

# 5) ЧЕСНА ПЕРЕВІРКА: вбудувати ADX≥20 у FVG (one-per-coin перевибирає слоти) і зміряти портфель
def portfolio(fvg_adx):
    rows = []
    for coin, d in BASE.items():
        cut = naive(d.index[int(len(d)*0.6)])
        for f in features(d, ENG[coin], fvg_adx):
            rows.append(("OOS" if f[0] >= cut else "IS", f[0], f[6]))
    return pd.DataFrame(rows, columns=["seg", "ts", "R"])

def pstats(P, seg, risk=0.01):
    T = P[P.seg == seg].sort_values("ts"); r = T["R"].values
    eq = np.cumprod(1 + risk*r)
    me = pd.Series(eq, index=pd.DatetimeIndex(T["ts"])).resample("ME").last().dropna()
    mr = me.pct_change().dropna(); mr = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mr])
    dd = ((eq/np.maximum.accumulate(eq))-1).min()*100
    span = (T["ts"].max()-T["ts"].min()).days/30.44
    return len(r), r.mean(), mr.mean()*100, mr.median()*100, (mr > 0).mean()*100, dd, len(r)/span

print("="*72)
print("ЧЕСНА ПЕРЕВІРКА: додати ADX≥20 у FVG (KC незмінний), risk 1%, реалістичне виконання\n")
print(f"{'варіант':28s} {'сег':4s} {'n':>5} {'exp':>7} {'сер/міс':>8} {'медіан':>7} {'+міс':>5} {'DD':>6} {'уг/міс':>6}")
for lbl, fadx in [("БАЗА (FVG без ADX)", 0.0), ("FVG з ADX≥20", 20.0)]:
    P = portfolio(fadx)
    for seg in ["IS", "OOS"]:
        n, e, avg, med, pos, dd, tpm = pstats(P, seg)
        print(f"{lbl:28s} {seg:4s} {n:5d} {e:+7.3f} {avg:+7.2f}% {med:+6.2f}% {pos:4.0f}% {dd:+5.0f}% {tpm:6.1f}")
print("\nПриймаємо ЛИШЕ якщо OOS exp і OOS сер/міс РОСТУТЬ, а угод/міс лишається достатньо.")
