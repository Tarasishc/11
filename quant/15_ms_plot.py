"""Графіки: робастний BOS-continuation (IS vs OOS) + стіна 'дохідність vs просадка'."""
import numpy as np
import pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import lib_data as L
import lib_split as SP
import strategies as ST
import engine as E
import market_structure as MS

btc15 = L.load_btc_15m()
is15, oos15 = SP.split(btc15)
is4 = ST.resample(is15, "4h"); oos4 = ST.resample(oos15, "4h")

def run(d, risk):
    side, sd = MS.ms_signals(d, k=3, mode="cont", stop_mode="atr", atr_mult=2.0, rr=2.0)
    return E.backtest(d, side, sd, E.Config(rr=2.0, risk_pct=risk, bar_minutes=240))

fig, ax = plt.subplots(1, 2, figsize=(14, 5))
for risk, c in [(0.01,"tab:blue"),(0.02,"tab:orange"),(0.03,"tab:red")]:
    ri, ro = run(is4, risk), run(oos4, risk)
    ax[0].plot(ri.equity.index, ri.equity.values, color=c, label=f"risk {risk*100:.0f}%")
    ax[1].plot(ro.equity.index, ro.equity.values, color=c, label=f"risk {risk*100:.0f}%")
ax[0].set_title("BOS-continuation (k3,atr,rr2) — IN-SAMPLE"); ax[0].set_yscale("log")
ax[1].set_title("BOS-continuation — OUT-OF-SAMPLE (ті самі параметри)"); ax[1].set_yscale("log")
for a in ax: a.axhline(10000, ls="--", c="gray", lw=.8); a.legend(); a.grid(alpha=.3)
plt.tight_layout(); plt.savefig("quant/out/ms_bos_is_oos.png", dpi=110)
print("-> quant/out/ms_bos_is_oos.png")

# стіна дохідність vs просадка (з risk-sweep стека, дані з кроку 14)
risks = [2,5,8,10,15]; avg_mo = [0.79,1.87,2.82,3.38,4.55]; dd = [23.8,52.1,71.8,81.0,94.0]
fig2, ax2 = plt.subplots(figsize=(8,5))
ax2.plot(dd, avg_mo, "o-", color="tab:red")
for r,x,y in zip(risks,dd,avg_mo): ax2.annotate(f"{r}%", (x,y), textcoords="offset points", xytext=(6,-2))
ax2.axhline(10, ls="--", c="green", label="ціль 10%/міс")
ax2.axvline(50, ls="--", c="purple", label="ліміт 50% DD")
ax2.set_xlabel("Max Drawdown, %"); ax2.set_ylabel("Сер. дохідність/міс, %")
ax2.set_title("Стіна: щоб дійти до 10%/міс, DD має бути далеко за 100%")
ax2.legend(); ax2.grid(alpha=.3)
plt.tight_layout(); plt.savefig("quant/out/return_dd_wall.png", dpi=110)
print("-> quant/out/return_dd_wall.png")
