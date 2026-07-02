"""СКАН ЗАКОНОМІРНОСТЕЙ НА BTC (15m/1h/1D, 2017-2026). Дисципліна:
  - ефект зараховується ЛИШЕ якщо: однаковий знак IS і OOS + перекриває витрати
    (тейкер+слип ~0.10-0.15% на КРУГ) + має пояснення. Інакше — цікаво, але СМІТТЯ.
  A) сезонність ГОДИН доби (UTC)     B) день тижня
  C) серії червоних/зелених днів      D) NR7-стиснення -> пробій наступного дня
  E) продовження після |руху| > 2σ    F) вол-таргетинг BnH (керування бетою, не таймінг)"""
import numpy as np, pandas as pd
import lib_data as L, strategies as ST

COST_RT = 0.0015                                    # витрати на круг (консервативно)
M15 = L.load_btc_15m()
H1 = ST.resample(M15, "1h"); D1 = ST.resample(M15, "1D")
cutD = D1.index[int(len(D1)*0.6)]
print(f"BTC {D1.index[0].date()}..{D1.index[-1].date()} | IS/OOS зріз {cutD.date()} | "
      f"поріг тредабельності {COST_RT*100:.2f}%/круг\n")

def seg_mask(idx, which): return (idx >= cutD) if which == "OOS" else (idx < cutD)

# ---------- A) години доби ----------
hr = H1["close"].pct_change().dropna()
tab = []
for h in range(24):
    row = [h]
    for which in ["IS", "OOS"]:
        s = hr[(hr.index.hour == h) & seg_mask(hr.index, which)]
        row += [s.mean()*100, len(s)]
    tab.append(row)
A = pd.DataFrame(tab, columns=["h", "is_m", "is_n", "oos_m", "oos_n"])
A["ok"] = (np.sign(A.is_m) == np.sign(A.oos_m)) & (A[["is_m", "oos_m"]].abs().min(axis=1) > COST_RT*100)
best = A.reindex(A.is_m.abs().sort_values(ascending=False).index).head(4)
print("A) Години доби (топ-4 за |IS|, сер. %/год):")
for _, r in best.iterrows():
    print(f"   {int(r.h):02d}:00 UTC | IS {r.is_m:+.3f}% | OOS {r.oos_m:+.3f}% | "
          f"{'ПРОЙШОВ' if r.ok else 'сміття (знак/витрати)'}")
print(f"   тредабельних годин: {int(A.ok.sum())} з 24\n")

# ---------- B) день тижня ----------
dr = D1["close"].pct_change().dropna()
print("B) День тижня (сер. %/день):")
names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
okB = 0
for wd in range(7):
    i_ = dr[(dr.index.weekday == wd) & seg_mask(dr.index, "IS")].mean()*100
    o_ = dr[(dr.index.weekday == wd) & seg_mask(dr.index, "OOS")].mean()*100
    ok = np.sign(i_) == np.sign(o_) and min(abs(i_), abs(o_)) > COST_RT*100
    okB += ok
    print(f"   {names[wd]} | IS {i_:+.3f}% | OOS {o_:+.3f}% | {'ПРОЙШОВ' if ok else '—'}")
print(f"   тредабельних днів: {okB} з 7\n")

# ---------- C) серії днів ----------
sign_d = np.sign(dr)
streak = sign_d.copy()*0
run = 0; prev = 0
vals = []
for s in sign_d.values:
    run = run + 1 if s == prev and s != 0 else 1
    prev = s; vals.append(run*s)
