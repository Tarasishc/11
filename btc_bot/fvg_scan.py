import pandas as pd, numpy as np, sys

FEE=0.0006
F15="/root/.claude/uploads/26e5ea76-e39e-5900-871b-43ddd9468ab1/a874c5b2-btc_15m_full.csv"

def load(tf_min):
    d=pd.read_csv(F15)
    d['dt']=pd.to_datetime(d['ts'],unit='ms')
    d=d.set_index('dt')
    if tf_min!=15:
        r=str(tf_min)+'min'
        d=d.resample(r).agg({'open':'first','high':'max','low':'min','close':'last','vol':'sum'}).dropna()
    return d.reset_index()

def atr(df,n=14):
    h,l,c=df['high'].values,df['low'].values,df['close'].values
    pc=np.roll(c,1); pc[0]=c[0]
    tr=np.maximum(h-l,np.maximum(abs(h-pc),abs(l-pc)))
    return pd.Series(tr).ewm(alpha=1/n,adjust=False).mean().values

def emaa(df,n):
    return df['close'].ewm(span=n,adjust=False).mean().values

def backtest(df, side='both', use_trend=True, stop_buf=0.5, rr=2.0,
             max_wait=80, min_gap_atr=0.25, risk=0.02, fresh_only=True):
    """FVG mitigation strategy.
    Bullish FVG (gap up): high[i-2] < low[i]; zone=[high[i-2], low[i]].
      long when price dips back into zone (low <= zone_top), entry at zone_top, stop below zone_bottom.
    Bearish FVG: low[i-2] > high[i]; zone=[high[i], low[i-2]].
      short when price rallies into zone (high>=zone_bottom), entry at zone_bottom, stop above zone_top.
    """
    o=df['open'].values; h=df['high'].values; l=df['low'].values; c=df['close'].values
    a=atr(df); e200=emaa(df,200); n=len(df)
    pending=[]  # active FVG zones: dict
    trades=[]
    inpos=False; entry=stop=take=0; pdir=0; feeR=0
    for i in range(3,n):
        # manage open position first (from bar AFTER entry)
        if inpos:
            if pdir==1:
                if l[i]<=stop: trades.append((-1.0-feeR,i)); inpos=False
                elif h[i]>=take: trades.append((rr-feeR,i)); inpos=False
            else:
                if h[i]>=stop: trades.append((-1.0-feeR,i)); inpos=False
                elif l[i]<=take: trades.append((rr-feeR,i)); inpos=False
        # detect new FVG at bar i (using i-2,i)
        if h[i-2] < l[i]:  # bullish
            gap=l[i]-h[i-2]
            if gap>min_gap_atr*a[i]:
                pending.append({'dir':1,'top':l[i],'bot':h[i-2],'born':i})
        if l[i-2] > h[i]:  # bearish
            gap=l[i-2]-h[i]
            if gap>min_gap_atr*a[i]:
                pending.append({'dir':-1,'top':l[i-2],'bot':h[i],'born':i})
        # try to trigger entries from pending zones
        if not inpos:
            for z in pending:
                if z.get('used'): continue
                if i-z['born']>max_wait or i-z['born']<1:
                    if i-z['born']>max_wait: z['used']=True
                    continue
                if z['dir']==1 and (side in('both','long')):
                    if use_trend and not (c[i]>e200[i]): continue
                    if l[i]<=z['top'] and h[i]>=z['bot']:  # touched zone
                        ent=z['top']; st=z['bot']-stop_buf*a[i]
                        risk_d=ent-st
                        if risk_d<=0: z['used']=True; continue
                        feeR=2*FEE*ent/risk_d
                        if l[i]<=st:  # same-bar stop-out
                            trades.append((-1.0-feeR,i)); z['used']=True; break
                        entry=ent; stop=st; take=ent+rr*risk_d; pdir=1; inpos=True
                        z['used']=True; break
                elif z['dir']==-1 and (side in('both','short')):
                    if use_trend and not (c[i]<e200[i]): continue
                    if h[i]>=z['bot'] and l[i]<=z['top']:
                        ent=z['bot']; st=z['top']+stop_buf*a[i]
                        risk_d=st-ent
                        if risk_d<=0: z['used']=True; continue
                        feeR=2*FEE*ent/risk_d
                        if h[i]>=st:
                            trades.append((-1.0-feeR,i)); z['used']=True; break
                        entry=ent; stop=st; take=ent-rr*risk_d; pdir=-1; inpos=True
                        z['used']=True; break
        if fresh_only:
            pending=[z for z in pending if not z.get('used') and i-z['born']<=max_wait]
    # equity. trades=(R, exit_bar_idx). fee: ~2*FEE on notional; in R-terms = 2*FEE/(risk_dist/entry)
    if not trades: return None
    dt=df['dt'].values
    Rs=np.array([t[0] for t in trades]); idx=[t[1] for t in trades]
    def stats(rs):
        if len(rs)==0: return None
        eq=1.0; peak=1.0; dd=0
        for R in rs:
            eq*=(1+risk*R)  # fee already in R
            peak=max(peak,eq); dd=max(dd,(peak-eq)/peak)
        return eq,dd
    span_days=(df['dt'].iloc[-1]-df['dt'].iloc[0]).days; months=span_days/30.4
    eq,dd=stats(Rs)
    # OOS split by exit time (70/30)
    cut=int(len(Rs)*0.7)
    isR=Rs[:cut]; oosR=Rs[cut:]
    return dict(n=len(Rs), win=(Rs>0).mean(), expR=Rs.mean(), final=eq,
                permo=eq**(1/months)-1, dd=dd, months=round(months,1),
                is_exp=isR.mean(), oos_exp=oosR.mean() if len(oosR) else 0, oos_n=len(oosR))

if __name__=="__main__":
    tf=int(sys.argv[1]) if len(sys.argv)>1 else 240
    df=load(tf)
    print(f"TF={tf}m rows={len(df)} span={df['dt'].iloc[0].date()}..{df['dt'].iloc[-1].date()}")
    for side in ['both','long','short']:
        for rr in [1.5,2.0,3.0]:
            r=backtest(df,side=side,rr=rr,use_trend=True)
            if r: print(f"{side:5} rr={rr} | n={r['n']:4} win={r['win']:.2f} expR={r['expR']:+.3f} | IS={r['is_exp']:+.3f} OOS={r['oos_exp']:+.3f}(n{r['oos_n']}) | {r['permo']*100:+.2f}%/mo DD={r['dd']*100:.0f}%")
