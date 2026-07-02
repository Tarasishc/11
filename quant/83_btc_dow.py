"""ГЛИБОКА ПЕРЕВІРКА ефекту ДНІВ ТИЖНЯ на BTC (єдина зачіпка зі скану 82).
Питання: Пн/Ср сильно плюсові, Чт мінусовий на IS І OOS — це справжнє чи артефакт?
  1) по РОКАХ (скільки років ефект тримається; чи не тягне 2019-21)
  2) медіана vs середнє (чи не 3 викиди роблять цифру)
  3) чесна симуляція: LONG Пн+Ср+Пт / +SHORT Чт, витрати 0.15%/круг,
     місячна стата IS/OOS vs BnH; окремо сучасна ера 2024+ (пост-ETF)
Планка: ефект має жити в БІЛЬШОСТІ років включно з новітніми, інакше — сміття."""
import numpy as np, pandas as pd
import lib_data as L, strategies as ST

COST_RT = 0.0015
D1 = ST.resample(L.load_btc_15m(), "1D")
dr = D1["close"].pct_change().dropna()
cutD = D1.index[int(len(D1)*0.6)]
names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]

print("1) СЕРЕДНІЙ %/день ПО РОКАХ (виділяємо Пн/Ср/Чт):\n")
yrs = sorted(set(dr.index.year))
print("рік  | " + " | ".join(f"{n:>6s}" for n in names))
for y in yrs:
    s = dr[dr.index.year == y]
    row = []
    for wd in range(7):
        v = s[s.index.weekday == wd].mean()*100
        row.append(f"{v:+6.2f}")
    print(f"{y} | " + " | ".join(row))
mon = [dr[(dr.index.year == y) & (dr.index.weekday == 0)].mean() for y in yrs]
wed = [dr[(dr.index.year == y) & (dr.index.weekday == 2)].mean() for y in yrs]
thu = [dr[(dr.index.year == y) & (dr.index.weekday == 3)].mean() for y in yrs]
print(f"\nПн плюсовий у {sum(1 for v in mon if v > 0)}/{len(yrs)} років | "
      f"Ср у {sum(1 for v in wed if v > 0)}/{len(yrs)} | Чт мінусовий у {sum(1 for v in thu if v < 0)}/{len(yrs)}")

print("\n2) СЕРЕДНЄ vs МЕДІАНА (повний період) — чи не викиди:")
for wd in [0, 2, 3]:
    s = dr[dr.index.weekday == wd]
    print(f"   {names[wd]}: сер {s.mean()*100:+.3f}% | медіана {s.median()*100:+.3f}% | "
          f"WR {(s > 0).mean()*100:.0f}% | n={len(s)}")

print("\n3) СИМУЛЯЦІЯ з витратами (0.15%/круг), close-to-close:")
def sim(longs, shorts=()):
    pos = pd.Series(0.0, index=dr.index)
    for wd in longs: pos[pos.index.weekday == wd] = 1.0
    for wd in shorts: pos[pos.index.weekday == wd] = -1.0
    # вхід на close попереднього дня -> позиція діє в день wd; витрати на зміну позиції
    trades_cost = pos.diff().abs().fillna(abs(pos.iloc[0]))*COST_RT/2
    return pos*dr - trades_cost
def mst(x):
    eq = (1+x).cumprod(); me = eq.resample("ME").last().dropna()
    mr = me.pct_change().dropna(); mr = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mr])*100
    dd = ((eq/eq.cummax())-1).min()*100
    sh = mr.mean()/mr.std()*np.sqrt(12) if mr.std() > 0 else 0
    return mr.mean(), mr.median(), (mr > 0).mean()*100, dd, sh
STRATS = [("LONG Пн", sim([0])), ("LONG Пн+Ср", sim([0, 2])), ("LONG Пн+Ср+Пт", sim([0, 2, 4])),
          ("Пн+Ср+Пт L, Чт S", sim([0, 2, 4], [3])), ("BnH", dr.copy())]
print(f"{'стратегія':18s} {'сег':4s} | {'сер/міс':>8} {'мед':>6} {'+міс':>5} {'DD':>6} {'Шарп':>5}")
for nm, x in STRATS:
    for which, m in [("IS", x.index < cutD), ("OOS", x.index >= cutD)]:
        a, md, p, dd, sh = mst(x[m])
        print(f"{nm:18s} {which:4s} | {a:+7.2f}% {md:+5.2f}% {p:4.0f}% {dd:5.0f}% {sh:+5.2f}")
    print()

print("4) СУЧАСНА ЕРА (2024-01-01 .. кінець) — чи живий ефект після ETF:")
mod = dr[dr.index >= "2024-01-01"]
for wd in [0, 2, 3]:
    s = mod[mod.index.weekday == wd]
    print(f"   {names[wd]}: сер {s.mean()*100:+.3f}% | медіана {s.median()*100:+.3f}% | n={len(s)}")
x = sim([0, 2, 4], [3]); x = x[x.index >= "2024-01-01"]
a, md, p, dd, sh = mst(x)
print(f"   Пн+Ср+Пт L, Чт S з 2024: сер/міс {a:+.2f}% | мед {md:+.2f}% | +міс {p:.0f}% | DD {dd:.0f}% | Шарп {sh:+.2f}")
b = dr[dr.index >= "2024-01-01"]; a2, md2, p2, dd2, sh2 = mst(b)
print(f"   BnH з 2024:              сер/міс {a2:+.2f}% | мед {md2:+.2f}% | +міс {p2:.0f}% | DD {dd2:.0f}% | Шарп {sh2:+.2f}")
