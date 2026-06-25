import pandas as pd, numpy as np, fvg_scan as F
FEE=0.0006
def atr(df,n=14):
    h,l,c=df['high'].values,df['low'].values,df['close'].values
    pc=np.roll(c,1);pc[0]=c[0]
    tr=np.maximum(h-l,np.maximum(abs(h-pc),abs(l-pc)))
    return pd.Series(tr).ewm(alpha=1/n,adjust=False).mean().values
def rsi(s,n=14):
    s=pd.Series(s);d=s.diff();up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean();dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return (100-100/(1+up/dn)).values
def adx(df,n=14):
    h,l,c=df['high'].values,df['low'].values,df['close'].values
    up=h[1:]-h[:-1];dn=l[:-1]-l[1:]
    plus=np.where((up>dn)&(up>0),up,0.0);minus=np.where((dn>up)&(dn>0),dn,0.0)
    pc=c[:-1];tr=np.maximum(h[1:]-l[1:],np.maximum(abs(h[1:]-pc),abs(l[1:]-pc)))
    tr=np.concatenate([[0],tr]);plus=np.concatenate([[0],plus]);minus=np.concatenate([[0],minus])
    atrn=pd.Series(tr).ewm(alpha=1/n,adjust=False).mean()
    pdi=100*pd.Series(plus).ewm(alpha=1/n,adjust=False).mean()/atrn
    mdi=100*pd.Series(minus).ewm(alpha=1/n,adjust=False).mean()/atrn
    dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    return dx.ewm(alpha=1/n,adjust=False).mean().values

def test(df, regime='adx', adx_max=20, bbw_q=0.4, side='both', rr=1.0, stop_mult=1.5, risk=0.02, rsi_lo=30, rsi_hi=70):
    o,h,l,c=df['open'].values,df['high'].values,df['low'].values,df['close'].values
    a=atr(df);rs=rsi(c);ad=adx(df);n=len(df)
    sma20=pd.Series(c).rolling(20).mean().values;sd20=pd.Series(c).rolling(20).std().values
    bbw=(2*sd20)/sma20  # band width normalized
    bbw_thr=np.nanquantile(bbw,bbw_q)
    if regime=='adx': rng=ad<adx_max
    elif regime=='bbw': rng=bbw<bbw_thr
    else: rng=(ad<adx_max)&(bbw<bbw_thr)
    tr=[];inpos=False;entry=stop=take=feeR=0;pdir=0;ei=0
    for i in range(21,n):
        if inpos:
            if pdir==1:
                if l[i]<=stop: tr.append((ei,i,-1.0-feeR));inpos=False
                elif h[i]>=take: tr.append((ei,i,rr-feeR));inpos=False
            else:
                if h[i]>=stop: tr.append((ei,i,-1.0-feeR));inpos=False
                elif l[i]<=take: tr.append((ei,i,rr-feeR));inpos=False
        if not inpos and rng[i] and a[i]>0:
            # mean-reversion: buy oversold, sell overbought
            if side in('both','long') and rs[i-1]>=rsi_lo and rs[i]<rsi_lo:
                entry=c[i];stop=entry-stop_mult*a[i];take=entry+rr*(entry-stop);feeR=2*FEE*entry/(entry-stop);pdir=1;ei=i;inpos=True
            elif side in('both','short') and rs[i-1]<=rsi_hi and rs[i]>rsi_hi:
                entry=c[i];stop=entry+stop_mult*a[i];take=entry-rr*(stop-entry);feeR=2*FEE*entry/(stop-entry);pdir=-1;ei=i;inpos=True
    if not tr: return None
    tr=sorted(tr,key=lambda t:t[1]);Rs=np.array([t[2] for t in tr]);cut=int(len(Rs)*0.7)
    eq=1.0;peak=1.0;dd=0
    for R in Rs: eq*=(1+risk*R);peak=max(peak,eq);dd=max(dd,(peak-eq)/peak)
    months=(df['dt'].iloc[-1]-df['dt'].iloc[0]).days/30.4
    return dict(n=len(Rs),win=(Rs>0).mean(),expR=Rs.mean(),IS=Rs[:cut].mean(),OOS=Rs[cut:].mean(),pm=eq**(1/months)-1,dd=dd)

if __name__=='__main__':
    for tf in [240,60]:
        df=F.load(tf)
        print(f'\n=== TF={tf}m — MR у боковику ===')
        for reg,p in [('adx',15),('adx',20),('adx',25),('bbw',0.3),('bbw',0.4),('both',20)]:
            for side in ['both','long','short']:
                for rr in [1.0,1.5]:
                    kw=dict(regime=reg,side=side,rr=rr)
                    if reg=='bbw': kw['bbw_q']=p
                    else: kw['adx_max']=p
                    r=test(df,**kw)
                    if r and r['n']>=30:
                        tag=f'{reg}{p}'
                        print('  %-8s %-5s rr%s | n=%4d win=%.2f expR=%+.3f IS=%+.3f OOS=%+.3f | %+.2f%%/mo DD=%.0f%%'%(tag,side,rr,r['n'],r['win'],r['expR'],r['IS'],r['OOS'],r['pm']*100,r['dd']*100))
