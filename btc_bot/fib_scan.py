import pandas as pd, numpy as np, fvg_scan as F
FEE=0.0006
def atr(df,n=14):
    h,l,c=df['high'].values,df['low'].values,df['close'].values
    pc=np.roll(c,1);pc[0]=c[0]
    tr=np.maximum(h-l,np.maximum(abs(h-pc),abs(l-pc)))
    return pd.Series(tr).ewm(alpha=1/n,adjust=False).mean().values

# Свінги по фракталах (lookback). У аптренді: відкат до fib-рівня попередньої ноги -> лонг.
def fib_test(df, lb=20, fib=0.618, side='long', rr=2.0, stop_buf=0.5, trend=True, risk=0.02, max_wait=40):
    o,h,l,c=df['open'].values,df['high'].values,df['low'].values,df['close'].values
    a=atr(df); n=len(df)
    e200=df['close'].ewm(span=200,adjust=False).mean().values
    # rolling swing high/low
    sh=pd.Series(h).rolling(lb).max().values
    sl=pd.Series(l).rolling(lb).min().values
    tr=[];inpos=False;entry=stop=take=feeR=0;pdir=0;ei=0
    for i in range(lb+1,n):
        if inpos:
            if pdir==1:
                if l[i]<=stop: tr.append((ei,i,-1.0-feeR));inpos=False
                elif h[i]>=take: tr.append((ei,i,rr-feeR));inpos=False
            else:
                if h[i]>=stop: tr.append((ei,i,-1.0-feeR));inpos=False
                elif l[i]<=take: tr.append((ei,i,rr-feeR));inpos=False
        if not inpos and a[i]>0:
            rng=sh[i-1]-sl[i-1]
            if rng<=0: continue
            if side=='long' and (not trend or c[i]>e200[i]):
                lvl=sh[i-1]-fib*rng  # відкат униз від хая
                if l[i]<=lvl and c[i]>sl[i-1]:
                    entry=lvl; stop=sl[i-1]-stop_buf*a[i]
                    if entry-stop<=0: continue
                    feeR=2*FEE*entry/(entry-stop); take=entry+rr*(entry-stop); pdir=1;ei=i;inpos=True
            elif side=='short' and (not trend or c[i]<e200[i]):
                lvl=sl[i-1]+fib*rng
                if h[i]>=lvl and c[i]<sh[i-1]:
                    entry=lvl; stop=sh[i-1]+stop_buf*a[i]
                    if stop-entry<=0: continue
                    feeR=2*FEE*entry/(stop-entry); take=entry-rr*(stop-entry); pdir=-1;ei=i;inpos=True
    if not tr: return None
    tr=sorted(tr,key=lambda t:t[1]); Rs=np.array([t[2] for t in tr]); cut=int(len(Rs)*0.7)
    eq=1.0;peak=1.0;dd=0
    for R in Rs: eq*=(1+risk*R);peak=max(peak,eq);dd=max(dd,(peak-eq)/peak)
    months=(df['dt'].iloc[-1]-df['dt'].iloc[0]).days/30.4
    return dict(n=len(Rs),win=(Rs>0).mean(),expR=Rs.mean(),IS=Rs[:cut].mean(),OOS=Rs[cut:].mean(),pm=eq**(1/months)-1,dd=dd)

if __name__=='__main__':
    fibs=[0.236,0.382,0.5,0.618,0.705,0.786,0.886]
    best=[]
    for tf in [60,240,1440]:
        df=F.load(tf)
        for lb in [10,20,34,50]:
            for fib in fibs:
                for side in ['long','short']:
                    for rr in [1.5,2.0,3.0]:
                        r=fib_test(df,lb=lb,fib=fib,side=side,rr=rr)
                        if r and r['n']>=40 and r['expR']>0 and r['OOS']>0:
                            best.append((tf,lb,fib,side,rr,r))
    best.sort(key=lambda x:-x[5]['pm'])
    print('ТОП фіба-конфіги (expR>0 І OOS>0), сорт за %/міс:')
    print('%4s %3s %5s %5s %3s | %4s %4s %7s %7s %7s | %8s %5s'%('tf','lb','fib','side','rr','n','win','expR','IS','OOS','%/mo','DD'))
    for tf,lb,fib,side,rr,r in best[:25]:
        print('%4d %3d %5.3f %5s %3.1f | %4d %.2f %+7.3f %+7.3f %+7.3f | %+7.2f%% %4.0f%%'%(
            tf,lb,fib,side,rr,r['n'],r['win'],r['expR'],r['IS'],r['OOS'],r['pm']*100,r['dd']*100))
