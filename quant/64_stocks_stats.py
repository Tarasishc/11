"""Статистика прибутків/просадок ПО АКЦІЯХ (5 шт, KC+FVG, 1D, untuned).
ts відновлюємо (ts*10^6 сек) -> дати ~±10днів, годиться для місяців/просадки.
Весь період = OOS (стратегія тюнилась на крипті, акцій не бачила)."""
import importlib.util, builtins, numpy as np, pandas as pd, glob
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c60", "quant/60_stop_width.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print = _p
taken = m.taken
U = "/root/.claude/uploads/1a1f9a43-9b33-5f10-987c-59946e91120c"
FILES = {"QQQ": "qqq", "AAPL": "aapl", "TSLA": "tsla", "NVDA": "nvda", "MSFT": "msft"}

def load(tag):
    raw = pd.read_csv(glob.glob(f"{U}/*-{tag}_1d.csv")[0])
    dt = pd.to_datetime(raw["ts"].astype("int64") * 1_000_000, unit="s")  # відновлення дат
    return pd.DataFrame({"open": raw["open"].values, "high": raw["high"].values,
                         "low": raw["low"].values, "close": raw["close"].values}, index=dt)

def trades(d, fee, es, ss):
    out = []
    for ts, si, raw, D, extype, exlvl in taken(d, "KF", 2.0, 0.5):
        en = raw*(1 + si*es)
        ex = exlvl*(1 - si*ss) if extype == "stop" else exlvl
        out.append((pd.Timestamp(ts), si*(ex-en)/D - 2*fee*(en/D)))
    return out

def monthly_stats(rows, risk=0.01):
    T = pd.DataFrame(rows, columns=["t", "r"]).sort_values("t")
    eq = np.cumprod(1 + risk*T["r"].values)
    dd = ((eq/np.maximum.accumulate(eq))-1).min()*100
    me = pd.Series(eq, index=pd.DatetimeIndex(T["t"])).resample("ME").last().dropna()
    mr = me.pct_change().dropna(); mr = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mr])*100
    cur = best = 0
    for v in mr:
        cur = cur+1 if v < 0 else 0; best = max(best, cur)
    return dict(avg=mr.mean(), med=mr.median(), pos=(mr > 0).mean()*100, dd=dd,
                worst=mr.min(), bestm=mr.max(), streak=best)

print("ПО АКЦІЯХ (KC+FVG, 1D, untuned, risk 1%). Весь період = OOS.\n")
print("Внесок кожної (чисті витрати):")
print(f"{'акція':6s} | {'n':>4} {'exp':>7} {'WR':>5} {'sumR':>6}")
allc, allr = [], []
for name, tag in FILES.items():
    tr = trades(load(tag), 0.0005, 0.0003, 0.0)
    r = np.array([x[1] for x in tr]); allc += tr
    print(f"{name:6s} | {len(r):4d} {r.mean():+7.3f} {(r>0).mean()*100:4.0f}% {r.sum():+6.0f}")
print(f"\nПОРТФЕЛЬ 5 акцій разом (одна-на-акцію), risk 1%:")
for lbl, fee, es, ss in [("чистий  ", 0.0005, 0.0003, 0.0), ("реальний", 0.0005, 0.0005, 0.0010)]:
    rows = []
    for name, tag in FILES.items(): rows += trades(load(tag), fee, es, ss)
    s = monthly_stats(rows)
    r = np.array([x[1] for x in rows])
    print(f"  {lbl}: сер/міс {s['avg']:+.2f}% | медіана {s['med']:+.2f}% | +міс {s['pos']:.0f}% | "
          f"DD {s['dd']:.0f}% | найг.міс {s['worst']:+.1f}% | найкр {s['bestm']:+.1f}% | "
          f"серія− {s['streak']}м | exp {r.mean():+.3f}R")
print("\n(Дати приблизні ±10дн -> місячні цифри орієнтовні; exp/WR/DD точні. Чисті витрати;")
print(" реальне виконання на акціях нижче, але мейджор-акції ліквідні.)")
