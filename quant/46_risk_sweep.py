"""Скільки прибутку дає БІЛЬША просадка? Розгін ризику на реальній конфігурації
(3 монети, одна позиція на монету, OOS). Показуємо, де компаундинг ламається:
більший DD перестає давати більше грошей (перебивання ставки за Келлі)."""
import importlib.util, builtins, numpy as np, pandas as pd
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("c44","quant/44_one_per_coin.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
BASE=m.BASE; one_per_coin=m.one_per_coin; naive=m.naive

rows=[]
for c,d in BASE.items():
    cut=naive(d.index[int(len(d)*0.6)])
    rows+=[(ts,r) for ts,r in one_per_coin(d) if ts>=cut]
T=pd.DataFrame(rows,columns=["t","r"]).sort_values("t")
r=T["r"].values; idx=pd.DatetimeIndex(T["t"]); yrs=(T["t"].max()-T["t"].min()).days/365.25
print(f"OOS, 3 монети одна-на-монету, n={len(r)}, {T['t'].min().date()}..{T['t'].max().date()} ({yrs:.1f}р)\n")
print(f"{'risk':>5} | {'медіана/міс':>11} {'сер/міс':>8} | {'DD реал':>7} {'~MTM':>6} | {'фінал ×':>9} {'CAGR':>6}")
print("-"*64)
for risk in [0.005,0.0075,0.01,0.0125,0.015,0.02,0.025,0.03,0.04,0.05,0.06]:
    eq=np.cumprod(1+risk*r)
    me=pd.Series(eq,index=idx).resample("ME").last().dropna()
    mret=me.pct_change().dropna(); mret=pd.concat([pd.Series([me.iloc[0]-1],index=[me.index[0]]),mret])
    dd=((eq/np.maximum.accumulate(eq))-1).min()*100
    cagr=(eq[-1]**(1/yrs)-1)*100
    flag=""
    print(f"{risk*100:4.2f}% | {mret.median()*100:10.2f}% {mret.mean()*100:7.2f}% | {dd:6.0f}% {dd-10:5.0f}% | {eq[-1]:8.1f} {cagr:5.0f}%")
print("\nDD реал = реалізована; ~MTM = реальна внутрішньопозиційна (≈ +10пп гірша).")
print("Дивись колонку 'фінал ×': де вона перестає рости (або падає) — там більший")
print("ризик дає БІЛЬШУ просадку, але вже НЕ більше грошей. Це і є стеля.")
