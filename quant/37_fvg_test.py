"""Механізація ОДНОГО поняття зі SMC-системи — FVG (Fair Value Gap) retest у бік тренду.
Решта системи (Narrative/Key Levels/A-B) — дискреційна, не тестується об'єктивно.
FVG bull (3 бари): high[i-2] < low[i] -> зона [high[i-2], low[i]].
Вхід: ціна повертається в зону, тренд вгору (close>EMA200). SL за зону, тейк RR2.
Порівняння з KC. Чесно: мій движок, реальні витрати, по режимах."""
import numpy as np, pandas as pd
import lib_data as L, strategies as ST, engine as E
FEE,SLIP=0.0005,0.0003
BASE={"BTC":ST.resample(L.load_btc_15m(),"4h"),
      "ETH":L.load_any("quant/data/eth_4h.csv"),
      "SOL":L.load_any("quant/data/sol_4h.csv")}

def fvg_trades(d, rr=2.0, lookahead=20, atr_floor=0.5):
    o,h,l,c=[d[x].to_numpy() for x in ["open","high","low","close"]]
    em=E.ema(d["close"],200).to_numpy(); atr=E.atr(d,14).to_numpy(); n=len(c); idx=d.index
    tr=[]; busy_until=1
    for k in range(2,n-1):
        # --- bull FVG ---
        if h[k-2]<l[k] and c[k]>em[k]:
            zt,zb=l[k],h[k-2]
            for j in range(k+1,min(k+1+lookahead,n)):
                if j<busy_until: break
                if l[j]<=zt and c[j]>em[j]:        # ретест зони у аптренді
                    entry=zt*(1+SLIP); sd=max(entry-zb, atr_floor*atr[j])
                    stop=entry-sd; tgt=entry+rr*sd; r=None; e=j
                    while e<n:
                        if l[e]<=stop: ex=stop*(1-SLIP); r=(ex-entry)/sd-2*FEE*(entry/sd); break
                        if h[e]>=tgt: r=rr-2*FEE*(entry/sd); break
                        e+=1
                    if r is None: r=(c[-1]-entry)/sd; e=n-1
                    tr.append((idx[j],idx[e],r,1)); busy_until=e+1; break
        # --- bear FVG ---
        if l[k-2]>h[k] and c[k]<em[k]:
            zt,zb=h[k],l[k-2]
            for j in range(k+1,min(k+1+lookahead,n)):
                if j<busy_until: break
                if h[j]>=zt and c[j]<em[j]:
                    entry=zt*(1-SLIP); sd=max(zb-entry, atr_floor*atr[j])
                    stop=entry+sd; tgt=entry-rr*sd; r=None; e=j
                    while e<n:
                        if h[e]>=stop: ex=stop*(1+SLIP); r=(entry-ex)/sd-2*FEE*(entry/sd); break
                        if l[e]<=tgt: r=rr-2*FEE*(entry/sd); break
                        e+=1
                    if r is None: r=(entry-c[-1])/sd; e=n-1
                    tr.append((idx[j],idx[e],r,-1)); busy_until=e+1; break
    return pd.DataFrame(tr,columns=["entry_time","exit_time","r_mult","sidi"])

# режим BTC
btc_d=BASE["BTC"]["close"].resample("1D").last().dropna(); e2=E.ema(btc_d,200); sl=e2-e2.shift(20)
reg=pd.Series("range",index=btc_d.index); reg[(btc_d>e2)&(sl>0)]="bull"; reg[(btc_d<e2)&(sl<0)]="bear"

print("FVG retest у бік тренду (RR2, 3 монети):\n")
allt=[]
for c,d in BASE.items():
    t=fvg_trades(d); t["coin"]=c; allt.append(t)
F=pd.concat(allt,ignore_index=True)
r=F["r_mult"].values
print(f"  Усього: n={len(r)} sumR={r.sum():.1f} expectancy={r.mean():+.3f}R WR={(r>0).mean()*100:.0f}%")
print(f"  Лонг: n={(F.sidi>0).sum()} exp={F[F.sidi>0].r_mult.mean():+.3f} | "
      f"Шорт: n={(F.sidi<0).sum()} exp={F[F.sidi<0].r_mult.mean():+.3f}")
F["reg"]=reg.reindex(pd.DatetimeIndex(pd.to_datetime(F.entry_time)).normalize(),method="ffill").values
print("  По режимах (чи допомагає в боковику, де KC слабка):")
for rg in ["bull","bear","range"]:
    g=F[F.reg==rg]["r_mult"]
    if len(g): print(f"     {rg:6}: n={len(g):3d} exp={g.mean():+.3f} sumR={g.sum():.1f}")
print("\n  Орієнтир KC (для порівняння): expectancy ~+0.29R, WR 44%.")
print("  Беззбиток для RR2 ≈ +0 при WR>33%. Дивимось, чи FVG має реальний едж.")

