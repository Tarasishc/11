"""Тест ідей із 3 наданих стратегій + схрещування:
(A) Частковий вихід 50%@1.5R + трейл 6*ATR  vs мій фікс-RR (на KC і BOS входах)
(B) Squeeze breakout (low-vol box) — чи має едж, чи заробляє у боковику/ведмеді
(C) Схрещування: KC-тренд + Squeeze -> чи більше плюс-місяців (всепогодність)
Чесно: мій движок, реальні витрати, R-простір + портфель IS/OOS."""
import numpy as np, pandas as pd, heapq
import lib_data as L, strategies as ST, engine as E, market_structure as MS

BASE={"BTC":ST.resample(L.load_btc_15m(),"4h"),
      "ETH":L.load_any("quant/data/eth_4h.csv"),
      "SOL":L.load_any("quant/data/sol_4h.csv")}
FEE,SLIP=0.0005,0.0003

def adx14(d):
    h,l=d["high"],d["low"];up=h.diff();dn=-l.diff()
    pdm=((up>dn)&(up>0))*up;mdm=((dn>up)&(dn>0))*dn;tr=E.true_range(d);a=tr.ewm(alpha=1/14,adjust=False).mean()
    pdi=100*pdm.ewm(alpha=1/14,adjust=False).mean()/a;mdi=100*mdm.ewm(alpha=1/14,adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).ewm(alpha=1/14,adjust=False).mean()

def kc_side(d):
    cl=d["close"]; mid=E.ema(cl,20); band=2*E.atr(d,10)
    s=np.zeros(len(d))
    s[((cl>mid+band)&(cl>E.ema(cl,200))).to_numpy()]=1
    s[((cl<mid-band)&(cl<E.ema(cl,200))).to_numpy()]=-1
    s[adx14(d).to_numpy()<20]=0
    return s

def bos_side(d):
    s,_=MS.ms_signals(d,k=2,mode="cont",stop_mode="atr",atr_mult=2.0,rr=2.0)
    return s

def squeeze_side(d, n=20, q=0.25):
    h,l,cl=d["high"],d["low"],d["close"]
    hh=h.rolling(n).max().shift(1); ll=l.rolling(n).min().shift(1)
    width=(hh-ll)/cl
    sq=width < width.rolling(100).quantile(q)        # вузька коробка = низька волатильність
    s=np.zeros(len(d))
    s[(sq.shift(1).fillna(False)&(cl>hh)).to_numpy()]=1   # пробій угору після стиснення
    s[(sq.shift(1).fillna(False)&(cl<ll)).to_numpy()]=-1  # пробій вниз
    return s

def exit_sim(d, side, mode="fixedRR", stop_mult=2.0, rr=2.0, partial_r=1.5, trail_mult=6.0):
    o,h,l,c=[d[x].to_numpy() for x in ["open","high","low","close"]]
    atr=E.atr(d,14).to_numpy(); n=len(c); idx=d.index
    trades=[]; i=0
    while i<n-1:
        s=side[i]; D=stop_mult*atr[i] if i<n else np.nan
        if s==0 or not np.isfinite(D) or D<=0: i+=1; continue
        eb=i+1; entry=o[eb]*(1+SLIP) if s>0 else o[eb]*(1-SLIP)
        costR=2*FEE*(entry/D)
        if mode=="fixedRR":
            stop=entry-s*D; tgt=entry+s*rr*D; j=eb; r=None
            while j<n:
                hitS=(l[j]<=stop) if s>0 else (h[j]>=stop)
                hitT=(h[j]>=tgt) if s>0 else (l[j]<=tgt)
                if hitS: ex=stop*(1-SLIP) if s>0 else stop*(1+SLIP); r=s*(ex-entry)/D-costR; break
                if hitT: r=rr-costR; break
                j+=1
            if r is None: r=s*(c[-1]-entry)/D-costR; j=n-1
        else:  # partial_trail
            stop0=entry-s*D; t1=entry+s*partial_r*D; ext=entry; part=False; rloc=0.0; j=eb; r=None
            while j<n:
                ext=max(ext,h[j]) if s>0 else min(ext,l[j])
                if not part:
                    hitS=(l[j]<=stop0) if s>0 else (h[j]>=stop0)
                    hitT=(h[j]>=t1) if s>0 else (l[j]<=t1)
                    if hitS and not hitT: ex=stop0*(1-SLIP) if s>0 else stop0*(1+SLIP); r=s*(ex-entry)/D-costR; break
                    if hitT: rloc=0.5*partial_r; part=True   # зафіксували 50% на +1.5R
                else:
                    trail=ext-s*trail_mult*atr[i]
                    hitTr=(l[j]<=trail) if s>0 else (h[j]>=trail)
                    if hitTr: ex=trail*(1-SLIP) if s>0 else trail*(1+SLIP); r=rloc+0.5*s*(ex-entry)/D-costR; break
                j+=1
            if r is None: r=rloc+(0.5 if part else 1.0)*s*(c[-1]-entry)/D-costR; j=n-1
        trades.append((idx[eb],idx[min(j,n-1)],r,s)); i=j+1
    return pd.DataFrame(trades,columns=["entry_time","exit_time","r_mult","sidi"])

