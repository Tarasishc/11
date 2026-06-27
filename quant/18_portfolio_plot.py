"""Ключовий графік: чому '10%/міс' — артефакт вікна.
Ліво: довге вікно 3-монети (чесна посередня крива). Право: 4-монети IS vs OOS."""
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import lib_data as L
from portfolio import instrument_daily_returns

PATHS = {"BTC":"quant/data/btc_15m.csv","ETH":"quant/data/eth_4h.csv",
         "SOL":"quant/data/sol_4h.csv","MNT":"quant/data/mnt_4h.csv"}
RET = {k: instrument_daily_returns(L.load_any(p))[0] for k,p in PATHS.items()}

fig, ax = plt.subplots(1, 2, figsize=(14,5))

# Ліво: 3-монетний довге вікно, плече під ~55% DD (scale 9)
R3 = pd.DataFrame({k:RET[k] for k in ["BTC","ETH","SOL"]})
R3 = R3.loc[R3.index>=max(RET[k].dropna().index[0] for k in ["BTC","ETH","SOL"])].fillna(0)
p3 = R3.mean(axis=1)*9
eq3 = (1+p3).cumprod()
ax[0].plot(eq3.index, eq3.values, color="tab:blue")
ax[0].set_title("3-монети (BTC+ETH+SOL), 2021-2026, плече ~55% DD\nчесний довгий період: ~1.5%/міс")
ax[0].set_yscale("log"); ax[0].axhline(1, ls="--", c="gray", lw=.8); ax[0].grid(alpha=.3)

# Право: 4-монети спільний період, scale 10, IS/OOS межа
R4 = pd.DataFrame(RET); R4 = R4.loc[R4.index>=max(RET[k].dropna().index[0] for k in RET)].fillna(0)
k = int(len(R4)*0.6)
p4 = R4.mean(axis=1)*10; eq4 = (1+p4).cumprod()
ax[1].plot(eq4.index[:k], eq4.values[:k], color="gray", label="IS 2023-2025: ~0%/міс (плоско)")
ax[1].plot(eq4.index[k:], eq4.values[k:], color="tab:red", label="OOS 2025-2026: ~10%/міс (сприятливий режим)")
ax[1].axvline(eq4.index[k], ls="--", c="black", lw=1)
ax[1].set_title("4-монети, плече ~scale10\n'10%/міс' зʼявляється ЛИШЕ на недавньому вікні")
ax[1].set_yscale("log"); ax[1].axhline(1, ls="--", c="gray", lw=.8); ax[1].legend(); ax[1].grid(alpha=.3)

plt.tight_layout(); plt.savefig("quant/out/portfolio_regime.png", dpi=110)
print("-> quant/out/portfolio_regime.png")
