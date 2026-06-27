"""СИНТЕЗ: сигнал KC (агент A, генералізується) × портфель з vol-targeting (агент B).
Незалежна реалізація моїм движком. Чесний IS/OOS + risk-sweep під 50/60% DD."""
import numpy as np
import pandas as pd
import lib_data as L
import strategies as ST
from portfolio import instrument_daily_returns

PATHS = {"BTC":"quant/data/btc_15m.csv","ETH":"quant/data/eth_4h.csv",
         "SOL":"quant/data/sol_4h.csv","MNT":"quant/data/mnt_4h.csv"}

def daily_returns_all(kind, rr):
    out = {}
    for name, p in PATHS.items():
        r, m = instrument_daily_returns(L.load_any(p), kind=kind, rr=rr)
        out[name] = r
    return pd.DataFrame(out)

def port_stats(r, label, p0=None):
    r = r.dropna()
    eq = (1+r).cumprod(); dd=(eq/eq.cummax()-1).min()
    yrs=max((r.index[-1]-r.index[0]).days/365.25,1e-9); cagr=eq.iloc[-1]**(1/yrs)-1
    sh=np.sqrt(365)*r.mean()/r.std() if r.std()>0 else 0
    mo=eq.resample("ME").last().pct_change().dropna().mean()
    print(f"  {label:30}: Sharpe={sh:.2f} CAGR={cagr*100:5.1f}% avg_mo={mo*100:5.2f}% maxDD={dd*100:5.0f}% дн={len(r)}")
    return dict(sharpe=sh,cagr=cagr,mo=mo,dd=dd)

def inv_vol_weight(R, lb=30):
    vol = R.rolling(lb).std().shift(1)
    w = (1.0/vol).replace([np.inf,-np.inf],np.nan)
    w = w.div(w.sum(axis=1), axis=0)
    return (R*w).sum(axis=1)

def risk_sweep(port, label):
    print(f"\n  Risk-sweep {label} (реальний компаундинг) — пошук стелі під 50/60% DD:")
    print(f"  {'scale×':>7}{'avg_mo%':>9}{'CAGR%':>8}{'maxDD%':>8}")
    for sc in [2,4,6,8,10,12,15,20]:
        r=(port*sc).dropna(); eq=(1+r).cumprod(); dd=(eq/eq.cummax()-1).min()
        mo=eq.resample("ME").last().pct_change().dropna().mean()
        yrs=max((r.index[-1]-r.index[0]).days/365.25,1e-9); cagr=eq.iloc[-1]**(1/yrs)-1
        tag=" <=10%/міс!" if mo>=0.10 else (" <=50-60%DD" if 0.50<=abs(dd)<=0.62 else "")
        print(f"  {sc:7d}{mo*100:9.2f}{cagr*100:8.1f}{dd*100:8.0f}{tag}")

print("СИНТЕЗ KC-сигнал × vol-targeting портфель (RR=2.0, у межах 1:2-1:3)\n")
RK = daily_returns_all("kc", 2.0)
RD = daily_returns_all("donchian", 3.0)

print("Соло Sharpe по монетах (повна історія):")
print("  KC      :", {c: round(np.sqrt(365)*RK[c].dropna().mean()/RK[c].dropna().std(),2) for c in RK})
print("  Donchian:", {c: round(np.sqrt(365)*RD[c].dropna().mean()/RD[c].dropna().std(),2) for c in RD})

# спільний 4-монетний період
R4 = RK.loc[RK.index >= max(RK[c].dropna().index[0] for c in RK)].fillna(0)
print(f"\n4-монетний спільний період: {R4.index[0].date()} → {R4.index[-1].date()} ({len(R4)} дн)")
eq_w = R4.mean(axis=1)
iv_w = inv_vol_weight(R4)
port_stats(eq_w, "KC equal-weight")
port_stats(iv_w, "KC inverse-vol")
# порівняння з Donchian-портфелем на тому ж періоді
RD4 = RD.loc[RD.index >= R4.index[0]].reindex(R4.index).fillna(0)
port_stats(RD4.mean(axis=1), "Donchian equal-weight (для порівняння)")

# IS/OOS на 4-монетному
k=int(len(R4)*0.6)
print(f"\nIS/OOS спліт (inverse-vol KC): IS {R4.index[0].date()}→{R4.index[k-1].date()} | OOS {R4.index[k].date()}→{R4.index[-1].date()}")
port_stats(iv_w.iloc[:k], "KC inv-vol IS")
port_stats(iv_w.iloc[k:], "KC inv-vol OOS")

risk_sweep(iv_w, "4-монетний KC inv-vol (повний період)")
risk_sweep(iv_w.iloc[k:], "4-монетний KC inv-vol (лише OOS)")

# 3-монетний довгий період (BTC+ETH+SOL, 2021-2026) — без MNT
print("\n" + "="*60)
R3 = RK[["BTC","ETH","SOL"]].loc[RK[["BTC","ETH","SOL"]].dropna().index[0]:].fillna(0)
R3 = R3.loc[R3.index >= max(RK[c].dropna().index[0] for c in ["BTC","ETH","SOL"])]
print(f"3-монетний довгий період: {R3.index[0].date()} → {R3.index[-1].date()} ({len(R3)} дн)")
iv3 = inv_vol_weight(R3)
port_stats(iv3, "KC inv-vol 3-coin")
risk_sweep(iv3, "3-монетний KC inv-vol (довге вікно)")
