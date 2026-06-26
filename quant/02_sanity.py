"""Перевірка движка + показ точки розділення IS/OOS на простій стратегії."""
import numpy as np
import lib_data as L
import lib_split as SP
import engine as E

df = L.load_btc_15m()
info = SP.describe(df)
print("=== Розділення IS/OOS (60/40) ===")
print(f"split bar : {info['split_bar']:,}")
print(f"IN-SAMPLE : {info['is_period'][0]} → {info['is_period'][1]}  ({info['is_period'][2]:,} барів)")
print(f"OUT-SAMPLE: {info['oos_period'][0]} → {info['oos_period'][1]}  ({info['oos_period'][2]:,} барів)")
print()

is_df, oos_df = SP.split(df)

# проста Donchian breakout-болванка для перевірки движка
def donchian_signals(d, n=50, atr_n=14, atr_mult=2.0):
    dh = E.donchian_high(d, n).shift(1)   # рівень по барах ДО поточного
    dl = E.donchian_low(d, n).shift(1)
    a = E.atr(d, atr_n)
    side = np.zeros(len(d))
    long_bo = d["close"] > dh
    short_bo = d["close"] < dl
    side[long_bo.to_numpy()] = 1
    side[short_bo.to_numpy()] = -1
    stop_dist = (a * atr_mult).to_numpy()
    return side, stop_dist

side, sd = donchian_signals(is_df)
cfg = E.Config(rr=2.0, risk_pct=0.01)
res = E.backtest(is_df, side, sd, cfg)
print("=== Donchian-50 breakout (IS, болванка для перевірки движка) ===")
print(E.fmt_metrics(res.metrics))
print(f"sample fills (перші 5 угод):")
cols = ["entry_time", "side", "entry", "exit", "stop", "target", "bars_held", "reason", "net", "r_mult"]
print(res.trades[cols].head().to_string(index=False))
print()
# розподіл причин виходу
print("Причини виходу:")
print(res.trades["reason"].value_counts().to_string())
print()
# перевірка: середній r_mult на стопі має бути ~ -1, на тейку ~ +rr
print("Середній r_mult за причиною:")
print(res.trades.groupby("reason")["r_mult"].mean().to_string())
