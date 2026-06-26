import pandas as pd, numpy as np, fvg_scan as F
FEE=0.0006
def atr(df,n=14):
    h,l,c=df['high'].values,df['low'].values,df['close'].values
    pc=np.roll(c,1);pc[0]=c[0]
    tr=np.maximum(h-l,np.maximum(abs(h-pc),abs(l-pc)))
    return pd.Series(tr).ewm(alpha=1/n,adjust=False).mean().values

def run(df, sig_long, sig_short, stop_mult=1.5, exit_mode='trail', trail_mult=4.0, rr=2.0,
        slip_bps=5, allow_long=True, allow_short=True):
    o,h,l,c=df['open'].values,df['high'].values,df['low'].values,df['close'].values
    a=atr(df);n=len(df);dt=df['dt'].values;slip=slip_bps/1e4
    trades=[];pos=0;entry=stop=feeR=ext=initR=take=0;pend=0
    for i in range(1,n):
        if pos==0 and pend!=0 and a[i]>0:
            if pend==1:
                entry=o[i]*(1+slip);initR=stop_mult*a[i];stop=entry-initR
                feeR=2*FEE*entry/initR;take=entry+rr*initR;ext=h[i];pos=1
            else:
                entry=o[i]*(1-slip);initR=stop_mult*a[i];stop=entry+initR
                feeR=2*FEE*entry/initR;take=entry-rr*initR;ext=l[i];pos=-1
            pend=0
        if pos==1:
            if exit_mode=='trail':
                ext=max(ext,h[i]);stop=max(stop,ext-trail_mult*a[i])
                if l[i]<=stop: trades.append((dt[i],(stop-entry)/initR-feeR));pos=0
            else:
                if l[i]<=stop: trades.append((dt[i],-1.0-feeR));pos=0
                elif h[i]>=take: trades.append((dt[i],rr-feeR));pos=0
        elif pos==-1:
            if exit_mode=='trail':
                ext=min(ext,l[i]);stop=min(stop,ext+trail_mult*a[i])
                if h[i]>=stop: trades.append((dt[i],(entry-stop)/initR-feeR));pos=0
            else:
                if h[i]>=stop: trades.append((dt[i],-1.0-feeR));pos=0
                elif l[i]<=take: trades.append((dt[i],rr-feeR));pos=0
        if pos==0 and pend==0:
            if allow_long and sig_long[i]: pend=1
            elif allow_short and sig_short[i]: pend=-1
    return trades

def stats(trades,risk=0.02,months=106.0,label='',ret=False):
    if len(trades)<30:
        if not ret: print(f'{label}: замало (n={len(trades)})')
        return None
    trades=sorted(trades,key=lambda x:x[0]);Rs=np.array([r for _,r in trades])
    cut=int(len(Rs)*0.7);eq=1.0;peak=1.0;dd=0
    for R in Rs: eq*=(1+risk*R);peak=max(peak,eq);dd=max(dd,(peak-eq)/peak)
    d=dict(n=len(Rs),win=(Rs>0).mean(),expR=Rs.mean(),IS=Rs[:cut].mean(),OOS=Rs[cut:].mean(),pm=eq**(1/months)-1,dd=dd)
    if ret: return d,trades
    print('%-28s| n=%4d win=%.2f expR=%+.3f IS=%+.3f OOS=%+.3f | %+6.2f%%/mo DD=%2.0f%%'%(
        label,d['n'],d['win'],d['expR'],d['IS'],d['OOS'],d['pm']*100,d['dd']*100))
    return d

# ---- бібліотека сигналів (усі по ЗАКРИТОМУ бару) ----
def signals(df):
    o,h,l,c=df['open'].values,df['high'].values,df['low'].values,df['close'].values
    n=len(df);cl=pd.Series(c)
    e50=cl.ewm(span=50,adjust=False).mean().values
    e200=cl.ewm(span=200,adjust=False).mean().values
    sig={}
    # Donchian breakout 20/55
    for p in [20,55]:
        hh=pd.Series(h).rolling(p).max().shift(1).values
        ll=pd.Series(l).rolling(p).min().shift(1).values
        sig[f'donch{p}_L']=(c>hh); sig[f'donch{p}_S']=(c<ll)
    # Bollinger breakout
    for p,m in [(20,2.0),(20,2.5)]:
        sma=cl.rolling(p).mean();sd=cl.rolling(p).std()
        up=(sma+m*sd).values;dn=(sma-m*sd).values
        cross_up=(c>up)&(np.roll(c,1)<=np.roll(up,1))
        cross_dn=(c<dn)&(np.roll(c,1)>=np.roll(dn,1))
        sig[f'bb{p}_{m}_L']=cross_up; sig[f'bb{p}_{m}_S']=cross_dn
    # EMA cross 50/200 (Golden/Death) — стан
    sig['emaX_L']=(e50>e200); sig['emaX_S']=(e50<e200)
    # MACD cross
    ema12=cl.ewm(span=12,adjust=False).mean();ema26=cl.ewm(span=26,adjust=False).mean()
    macd=ema12-ema26;sigl=macd.ewm(span=9,adjust=False).mean()
    mc_up=((macd>sigl)&(macd.shift(1)<=sigl.shift(1))).values
    mc_dn=((macd<sigl)&(macd.shift(1)>=sigl.shift(1))).values
    sig['macd_L']=mc_up&(c>e200); sig['macd_S']=mc_dn&(c<e200)
    # Momentum: close > close[N] (ROC>0) crossing
    for N in [10,20]:
        roc=c/np.roll(c,N)-1
        sig[f'mom{N}_L']=(roc>0)&(np.roll(roc,1)<=0)&(c>e200)
        sig[f'mom{N}_S']=(roc<0)&(np.roll(roc,1)>=0)&(c<e200)
    return sig,e200
