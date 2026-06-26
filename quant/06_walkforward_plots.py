"""Крок 6 (продовження) — walk-forward + графіки equity.
Walk-forward: на кожному вікні train обираємо найкращі (n,atr,rr) за profit_factor,
застосовуємо до наступного вікна test. Конкатенуємо test-результати."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import lib_data as L
import lib_split as SP
import strategies as ST
import engine as E

btc15 = L.load_btc_15m()
full4 = ST.resample(btc15, "4h")
is15, oos15 = SP.split(btc15)
is4 = ST.resample(is15, "4h")
oos4 = ST.resample(oos15, "4h")

LOCK = dict(n=80, ema_trend=200, atr_n=14, atr_mult=2.0)
RR = 3.0

# ---------- 1) Транспарентно: OOS для rr=2.5 (IS-оптимум) ----------
print("===== Транспарентно: OOS для альтернативних RR (конфіг n=80 atr=2) =====")
for rr in [2.0, 2.5, 3.0]:
    side, sd = ST.h2_breakout_trend(oos4, **LOCK)
    m = E.backtest(oos4, side, sd, E.Config(rr=rr, risk_pct=0.01, bar_minutes=240)).metrics
    print(f" OOS rr={rr}: {E.fmt_metrics(m)}")

# ---------- 2) Walk-forward ----------
print("\n===== WALK-FORWARD (4h, H2) =====")
GN = [30, 50, 80]
GA = [1.5, 2.0, 3.0]
GR = [2.0, 2.5, 3.0]
n_bars_year = int(365 * 24 / 4)   # 4h барів у році
train_len = 3 * n_bars_year
test_len = 1 * n_bars_year
risk = 0.02

all_test_trades = []
wf_log = []
start = 0
while start + train_len + test_len <= len(full4):
    tr = full4.iloc[start:start + train_len]
    te = full4.iloc[start + train_len:start + train_len + test_len]
    # вибір найкращих параметрів на train за PF (min 25 угод)
    best = None
    for n in GN:
        for am in GA:
            for rr in GR:
                side, sd = ST.h2_breakout_trend(tr, n=n, ema_trend=200, atr_n=14, atr_mult=am)
                m = E.backtest(tr, side, sd, E.Config(rr=rr, risk_pct=0.01, bar_minutes=240)).metrics
                if m["n_trades"] >= 25 and (best is None or m["profit_factor"] > best[0]):
                    best = (m["profit_factor"], n, am, rr)
    if best is None:
        start += test_len; continue
    _, bn, bam, brr = best
    side, sd = ST.h2_breakout_trend(te, n=bn, ema_trend=200, atr_n=14, atr_mult=bam)
    res = E.backtest(te, side, sd, E.Config(rr=brr, risk_pct=risk, bar_minutes=240))
    m = res.metrics
    wf_log.append(dict(test_from=str(te.index[0].date()), test_to=str(te.index[-1].date()),
                       n=bn, atr=bam, rr=brr, trades=m["n_trades"],
                       ret=m["total_return"], PF=m["profit_factor"], WR=m["win_rate"]))
    if len(res.trades):
        all_test_trades.append(res.trades)
    start += test_len

wf = pd.DataFrame(wf_log)
print(wf.to_string(index=False))

# зшиваємо WF equity з усіх test-вікон (компаундинг 2% ризику)
if all_test_trades:
    eq = 10000.0
    pts_t, pts_v = [], []
    for tt in all_test_trades:
        for _, row in tt.iterrows():
            # масштабований net під поточний eq (угоди рахувались від 10k локально)
            pass
    # простіше: пере-симулюємо послідовно з єдиним капіталом
    eq = 10000.0
    eq_t, eq_v = [], []
    for i, row_block in enumerate(wf_log):
        pass

# Послідовна WF-симуляція з єдиним капіталом
eq = 10000.0
eq_curve_t, eq_curve_v = [full4.index[train_len]], [eq]
start = 0
wf_trades_concat = []
while start + train_len + test_len <= len(full4):
    tr = full4.iloc[start:start + train_len]
    te = full4.iloc[start + train_len:start + train_len + test_len]
    best = None
    for n in GN:
        for am in GA:
            for rr in GR:
                side, sd = ST.h2_breakout_trend(tr, n=n, ema_trend=200, atr_n=14, atr_mult=am)
                m = E.backtest(tr, side, sd, E.Config(rr=rr, risk_pct=0.01, bar_minutes=240)).metrics
                if m["n_trades"] >= 25 and (best is None or m["profit_factor"] > best[0]):
                    best = (m["profit_factor"], n, am, rr)
    if best is None:
        start += test_len; continue
    _, bn, bam, brr = best
    side, sd = ST.h2_breakout_trend(te, n=bn, ema_trend=200, atr_n=14, atr_mult=bam)
    res = E.backtest(te, side, sd, E.Config(rr=brr, risk_pct=risk, initial_equity=eq, bar_minutes=240))
    if len(res.trades):
        for _, r in res.trades.iterrows():
            eq_curve_t.append(r["exit_time"]); eq_curve_v.append(r["equity"])
        eq = res.trades["equity"].iloc[-1]
        wf_trades_concat.append(res.trades)
    start += test_len

wf_eq = pd.Series(eq_curve_v, index=pd.DatetimeIndex(eq_curve_t))
wf_eq = wf_eq[~wf_eq.index.duplicated(keep="last")]
if len(wf_trades_concat):
    wft = pd.concat(wf_trades_concat)
    daily = wf_eq.resample("1D").last().ffill()
    dd = (daily / daily.cummax() - 1).min()
    yrs = (wf_eq.index[-1] - wf_eq.index[0]).days / 365.25
    cagr = (wf_eq.iloc[-1] / 10000) ** (1 / yrs) - 1
    mret = daily.resample("ME").last().pct_change().dropna()
    print(f"\nWF разом (risk {risk*100:.0f}%): угод={len(wft)}  кінц.капітал={wf_eq.iloc[-1]:.0f} "
          f"(×{wf_eq.iloc[-1]/10000:.2f})  CAGR={cagr*100:.1f}%  avg_mo={mret.mean()*100:.2f}%  "
          f"maxDD={dd*100:.1f}%  WR={(wft.net>0).mean()*100:.1f}%")

# ---------- 3) Графіки equity (locked config, risk 2%) ----------
def equity_curve(d, risk):
    side, sd = ST.h2_breakout_trend(d, **LOCK)
    return E.backtest(d, side, sd, E.Config(rr=RR, risk_pct=risk, bar_minutes=240))

fig, axes = plt.subplots(2, 1, figsize=(12, 9))
for risk, c in [(0.01, "tab:blue"), (0.02, "tab:orange"), (0.03, "tab:red")]:
    r_is = equity_curve(is4, risk)
    r_oos = equity_curve(oos4, risk)
    axes[0].plot(r_is.equity.index, r_is.equity.values, color=c, label=f"risk {risk*100:.0f}%")
    axes[1].plot(r_oos.equity.index, r_oos.equity.values, color=c, label=f"risk {risk*100:.0f}%")
axes[0].axhline(10000, ls="--", c="gray", lw=0.8)
axes[0].set_title("H2 4h breakout — IN-SAMPLE equity (n=80, atr=2, RR=3)")
axes[0].set_yscale("log"); axes[0].legend(); axes[0].grid(alpha=0.3)
axes[1].axhline(10000, ls="--", c="gray", lw=0.8)
axes[1].set_title("H2 4h breakout — OUT-OF-SAMPLE equity (ті самі параметри)")
axes[1].set_yscale("log"); axes[1].legend(); axes[1].grid(alpha=0.3)
plt.tight_layout()
plt.savefig("quant/out/equity_is_oos.png", dpi=110)
print("\nГрафік -> quant/out/equity_is_oos.png")

# WF equity plot
if len(wf_eq) > 2:
    plt.figure(figsize=(12, 5))
    plt.plot(wf_eq.index, wf_eq.values, color="tab:green")
    plt.axhline(10000, ls="--", c="gray", lw=0.8)
    plt.title(f"Walk-forward equity (4h H2, переоптимізація щороку, risk {risk*100:.0f}%)")
    plt.yscale("log"); plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig("quant/out/equity_walkforward.png", dpi=110)
    print("Графік -> quant/out/equity_walkforward.png")
