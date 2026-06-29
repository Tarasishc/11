"""Детальна статистика по MNT (KC+FVG, одна-на-монету, 4h, risk 1%)."""
import importlib.util, builtins, numpy as np, pandas as pd
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c44", "quant/44_one_per_coin.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print = _p
import lib_data as L
mnt = L.load_any("quant/data/mnt_4h.csv")
rows = [(m.naive(ts), r) for ts, r in m.one_per_coin(mnt)]
T = pd.DataFrame(rows, columns=["t", "r"]).sort_values("t")
r = T["r"].values
eq = np.cumprod(1 + 0.01 * r)
dd = ((eq/np.maximum.accumulate(eq))-1).min()*100
me = pd.Series(eq, index=pd.DatetimeIndex(T["t"])).resample("ME").last().dropna()
mr = me.pct_change().dropna(); mr = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mr])*100
cut = m.naive(mnt.index[int(len(mnt)*0.6)])
iss = T[T["t"] < cut]["r"].values; oos = T[T["t"] >= cut]["r"].values
cur = best = 0
for v in mr:
    cur = cur+1 if v < 0 else 0; best = max(best, cur)
print(f"MNT 4h | історія {T['t'].min().date()}..{T['t'].max().date()} | угод {len(r)} | risk 1%\n")
print(f"  Очікування: всього {r.mean():+.3f}R | IS {iss.mean():+.3f} | OOS {oos.mean() if len(oos) else 0:+.3f}")
print(f"  WR {(r>0).mean()*100:.0f}% | угод/міс {len(r)/((T['t'].max()-T['t'].min()).days/30.44):.1f}")
print(f"  Місяць: сер {mr.mean():+.2f}% | медіана {mr.median():+.2f}% | +міс {(mr>0).mean()*100:.0f}%")
print(f"  Просадка: {dd:.0f}% | найг.міс {mr.min():+.1f}% | найкр.міс {mr.max():+.1f}% | серія− {best}м")
print(f"\nПорівняння exp: SOL +0.288 BTC +0.233 ETH +0.210 BNB +0.13 | MNT {r.mean():+.3f} (найслабша)")
print("Held-out (KC+FVG, §40) було +0.224R. У портфель не беремо — розбавляє.")
