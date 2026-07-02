"""ПОЛЮВАННЯ НА МІНУСОВІ СЕТАПИ — нові фічі, яких ще не тестували.
База: BTC/ETH/SOL=KC+FVG, BNB=FVG, 4h, одна-на-монету, реалістичні витрати.
Нові кандидати:
  1) FVG: товщина зони / ATR (тонкий імбаланс = слабший?)
  2) FVG: швидкість ретесту (1-2 бари vs 10-20 — пізній ретест = згасання?)
  3) KC: якість пробійного бара (закриття у верхівці діапазону?)
  4) MTF: узгодження з ДЕННИМ трендом (EMA200 на 1D, без lookahead — вчорашнє значення)
  5) Серія збитків на монеті (skip після 2-3 лузів поспіль?)
  6) FVG: вхід на 50% зони замість краю (краща ціна, менше філів)
ДИСЦИПЛІНА: біни дивимось на IS; будь-який поріг перевіряємо OOS; приймаємо лише
якщо викинуте <=0 на ОБОХ сегментах і лишок кращає."""
import numpy as np, pandas as pd
import lib_data as L, strategies as ST, engine as E

BASE = {"BTC": ST.resample(L.load_btc_15m(), "4h"), "ETH": L.load_any("quant/data/eth_4h.csv"),
        "SOL": L.load_any("quant/data/sol_4h.csv"), "BNB": L.load_any("quant/data/bnb_4h.csv")}
ENG = {"BTC": "KF", "ETH": "KF", "SOL": "KF", "BNB": "F"}
FEE, ES, SS = 0.0005, 0.0005, 0.0010

def naive(t): ts = pd.Timestamp(t); return ts.tz_localize(None) if ts.tzinfo else ts
def adxv(d):
    h, l = d["high"], d["low"]; up = h.diff(); dn = -l.diff()
    pdm = ((up > dn) & (up > 0))*up; mdm = ((dn > up) & (dn > 0))*dn
    tr = E.true_range(d); a = tr.ewm(alpha=1/14, adjust=False).mean()
    pdi = 100*pdm.ewm(alpha=1/14, adjust=False).mean()/a; mdi = 100*mdm.ewm(alpha=1/14, adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)).ewm(alpha=1/14, adjust=False).mean().to_numpy()

def daily_bull(d):
    """денний тренд (EMA200 на 1D) станом на ВЧОРА -> Series bool по 4h-індексу."""
    dc = d["close"].resample("1D").last().dropna()
    e2 = dc.ewm(span=200, adjust=False).mean()
    bull = (dc > e2).shift(1)                       # вчорашній стан, без lookahead
    return bull.reindex(d.index.normalize()).ffill().to_numpy()

def collect(d, eng, fvg_adx=0.0, fvg_mid=False):
    """взяті угоди (одна-на-монету) з повним набором фіч."""
    cl = d["close"]; o, h, l, c = [d[x].to_numpy() for x in ["open", "high", "low", "close"]]
    atr = E.atr(d, 14).to_numpy(); em = E.ema(cl, 200).to_numpy(); ax = adxv(d)
    dbull = daily_bull(d); n = len(c); S = []
    if "K" in eng:
        mid = E.ema(cl, 20); band = 2*E.atr(d, 10)
        up = ((cl > mid+band) & (cl > E.ema(cl, 200))).to_numpy()
        dn = ((cl < mid-band) & (cl < E.ema(cl, 200))).to_numpy()
        for i in range(1, n-1):
            if not np.isfinite(atr[i]) or ax[i] < 20: continue
            rng = h[i]-l[i]
            for si, sig in ((1, up), (-1, dn)):
                if sig[i] and not sig[i-1]:
                    pos = ((c[i]-l[i])/rng if si > 0 else (h[i]-c[i])/rng) if rng > 0 else 0.5
                    S.append((i+1, si, o[i+1], 2.0*atr[i], "KC", dict(kc_pos=pos)))
    if "F" in eng:
        for k in range(2, n-1):
            for si in (1, -1):
                if si > 0 and not (h[k-2] < l[k] and c[k] > em[k]): continue
                if si < 0 and not (l[k-2] > h[k] and c[k] < em[k]): continue
                zt = l[k] if si > 0 else h[k]; zb = h[k-2] if si > 0 else l[k-2]
                thick = abs(zt - zb)
                for j in range(k+1, min(k+21, n)):
                    trok = c[j] > em[j] if si > 0 else c[j] < em[j]
                    if not trok: continue
                    if fvg_mid:
                        entry = (zt + zb) / 2
                        hit = l[j] <= entry if si > 0 else h[j] >= entry
                    else:
                        entry = zt
                        hit = l[j] <= zt if si > 0 else h[j] >= zt
                    if hit:
                        if fvg_adx > 0 and not (np.isfinite(ax[j]) and ax[j] >= fvg_adx): break
                        D = max(abs(entry - zb), 0.5*atr[j])
                        S.append((j, si, entry, D, "FVG",
                                  dict(gap_atr=thick/atr[k] if np.isfinite(atr[k]) and atr[k] > 0 else np.nan,
                                       wait=j-k)))
                        break
    S.sort(key=lambda x: x[0]); out = []; ou = -1
    for eb, si, raw, D, tag, meta in S:
        if eb <= ou: continue
        stop = raw - si*D; tgt = raw + si*2.0*D; j = eb; ex = None
        while j < n:
            if (l[j] <= stop) if si > 0 else (h[j] >= stop): ex = ("stop", stop, j); break
            if (h[j] >= tgt) if si > 0 else (l[j] <= tgt): ex = ("tgt", tgt, j); break
            j += 1
        if ex is None: ex = ("eod", c[-1], n-1)
        en = raw*(1 + si*ES); exf = ex[1]*(1 - si*SS) if ex[0] == "stop" else ex[1]
        R = si*(exf-en)/D - 2*FEE*(en/D)
        mtf = bool(dbull[eb]) if not np.isnan(dbull[eb] if dbull[eb] is not None else np.nan) else None
        agree = None if mtf is None else (mtf if si > 0 else (not mtf))
        out.append(dict(ts=naive(d.index[eb]), side=si, eng=tag, R=R, adx=ax[eb],
                        agree=agree, **meta))
        ou = ex[2]
    return out

