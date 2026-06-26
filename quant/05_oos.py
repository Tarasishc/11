"""Крок 6 — ЧЕСНА перевірка на OUT-OF-SAMPLE.
Конфіг зафіксований з IS-робастності: H2 (Donchian breakout + EMA200), 4h, both.
Структурні параметри: n=80, atr_mult=2.0, ema_trend=200, atr_n=14.
RR обираємо на IS, далі НЕ чіпаємо."""
import numpy as np
import pandas as pd
import lib_data as L
import lib_split as SP
import strategies as ST
import engine as E

pd.set_option("display.width", 200)

btc15 = L.load_btc_15m()
is15, oos15 = SP.split(btc15)
is4 = ST.resample(is15, "4h")
oos4 = ST.resample(oos15, "4h")
print(f"IS 4h барів={len(is4)} ({is4.index[0]}→{is4.index[-1]})")
print(f"OOS 4h барів={len(oos4)} ({oos4.index[0]}→{oos4.index[-1]})")

LOCK = dict(n=80, ema_trend=200, atr_n=14, atr_mult=2.0)

def run(d, rr, risk, bmin=240):
    side, sd = ST.h2_breakout_trend(d, **LOCK)
    cfg = E.Config(rr=rr, risk_pct=risk, bar_minutes=bmin)
    return E.backtest(d, side, sd, cfg)

# --- 1) вибір RR на IS (структуру вже зафіксовано) ---
print("\n===== Вибір RR на IS (n=80, atr=2.0, risk=1%) =====")
for rr in [2.0, 2.5, 3.0]:
    m = run(is4, rr, 0.01).metrics
    print(f" rr={rr}: {E.fmt_metrics(m)}")

RR = 3.0   # фіксуємо за результатом IS (найкращий PF/Sharpe), у межах 1:2–1:3
print(f"\n>>> Зафіксовано RR={RR}. Далі OOS без підкрутки.")

# --- 2) генералізація еджу: ВЕСЬ 4h-грід H2 на OOS ---
print("\n===== Генералізація: весь 4h-грід H2 на OOS (risk 1%), rr=3 =====")
print("  (перевіряємо, що едж не в одній клітинці, а на всьому плато)")
recs = []
for n in [30, 50, 80]:
    for am in [1.5, 2.0, 3.0]:
        side, sd = ST.h2_breakout_trend(oos4, n=n, ema_trend=200, atr_n=14, atr_mult=am)
        m = E.backtest(oos4, side, sd, E.Config(rr=3.0, risk_pct=0.01, bar_minutes=240)).metrics
        recs.append(dict(n=n, atr_mult=am, n_trades=m["n_trades"], PF=m["profit_factor"],
                         ER=m["expectancy_R"], WR=m["win_rate"], maxDD=m["max_dd"],
                         avg_mo=m["avg_monthly"]))
g = pd.DataFrame(recs)
print(g.pivot_table(index="n", columns="atr_mult", values="PF").round(3).to_string())
print(f"  OOS 4h-грід: прибуткових клітинок (PF>1): {(g.PF>1).sum()}/{len(g)}; "
      f"медіана PF={g.PF.median():.3f}")

# --- 3) детально IS vs OOS для зафіксованого конфіга ---
print("\n===== IS vs OOS для зафіксованого конфіга (n=80 atr=2.0 rr=3 risk=1%) =====")
mis = run(is4, RR, 0.01).metrics
moos = run(oos4, RR, 0.01).metrics
def line(tag, m):
    print(f" {tag}: {E.fmt_metrics(m)}")
line("IS ", mis)
line("OOS", moos)

# --- 4) sweep ризику на OOS: компроміс дохідність/просадка ---
print("\n===== OOS: компроміс ризик→дохідність/просадка (n=80 atr=2 rr=3) =====")
print(f"{'risk%':>6} {'avg_mo%':>8} {'CAGR%':>8} {'maxDD%':>8} {'final×':>8} {'Sharpe':>7} {'trades':>7}")
for risk in [0.01, 0.02, 0.03, 0.05, 0.075, 0.10]:
    m = run(oos4, RR, risk).metrics
    print(f"{risk*100:6.1f} {m['avg_monthly']*100:8.2f} {m['cagr']*100:8.1f} "
          f"{m['max_dd']*100:8.1f} {m['final_equity']/10000:8.2f} {m['sharpe']:7.2f} {m['n_trades']:7d}")

# --- 5) лонг/шорт та по роках на OOS ---
res = run(oos4, RR, 0.02)
t = res.trades.copy()
print("\n===== OOS лонг/шорт (risk 2%) =====")
print(E.fmt_metrics(res.metrics))
for sc in ["L", "S"]:
    ts = t[t.side == sc]
    if len(ts):
        wr = (ts.net>0).mean()
        print(f"  {sc}: n={len(ts):3d} WR={wr*100:.1f}% E[R]={ts.r_mult.mean():+.3f} netR={ts.r_mult.sum():+.1f}")
t["year"] = pd.to_datetime(t["entry_time"]).dt.year
print("  Сума R по роках:")
print(t.pivot_table(index="year", columns="side", values="r_mult", aggfunc="sum").round(1).to_string())
print("  К-сть угод по роках:")
print(t.pivot_table(index="year", columns="side", values="r_mult", aggfunc="count").to_string())

# зберегти угоди OOS
t.to_csv("quant/out/oos_trades.csv", index=False)
print("\nУгоди OOS збережено -> quant/out/oos_trades.csv")
