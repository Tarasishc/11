"""Аналіз робастності H2 (Donchian breakout + EMA200) — плато чи пік?
Та розбивка лонг/шорт. Усе на IN-SAMPLE."""
import numpy as np
import pandas as pd
import lib_data as L
import lib_split as SP
import strategies as ST
import engine as E

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)

df = pd.read_csv("quant/out/is_grid.csv")
h2 = df[df.strat == "H2_breakout_trend"].copy()

print("===== H2 4h: матриця profit_factor за (n, atr_mult), rr=2, both =====")
sub = h2[(h2.tf == "4h") & (h2.rr == 2.0) & (h2.direction == "both")]
print(sub.pivot_table(index="n", columns="atr_mult", values="profit_factor").round(3).to_string())
print("\n===== H2 4h: avg_monthly (риз.1%) за (n, atr_mult), rr=2 =====")
print((sub.pivot_table(index="n", columns="atr_mult", values="avg_monthly")*100).round(2).to_string())
print("\n===== H2 4h: n_trades за (n, atr_mult), rr=2 =====")
print(sub.pivot_table(index="n", columns="atr_mult", values="n_trades").round(0).to_string())

print("\n===== H2 4h rr=3, both: PF та maxDD =====")
sub3 = h2[(h2.tf == "4h") & (h2.rr == 3.0) & (h2.direction == "both")]
print(sub3.pivot_table(index="n", columns="atr_mult", values="profit_factor").round(3).to_string())

print("\n===== H2 порівняння таймфреймів (rr=2, both, усі n/atr) — медіана PF =====")
print(h2[(h2.rr==2.0)&(h2.direction=="both")].groupby("tf")["profit_factor"].agg(["median","max","count"]).round(3).to_string())

# --- Розбивка лонг/шорт для базового кандидата H2 4h n=50 atr=2 rr=2 ---
print("\n===== Лонг/шорт розбивка: H2 4h n=50 atr_mult=2.0 rr=2 (IS) =====")
btc15 = L.load_btc_15m()
is15, _ = SP.split(btc15)
d4 = ST.resample(is15, "4h")
side, sd = ST.h2_breakout_trend(d4, n=50, ema_trend=200, atr_n=14, atr_mult=2.0)
cfg = E.Config(rr=2.0, risk_pct=0.01, bar_minutes=240)
res = E.backtest(d4, side, sd, cfg)
t = res.trades
print(E.fmt_metrics(res.metrics))
for sidecode in ["L", "S"]:
    ts = t[t.side == sidecode]
    if len(ts):
        wr = (ts.net > 0).mean()
        pf = ts[ts.net>0].net.sum() / max(-ts[ts.net<=0].net.sum(), 1e-9)
        print(f"  {sidecode}: n={len(ts):3d}  WR={wr*100:.1f}%  E[R]={ts.r_mult.mean():+.3f}  "
              f"PF={pf:.2f}  netR_sum={ts.r_mult.sum():+.1f}")

# розподіл угод по роках і напрямку
t = t.copy()
t["year"] = pd.to_datetime(t["entry_time"]).dt.year
print("\n  Угоди та сумарний R по роках (L/S):")
piv = t.pivot_table(index="year", columns="side", values="r_mult", aggfunc="sum").round(1)
cnt = t.pivot_table(index="year", columns="side", values="r_mult", aggfunc="count")
print("  Сума R:"); print(piv.to_string())
print("  К-сть угод:"); print(cnt.to_string())
