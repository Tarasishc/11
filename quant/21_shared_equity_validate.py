"""ВИРІШАЛЬНА перевірка: строгий per-trade shared-equity портфель (не денне масштабування).
Кожна угода ризикує risk_pct від ПОТОЧНОГО реалізованого капіталу; позиції можуть
накладатися (concurrency -> реальна експозиція). Реальна max DD. KC-сигнал, RR2.0.

Спершу sanity: одно-монетний sim має збігатися з engine.backtest."""
import numpy as np
import pandas as pd
import lib_data as L
import strategies as ST
import engine as E
from portfolio import signals  # має kind="kc"

PATHS = {"BTC":"quant/data/btc_15m.csv","ETH":"quant/data/eth_4h.csv",
         "SOL":"quant/data/sol_4h.csv","MNT":"quant/data/mnt_4h.csv"}

def coin_trades(name, rr=2.0):
    df = L.load_any(PATHS[name])
    d, bmin = (ST.resample(df,"4h"),240) if name=="BTC" else (df,240)
    side, sd = signals(d, kind="kc", bmin=bmin)
    res = E.backtest(d, side, sd, E.Config(rr=rr, risk_pct=0.01, bar_minutes=bmin))
    t = res.trades.copy()
    if len(t)==0: return t
    t["coin"]=name
    return t[["entry_time","exit_time","r_mult","coin","side"]]

def shared_equity_sim(trades, risk_pct, init=10000.0):
    """Угоди (з усіх монет) -> єдиний капітал. Розмір = risk_pct*realized_equity на вході.
    Реалізація PnL на exit_time. Concurrency дозволено."""
    t = trades.sort_values("entry_time").reset_index(drop=True)
    equity = init
    pending = []  # (exit_time, pnl)
    curve_t=[t["entry_time"].iloc[0]]; curve_v=[equity]
    # для коректного realized-equity на вході: реалізуємо всі exits <= поточний entry
    import heapq
    heap=[]  # (exit_time, pnl)
    for _,row in t.iterrows():
        et=row["entry_time"]
        while heap and heap[0][0] <= et:
            xt,pnl=heapq.heappop(heap); equity+=pnl
            curve_t.append(xt); curve_v.append(equity)
        size = risk_pct*equity
        pnl = row["r_mult"]*size
        heapq.heappush(heap,(row["exit_time"],pnl))
    while heap:
        xt,pnl=heapq.heappop(heap); equity+=pnl
        curve_t.append(xt); curve_v.append(equity)
    eq=pd.Series(curve_v,index=pd.DatetimeIndex(curve_t)).sort_index()
    eq=eq[~eq.index.duplicated(keep="last")]
    return eq

def metrics(eq):
    daily=eq.resample("1D").last().ffill()
    dd=(daily/daily.cummax()-1).min()
    yrs=max((daily.index[-1]-daily.index[0]).days/365.25,1e-9)
    cagr=(daily.iloc[-1]/daily.iloc[0])**(1/yrs)-1
    mo=daily.resample("ME").last().pct_change().dropna()
    return mo.mean(), cagr, dd, daily.iloc[-1]/daily.iloc[0]

# ---- SANITY: одно-монетний sim vs engine ----
print("SANITY (BTC лише, risk 2%): shared-sim vs engine.backtest")
bt=coin_trades("BTC")
eq=shared_equity_sim(bt,0.02)
mo,cagr,dd,fin=metrics(eq)
df=ST.resample(L.load_any(PATHS["BTC"]),"4h"); side,sd=signals(df,"kc",240)
m=E.backtest(df,side,sd,E.Config(rr=2.0,risk_pct=0.02,bar_minutes=240)).metrics
print(f"  sim:    final×={fin:.2f} maxDD={dd*100:.1f}% avg_mo={mo*100:.2f}%")
print(f"  engine: final×={m['final_equity']/10000:.2f} maxDD={m['max_dd']*100:.1f}% avg_mo={m['avg_monthly']*100:.2f}%")
print(f"  (мають бути близькі -> sim валідний)\n")

# ---- 3-монетний (BTC+ETH+SOL, 2021-2026) ----
def build(coins):
    return pd.concat([coin_trades(c) for c in coins], ignore_index=True)

for label, coins in [("3-монети BTC+ETH+SOL", ["BTC","ETH","SOL"]),
                     ("4-монети +MNT", ["BTC","ETH","SOL","MNT"])]:
    T=build(coins)
    T=T.sort_values("entry_time")
    start=T["entry_time"].min()
    print(f"===== {label}: {len(T)} угод, {start.date()} → {T['exit_time'].max().date()} =====")
    print(f"  {'risk%':>6}{'avg_mo%':>9}{'CAGR%':>8}{'maxDD%':>8}{'final×':>8}")
    for risk in [0.01,0.02,0.03,0.05,0.07,0.10,0.13]:
        eq=shared_equity_sim(T,risk); mo,cagr,dd,fin=metrics(eq)
        tag=" <=10%/міс" if mo>=0.10 else (" <=50-60%DD" if 0.50<=abs(dd)<=0.62 else "")
        print(f"  {risk*100:6.1f}{mo*100:9.2f}{cagr*100:8.1f}{dd*100:8.0f}{fin:8.2f}{tag}")
    # IS/OOS
    Ts=T.sort_values("entry_time"); k=int(len(Ts)*0.6)
    cut=Ts["entry_time"].iloc[k]
    for tag,sub in [("IS",Ts[Ts.entry_time<cut]),("OOS",Ts[Ts.entry_time>=cut])]:
        eq=shared_equity_sim(sub,0.03); mo,cagr,dd,fin=metrics(eq)
        print(f"   [{tag} risk3%] avg_mo={mo*100:.2f}% CAGR={cagr*100:.1f}% maxDD={dd*100:.0f}% final×={fin:.2f}")
    print()
