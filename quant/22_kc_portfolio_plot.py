"""Графік KC shared-equity портфеля (BTC+ETH+SOL) + просадка. IS/OOS межа."""
import numpy as np, pandas as pd, heapq
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import lib_data as L, strategies as ST, engine as E
from portfolio import signals

PATHS={"BTC":"quant/data/btc_15m.csv","ETH":"quant/data/eth_4h.csv","SOL":"quant/data/sol_4h.csv"}
def coin_trades(name):
    df=L.load_any(PATHS[name]); d=ST.resample(df,"4h") if name=="BTC" else df
    side,sd=signals(d,"kc",240)
    t=E.backtest(d,side,sd,E.Config(rr=2.0,risk_pct=0.01,bar_minutes=240)).trades.copy()
    return t[["entry_time","exit_time","r_mult"]]
def sim(T,risk,init=10000.0):
    T=T.sort_values("entry_time"); eq=init; heap=[]; ct=[T.entry_time.min()]; cv=[eq]
    for _,r in T.iterrows():
        et=r["entry_time"]
        while heap and heap[0][0]<=et:
            xt,p=heapq.heappop(heap); eq+=p; ct.append(xt); cv.append(eq)
        size=risk*eq; heapq.heappush(heap,(r["exit_time"],r["r_mult"]*size))
    while heap:
        xt,p=heapq.heappop(heap); eq+=p; ct.append(xt); cv.append(eq)
    s=pd.Series(cv,index=pd.DatetimeIndex(ct)).sort_index(); return s[~s.index.duplicated(keep="last")]

T=pd.concat([coin_trades(c) for c in PATHS],ignore_index=True).sort_values("entry_time")
k=int(len(T)*0.6); cut=T.entry_time.iloc[k]

fig,ax=plt.subplots(2,1,figsize=(13,8),gridspec_kw={"height_ratios":[2,1]})
for risk,c in [(0.01,"tab:blue"),(0.03,"tab:orange"),(0.05,"tab:red")]:
    eq=sim(T,risk); d=eq.resample("1D").last().ffill()
    ax[0].plot(d.index,d.values,color=c,label=f"risk {risk*100:.0f}%/угода")
eqd=sim(T,0.03).resample("1D").last().ffill()
ax[0].axvline(cut,ls="--",c="black",lw=1,label="IS|OOS межа (60/40)")
ax[0].axhline(10000,ls="--",c="gray",lw=.8)
ax[0].set_title("KC shared-equity портфель BTC+ETH+SOL (per-trade, 2017-2026)\nOOS тримається; 10%/міс=risk5%@67%DD, ~6%/міс=risk3%@46%DD")
ax[0].set_yscale("log"); ax[0].legend(fontsize=8); ax[0].grid(alpha=.3)
# просадка risk3%
dd=(eqd/eqd.cummax()-1)*100
ax[1].fill_between(dd.index,dd.values,0,color="tab:orange",alpha=.5)
ax[1].axvline(cut,ls="--",c="black",lw=1); ax[1].axhline(-50,ls=":",c="red",lw=.8,label="-50%")
ax[1].set_title("Просадка (risk 3%)"); ax[1].set_ylabel("DD %"); ax[1].legend(fontsize=8); ax[1].grid(alpha=.3)
plt.tight_layout(); plt.savefig("quant/out/kc_portfolio_equity.png",dpi=110)
print("-> quant/out/kc_portfolio_equity.png")
