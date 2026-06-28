"""KC + FVG (з SMC-системи) — безпечна операційна точка (як §26, але з FVG).
Реальна MTM-DD + пік плеча + ліміт плеча. Sharpe 2.56 -> чи дає 10%/міс безпечно?"""
import numpy as np, pandas as pd, heapq
import lib_data as L, strategies as ST, engine as E
FEE,SLIP=0.0005,0.0003
BASE={"BTC":ST.resample(L.load_btc_15m(),"4h"),
      "ETH":L.load_any("quant/data/eth_4h.csv"),
      "SOL":L.load_any("quant/data/sol_4h.csv")}
CL_D={c:BASE[c]["close"].resample("1D").last() for c in BASE}

def adxv(d):
    h,l=d["high"],d["low"];up=h.diff();dn=-l.diff()
    pdm=((up>dn)&(up>0))*up;mdm=((dn>up)&(dn>0))*dn;tr=E.true_range(d);a=tr.ewm(alpha=1/14,adjust=False).mean()
    pdi=100*pdm.ewm(alpha=1/14,adjust=False).mean()/a;mdi=100*mdm.ewm(alpha=1/14,adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).ewm(alpha=1/14,adjust=False).mean().to_numpy()

def gen_kc(d):
    cl=d["close"];mid=E.ema(cl,20);band=2*E.atr(d,10)
    s=np.zeros(len(d));s[((cl>mid+band)&(cl>E.ema(cl,200))).to_numpy()]=1;s[((cl<mid-band)&(cl<E.ema(cl,200))).to_numpy()]=-1
    s[adxv(d)<20]=0
    o,h,l,c=[d[x].to_numpy() for x in ["open","high","low","close"]];atr=E.atr(d,14).to_numpy();idx=d.index;n=len(c);tr=[];i=0
    while i<n-1:
        if s[i]==0 or not np.isfinite(atr[i]): i+=1;continue
        D=2*atr[i];eb=i+1;si=s[i];entry=o[eb]*(1+SLIP) if si>0 else o[eb]*(1-SLIP)
        stop=entry-si*D;tgt=entry+si*2*D;j=eb;r=None
        while j<n:
            if (l[j]<=stop) if si>0 else (h[j]>=stop): ex=stop*(1-SLIP) if si>0 else stop*(1+SLIP);r=si*(ex-entry)/D-2*FEE*(entry/D);break
            if (h[j]>=tgt) if si>0 else (l[j]<=tgt): r=2-2*FEE*(entry/D);break
            j+=1
        if r is None: r=si*(c[-1]-entry)/D;j=n-1
        tr.append((idx[eb],idx[j],r,si,entry,D));i=j+1
    return pd.DataFrame(tr,columns=["entry_time","exit_time","r_mult","sidi","entry","stop_dist"])

def gen_fvg(d,rr=2.0,la=20,af=0.5):
    o,h,l,c=[d[x].to_numpy() for x in ["open","high","low","close"]];em=E.ema(d["close"],200).to_numpy();atr=E.atr(d,14).to_numpy();n=len(c);idx=d.index;tr=[];bz=1
    for k in range(2,n-1):
        if h[k-2]<l[k] and c[k]>em[k]:
            zt,zb=l[k],h[k-2]
            for j in range(k+1,min(k+1+la,n)):
                if j<bz: break
                if l[j]<=zt and c[j]>em[j]:
                    entry=zt*(1+SLIP);D=max(entry-zb,af*atr[j]);stop=entry-D;tgt=entry+rr*D;r=None;e=j
                    while e<n:
                        if l[e]<=stop: ex=stop*(1-SLIP);r=(ex-entry)/D-2*FEE*(entry/D);break
                        if h[e]>=tgt: r=rr-2*FEE*(entry/D);break
                        e+=1
                    if r is None: r=(c[-1]-entry)/D;e=n-1
                    tr.append((idx[j],idx[e],r,1,entry,D));bz=e+1;break
        if l[k-2]>h[k] and c[k]<em[k]:
            zt,zb=h[k],l[k-2]
            for j in range(k+1,min(k+1+la,n)):
                if j<bz: break
                if h[j]>=zt and c[j]<em[j]:
                    entry=zt*(1-SLIP);D=max(zb-entry,af*atr[j]);stop=entry+D;tgt=entry-rr*D;r=None;e=j
                    while e<n:
                        if h[e]>=stop: ex=stop*(1+SLIP);r=(entry-ex)/D-2*FEE*(entry/D);break
                        if l[e]<=tgt: r=rr-2*FEE*(entry/D);break
                        e+=1
                    if r is None: r=(entry-c[-1])/D;e=n-1
                    tr.append((idx[j],idx[e],r,-1,entry,D));bz=e+1;break
    return pd.DataFrame(tr,columns=["entry_time","exit_time","r_mult","sidi","entry","stop_dist"])

