"""Графік: той самий ~10%/міс (risk 5%) — baseline DD -67% vs КОМБО DD -49%."""
import importlib.util, builtins
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

# імпорт функцій з 23 без його друку
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("r23","quant/23_reduce_dd.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
builtins.print=_p

base=m.gen_trades({})
combo=m.gen_trades({"adx_min":20})
RISK=0.05
eqB=m.sim(base,RISK).resample("1D").last().ffill()
eqC=m.sim(combo,RISK,vol_target=True,dd_throttle=0.25).resample("1D").last().ffill()
cut=combo.sort_values("entry_time").entry_time.iloc[int(len(combo)*0.6)]

def dd(s): return (s/s.cummax()-1)*100

fig,ax=plt.subplots(2,1,figsize=(13,8),gridspec_kw={"height_ratios":[2,1]})
ax[0].plot(eqB.index,eqB.values,color="tab:gray",label="BASELINE KC (risk5%): ~10%/міс, DD -67%")
ax[0].plot(eqC.index,eqC.values,color="tab:green",label="КОМБО ADX>20+vol-target+DD-throttle: ~10%/міс, DD -49%")
ax[0].axvline(cut,ls="--",c="black",lw=1,label="IS|OOS межа"); ax[0].axhline(10000,ls="--",c="gray",lw=.6)
ax[0].set_yscale("log"); ax[0].legend(fontsize=8); ax[0].grid(alpha=.3)
ax[0].set_title("Той самий ~10%/міс за меншої просадки: фільтр ADX + vol-targeting + DD-throttle\n(BTC+ETH+SOL, per-trade sim, 2017-2026, risk 5%)")
ax[1].fill_between(dd(eqB).index,dd(eqB).values,0,color="tab:gray",alpha=.45,label="baseline DD")
ax[1].plot(dd(eqC).index,dd(eqC).values,color="tab:green",lw=1.2,label="комбо DD")
ax[1].axhline(-50,ls=":",c="red",lw=.8); ax[1].axvline(cut,ls="--",c="black",lw=1)
ax[1].set_ylabel("DD %"); ax[1].legend(fontsize=8); ax[1].grid(alpha=.3)
plt.tight_layout(); plt.savefig("quant/out/dd_reduction.png",dpi=110)
print("-> quant/out/dd_reduction.png")
