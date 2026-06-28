"""Максимальний прибуток при БЕЗПЕЧНІЙ просадці.
Обмеження безпеки: реальна (MTM) DD <= ~45% І пік валового плеча <= ~6x (вижити в день FTX).
Важіль: ризик/угоду + ЖОРСТКИЙ ліміт плеча (cap на сумарну експозицію) + corr-size.
Конфіг: KC+ADX>20, BTC+ETH+SOL, фікс-RR2."""
import numpy as np, pandas as pd, heapq
import lib_data as L, strategies as ST, engine as E

BASE={"BTC":ST.resample(L.load_btc_15m(),"4h"),
      "ETH":L.load_any("quant/data/eth_4h.csv"),
      "SOL":L.load_any("quant/data/sol_4h.csv")}
CL_D={c:BASE[c]["close"].resample("1D").last() for c in BASE}
FEE,SLIP=0.0005,0.0003

def adx14(d):
    h,l=d["high"],d["low"];up=h.diff();dn=-l.diff()
    pdm=((up>dn)&(up>0))*up;mdm=((dn>up)&(dn>0))*dn;tr=E.true_range(d);a=tr.ewm(alpha=1/14,adjust=False).mean()
    pdi=100*pdm.ewm(alpha=1/14,adjust=False).mean()/a;mdi=100*mdm.ewm(alpha=1/14,adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).ewm(alpha=1/14,adjust=False).mean()

def gen():
    rows=[]
    for c,d in BASE.items():
        cl=d["close"]; mid=E.ema(cl,20); band=2*E.atr(d,10)
        side=np.zeros(len(d))
        side[((cl>mid+band)&(cl>E.ema(cl,200))).to_numpy()]=1
        side[((cl<mid-band)&(cl<E.ema(cl,200))).to_numpy()]=-1
        side[adx14(d).to_numpy()<20]=0
        t=E.backtest(d,side,(E.atr(d,14)*2).to_numpy(),E.Config(rr=2.0,risk_pct=0.01,bar_minutes=240)).trades
        if len(t):
            t=t.copy(); t["coin"]=c; t["stop_dist"]=(t["entry"]-t["stop"]).abs(); t["sidi"]=np.where(t["side"]=="L",1,-1)
            v=cl.pct_change().rolling(30).std().shift(1); v=v/v.median()
            t["volscale"]=(1.0/v.reindex(pd.to_datetime(t["entry_time"])).clip(0.3,3).values).clip(0.3,2.5)
            rows.append(t[["entry_time","exit_time","r_mult","coin","entry","stop_dist","sidi","volscale"]])
    return pd.concat(rows,ignore_index=True).sort_values("entry_time").reset_index(drop=True)

def sim(T,risk,lev_cap=None,corr_size=True,dd_throttle=0.25,throttle_f=0.5,init=10000.0):
    T=T.sort_values("entry_time").reset_index(drop=True); eq=init; peak=init
    heap=[]; od=[]; open_notional=0.0; ct=[T.entry_time.min()]; cv=[eq]; ex=[]
    for _,r in T.iterrows():
        et=r["entry_time"]
        while heap and heap[0][0]<=et:
            xt,p,sg,nt=heapq.heappop(heap); eq+=p; peak=max(peak,eq); open_notional-=nt; od.remove(sg); ct.append(xt);cv.append(eq)
        size=risk*eq*r["volscale"]
        if dd_throttle and eq<peak*(1-dd_throttle): size*=throttle_f
        if corr_size and od:
            same=sum(1 for s in od if s==r["sidi"]); size/=(1+same)**0.5
        notional=size/r["stop_dist"]*r["entry"]
        if lev_cap is not None:
            room=max(0.0, lev_cap*eq-open_notional)
            if notional>room:
                scale=room/notional if notional>0 else 0; size*=scale; notional*=scale
            if size<=0: continue
        heapq.heappush(heap,(r["exit_time"], r["r_mult"]*size, r["sidi"], notional)); od.append(r["sidi"]); open_notional+=notional
        ex.append((r["entry_time"],r["exit_time"],r["sidi"],r["entry"],r["stop_dist"],size,r["coin"]))
    while heap:
        xt,p,sg,nt=heapq.heappop(heap); eq+=p; ct.append(xt);cv.append(eq)
    s=pd.Series(cv,index=pd.DatetimeIndex(ct)).sort_index(); s=s[~s.index.duplicated(keep="last")]
    return s, pd.DataFrame(ex,columns=["entry_time","exit_time","sidi","entry","stop_dist","size","coin"])

def mtm_dd(s, extr):
    d=s.resample("1D").last().ffill(); g=d.index
    co={c:CL_D[c].reindex(g,method="ffill") for c in BASE}
    add=np.zeros(len(g))
    for _,r in extr.iterrows():
        a=g.searchsorted(r["entry_time"]); b=g.searchsorted(r["exit_time"])
        if b<=a: continue
        add[a:b]+= r["sidi"]*(co[r["coin"]].values[a:b]-r["entry"])/r["stop_dist"]*r["size"]
    v=pd.Series(d.values+add,index=g); return (v/v.cummax()-1).min()*100

def peak_lev(s, extr):
    ev=[]; eqmap=s
    for _,r in extr.iterrows():
        nt=r["size"]/r["stop_dist"]*r["entry"]
        ev.append((r["entry_time"],nt,1)); ev.append((r["exit_time"],-nt,0))
    ev.sort(key=lambda x:x[0]); opn=0; ml=0
    for t,dn,o in ev:
        opn+=dn
        if o:
            eqx=eqmap.asof(t)
            if eqx and eqx>0: ml=max(ml, opn/eqx)
    return ml

def stats(s):
    d=s.resample("1D").last().ffill(); dd=(d/d.cummax()-1).min()*100
    mr=d.resample("ME").last().pct_change().dropna()
    yrs=(d.index[-1]-d.index[0]).days/365.25; cagr=((d.iloc[-1]/d.iloc[0])**(1/yrs)-1)*100
    return mr.mean()*100,(mr>0).mean()*100,dd,cagr

T=gen()
print("KC+ADX+corr-size, фікс-RR2. Пошук МАКС прибутку за БЕЗПЕКИ (real DD<=~45%, плече<=~6x):\n")
print(f"{'risk%':>5}{'lev_cap':>8}{'avg_mo%':>8}{'CAGR%':>7}{'realDD%':>8}{'MTM_DD%':>8}{'плече':>7}{'плюс.міс':>9}")
for risk in [0.02,0.03,0.04,0.05]:
    for cap in [None,6,5,4]:
        s,extr=sim(T,risk,lev_cap=cap)
        mo,pos,dd,cagr=stats(s); md=mtm_dd(s,extr); lev=peak_lev(s,extr)
        capn="-" if cap is None else str(cap)
        flag=""
        if md>-46 and lev<=6.2: flag=" ✅безпечно"
        print(f"{risk*100:5.0f}{capn:>8}{mo:8.2f}{cagr:7.0f}{dd:8.0f}{md:8.0f}{lev:7.1f}{pos:9.0f}{flag}")
