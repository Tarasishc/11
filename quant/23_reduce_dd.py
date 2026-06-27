"""Зменшити DD за того ж прибутку: фільтри входу + стоп-тюнінг + портфельні овердрайви.
Метрика — MAR=avg_mo/|maxDD| (вища=краще, ~інваріантна до ризику). Чесно IS/OOS.
Per-trade shared-equity sim (звірений з движком у кроці 21)."""
import numpy as np, pandas as pd, heapq
import lib_data as L, strategies as ST, engine as E

PATHS={"BTC":"quant/data/btc_15m.csv","ETH":"quant/data/eth_4h.csv","SOL":"quant/data/sol_4h.csv"}
def get4h(name):
    df=L.load_any(PATHS[name]); return ST.resample(df,"4h") if name=="BTC" else df

DATA={c:get4h(c) for c in PATHS}
# причинна (shifted) волатильність кожної монети для vol-targeting
COINVOL={}
for c,d in DATA.items():
    v=d["close"].pct_change().rolling(30).std().shift(1)
    COINVOL[c]=(v/ v.median())   # нормована: ~1 у середньому

def adx_di(d,n=14):
    h,l=d["high"],d["low"];up=h.diff();dn=-l.diff()
    pdm=((up>dn)&(up>0))*up;mdm=((dn>up)&(dn>0))*dn;tr=E.true_range(d);a=tr.ewm(alpha=1/n,adjust=False).mean()
    pdi=100*pdm.ewm(alpha=1/n,adjust=False).mean()/a;mdi=100*mdm.ewm(alpha=1/n,adjust=False).mean()/a
    adx=(100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).ewm(alpha=1/n,adjust=False).mean()
    return adx

def kc_signals(d, adx_min=0, daily_trend=False, vol_lo=0.0, vol_hi=10.0, strong=0.0):
    c=d["close"]; mid=E.ema(c,20); band=2.0*E.atr(d,10)
    upper=mid+band; lower=mid-band; trend=E.ema(c,200)
    long=(c>upper)&(c>trend); short=(c<lower)&(c<trend)
    side=np.zeros(len(d)); side[long.to_numpy()]=1; side[short.to_numpy()]=-1
    # фільтри (зануляють слабкі сетапи -> менше стопів)
    if adx_min>0:
        ax=adx_di(d,14).to_numpy(); side[ax<adx_min]=0
    if daily_trend:
        de=E.ema(c.resample("1D",label="left",closed="left").last().dropna(),50)
        cd=c.resample("1D",label="left",closed="left").last()
        up=(cd>de).shift(1).reindex(d.index,method="ffill").fillna(False).astype(bool).to_numpy()
        dn=(cd<de).shift(1).reindex(d.index,method="ffill").fillna(False).astype(bool).to_numpy()
        side[(side>0)&~up]=0; side[(side<0)&~dn]=0
    if vol_lo>0 or vol_hi<10:
        atrp=(E.atr(d,14)/c); q=atrp.rank(pct=True).to_numpy()
        side[(q<vol_lo)|(q>vol_hi)]=0
    if strong>0:
        rng=(d["high"]-d["low"]).replace(0,np.nan)
        pos=((c-d["low"])/rng).to_numpy()  # 1=закриття на максимумі
        side[(side>0)&(pos<strong)]=0
        side[(side<0)&(pos>1-strong)]=0
    return side,(E.atr(d,14)*2.0).to_numpy()

def gen_trades(filters, be=False, max_hold=0):
    rows=[]
    for c,d in DATA.items():
        side,sd=kc_signals(d,**filters)
        cfg=E.Config(rr=2.0,risk_pct=0.01,bar_minutes=240,max_hold_bars=max_hold)
        t=E.backtest(d,side,sd,cfg).trades
        if be and len(t): t=apply_breakeven(d,side,sd,t)  # placeholder, BE done in custom below
        if len(t):
            t=t.copy(); t["coin"]=c
            t["volscale"]=COINVOL[c].reindex(pd.to_datetime(t["entry_time"])).clip(0.3,3).values
            t["volscale"]=(1.0/t["volscale"]).clip(0.3,2.5)
            rows.append(t[["entry_time","exit_time","r_mult","coin","volscale"]])
    return pd.concat(rows,ignore_index=True).sort_values("entry_time")

