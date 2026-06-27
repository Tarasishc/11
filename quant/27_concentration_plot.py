"""Візуалізація: едж розподілений, не від кількох рухів."""
import importlib.util, builtins
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import engine as E
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("r23","quant/23_reduce_dd.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
DATA=m.DATA
rows=[]
for c,d in DATA.items():
    side,sd=m.kc_signals(d,adx_min=20)
    t=E.backtest(d,side,sd,E.Config(rr=2.0,risk_pct=0.01,bar_minutes=240)).trades
    if len(t): t=t.copy(); t["coin"]=c; rows.append(t[["entry_time","r_mult","coin"]])
T=pd.concat(rows,ignore_index=True).sort_values("entry_time").reset_index(drop=True)
rm=T["r_mult"].values

fig,ax=plt.subplots(2,2,figsize=(13,8))
# 1 cum R
cum=np.cumsum(rm); x=np.arange(len(rm))
r2=np.corrcoef(x,cum)[0,1]**2
ax[0,0].plot(x,cum,color="tab:green"); ax[0,0].set_title(f"Накопичений R (рівна вага) — R²={r2:.3f} (рівна крива)")
ax[0,0].set_xlabel("№ угоди"); ax[0,0].set_ylabel("сум. R"); ax[0,0].grid(alpha=.3)
# 2 histogram r_mult
ax[0,1].hist(rm,bins=40,color="tab:blue",alpha=.8)
ax[0,1].axvline(2,color="green",ls="--",lw=1,label="+2R (стеля виграшу)")
ax[0,1].axvline(-1,color="red",ls="--",lw=1,label="-1R")
ax[0,1].set_title("Розподіл R/угода — обрізано на +2R, без аутлаєрів"); ax[0,1].legend(fontsize=8)
# 3 per year
T["yr"]=pd.to_datetime(T["entry_time"]).dt.year
yr=T.groupby("yr")["r_mult"].sum()
ax[1,0].bar(yr.index.astype(str),yr.values,color=["tab:green" if v>0 else "tab:red" for v in yr.values])
ax[1,0].set_title("Сумарний R по роках — усі 10 років у плюсі"); ax[1,0].grid(alpha=.3,axis="y")
# 4 remove top-N
order=np.argsort(rm)[::-1]; Ns=[0,1,5,10,20,50,100]; vals=[]
for N in Ns:
    r=rm.copy(); r[order[:N]]=0; vals.append(r.sum())
ax[1,1].bar([str(nn) for nn in Ns],vals,color="tab:purple")
ax[1,1].set_title("Сумарний R без топ-N виграшів — лишається плюс"); ax[1,1].set_xlabel("видалено топ-N")
ax[1,1].grid(alpha=.3,axis="y")
plt.tight_layout(); plt.savefig("quant/out/concentration.png",dpi=110)
print("-> quant/out/concentration.png")
