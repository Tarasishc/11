"""Чи стратегія плюсова через РОЗПОДІЛЕНИЙ едж, а не пару великих рухів?
Аналіз концентрації P&L: по угодах (R-простір), монетах, місяцях/роках.
Конфіг: KC + ADX>20, BTC+ETH+SOL (combo з §14)."""
import importlib.util, builtins
import numpy as np, pandas as pd
import lib_data as L, engine as E
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("r23","quant/23_reduce_dd.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
DATA=m.DATA

rows=[]
for c,d in DATA.items():
    side,sd=m.kc_signals(d,adx_min=20)
    t=E.backtest(d,side,sd,E.Config(rr=2.0,risk_pct=0.01,bar_minutes=240)).trades
    if len(t): t=t.copy(); t["coin"]=c; rows.append(t[["entry_time","r_mult","coin","reason","side"]])
T=pd.concat(rows,ignore_index=True).sort_values("entry_time").reset_index(drop=True)
rm=T["r_mult"].values; n=len(rm); totR=rm.sum()

print("="*64); print("РОЗПОДІЛ ВИГРАШІВ (R-простір, рівна вага — чистий едж)"); print("="*64)
print(f"  Угод: {n} | сумарний R: {totR:.1f} | expectancy: {rm.mean():.3f}R/угода")
print(f"  Win rate: {(rm>0).mean()*100:.1f}% | сер.виграш: {rm[rm>0].mean():.2f}R | сер.програш: {rm[rm<=0].mean():.2f}R")
print(f"  Максимальний виграш: {rm.max():.2f}R | угод >3R (аутлаєри): {(rm>3).sum()} "
      f"({(rm>3).mean()*100:.1f}%)")
print("  => виграші обрізані ~+2R (RR=2): гігантських угод немає за конструкцією.")

print("\n"+"="*64); print("ВИДАЛЕННЯ ТОП-N ВИГРАШІВ — чи лишається плюс?"); print("="*64)
order=np.argsort(rm)[::-1]
for N in [1,5,10,20,50]:
    rem=rm.copy(); rem[order[:N]]=0
    print(f"  без топ-{N:2d} виграшів: сумарний R={rem.sum():6.1f} (з {totR:.1f}), "
          f"expectancy={rem.mean():+.3f}R  {'ПЛЮС' if rem.sum()>0 else 'МІНУС'}")

print("\n"+"="*64); print("КОНЦЕНТРАЦІЯ: яку частку прибутку дають топ-угоди"); print("="*64)
pos=np.sort(rm[rm>0])[::-1]; gp=pos.sum()
for pct in [0.01,0.05,0.10,0.20]:
    k=max(1,int(n*pct)); share=np.sort(rm)[::-1][:k].sum()/totR*100
    print(f"  топ-{pct*100:.0f}% угод ({k}) дають {share:.0f}% сумарного R")

print("\n"+"="*64); print("ПО МОНЕТАХ — чи одна монета все тягне?"); print("="*64)
for c,g in T.groupby("coin"):
    r=g["r_mult"].values
    print(f"  {c}: n={len(r):3d} сумаR={r.sum():6.1f} exp={r.mean():+.3f} WR={(r>0).mean()*100:.0f}%")

print("\n"+"="*64); print("ПО МІСЯЦЯХ — чи прибуток розподілений у часі"); print("="*64)
T["ym"]=pd.to_datetime(T["entry_time"]).dt.to_period("M")
mon=T.groupby("ym")["r_mult"].sum()
print(f"  Місяців: {len(mon)} | прибуткових: {(mon>0).mean()*100:.0f}% | "
      f"найкращий: {mon.max():.1f}R | найгірший: {mon.min():.1f}R")
print(f"  Найкращий місяць = {mon.max()/totR*100:.0f}% сумарного R")
mo_sorted=mon.sort_values(ascending=False)
for k in [1,3,6]:
    print(f"  без топ-{k} місяців: сумарний R={mon.sum()-mo_sorted.head(k).sum():.1f} (з {totR:.1f})  "
          f"{'ПЛЮС' if mon.sum()-mo_sorted.head(k).sum()>0 else 'МІНУС'}")

print("\n"+"="*64); print("ЛІНІЙНІСТЬ кривої (R² накопиченого R vs № угоди)"); print("="*64)
cum=np.cumsum(rm); x=np.arange(n)
r2=np.corrcoef(x,cum)[0,1]**2
print(f"  R²={r2:.3f} (1.0=ідеально рівна крива; <0.9 = є грудкуватість)")

print("\n"+"="*64); print("ПО РОКАХ (сумарний R)"); print("="*64)
T["yr"]=pd.to_datetime(T["entry_time"]).dt.year
yr=T.groupby("yr")["r_mult"].agg(["count","sum"]);
print(yr.to_string())
print(f"  прибуткових років: {(yr['sum']>0).mean()*100:.0f}% з {len(yr)}")