streak = pd.Series(vals, index=dr.index)
nxt = dr.shift(-1)
print("C) Наступний день після серії (сер. %):")
for k in [-4, -3, -2, 2, 3, 4]:
    m = streak[abs(streak) >= abs(k)]
    m = m[np.sign(m) == np.sign(k)]
    i_ = nxt[m.index[seg_mask(m.index, 'IS')]].mean()*100
    o_ = nxt[m.index[seg_mask(m.index, 'OOS')]].mean()*100
    lbl = f"{abs(k)}+ {'червоних' if k < 0 else 'зелених'}"
    ok = np.sign(i_) == np.sign(o_) and min(abs(i_), abs(o_)) > COST_RT*100
    ni = seg_mask(m.index, 'IS').sum(); no = seg_mask(m.index, 'OOS').sum()
    print(f"   {lbl:12s} | IS {i_:+.3f}% (n={ni}) | OOS {o_:+.3f}% (n={no}) | {'ПРОЙШОВ' if ok else '—'}")
print()

# ---------- D) NR7 -> пробій ----------
rng = (D1["high"] - D1["low"])
nr7 = rng == rng.rolling(7).min()
o, h, l, c = [D1[x].to_numpy() for x in ["open", "high", "low", "close"]]
print("D) Наступний день після NR7 (стиснення):")
for which in ["IS", "OOS"]:
    mask = nr7 & seg_mask(D1.index, which)
    idx = np.where(mask.to_numpy()[:-1])[0] + 1          # наступний день
    if not len(idx): continue
    fol = np.abs(c[idx]/o[idx] - 1).mean()*100
    base = np.abs(c/o - 1)[np.array(sorted(set(range(1, len(c))) - set(idx)))].mean()*100
    # напрямний пробій: купи пробій хай NR7-дня / продай пробій лоу (перший дотик, 15m)
    print(f"   {which}: |рух| після NR7 {fol:.2f}% vs звичайний {base:.2f}% (експансія?)")
print("   (напрямної переваги NR7 не дає — перевіряємо лише розмір руху; таймінг = VB, який у мінусі)\n")

# ---------- E) після великого руху ----------
sig20 = dr.rolling(20).std()
big = dr[abs(dr) > 2*sig20]
print("E) Наступний день після |руху|>2σ:")
for d_, lbl in [(1, "великий ЗЕЛЕНИЙ"), (-1, "великий ЧЕРВОНИЙ")]:
    m = big[np.sign(big) == d_]
    i_ = nxt[m.index[seg_mask(m.index, 'IS')]].mean()*100
    o_ = nxt[m.index[seg_mask(m.index, 'OOS')]].mean()*100
    ok = np.sign(i_) == np.sign(o_) and min(abs(i_), abs(o_)) > COST_RT*100
    ni = seg_mask(m.index, 'IS').sum(); no = seg_mask(m.index, 'OOS').sum()
    print(f"   {lbl:16s} | IS {i_:+.3f}% (n={ni}) | OOS {o_:+.3f}% (n={no}) | {'ПРОЙШОВ' if ok else '—'}")
print()

# ---------- F) вол-таргетинг BnH ----------
print("F) Вол-таргетинг BnH (бета-менеджмент, лонг-онлі, target 40% річних, w<=1.5):")
rv = dr.rolling(20).std()*np.sqrt(365)
w = (0.40/rv).clip(upper=1.5).shift(1).fillna(0)
strat = w*dr - (w.diff().abs().fillna(0))*COST_RT/2
def mst(x):
    eq = (1+x).cumprod(); me = eq.resample("ME").last().dropna()
    mr = me.pct_change().dropna(); mr = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mr])*100
    dd = ((eq/eq.cummax())-1).min()*100
    return mr.mean(), mr.median(), (mr > 0).mean()*100, dd, mr.std(), mr.mean()/mr.std()*np.sqrt(12) if mr.std() > 0 else 0
for which in ["IS", "OOS"]:
    for nm, x in [("BnH     ", dr[seg_mask(dr.index, which)]), ("VolTgt  ", strat[seg_mask(strat.index, which)])]:
        a, md, p, dd, sd, sh = mst(x)
        print(f"   {which} {nm} | сер {a:+5.2f}% мед {md:+5.2f}% +міс {p:3.0f}% DD {dd:5.0f}% Шарп {sh:+4.2f}")
    print()
print("Вердикт друкується фактами вище: що ПРОЙШЛО подвійний бар'єр (знак IS=OOS + > витрат).")
