"""IS-грід стратегій структури ринку (фрактали + BOS/CHoCH). Ризик 1% (едж у R)."""
import itertools, time
import numpy as np
import pandas as pd
import lib_data as L
import lib_split as SP
import strategies as ST
import engine as E
import market_structure as MS

pd.set_option("display.width", 220)

btc15 = L.load_btc_15m()
is15, _ = SP.split(btc15)
TF = {"4h": (ST.resample(is15, "4h"), 240), "1h": (ST.resample(is15, "1h"), 60)}
# кеш структур і ATR
STRUCT = {}; ATRA = {}
for tf, (d, _) in TF.items():
    ATRA[tf] = E.atr(d, 14).to_numpy()
    for k in [2, 3]:
        STRUCT[(tf, k)] = MS.compute_structure(d, k)
print("IS барів:", {k: len(v[0]) for k, v in TF.items()})

rows = []
t0 = time.time()
for tf in TF:
    d, bmin = TF[tf]
    for k in [2, 3]:
        st = STRUCT[(tf, k)]; aa = ATRA[tf]
        for mode in ["cont", "rev", "both"]:
            for stop_mode in ["struct", "atr"]:
                for rr in [2.0, 3.0]:
                    for direction in ["both", "short"]:
                        al = direction == "both"; ash = True
                        side, sd = MS.ms_signals(d, k=k, mode=mode, stop_mode=stop_mode,
                                                 atr_mult=2.0, stop_cap_atr=4.0, rr=rr,
                                                 allow_long=al, allow_short=ash,
                                                 struct=st, atr_arr=aa)
                        cfg = E.Config(rr=rr, risk_pct=0.01, bar_minutes=bmin,
                                       allow_long=al, allow_short=ash)
                        m = E.backtest(d, side, sd, cfg).metrics
                        rows.append(dict(tf=tf, k=k, mode=mode, stop=stop_mode, rr=rr,
                                         direction=direction, n_trades=m["n_trades"],
                                         win_rate=m["win_rate"], expectancy_R=m["expectancy_R"],
                                         profit_factor=m["profit_factor"], avg_monthly=m["avg_monthly"],
                                         max_dd=m["max_dd"], sharpe=m["sharpe"],
                                         mar=(m["avg_monthly"]/abs(m["max_dd"]) if m["max_dd"]<0 else 0),
                                         pct_long=m.get("pct_long", 0)))
df = pd.DataFrame(rows)
df.to_csv("quant/out/ms_grid.csv", index=False)
print(f"Кандидатів: {len(df)}  ({time.time()-t0:.0f}s) -> quant/out/ms_grid.csv\n")

show = ["tf","k","mode","stop","rr","direction","n_trades","win_rate","expectancy_R",
        "profit_factor","avg_monthly","max_dd","sharpe"]
print("===== ТОП-15 за profit_factor (n>=100, E[R]>0) =====")
good = df[(df.n_trades>=100)&(df.expectancy_R>0)].sort_values("profit_factor", ascending=False)
with pd.option_context("display.float_format", lambda x: f"{x:.3f}"):
    print(good[show].head(15).to_string(index=False))

print("\n===== Найкраще за режимом (cont/rev/both), n>=100 =====")
for mode in ["cont","rev","both"]:
    sub = df[(df["mode"]==mode)&(df.n_trades>=100)].sort_values("profit_factor", ascending=False)
    if len(sub):
        r = sub.iloc[0]
        print(f"  {mode:5}: PF={r.profit_factor:.2f} Sharpe={r.sharpe:.2f} E[R]={r.expectancy_R:+.3f} "
              f"n={int(r.n_trades)} tf={r.tf} k={int(r.k)} stop={r['stop']} rr={r.rr} dir={r.direction} "
              f"avg_mo={r.avg_monthly*100:.2f}% DD={r.max_dd*100:.0f}%")
    else:
        print(f"  {mode:5}: немає кандидатів n>=100")