def sim(T,risk,vol_target=False,dd_throttle=0.0,throttle_f=0.5,max_conc=0,init=10000.0):
    T=T.sort_values("entry_time"); eq=init; peak=init; heap=[]; ct=[T.entry_time.min()];cv=[eq]
    for _,r in T.iterrows():
        et=r["entry_time"]
        while heap and heap[0][0]<=et:
            xt,p=heapq.heappop(heap); eq+=p; peak=max(peak,eq); ct.append(xt);cv.append(eq)
        if max_conc and len(heap)>=max_conc:   # ліміт одночасних позицій
            continue
        size=risk*eq
        if vol_target: size*=r["volscale"]
        if dd_throttle and eq< peak*(1-dd_throttle): size*=throttle_f   # різати ризик у DD
        heapq.heappush(heap,(r["exit_time"], r["r_mult"]*size))
    while heap:
        xt,p=heapq.heappop(heap); eq+=p; ct.append(xt);cv.append(eq)
    s=pd.Series(cv,index=pd.DatetimeIndex(ct)).sort_index(); return s[~s.index.duplicated(keep="last")]

def met(eq):
    d=eq.resample("1D").last().ffill(); dd=(d/d.cummax()-1).min()
    mo=d.resample("ME").last().pct_change().dropna().mean()
    yrs=max((d.index[-1]-d.index[0]).days/365.25,1e-9); cagr=(d.iloc[-1]/d.iloc[0])**(1/yrs)-1
    return mo,dd,cagr

def report(T,label,**simkw):
    eq=sim(T,0.03,**simkw); mo,dd,cagr=met(eq); mar=mo/abs(dd) if dd<0 else 0
    k=int(len(T)*0.6); cut=T.entry_time.iloc[k]
    eqo=sim(T[T.entry_time>=cut],0.03,**simkw); moo,ddo,_=met(eqo)
    print(f"  {label:34} n={len(T):4d} | avg_mo={mo*100:5.2f}% DD={dd*100:5.0f}% MAR={mar:.3f} CAGR={cagr*100:5.0f}% "
          f"| OOS avg_mo={moo*100:4.1f}% DD={ddo*100:4.0f}%")
    return mar,mo,dd

print("BASELINE та ФІЛЬТРИ ВХОДУ (risk 3%, KC BTC+ETH+SOL):")
base=gen_trades({})
report(base,"baseline KC")
report(gen_trades({"adx_min":20}),"+ADX>20")
report(gen_trades({"adx_min":25}),"+ADX>25")
report(gen_trades({"daily_trend":True}),"+denний тренд (EMA50d)")
report(gen_trades({"vol_lo":0.25}),"+vol-фільтр (відсікти низ 25%)")
report(gen_trades({"strong":0.5}),"+сильний бар (закр. в пів бара)")
report(gen_trades({"adx_min":20,"daily_trend":True}),"+ADX>20 & денний тренд")

print("\nСТОП/ВИХІД (на baseline):")
report(gen_trades({},max_hold=12),"+часовий стоп 12 барів (2 дні)")
report(gen_trades({},max_hold=30),"+часовий стоп 30 барів (5 днів)")

print("\nПОРТФЕЛЬНІ ОВЕРДРАЙВИ проти DD (на baseline):")
report(base,"+vol-targeting",vol_target=True)
report(base,"+DD-throttle >25%->0.5x",dd_throttle=0.25)
report(base,"+ліміт 2 одночасні",max_conc=2)
report(base,"+vol-target & DD-throttle",vol_target=True,dd_throttle=0.25)

print("\nКОМБО найкращих:")
best=gen_trades({"adx_min":20})
report(best,"ADX>20 + vol-target + DD-throttle",vol_target=True,dd_throttle=0.25)

# ===== СТРОГИЙ risk-sweep: baseline vs найкраще комбо (та сама дохідність -> менша DD?) =====
def sweep(T, label, **simkw):
    print(f"\n  {label}:")
    print(f"  {'risk%':>6}{'avg_mo%':>9}{'CAGR%':>8}{'maxDD%':>8}")
    for risk in [0.02,0.03,0.04,0.05,0.06,0.08]:
        eq=sim(T,risk,**simkw); mo,dd,cagr=met(eq)
        tag=" <=10%/міс" if mo>=0.10 else (" <=50-60%DD" if 0.50<=abs(dd)<=0.62 else "")
        print(f"  {risk*100:6.1f}{mo*100:9.2f}{cagr*100:8.0f}{dd*100:8.0f}{tag}")

print("\n" + "="*64)
print("ФІНАЛ: baseline vs КОМБО (ADX>20 + vol-target + DD-throttle)")
print("="*64)
sweep(base, "BASELINE KC")
combo=gen_trades({"adx_min":20})
sweep(combo, "КОМБО", vol_target=True, dd_throttle=0.25)
