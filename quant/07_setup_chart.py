"""Ілюстрація сетапу H2 на реальному прикладі (шорт, лютий 2026)."""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import lib_data as L
import strategies as ST
import engine as E

btc15 = L.load_btc_15m()
d = ST.resample(btc15, "4h")
dh = E.donchian_high(d, 80).shift(1)
dl = E.donchian_low(d, 80).shift(1)
et = E.ema(d["close"], 200)
a = E.atr(d, 14)

# вікно навколо шорта 2026-02-05
lo = pd.Timestamp("2026-01-10", tz="UTC")
hi = pd.Timestamp("2026-02-20", tz="UTC")
w = d.loc[lo:hi]

entry_t = pd.Timestamp("2026-02-05 04:00:00", tz="UTC")
entry = 71201.88; stop = 74910.05; target = 60077.39

fig, ax = plt.subplots(figsize=(13, 7))
# свічки
for t, row in w.iterrows():
    c = "tab:green" if row["close"] >= row["open"] else "tab:red"
    ax.plot([t, t], [row["low"], row["high"]], color=c, lw=0.8)
    ax.add_patch(Rectangle((t - pd.Timedelta(hours=1.4), min(row["open"], row["close"])),
                           pd.Timedelta(hours=2.8), abs(row["close"] - row["open"]) + 1,
                           color=c, alpha=0.8))
ax.plot(w.index, et.loc[lo:hi], color="black", lw=1.4, label="EMA200 (тренд-фільтр)")
ax.plot(w.index, dl.loc[lo:hi], color="tab:blue", lw=1.0, ls="--", label="Donchian-80 low (рівень пробою вниз)")
ax.plot(w.index, dh.loc[lo:hi], color="tab:gray", lw=0.8, ls=":", label="Donchian-80 high")

ax.axhline(entry, color="purple", lw=1.2, label=f"Вхід (шорт) {entry:.0f}")
ax.axhline(stop, color="red", lw=1.2, ls="--", label=f"Стоп {stop:.0f} (+2·ATR)")
ax.axhline(target, color="green", lw=1.2, ls="--", label=f"Тейк {target:.0f} (RR=3)")
ax.axvline(entry_t, color="purple", lw=0.8, alpha=0.5)
ax.annotate("Пробій Donchian-low\nпід EMA200 → SHORT",
            xy=(entry_t, entry), xytext=(entry_t + pd.Timedelta(days=3), entry + 4000),
            arrowprops=dict(arrowstyle="->", color="purple"), color="purple", fontsize=10)

ax.set_title("Приклад сетапу H2: шорт BTC 4h, 05.02.2026 (досяг тейка, +2.98R)")
ax.legend(loc="upper right", fontsize=8)
ax.grid(alpha=0.3)
ax.set_ylabel("BTC, $")
plt.tight_layout()
plt.savefig("quant/out/setup_example.png", dpi=110)
print("Збережено -> quant/out/setup_example.png")
