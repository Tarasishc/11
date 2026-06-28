"""Реалістичне обмеження: ОДНА позиція на монету загалом (бо два шорти на біржі
зливаються). Порівнюємо OOS: (A) 1 KC + 1 FVG на двигун (як рахувалось)
vs (B) 1 угода на монету загалом (як реально можна руками). Чесно, R-простір."""
import numpy as np, pandas as pd
import lib_data as L, strategies as ST, engine as E
FEE,SLIP=0.0005,0.0003
BASE={"BTC":ST.resample(L.load_btc_15m(),"4h"),
      "ETH":L.load_any("quant/data/eth_4h.csv"),
      "SOL":L.load_any("quant/data/sol_4h.csv")}

def adxv(d):
    h,l=d["high"],d["low"];up=h.diff();dn=-l.diff();pdm=((up>dn)&(up>0))*up;mdm=((dn>up)&(dn>0))*dn
    tr=E.true_range(d);a=tr.ewm(alpha=1/14,adjust=False).mean()
    pdi=100*pdm.ewm(alpha=1/14,adjust=False).mean()/a;mdi=100*mdm.ewm(alpha=1/14,adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).ewm(alpha=1/14,adjust=False).mean().to_numpy()

def kc_tr(d):  # -> list (entry_bar, exit_bar, ts, r)
    cl=d["close"];mid=E.ema(cl,20);band=2*E.atr(d,10);s=np.zeros(len(d))
    s[((cl>mid+band)&(cl>E.ema(cl,200))).to_numpy()]=1
    s[((cl<mid-band)&(cl<E.ema(cl,200))).to_numpy()]=-1;s[adxv(d)<20]=0
    o,h,l,c=[d[x].to_numpy() for x in ["open","high","low","close"]];atr=E.atr(d,14).to_numpy();idx=d.index;n=len(c);out=[];i=0
    while i<n-1:
        if s[i]==0 or not np.isfinite(atr[i]):i+=1;continue
        D=2*atr[i];eb=i+1;si=s[i];en=o[eb]*(1+SLIP) if si>0 else o[eb]*(1-SLIP);st=en-si*D;tg=en+si*2*D;j=eb;r=None
        while j<n:
            if (l[j]<=st) if si>0 else (h[j]>=st):ex=st*(1-SLIP) if si>0 else st*(1+SLIP);r=si*(ex-en)/D-2*FEE*(en/D);break
            if (h[j]>=tg) if si>0 else (l[j]<=tg):r=2-2*FEE*(en/D);break
            j+=1
        if r is None:r=si*(c[-1]-en)/D;j=n-1
        out.append((eb,j,idx[eb],r));i=j+1
    return out

def fvg_tr(d,la=20,af=0.5):
    o,h,l,c=[d[x].to_numpy() for x in ["open","high","low","close"]];em=E.ema(d["close"],200).to_numpy();atr=E.atr(d,14).to_numpy();n=len(c);idx=d.index;out=[];bz=1
    for k in range(2,n-1):
        if h[k-2]<l[k] and c[k]>em[k]:
            zt,zb=l[k],h[k-2]
            for j in range(k+1,min(k+1+la,n)):
                if j<bz:break
                if l[j]<=zt and c[j]>em[j]:
                    en=zt*(1+SLIP);D=max(en-zb,af*atr[j]);st=en-D;tg=en+2*D;r=None;e=j
                    while e<n:
                        if l[e]<=st:r=(st*(1-SLIP)-en)/D-2*FEE*(en/D);break
                        if h[e]>=tg:r=2-2*FEE*(en/D);break
                        e+=1
                    if r is None:r=(c[-1]-en)/D;e=n-1
                    out.append((j,e,idx[j],r));bz=e+1;break
        if l[k-2]>h[k] and c[k]<em[k]:
            zt,zb=h[k],l[k-2]
            for j in range(k+1,min(k+1+la,n)):
                if j<bz:break
                if h[j]>=zt and c[j]<em[j]:
                    en=zt*(1-SLIP);D=max(zb-en,af*atr[j]);st=en+D;tg=en-2*D;r=None;e=j
                    while e<n:
                        if h[e]>=st:r=(en-st*(1+SLIP))/D-2*FEE*(en/D);break
                        if l[e]<=tg:r=2-2*FEE*(en/D);break
                        e+=1
                    if r is None:r=(en-c[-1])/D;e=n-1
                    out.append((j,e,idx[j],r));bz=e+1;break
    return out

def naive(t):
    ts=pd.Timestamp(t);return ts.tz_localize(None) if ts.tzinfo is not None else ts

def per_engine(d):   # A: беремо всі угоди обох двигунів (1 KC + 1 FVG можуть збігатись)
    return [(naive(ts),r) for _,_,ts,r in (kc_tr(d)+fvg_tr(d))]

def one_per_coin(d): # B: одна угода на монету; беремо першу за часом, поки не вийде — пропускаємо
    trs=sorted(kc_tr(d)+fvg_tr(d),key=lambda x:x[0]);taken=[];open_until=-1
    for eb,xb,ts,r in trs:
        if eb>open_until:taken.append((naive(ts),r));open_until=xb
    return taken

def oos_monthly(builder,risk=0.01):
    rows=[]
    for c,d in BASE.items():
        cut=naive(d.index[int(len(d)*0.6)])
        rows+=[(ts,r) for ts,r in builder(d) if ts>=cut]
    T=pd.DataFrame(rows,columns=["t","r"]).sort_values("t")
    r=T["r"].values;eq=np.cumprod(1+risk*r)
    me=pd.Series(eq,index=pd.DatetimeIndex(T["t"])).resample("ME").last().dropna()
    mret=me.pct_change().dropna();mret=pd.concat([pd.Series([me.iloc[0]-1],index=[me.index[0]]),mret])
    dd=((eq/np.maximum.accumulate(eq))-1).min()*100
    return len(r),r.mean(),mret.mean()*100,mret.median()*100,(mret>0).mean()*100,dd

print("OOS (нові дані), risk 1%/угода, BTC+ETH+SOL 4h:\n")
for name,b in [("A) 1 KC + 1 FVG на двигун (як рахувалось)",per_engine),
               ("B) 1 угода на монету (реально руками)   ",one_per_coin)]:
    n,exp,avg,med,pos,dd=oos_monthly(b)
    print(f"{name}: n={n:4d} exp={exp:+.3f}R | сер.міс={avg:+.2f}% медіана={med:+.2f}% | +міс={pos:.0f}% | DD={dd:+.0f}%")
