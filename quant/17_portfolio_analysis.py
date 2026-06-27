"""Чесний портфельний аналіз: 3-монетний (довге вікно) + 4-монетний з IS/OOS-сплітом.
Параметри стратегії зафіксовані на BTC -> для решти монет це OOS-перенос."""
import numpy as np
import pandas as pd
from portfolio import instrument_daily_returns

PATHS = {"BTC":"quant/data/btc_15m.csv","ETH":"quant/data/eth_4h.csv",
         "SOL":"quant/data/sol_4h.csv","MNT":"quant/data/mnt_4h.csv"}

# денні дохідності кожного інструмента (повна історія, ризик 1%)
RET = {}
for name, p in PATHS.items():
    r, m = instrument_daily_returns(__import__("lib_data").load_any(p))
    RET[name] = r

def stats(r, label):
    r = r.dropna()
    if len(r) < 30: return None
    eq = (1+r).cumprod(); dd=(eq/eq.cummax()-1).min()
    yrs=max((r.index[-1]-r.index[0]).days/365.25,1e-9); cagr=eq.iloc[-1]**(1/yrs)-1
    sh=np.sqrt(365)*r.mean()/r.std() if r.std()>0 else 0
    mo=eq.resample("ME").last().pct_change().dropna().mean()
    print(f"  {label:26}: Sharpe={sh:.2f} CAGR={cagr*100:5.1f}% avg_mo={mo*100:5.2f}% maxDD={dd*100:5.0f}% дн={len(r)}")
    return dict(sharpe=sh,cagr=cagr,mo=mo,dd=dd)

def risk_sweep(port, label):
    print(f"\n  Risk-sweep {label} (реальний компаундинг):")
    print(f"  {'scale×':>7}{'avg_mo%':>9}{'CAGR%':>8}{'maxDD%':>8}")
    for sc in [4,6,8,10,12,15,20]:
        r=(port*sc).dropna(); eq=(1+r).cumprod(); dd=(eq/eq.cummax()-1).min()
        mo=eq.resample("ME").last().pct_change().dropna().mean()
        yrs=max((r.index[-1]-r.index[0]).days/365.25,1e-9); cagr=eq.iloc[-1]**(1/yrs)-1
        tag=" <= 10%/міс" if mo>=0.10 else (" <= 50-60%DD" if 0.50<=abs(dd)<=0.62 else "")
        print(f"  {sc:7d}{mo*100:9.2f}{cagr*100:8.1f}{dd*100:8.0f}{tag}")

print("="*70)
print("A) 3-МОНЕТНИЙ портфель BTC+ETH+SOL (довге вікно 2021-2026)")
print("="*70)
R3 = pd.DataFrame({k:RET[k] for k in ["BTC","ETH","SOL"]})
R3 = R3.loc[R3.index >= max(RET[k].dropna().index[0] for k in ["BTC","ETH","SOL"])].fillna(0)
print(f"  Період: {R3.index[0].date()} → {R3.index[-1].date()} ({len(R3)} дн)")
for k in R3.columns: stats(R3[k], k+" соло")
port3 = R3.mean(axis=1); stats(port3, "ПОРТФЕЛЬ 3-equal")
risk_sweep(port3, "3-монетного")

print("\n"+"="*70)
print("B) 4-МОНЕТНИЙ портфель, IS/OOS спліт 60/40 на спільному періоді")
print("="*70)
R4 = pd.DataFrame(RET)
R4 = R4.loc[R4.index >= max(RET[k].dropna().index[0] for k in RET)].fillna(0)
k=int(len(R4)*0.6)
print(f"  Спільний період: {R4.index[0].date()} → {R4.index[-1].date()} ({len(R4)} дн)")
print(f"  IS:  {R4.index[0].date()} → {R4.index[k-1].date()}")
print(f"  OOS: {R4.index[k].date()} → {R4.index[-1].date()}")
port4 = R4.mean(axis=1)
print(" In-sample:"); stats(port4.iloc[:k], "ПОРТФЕЛЬ IS")
print(" Out-of-sample:"); stats(port4.iloc[k:], "ПОРТФЕЛЬ OOS")
risk_sweep(port4.iloc[k:], "4-монетного OOS")

print("\n"+"="*70)
print("C) Edge-зважений (тільки монети з еджем: BTC+MNT) — для порівняння")
print("="*70)
R2 = pd.DataFrame({k:RET[k] for k in ["BTC","MNT"]})
R2 = R2.loc[R2.index >= max(RET[k].dropna().index[0] for k in ["BTC","MNT"])].fillna(0)
print(f"  Період: {R2.index[0].date()} → {R2.index[-1].date()} ({len(R2)} дн)")
port2 = R2.mean(axis=1); stats(port2, "BTC+MNT equal")
risk_sweep(port2, "BTC+MNT")
print("\n  (BTC+MNT — це hindsight-вибір переможців, НЕ чесний; лише щоб оцінити стелю.)")
