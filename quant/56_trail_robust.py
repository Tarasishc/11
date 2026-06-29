"""Чи едж трейлінгу РОЗПОДІЛЕНИЙ, чи від кількох монстро-угод? (OOS, чесно)"""
import importlib.util, builtins, numpy as np, pandas as pd
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c55", "quant/55_more_profit.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print = _p
BASE, ENG, run = m.BASE, m.ENG, m.run

def oos_R(mode):
    rr = []
    for coin, d in BASE.items():
        cut = pd.Timestamp(d.index[int(len(d)*0.6)]); cut = cut.tz_localize(None) if cut.tzinfo else cut
        rr += [r for ts, r in run(d, ENG[coin], mode) if ts >= cut]
    return np.array(rr)

for mode in ["rr2", "trail"]:
    r = oos_R(mode); s = np.sort(r)[::-1]; tot = r.sum()
    print(f"\n=== {mode} === n={len(r)} sumR={tot:.0f} exp={r.mean():+.3f} WR={(r>0).mean()*100:.0f}% maxR={r.max():.1f}")
    print(f"  угод >3R: {(r>3).sum()}  >5R: {(r>5).sum()}  >10R: {(r>10).sum()}")
    for N in [10, 25, 50]:
        v = tot - s[:N].sum()
        print(f"  без топ-{N:2d} виграшів: sumR={v:6.0f}  ({'ПЛЮС' if v > 0 else 'МІНУС'}, {v/tot*100:.0f}% від повного)")
    # частка топ-10% угод у прибутку
    top10 = s[:max(1, len(s)//10)].sum()
    print(f"  топ-10% угод дають {top10/tot*100:.0f}% сумарного R")
print("\nРозподілений едж = і без топ-угод лишається плюс. Якщо без топ-50 стає мінус — це лотерея.")