def meta(t,c,d):
    t=t.copy();t["coin"]=c;v=d["close"].pct_change().rolling(30).std().shift(1);v=v/v.median()
    t["volscale"]=pd.Series((1.0/v.reindex(pd.to_datetime(t["entry_time"])).clip(0.3,3).values).clip(0.3,2.5)).fillna(1.0).values;return t

def sim(T,risk,lev_cap=None,init=1e4):
    T=T.sort_values("entry_time").reset_index(drop=True);eq=init;pk=init;hp=[];od=[];opn=0.0;ct=[T.entry_time.min()];cv=[eq];ex=[]
    for _,r in T.iterrows():
        while hp and hp[0][0]<=r["entry_time"]:
            xt,p,sg,nt=heapq.heappop(hp);eq+=p;pk=max(pk,eq);opn-=nt;od.remove(sg);ct.append(xt);cv.append(eq)
        sz=risk*eq*r["volscale"]
        if eq<pk*0.75: sz*=0.5
        if od:
            same=sum(1 for s in od if s==r["sidi"]);sz/=(1+same)**0.5
        nt=sz/r["stop_dist"]*r["entry"]
        if lev_cap is not None:
            room=max(0.0,lev_cap*eq-opn)
            if nt>room: f=room/nt if nt>0 else 0;sz*=f;nt*=f
            if sz<=0: continue
        heapq.heappush(hp,(r["exit_time"],r["r_mult"]*sz,r["sidi"],nt));od.append(r["sidi"]);opn+=nt
        ex.append((r["entry_time"],r["exit_time"],r["sidi"],r["entry"],r["stop_dist"],sz,r["coin"]))
    while hp: xt,p,sg,nt=heapq.heappop(hp);eq+=p;ct.append(xt);cv.append(eq)
    s=pd.Series(cv,index=pd.DatetimeIndex(ct)).sort_index();return s[~s.index.duplicated(keep="last")],pd.DataFrame(ex,columns=["entry_time","exit_time","sidi","entry","stop_dist","size","coin"])

def mtm_dd(s,extr):
    d=s.resample("1D").last().ffill();g=d.index;co={c:CL_D[c].reindex(g,method="ffill") for c in BASE};add=np.zeros(len(g))
    for _,r in extr.iterrows():
        a=g.searchsorted(r["entry_time"]);b=g.searchsorted(r["exit_time"])
        if b<=a: continue
        add[a:b]+=r["sidi"]*(co[r["coin"]].values[a:b]-r["entry"])/r["stop_dist"]*r["size"]
    v=pd.Series(d.values+add,index=g);return (v/v.cummax()-1).min()*100

def plev(s,extr):
    ev=[]
    for _,r in extr.iterrows():
        nt=r["size"]/r["stop_dist"]*r["entry"];ev.append((r["entry_time"],nt,1));ev.append((r["exit_time"],-nt,0))
    ev.sort(key=lambda x:x[0]);opn=0;ml=0
    for t,dn,o in ev:
        opn+=dn
        if o:
            e=s.asof(t)
            if e and e>0: ml=max(ml,opn/e)
    return ml

def st(s):
    d=s.resample("1D").last().ffill();dd=(d/d.cummax()-1).min()*100;mr=d.resample("ME").last().pct_change().dropna()
    yrs=(d.index[-1]-d.index[0]).days/365.25;cagr=((d.iloc[-1]/d.iloc[0])**(1/yrs)-1)*100
    return mr.mean()*100,(mr>0).mean()*100,dd,cagr

T=pd.concat([meta(gen_kc(d),c,d) for c,d in BASE.items()]+[meta(gen_fvg(d),c,d) for c,d in BASE.items()],ignore_index=True).sort_values("entry_time")
print("KC + FVG — безпечна операційна точка (real DD<=~45%, плече<=~6x):\n")
print(f"{'risk%':>5}{'cap':>5}{'avg_mo%':>8}{'CAGR%':>7}{'realDD%':>8}{'MTM_DD%':>8}{'плече':>7}{'плюс.міс':>9}")
for risk in [0.005,0.01,0.015,0.02]:
    for cap in [6,5,4]:
        s,extr=sim(T,risk,lev_cap=cap);mo,pos,dd,cagr=st(s);md=mtm_dd(s,extr);lev=plev(s,extr)
        flag=" ✅" if md>-46 and lev<=6.2 else ""
        print(f"{risk*100:5.1f}{cap:>5}{mo:8.2f}{cagr:7.0f}{dd:8.0f}{md:8.0f}{lev:7.1f}{pos:9.0f}{flag}")
