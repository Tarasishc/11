"""Графік: дохідність по режимах (R/міс) + лонг/шорт по режимах."""
import importlib.util, builtins
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import engine as E
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("r23","quant/23_reduce_dd.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
DATA=m.DATA
btc_d=DATA["BTC"]["close"].resample("1D").last().dropna()
ema200=E.ema(btc_d,200); slope=ema200-ema200.shift(20)
regime=pd.Series("range",index=btc_d.index)
regime[(btc_d>ema200)&(slope>0)]="bull"; regime[(btc_d<ema200)&(slope<0)]="bear"
regime=regime.shift(1); months={k:v/30.4 for k,v in regime.value_counts().items()}
rows=[]
for c,d in DATA.items():
    side,sd=m.kc_signals(d,adx_min=20)
    t=E.backtest(d,side,sd,E.Config(rr=2.0,risk_pct=0.01,bar_minutes=240)).trades
    if len(t): t=t.copy(); t["coin"]=c; rows.append(t[["entry_time","r_mult","side"]])
T=pd.concat(rows,ignore_index=True)
T["regime"]=regime.reindex(pd.DatetimeIndex(pd.to_datetime(T["entry_time"])).normalize(),method="ffill").values
regs=["bull","bear","range"]; names=["Бичка","Ведмежка","Боковик"]
fig,ax=plt.subplots(1,2,figsize=(13,5))
rpm=[T[T.regime==r]["r_mult"].sum()/max(months.get(r,1),1) for r in regs]
ax[0].bar(names,rpm,color=["tab:green","tab:red","tab:gray"])
for i,v in enumerate(rpm): ax[0].text(i,v,f"{v:.2f}",ha="center",va="bottom")
ax[0].set_title("Дохідність на одиницю часу (R/місяць)"); ax[0].set_ylabel("R/міс"); ax[0].grid(alpha=.3,axis="y")
L=[T[(T.regime==r)&(T.side=="L")]["r_mult"].sum() for r in regs]
S=[T[(T.regime==r)&(T.side=="S")]["r_mult"].sum() for r in regs]
x=np.arange(3); w=0.38
ax[1].bar(x-w/2,L,w,label="Лонг",color="tab:green"); ax[1].bar(x+w/2,S,w,label="Шорт",color="tab:red")
ax[1].set_xticks(x); ax[1].set_xticklabels(names); ax[1].set_title("Сумарний R: лонг vs шорт по режимах")
ax[1].legend(); ax[1].grid(alpha=.3,axis="y")
plt.tight_layout(); plt.savefig("quant/out/regime.png",dpi=110); print("-> quant/out/regime.png")
