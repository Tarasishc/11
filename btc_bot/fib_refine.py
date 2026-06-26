import pandas as pd, numpy as np, fvg_scan as F
def atr(df,n=14):
    h,l,c=df['high'].values,df['low'].values,df['close'].values
    pc=np.roll(c,1);pc[0]=c[0]
    tr=np.maximum(h-l,np.maximum(abs(h-pc),abs(l-pc)))
    return pd.Series(tr).ewm(alpha=1/n,adjust=False).mean().values
def rsi(c,n=14):
    s=pd.Series(c);d=s.diff();up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean();dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
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

def fib_trades(tf,side,rr,lb=10,fib=0.886,stop_buf=0.5,slip_bps=0.0):
    df=F.load(tf);o,h,l,c=df['open'].values,df['high'].values,df['low'].values,df['close'].values
    a=atr(df);n=len(df);e200=df['close'].ewm(span=200,adjust=False).mean().values
    e50=df['close'].ewm(span=50,adjust=False).mean().values
    rs=rsi(c);ad=adx(df);v=df['vol'].values;vma=pd.Series(v).rolling(20).mean().values
    sh=pd.Series(h).rolling(lb).max().values;sl=pd.Series(l).rolling(lb).min().values;dt=df['dt'].values
    slip=slip_bps/10000.0
    rows=[];inpos=False;entry=stop=take=feeR=0;pdir=0;ctx=None
    for i in range(lb+1,n):
        if inpos:
            R=None
            if pdir==1:
                if l[i]<=stop: R=-1.0-feeR
                elif h[i]>=take: R=rr-feeR
            else:
                if h[i]>=stop: R=-1.0-feeR
                elif l[i]<=take: R=rr-feeR
            if R is not None: rows.append({**ctx,'R':R,'exit':dt[i]});inpos=False
        if not inpos and a[i]>0:
            rng=sh[i-1]-sl[i-1]
            if rng<=0: continue
            ctxb=dict(rsi=rs[i],adx=ad[i],vrel=v[i]/vma[i] if vma[i]>0 else 1.0,
                      rngatr=rng/a[i],ext200=(c[i]-e200[i])/e200[i]*100,
                      e50_200=(e50[i]-e200[i])/e200[i]*100)
            if side=='long' and c[i]>e200[i]:
                lvl=sh[i-1]-fib*rng
                if l[i]<=lvl and c[i]>sl[i-1]:
                    entry=lvl*(1+slip);stop=sl[i-1]-stop_buf*a[i]
                    if entry-stop<=0: continue
                    feeR=2*6e-4*entry/(entry-stop);take=entry+rr*(entry-stop);pdir=1;ctx=ctxb;inpos=True
            elif side=='short' and c[i]<e200[i]:
                lvl=sl[i-1]+fib*rng
                if h[i]>=lvl and c[i]<sh[i-1]:
                    entry=lvl*(1-slip);stop=sh[i-1]+stop_buf*a[i]
                    if stop-entry<=0: continue
                    feeR=2*6e-4*entry/(stop-entry);take=entry-rr*(stop-entry);pdir=-1;ctx=ctxb;inpos=True
    d=pd.DataFrame(rows);d['side']=side;d['tf']=tf
    return d

def poolstats(d,risk=0.01,label=''):
    d=d.sort_values('exit');Rs=d['R'].values
    if len(Rs)<30: return
    cut=int(len(Rs)*0.7);eq=1.0;peak=1.0;dd=0
    for R in Rs: eq*=(1+risk*R);peak=max(peak,eq);dd=max(dd,(peak-eq)/peak)
    months=106.0
    print('%-30s| n=%4d win=%.2f expR=%+.3f IS=%+.3f OOS=%+.3f | %+6.2f%%/mo DD=%2.0f%%'%(
        label,len(Rs),(Rs>0).mean(),Rs.mean(),Rs[:cut].mean(),Rs[cut:].mean(),(eq**(1/months)-1)*100,dd*100))
