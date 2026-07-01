"""Звірка чисел: чому '70%+ плюсових / 6-10%/міс' було, а нове OOS ~56-63% / ~5%.
Драбина чесності (кожен крок ближчий до реальності):
  1) per-engine, ПОВНА історія, ЧИСТО      -> звідки взялись 73% / +7.5%
  2) one-per-coin, ПОВНА історія, реально   -> як реально можна руками
  3) one-per-coin, OOS (нові дані), реально  -> чесний форвард-орієнтир
  4) + ADX≥20 на FVG, OOS, реально           -> покращений варіант
Різниця = НЕ інша стратегія, а той самий движок під різними лінзами."""
import importlib.util, builtins, numpy as np, pandas as pd
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c67", "quant/67_stopout_patterns.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print = _p

def mstats(rows, risk=0.01):
    T = pd.DataFrame(rows, columns=["ts", "R"]).sort_values("ts"); r = T["R"].values
    eq = np.cumprod(1 + risk*r)
    me = pd.Series(eq, index=pd.DatetimeIndex(T["ts"])).resample("ME").last().dropna()
    mr = me.pct_change().dropna(); mr = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mr])
    dd = ((eq/np.maximum.accumulate(eq))-1).min()*100
    return len(r), r.mean(), mr.mean()*100, mr.median()*100, (mr > 0).mean()*100, dd

# --- рівень 2/3/4: one-per-coin (робоча логіка) ---
def opc_rows(fvg_adx, seg):
    rows = []
    for coin, d in m.BASE.items():
        cut = m.naive(d.index[int(len(d)*0.6)])
        for f in m.features(d, m.ENG[coin], fvg_adx):
            s = "OOS" if f[0] >= cut else "IS"
            if seg == "ALL" or s == seg: rows.append((f[0], f[6]))
    return rows

print("ДРАБИНА ЧИСЕЛ (той самий движок, різні лінзи), risk 1%:\n")
print(f"{'варіант':46s} {'n':>5} {'exp':>7} {'сер/міс':>8} {'медіан':>7} {'+міс':>5} {'DD':>6}")
print("-"*92)

# рядок-орієнтир з STATS.md (per-engine, повна історія)
print(f"{'[STATS.md] per-engine, ПОВНА, чисто (істор.орієнтир)':46s} {'~5000':>5} {'+0.211':>7} {'+7.5%':>8} {'+4.7%':>7} {'73%':>5} {'-34%':>6}")
print(f"{'[STATS.md] per-engine, ПОВНА, реально':46s} {'~5000':>5} {'+0.149':>7} {'+5.3%':>8} {'+3.2%':>7} {'65%':>5} {'-50%':>6}")

for lbl, fadx, seg in [
        ("one-per-coin, ПОВНА історія, реально", 0.0, "ALL"),
        ("one-per-coin, OOS (нові дані), реально  [БАЗА]", 0.0, "OOS"),
        ("one-per-coin, OOS, реально + ADX≥20 на FVG", 20.0, "OOS")]:
    n, e, avg, med, pos, dd = mstats(opc_rows(fadx, seg))
    print(f"{lbl:46s} {n:5d} {e:+7.3f} {avg:+7.2f}% {med:+6.2f}% {pos:4.0f}% {dd:+5.0f}%")

print("""
ЧОМУ '70%+/6-10%' -> '56-63%/~5%':
  • '73%/+7.5%' = per-engine + ПОВНА історія 2017-26 (2 величезні бичі 2017 і 2020-21)
    + ЧИСТО (без реального слипу стопа). Це найоптимістичніша лінза.
  • Кожен чесний крок знижує: реальні комісії/слип -> one-per-coin (руками не візьмеш
    2 позиції) -> OOS (останні ~40% = 2023-26, боковик/ведмідь, БЕЗ мега-бичів).
  • Тобто 63% — це той самий едж на НАЙВАЖЧОМУ, невидимому шматку. Це і є чесний
    орієнтир на лайв. Повна історія завжди виглядає кращою, ніж майбутнє.
  • ADX≥20 на FVG OOS цифри ПІДНІМАЄ (56->63%, медіана +2.0->+3.9%), не опускає.""")