def rstats(df,label):
    r=df["r_mult"].values
    print(f"  {label:30} n={len(r):4d} sumR={r.sum():6.1f} exp={r.mean():+.3f} WR={(r>0).mean()*100:.0f}% "
          f"maxR={r.max():.1f}")

print("="*66); print("(A) ВИХІД: фікс-RR vs частковий+трейл (R-простір, 3 монети)"); print("="*66)
for entry_name, sfn in [("KC", kc_side), ("BOS", bos_side)]:
    for mode in ["fixedRR","partial_trail"]:
        allt=[]
        for c,d in BASE.items():
            allt.append(exit_sim(d, sfn(d), mode=mode))
        df=pd.concat(allt)
        rstats(df, f"{entry_name} + {mode}")
    print()

print("="*66); print("(B) SQUEEZE BREAKOUT — чи має едж + по режимах"); print("="*66)
sq_all=[]
for c,d in BASE.items():
    t=exit_sim(d, squeeze_side(d), mode="partial_trail"); t["coin"]=c; sq_all.append(t)
sqdf=pd.concat(sq_all,ignore_index=True)
rstats(sqdf,"Squeeze (partial_trail)")
# режим BTC
btc_d=BASE["BTC"]["close"].resample("1D").last().dropna(); e2=E.ema(btc_d,200); sl=e2-e2.shift(20)
reg=pd.Series("range",index=btc_d.index); reg[(btc_d>e2)&(sl>0)]="bull"; reg[(btc_d<e2)&(sl<0)]="bear"
sqdf["reg"]=reg.reindex(pd.DatetimeIndex(pd.to_datetime(sqdf.entry_time)).normalize(),method="ffill").values
for rg in ["bull","bear","range"]:
    g=sqdf[sqdf.reg==rg]["r_mult"]
    if len(g): print(f"     {rg:6}: n={len(g):3d} sumR={g.sum():6.1f} exp={g.mean():+.3f}")

# ============ (C) ПОРТФЕЛЬ: чи покращують стабільність (IS/OOS) ============
def add_meta(df, coin, d):
    df=df.copy(); df["coin"]=coin
    v=d["close"].pct_change().rolling(30).std().shift(1); v=(v/v.median())
    vs=v.reindex(pd.to_datetime(df["entry_time"])).clip(0.3,3).values
    df["volscale"]=(1.0/vs).clip(0.3,2.5); return df

def build(strat_fns, mode):
    parts=[]
    for c,d in BASE.items():
        for sfn in strat_fns:
            parts.append(add_meta(exit_sim(d, sfn(d), mode=mode), c, d))
    return pd.concat(parts,ignore_index=True).sort_values("entry_time").reset_index(drop=True)

def sim(T,risk=0.02,corr_size=True,dd_throttle=0.25,throttle_f=0.5,init=10000.0):
    T=T.sort_values("entry_time").reset_index(drop=True); eq=init; peak=init; heap=[]; od=[]
    ct=[T.entry_time.min()]; cv=[eq]
    for _,r in T.iterrows():
        et=r["entry_time"]
        while heap and heap[0][0]<=et:
            xt,p,sg=heapq.heappop(heap); eq+=p; peak=max(peak,eq); ct.append(xt);cv.append(eq); od.remove(sg)
        size=risk*eq*r["volscale"]
        if dd_throttle and eq<peak*(1-dd_throttle): size*=throttle_f
        if corr_size and od:
            same=sum(1 for s in od if s==r["sidi"]); size/=(1+same)**0.5
        heapq.heappush(heap,(r["exit_time"], r["r_mult"]*size, r["sidi"])); od.append(r["sidi"])
    while heap:
        xt,p,sg=heapq.heappop(heap); eq+=p; ct.append(xt);cv.append(eq)
    s=pd.Series(cv,index=pd.DatetimeIndex(ct)).sort_index(); return s[~s.index.duplicated(keep="last")]

def metr(T,label):
    s=sim(T); d=s.resample("1D").last().ffill(); dd=(d/d.cummax()-1).min()*100
    mr=d.resample("ME").last().pct_change().dropna(); sh=np.sqrt(365)*d.pct_change().dropna().mean()/d.pct_change().dropna().std()
    k=int(len(T)*0.6); cut=T.entry_time.iloc[k]
    so=sim(T[T.entry_time>=cut]); do=so.resample("1D").last().ffill(); mro=do.resample("ME").last().pct_change().dropna()
    print(f"  {label:34} n={len(T):4d} | плюс.міс={(mr>0).mean()*100:.0f}% Sharpe={sh:.2f} avg_mo={mr.mean()*100:.2f}% DD={dd:.0f}% | OOS плюс.міс={(mro>0).mean()*100:.0f}%")

print("\n"+"="*66); print("(C) ПОРТФЕЛЬ (risk2%, corr-size) — чи покращують стабільність"); print("="*66)
metr(build([kc_side],"fixedRR"),        "KC фікс-RR (поточний best)")
metr(build([kc_side],"partial_trail"),  "KC частковий+трейл")
metr(build([kc_side,squeeze_side],"fixedRR"),      "KC + Squeeze (фікс-RR)")
metr(build([kc_side,squeeze_side],"partial_trail"),"KC + Squeeze (частк.+трейл)")
metr(build([kc_side,bos_side,squeeze_side],"partial_trail"),"KC + BOS + Squeeze (частк.+трейл)")
