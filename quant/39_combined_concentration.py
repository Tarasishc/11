"""Чи виживає KC+FVG суто на кількох великих місяцях/рухах? (R-простір, рівна вага)."""
import numpy as np, pandas as pd
import lib_data as L, strategies as ST, engine as E
FEE,SLIP=0.0005,0.0003
BASE={"BTC":ST.resample(L.load_btc_15m(),"4h"),"ETH":L.load_any("quant/data/eth_4h.csv"),"SOL":L.load_any("quant/data/sol_4h.csv")}
def adxv(d):
    h,l=d["high"],d["low"];up=h.diff();dn=-l.diff();pdm=((up>dn)&(up>0))*up;mdm=((dn>up)&(dn>0))*dn
    tr=E.true_range(d);a=tr.ewm(alpha=1/14,adjust=False).mean()
    pdi=100*pdm.ewm(alpha=1/14,adjust=False).mean()/a;mdi=100*mdm.ewm(alpha=1/14,adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).ewm(alpha=1/14,adjust=False).mean().to_numpy()
def kc(d):
    cl=d["close"];mid=E.ema(cl,20);band=2*E.atr(d,10);s=np.zeros(len(d))
    s[((cl>mid+band)&(cl>E.ema(cl,200))).to_numpy()]=1;s[((cl<mid-band)&(cl<E.ema(cl,200))).to_numpy()]=-1;s[adxv(d)<20]=0
    o,h,l,c=[d[x].to_numpy() for x in ["open","high","low","close"]];atr=E.atr(d,14).to_numpy();idx=d.index;n=len(c);tr=[];i=0
    while i<n-1:
        if s[i]==0 or not np.isfinite(atr[i]):i+=1;continue
        D=2*atr[i];eb=i+1;si=s[i];en=o[eb]*(1+SLIP) if si>0 else o[eb]*(1-SLIP);st=en-si*D;tg=en+si*2*D;j=eb;r=None
        while j<n:
            if (l[j]<=st) if si>0 else (h[j]>=st):ex=st*(1-SLIP) if si>0 else st*(1+SLIP);r=si*(ex-en)/D-2*FEE*(en/D);break
            if (h[j]>=tg) if si>0 else (l[j]<=tg):r=2-2*FEE*(en/D);break
            j+=1
        if r is None:r=si*(c[-1]-en)/D;j=n-1
        tr.append((idx[eb],r));i=j+1
    return tr
def fvg(d,la=20,af=0.5):
    o,h,l,c=[d[x].to_numpy() for x in ["open","high","low","close"]];em=E.ema(d["close"],200).to_numpy();atr=E.atr(d,14).to_numpy();n=len(c);idx=d.index;tr=[];bz=1
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
                    tr.append((idx[j],r));bz=e+1;break
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
                    tr.append((idx[j],r));bz=e+1;break
    return tr
rows=[]
for c,d in BASE.items():
    for t,r in kc(d): rows.append((t,r))
    for t,r in fvg(d): rows.append((t,r))
T=pd.DataFrame(rows,columns=["t","r"]).sort_values("t"); rm=T["r"].values; tot=rm.sum()
print(f"KC+FVG разом: угод={len(rm)} сумарний R={tot:.0f} expectancy={rm.mean():+.3f} WR={(rm>0).mean()*100:.0f}% maxR={rm.max():.1f}")
print(f"Аутлаєр-угод (>3R): {(rm>3).sum()}  <- кожен виграш обрізаний на +2R")
print("\nВидалення ТОП-N виграшних УГОД (чи лишається плюс):")
o=np.argsort(rm)[::-1]
for N in [10,50,100,200]:
    r2=rm.copy();r2[o[:N]]=0;print(f"  без топ-{N:3d}: R={r2.sum():5.0f} ({'ПЛЮС' if r2.sum()>0 else 'МІНУС'})")
T["ym"]=pd.to_datetime(T["t"]).dt.to_period("M");mon=T.groupby("ym")["r"].sum()
print(f"\nМісяців={len(mon)} плюсових={ (mon>0).mean()*100:.0f}%")
print("ТОП-5 найкращих місяців (R та % від загального):")
for ym,v in mon.sort_values(ascending=False).head(5).items(): print(f"  {ym}: {v:.1f}R ({v/tot*100:.0f}%)")
print("ТОП-5 найгірших місяців:")
for ym,v in mon.sort_values().head(5).items(): print(f"  {ym}: {v:.1f}R")
ms=mon.sort_values(ascending=False)
for k in [1,3,5,10]:
    print(f"  без топ-{k} місяців: R={mon.sum()-ms.head(k).sum():.0f} ({'ПЛЮС' if mon.sum()-ms.head(k).sum()>0 else 'МІНУС'})")
cum=np.cumsum(rm);r2=np.corrcoef(np.arange(len(rm)),cum)[0,1]**2
print(f"\nЛінійність кривої R²={r2:.3f} (1=ідеально рівна)")
T["yr"]=pd.to_datetime(T["t"]).dt.year;yr=T.groupby("yr")["r"].sum()
print(f"Прибуткових років: {(yr>0).sum()}/{len(yr)}")
