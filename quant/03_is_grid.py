"""Крок 5 — ітерація на IN-SAMPLE.
Перебір гіпотез/параметрів при ФІКСОВАНОМУ ризику 1% (шукаємо ЕДЖ у R-просторі,
не плутаючи його з плечем). Лог усіх кандидатів у quant/out/is_grid.csv."""
import itertools
import numpy as np
import pandas as pd
import lib_data as L
import lib_split as SP
import strategies as ST
import engine as E

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)

# --- дані IS на трьох таймфреймах ---
btc15 = L.load_btc_15m()
is15, _ = SP.split(btc15)
TF = {
    "15m": (is15, 15),
    "1h": (ST.resample(is15, "1h"), 60),
    "4h": (ST.resample(is15, "4h"), 240),
}
print("IS барів:", {k: len(v[0]) for k, v in TF.items()})

RISK = 0.01
rows = []


def run(name, tf, fn, params, rr, direction):
    d, bmin = TF[tf]
    al = direction in ("both", "long")
    ash = direction in ("both", "short")
    side, sd = fn(d, allow_long=al, allow_short=ash, **params)
    cfg = E.Config(rr=rr, risk_pct=RISK, bar_minutes=bmin,
                   allow_long=al, allow_short=ash)
    res = E.backtest(d, side, sd, cfg)
    m = res.metrics
    row = dict(strat=name, tf=tf, direction=direction, rr=rr, **params)
    row.update({
        "n_trades": m["n_trades"], "avg_monthly": m["avg_monthly"],
        "total_return": m["total_return"], "cagr": m["cagr"],
        "max_dd": m["max_dd"], "sharpe": m["sharpe"], "sortino": m["sortino"],
        "win_rate": m["win_rate"], "profit_factor": m["profit_factor"],
        "expectancy_R": m["expectancy_R"],
        "mar_monthly": (m["avg_monthly"] / abs(m["max_dd"])) if m["max_dd"] < 0 else 0,
        "pct_long": m.get("pct_long", 0),
    })
    rows.append(row)


GRIDS = {
    "H1_trend_pullback": dict(
        fn=ST.h1_trend_pullback,
        tfs=["15m", "1h", "4h"],
        params=dict(atr_mult=[1.0, 1.5, 2.0]),
        fixed=dict(ema_fast=50, ema_slow=200, ema_pull=20, atr_n=14),
        rrs=[2.0, 2.5, 3.0], dirs=["both", "short"],
    ),
    "H2_breakout_trend": dict(
        fn=ST.h2_breakout_trend,
        tfs=["15m", "1h", "4h"],
        params=dict(n=[30, 50, 80], atr_mult=[1.5, 2.0, 3.0]),
        fixed=dict(ema_trend=200, atr_n=14),
        rrs=[2.0, 3.0], dirs=["both"],
    ),
    "H3_failed_breakout": dict(
        fn=ST.h3_failed_breakout,
        tfs=["15m", "1h", "4h"],
        params=dict(n=[20, 40], atr_mult=[1.0, 1.5, 2.0], adx_max=[0, 25]),
        fixed=dict(atr_n=14, adx_n=14),
        rrs=[2.0, 3.0], dirs=["both", "short"],
    ),
    "H4_bb_meanrev": dict(
        fn=ST.h4_bb_meanrev,
        tfs=["1h", "4h"],
        params=dict(k=[2.0, 2.5], atr_mult=[1.0, 1.5], adx_max=[15, 20, 25]),
        fixed=dict(n=20, atr_n=14, adx_n=14),
        rrs=[2.0, 3.0], dirs=["both", "short"],
    ),
}


def expand(params):
    keys = list(params.keys())
    for combo in itertools.product(*params.values()):
        yield dict(zip(keys, combo))


import time
t0 = time.time()
for name, g in GRIDS.items():
    cnt = 0
    for tf in g["tfs"]:
        for p in expand(g["params"]):
            full = dict(g["fixed"], **p)
            for rr in g["rrs"]:
                for direction in g["dirs"]:
                    run(name, tf, g["fn"], full, rr, direction)
                    cnt += 1
    print(f"{name}: {cnt} комбінацій  ({time.time()-t0:.0f}s)")

df = pd.DataFrame(rows)
df.to_csv("quant/out/is_grid.csv", index=False)
print(f"\nУсього кандидатів: {len(df)}  -> quant/out/is_grid.csv  ({time.time()-t0:.0f}s)")

# --- топ по кожній стратегії: фільтр n>=100 та expectancy>0, сорт за profit_factor ---
show = ["strat", "tf", "direction", "rr", "n_trades", "win_rate", "expectancy_R",
        "profit_factor", "avg_monthly", "max_dd", "mar_monthly", "sharpe", "pct_long"]
for name in GRIDS:
    sub = df[(df.strat == name) & (df.n_trades >= 100) & (df.expectancy_R > 0)]
    sub = sub.sort_values("mar_monthly", ascending=False)
    print(f"\n===== {name}: топ-8 (n>=100, E[R]>0, сорт mar_monthly) =====")
    if len(sub) == 0:
        print("  — немає кандидатів, що проходять фільтр —")
    else:
        with pd.option_context("display.float_format", lambda x: f"{x:.3f}"):
            print(sub[show].head(8).to_string(index=False))
