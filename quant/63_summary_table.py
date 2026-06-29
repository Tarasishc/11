"""Зведена таблиця: прибутки, просадки, місяці — робоча конфігурація,
risk 1%/1.5%, чистий vs реалістичний (зі слипом). Повний період 2017-2026."""
import importlib.util, builtins, numpy as np, pandas as pd
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c59", "quant/59_fill_realism.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print = _p
ALL, R_of = m.ALL, m.R_of

def metrics(risk, fee, es, ss):
    rows = [R_of(r, fee, es, ss) for r in ALL]
    T = pd.DataFrame(rows, columns=["t", "r"]).sort_values("t")
    r = T["r"].values; n = len(r)
    eq = np.cumprod(1 + risk * r)
    dd = ((eq / np.maximum.accumulate(eq)) - 1).min() * 100
    me = pd.Series(eq, index=pd.DatetimeIndex(T["t"])).resample("ME").last().dropna()
    mret = me.pct_change().dropna()
    mret = pd.concat([pd.Series([me.iloc[0] - 1], index=[me.index[0]]), mret]) * 100
    # найдовша серія мінусів
    cur = best = 0
    for v in mret:
        cur = cur + 1 if v < 0 else 0; best = max(best, cur)
    span = (T["t"].max() - T["t"].min()).days / 30.44
    return dict(n=n, exp=r.mean(), wr=(r > 0).mean() * 100, tpm=n / span,
                avg=mret.mean(), med=mret.median(), pos=(mret > 0).mean() * 100,
                dd=dd, worst=mret.min(), best=mret.max(), streak=best)

SCEN = [("1.0% чистий",   0.010, 0.0005, 0.0003, 0.0000),
        ("1.0% реальний", 0.010, 0.0005, 0.0005, 0.0010),
        ("1.5% чистий",   0.015, 0.0005, 0.0003, 0.0000),
        ("1.5% реальний", 0.015, 0.0005, 0.0005, 0.0010)]
print("РОБОЧА КОНФІГУРАЦІЯ (BTC+ETH+SOL KC+FVG, BNB FVG, одна-на-монету), 2017-2026\n")
hdr = ["сценарій", "сер/міс", "медіана", "+міс%", "maxDD", "найг.міс", "найкр.міс", "серія−", "exp/угода", "WR", "уг/міс"]
print(" | ".join(f"{h:>9s}" for h in hdr)); print("-" * 118)
for name, risk, fee, es, ss in SCEN:
    x = metrics(risk, fee, es, ss)
    print(f"{name:>9s} | {x['avg']:+8.2f}% | {x['med']:+7.2f}% | {x['pos']:7.0f}% | {x['dd']:7.0f}% | "
          f"{x['worst']:+7.1f}% | {x['best']:+8.1f}% | {x['streak']:6d}м | {x['exp']:+8.3f} | {x['wr']:6.0f}% | {x['tpm']:5.1f}")
print("\nРеальна MTM-просадка ~ +10пп до показаної (одночасні позиції).")
print("Це бектест 2017-2026 (бичача історія) — лайв нижчий; форвард дасть правду.")
