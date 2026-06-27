"""НЕЗАЛЕЖНА валідація знахідки агента A (Keltner breakout + EMA200) МОЇМ движком.
Перевіряємо: чи справді позитивний IS І OOS на всіх 4 монетах. RR 1.5 і 2.0."""
import numpy as np
import pandas as pd
import lib_data as L
import lib_split as SP
import strategies as ST
import engine as E

def kc_signals(d, ema_mid=20, atr_band=10, mult=2.0, ema_trend=200, atr_stop=14, stop_mult=2.0):
    c = d["close"]
    mid = E.ema(c, ema_mid)
    band = mult * E.atr(d, atr_band)
    upper = mid + band; lower = mid - band
    trend = E.ema(c, ema_trend)
    long = (c > upper) & (c > trend)
    short = (c < lower) & (c < trend)
    side = np.zeros(len(d))
    side[long.to_numpy()] = 1; side[short.to_numpy()] = -1
    sd = (E.atr(d, atr_stop) * stop_mult).to_numpy()
    return side, sd

def get_4h(name):
    if name == "BTC":
        return ST.resample(L.load_btc_15m(), "4h")
    return L.load_any(f"quant/data/{name.lower()}_4h.csv")

print("НЕЗАЛЕЖНА валідація KC-breakout (мій движок, ризик 1%, 4h)\n")
for rr in [1.5, 2.0]:
    print(f"===== RR = {rr} =====")
    print(f"{'coin':5}{'split':5}{'n':>5}{'avg_mo%':>9}{'maxDD%':>8}{'Sharpe':>8}{'PF':>6}{'WR%':>6}")
    for coin in ["BTC", "ETH", "SOL", "MNT"]:
        d = get_4h(coin)
        is_d, oos_d = SP.split(d, 0.6)
        for tag, dd in [("IS", is_d), ("OOS", oos_d)]:
            side, sd = kc_signals(dd)
            m = E.backtest(dd, side, sd, E.Config(rr=rr, risk_pct=0.01, bar_minutes=240)).metrics
            print(f"{coin:5}{tag:5}{m['n_trades']:>5}{m['avg_monthly']*100:>9.2f}"
                  f"{m['max_dd']*100:>8.1f}{m['sharpe']:>8.2f}{m['profit_factor']:>6.2f}{m['win_rate']*100:>6.1f}")
    print()

# Підсумок: на скількох монетах позитивний OOS Sharpe (RR2.0 — в межах вимоги 1:2-1:3)
print("===== Перевірка генералізації (RR2.0): OOS Sharpe по монетах =====")
ok = 0
for coin in ["BTC", "ETH", "SOL", "MNT"]:
    d = get_4h(coin); _, oos_d = SP.split(d, 0.6)
    side, sd = kc_signals(oos_d)
    m = E.backtest(oos_d, side, sd, E.Config(rr=2.0, risk_pct=0.01, bar_minutes=240)).metrics
    flag = "✓" if m["sharpe"] > 0.3 and m["expectancy_R"] > 0 else "✗"
    if flag == "✓": ok += 1
    print(f"  {coin}: OOS Sharpe={m['sharpe']:.2f} E[R]={m['expectancy_R']:+.3f} PF={m['profit_factor']:.2f} {flag}")
print(f"\nГенералізує на {ok}/4 монетах (поріг Sharpe>0.3 & E[R]>0).")