# ============ ПОРТФЕЛЬ: KC vs FVG vs KC+FVG (IS/OOS) ============
import heapq
def kc_trades(d):
    cl=d["close"]; mid=E.ema(cl,20); band=2*E.atr(d,10)
    s=np.zeros(len(d)); s[((cl>mid+band)&(cl>E.ema(cl,200))).to_numpy()]=1
    s[((cl<mid-band)&(cl<E.ema(cl,200))).to_numpy()]=-1
    h,l_,c_=d["high"].to_numpy(),d["low"].to_numpy(),d["close"].to_numpy()
    ax=adx_arr(d)
    s[ax<20]=0
    o=d["open"].to_numpy(); atr=E.atr(d,14).to_numpy(); idx=d.index; n=len(c_); tr=[]; i=0
    while i<n-1:
        if s[i]==0 or not np.isfinite(atr[i]): i+=1; continue
        D=2*atr[i]; eb=i+1; si=s[i]; entry=o[eb]*(1+SLIP) if si>0 else o[eb]*(1-SLIP)
        stop=entry-si*D; tgt=entry+si*2*D; j=eb; r=None
        while j<n:
            if (l_[j]<=stop) if si>0 else (h[j]>=stop): ex=stop*(1-SLIP) if si>0 else stop*(1+SLIP); r=si*(ex-entry)/D-2*FEE*(entry/D); break
            if (h[j]>=tgt) if si>0 else (l_[j]<=tgt): r=2-2*FEE*(entry/D); break
            j+=1
        if r is None: r=si*(c_[-1]-entry)/D; j=n-1
        tr.append((idx[eb],idx[j],r,si)); i=j+1
    return pd.DataFrame(tr,columns=["entry_time","exit_time","r_mult","sidi"])
def adx_arr(d):
    h,l=d["high"],d["low"];up=h.diff();dn=-l.diff()
    pdm=((up>dn)&(up>0))*up;mdm=((dn>up)&(dn>0))*dn;tr=E.true_range(d);a=tr.ewm(alpha=1/14,adjust=False).mean()
    pdi=100*pdm.ewm(alpha=1/14,adjust=False).mean()/a;mdi=100*mdm.ewm(alpha=1/14,adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).ewm(alpha=1/14,adjust=False).mean().to_numpy()
def meta(t,c,d):
    t=t.copy();t["coin"]=c;v=d["close"].pct_change().rolling(30).std().shift(1);v=v/v.median()
    t["volscale"]=pd.Series((1.0/v.reindex(pd.to_datetime(t["entry_time"])).clip(0.3,3).values).clip(0.3,2.5)).fillna(1.0).values;return t
def sim(T,risk=0.02):
    T=T.sort_values("entry_time").reset_index(drop=True);eq=1e4;pk=1e4;hp=[];od=[];ct=[T.entry_time.min()];cv=[eq]
    for _,r in T.iterrows():
        while hp and hp[0][0]<=r["entry_time"]:
            xt,p,sg=heapq.heappop(hp);eq+=p;pk=max(pk,eq);od.remove(sg);ct.append(xt);cv.append(eq)
        sz=risk*eq*r["volscale"]
        if eq<pk*0.75: sz*=0.5
        if od:
            same=sum(1 for s in od if s==r["sidi"]);sz/=(1+same)**0.5
        heapq.heappush(hp,(r["exit_time"],r["r_mult"]*sz,r["sidi"]));od.append(r["sidi"])
    while hp: xt,p,sg=heapq.heappop(hp);eq+=p;ct.append(xt);cv.append(eq)
    return pd.Series(cv,index=pd.DatetimeIndex(ct)).sort_index()
def mm(s,T,label):
    d=s.resample("1D").last().ffill();dd=(d/d.cummax()-1).min()*100;mr=d.resample("ME").last().pct_change().dropna()
    sh=np.sqrt(365)*d.pct_change().dropna().mean()/d.pct_change().dropna().std()
    k=int(len(T)*0.6);cut=T.entry_time.iloc[k];so=sim(T[T.entry_time>=cut])
    mro=so.resample("1D").last().ffill().resample("ME").last().pct_change().dropna()
    print(f"  {label:20} n={len(T):4d} | плюс.міс={(mr>0).mean()*100:.0f}% Sharpe={sh:.2f} avg_mo={mr.mean()*100:.2f}% DD={dd:.0f}% | OOS плюс.міс={(mro>0).mean()*100:.0f}%")
KC=pd.concat([meta(kc_trades(d),c,d) for c,d in BASE.items()],ignore_index=True)
FV=pd.concat([meta(fvg_trades(d),c,d) for c,d in BASE.items()],ignore_index=True)
BOTH=pd.concat([KC,FV],ignore_index=True).sort_values("entry_time")
print("\n"+"="*60);print("ПОРТФЕЛЬ (risk2%, corr-size): KC vs FVG vs KC+FVG");print("="*60)
mm(sim(KC),KC,"KC")
mm(sim(FV),FV,"FVG")
mm(sim(BOTH),BOTH,"KC + FVG")
