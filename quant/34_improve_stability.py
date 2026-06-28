"""Покращення СТАБІЛЬНОСТІ (не гонитва за прибутком):
A) мульти-таймфрейм ансамбль (4h+8h+1d) — більше незалежних угод/місяць
B) portfolio vol-targeting (сталий ризик портфеля)
C) кореляційне зменшення розміру (менше, коли всі позиції в один бік)
Метрики: %плюс-місяців, Sharpe, MAR, DD; чесно IS/OOS. Self-contained."""
import numpy as np, pandas as pd, heapq
import lib_data as L, strategies as ST, engine as E

BASE={"BTC":ST.resample(L.load_btc_15m(),"4h"),
      "ETH":L.load_any("quant/data/eth_4h.csv"),
      "SOL":L.load_any("quant/data/sol_4h.csv")}

def adx14(d):
    h,l=d["high"],d["low"];up=h.diff();dn=-l.diff()
    pdm=((up>dn)&(up>0))*up;mdm=((dn>up)&(dn>0))*dn;tr=E.true_range(d);a=tr.ewm(alpha=1/14,adjust=False).mean()
    pdi=100*pdm.ewm(alpha=1/14,adjust=False).mean()/a;mdi=100*mdm.ewm(alpha=1/14,adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).ewm(alpha=1/14,adjust=False).mean()

def gen(coins, tfs, rr=2.0, adx_min=20):
    rows=[]
    bmin={"4h":240,"8h":480,"12h":720,"1d":1440}
    for c in coins:
        for tf in tfs:
            d=BASE[c] if tf=="4h" else ST.resample(BASE[c],tf)
            if len(d)<260: continue
            cl=d["close"]; mid=E.ema(cl,20); band=2*E.atr(d,10)
            side=np.zeros(len(d))
            side[((cl>mid+band)&(cl>E.ema(cl,200))).to_numpy()]=1
            side[((cl<mid-band)&(cl<E.ema(cl,200))).to_numpy()]=-1
            side[adx14(d).to_numpy()<adx_min]=0
            t=E.backtest(d,side,(E.atr(d,14)*2).to_numpy(),E.Config(rr=rr,risk_pct=0.01,bar_minutes=bmin[tf])).trades
            if len(t):
                t=t.copy(); t["coin"]=c; t["tf"]=tf
                v=cl.pct_change().rolling(30).std().shift(1); v=(v/v.median())
                vs=v.reindex(pd.to_datetime(t["entry_time"])).clip(0.3,3).values
                t["volscale"]=(1.0/vs).clip(0.3,2.5)
                t["sidi"]=np.where(t["side"]=="L",1,-1)
                rows.append(t[["entry_time","exit_time","r_mult","coin","tf","volscale","sidi"]])
    return pd.concat(rows,ignore_index=True).sort_values("entry_time").reset_index(drop=True)

def sim(T,risk,vol_target=True,dd_throttle=0.25,throttle_f=0.5,corr_size=False,init=10000.0):
    T=T.sort_values("entry_time").reset_index(drop=True); eq=init; peak=init; heap=[]
    ct=[T.entry_time.min()]; cv=[eq]; open_dir=[]  # для corr_size: напрями відкритих
    for _,r in T.iterrows():
        et=r["entry_time"]
        while heap and heap[0][0]<=et:
            xt,p,sgn=heapq.heappop(heap); eq+=p; peak=max(peak,eq); ct.append(xt);cv.append(eq)
            open_dir.remove(sgn)
        size=risk*eq
        if vol_target: size*=r["volscale"]
        if dd_throttle and eq<peak*(1-dd_throttle): size*=throttle_f
        if corr_size and open_dir:
            same=sum(1 for s in open_dir if s==r["sidi"])
            size/= (1+same)**0.5    # менше, коли вже багато в той самий бік
        heapq.heappush(heap,(r["exit_time"], r["r_mult"]*size, r["sidi"])); open_dir.append(r["sidi"])
    while heap:
        xt,p,sgn=heapq.heappop(heap); eq+=p; ct.append(xt);cv.append(eq)
    s=pd.Series(cv,index=pd.DatetimeIndex(ct)).sort_index(); return s[~s.index.duplicated(keep="last")]

def stats(s):
    d=s.resample("1D").last().ffill(); dd=(d/d.cummax()-1).min()*100
    mr=d.resample("ME").last().pct_change().dropna()
    sh=np.sqrt(365)*d.pct_change().dropna().mean()/d.pct_change().dropna().std()
    return (mr>0).mean()*100, mr.mean()*100, dd, sh

def ev(T,label,**kw):
    s=stats(sim(T,0.02,**kw)); pos,mo,dd,sh=s; mar=mo/abs(dd)*30 if dd else 0
    k=int(len(T)*0.6); cut=T.entry_time.iloc[k]
    poso=stats(sim(T[T.entry_time>=cut],0.02,**kw))[0]
    wk=len(T)/((pd.to_datetime(T.entry_time.max())-pd.to_datetime(T.entry_time.min())).days/7)
    print(f"  {label:34} n={len(T):4d}({wk:.1f}/тиж) | плюс.міс={pos:.0f}% Sharpe={sh:.2f} avg_mo={mo:.2f}% DD={dd:.0f}% | OOS плюс.міс={poso:.0f}%")

print("БАЗА vs ТЮНІНГ ОВЕРДРАЙВІВ (risk 2%, 4h 3 монети):\n")
b4=gen(["BTC","ETH","SOL"],["4h"])
ev(b4,"БАЗА (vol-target + throttle25→0.5)")
print("\nКореляційне зменшення розміру:")
ev(b4,"+ corr-size",corr_size=True)
print("\nВаріації DD-throttle (різати ризик глибше/раніше в просадці):")
ev(b4,"throttle 0.30→0.5 (м'якше)",dd_throttle=0.30,throttle_f=0.5)
ev(b4,"throttle 0.20→0.4",dd_throttle=0.20,throttle_f=0.4)
ev(b4,"throttle 0.15→0.3 (агресивно)",dd_throttle=0.15,throttle_f=0.3)
print("\nКомбо найкращого:")
ev(b4,"corr-size + throttle 0.20→0.4",corr_size=True,dd_throttle=0.20,throttle_f=0.4)
print("\n(MTF-ансамбль 4h+8h перевірено окремо — погіршив: 28% міс vs 63%. Відкинуто.)")