# ------------------ збір бази ------------------
rows = []
for coin, d in BASE.items():
    cut = naive(d.index[int(len(d)*0.6)])
    for t in collect(d, ENG[coin]):
        t["coin"] = coin; t["seg"] = "OOS" if t["ts"] >= cut else "IS"; rows.append(t)
DF = pd.DataFrame(rows)
IS, OOS = DF[DF.seg == "IS"], DF[DF.seg == "OOS"]
print(f"БАЗА свіжий прогін: IS n={len(IS)} exp={IS['R'].mean():+.3f} | OOS n={len(OOS)} exp={OOS['R'].mean():+.3f}\n")

def bins(sub, col, edges, lbl):
    print(f"{lbl} (IS біни, exp R):")
    for a, b in zip(edges[:-1], edges[1:]):
        s = sub[(sub[col] > a) & (sub[col] <= b)]
        if len(s): print(f"  ({a:5.2f}..{b:5.2f}] n={len(s):4d} exp={s['R'].mean():+.3f} WR={(s['R']>0).mean()*100:.0f}%")
    print()

# 1) FVG товщина зони/ATR
f_is = IS[IS.eng == "FVG"]
bins(f_is, "gap_atr", list(f_is["gap_atr"].quantile([0, .25, .5, .75, 1]).values + [0]), "1) FVG товщина зони/ATR")
# 2) FVG швидкість ретесту
print("2) FVG бари до ретесту (IS):")
for a, b in [(0, 2), (2, 5), (5, 10), (10, 20)]:
    s = f_is[(f_is["wait"] > a) & (f_is["wait"] <= b)]
    print(f"  ({a:2d}..{b:2d}] n={len(s):4d} exp={s['R'].mean():+.3f} WR={(s['R']>0).mean()*100:.0f}%")
print()
# 3) KC якість пробійного бара
k_is = IS[IS.eng == "KC"]
bins(k_is, "kc_pos", [0, .4, .6, .8, 1.0], "3) KC закриття у діапазоні бара (1=на екстремумі)")
# 4) MTF денний тренд
print("4) Узгодження з ДЕННИМ трендом (EMA200 1D):")
for seg, D_ in [("IS", IS), ("OOS", OOS)]:
    a = D_[D_.agree == True]; b = D_[D_.agree == False]
    print(f"  {seg}: збіг n={len(a):4d} exp={a['R'].mean():+.3f} | ПРОТИ n={len(b):4d} exp={b['R'].mean():+.3f}")
print()
# 5) серія збитків на монеті перед входом
print("5) Скільки лузів поспіль на монеті ПЕРЕД входом (IS):")
DF2 = DF.sort_values(["coin", "ts"]).copy()
DF2["streak"] = 0
for coin in DF2["coin"].unique():
    idx = DF2.index[DF2["coin"] == coin]; s = 0
    for i in idx:
        DF2.loc[i, "streak"] = s
        s = s + 1 if DF2.loc[i, "R"] <= 0 else 0
I2 = DF2[DF2.seg == "IS"]
for k in [0, 1, 2]:
    s = I2[I2["streak"] == k]; print(f"  {k} лузів: n={len(s):4d} exp={s['R'].mean():+.3f}")
s = I2[I2["streak"] >= 3]; print(f"  3+ лузів: n={len(s):4d} exp={s['R'].mean():+.3f}")
O2 = DF2[DF2.seg == "OOS"]
s3i, s3o = I2[I2["streak"] >= 3], O2[O2["streak"] >= 3]
print(f"  перевірка OOS 3+: n={len(s3o):4d} exp={s3o['R'].mean():+.3f}\n")

# 6) FVG вхід на 50% зони — повний паралельний прогін
rows_mid = []
for coin, d in BASE.items():
    cut = naive(d.index[int(len(d)*0.6)])
    for t in collect(d, ENG[coin], fvg_mid=True):
        t["seg"] = "OOS" if t["ts"] >= cut else "IS"; rows_mid.append(t)
M = pd.DataFrame(rows_mid)
print("6) FVG вхід на 50% зони (vs край):")
for seg in ["IS", "OOS"]:
    b_ = DF[(DF.seg == seg) & (DF.eng == "FVG")]; m_ = M[(M.seg == seg) & (M.eng == "FVG")]
    print(f"  {seg}: край n={len(b_):4d} exp={b_['R'].mean():+.3f} | 50% n={len(m_):4d} exp={m_['R'].mean():+.3f}")
print("\n(Пороги, що виглядають перспективно на IS, перевіряти окремо — див. вивід вище.)")
