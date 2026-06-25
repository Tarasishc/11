import pandas as pd, numpy as np, fvg_scan as F
FEE=0.0006
def atr(df,n=14):
    h,l,c=df['high'].values,df['low'].values,df['close'].values
    pc=np.roll(c,1);pc[0]=c[0]
    tr=np.maximum(h-l,np.maximum(abs(h-pc),abs(l-pc)))
    return pd.Series(tr).ewm(alpha=1/n,adjust=False).mean().values
def rsi(s,n=14):
    d=s.diff();up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean();dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return (100-100/(1+up/dn)).values

# each stream returns list of trades: (entry_bar, exit_bar, R) with fee already in R
def trail_long(df,enter_mask,stop_mult,trail_mult):
    o,h,l,c=df['open'].values,df['high'].values,df['low'].values,df['close'].values
    a=atr(df);n=len(df);tr=[]
    inpos=False;stop=ext=entry=feeR=0
    for i in range(1,n):
        if inpos:
            ext=max(ext,h[i]);stop=max(stop,ext-trail_mult*a[i])
            if l[i]<=stop: tr.append((ei,i,(stop-entry)/(entry-istop)-feeR));inpos=False
        if not inpos and enter_mask[i] and a[i]>0:
            entry=c[i];istop=c[i]-stop_mult*a[i];stop=istop;ext=h[i];feeR=2*FEE*entry/(entry-istop);ei=i;inpos=True
    return tr

def fixed_rr_long(df,enter_mask,stop_mult,rr):
    o,h,l,c=df['open'].values,df['high'].values,df['low'].values,df['close'].values
    a=atr(df);n=len(df);tr=[]
    inpos=False;stop=take=entry=feeR=0;ei=0
    for i in range(1,n):
        if inpos:
            if l[i]<=stop: tr.append((ei,i,-1.0-feeR));inpos=False
            elif h[i]>=take: tr.append((ei,i,rr-feeR));inpos=False
        if not inpos and enter_mask[i] and a[i]>0:
            entry=c[i];stop=c[i]-stop_mult*a[i];take=entry+rr*(entry-stop);feeR=2*FEE*entry/(entry-stop);ei=i;inpos=True
    return tr

def fvg_rsi_trades(df,rr=2.0,stop_buf=0.5,max_wait=80,min_gap_atr=0.25):
    h,l,c=df['high'].values,df['low'].values,df['close'].values
    a=atr(df);e200=df['close'].ewm(span=200,adjust=False).mean().values;rs=rsi(df['close']);n=len(df)
    pend=[];tr=[];inpos=False;entry=stop=feeR=0;ei=0
    for i in range(3,n):
        if inpos:
            if l[i]<=stop: tr.append((ei,i,-1.0-feeR));inpos=False
            elif h[i]>=entry+rr*(entry-stop): tr.append((ei,i,rr-feeR));inpos=False
        if h[i-2]<l[i]:
            g=l[i]-h[i-2]
            if g>min_gap_atr*a[i]: pend.append({'top':l[i],'bot':h[i-2],'born':i})
        if not inpos:
            for z in pend:
                if z.get('used') or i-z['born']<1 or i-z['born']>max_wait:
                    if i-z['born']>max_wait: z['used']=True
                    continue
                if not (c[i]>e200[i] and rs[i]>50): continue
                if l[i]<=z['top'] and h[i]>=z['bot']:
                    ent=z['top'];st=z['bot']-stop_buf*a[i];rd=ent-st
                    if rd<=0: z['used']=True;continue
                    feeR=2*FEE*ent/rd
                    if l[i]<=st: tr.append((i,i,-1.0-feeR));z['used']=True;break
                    entry=ent;stop=st;ei=i;inpos=True;z['used']=True;break
        pend=[z for z in pend if not z.get('used') and i-z['born']<=max_wait]
    return tr

def build(df):
    c=df['close'];n=len(df)
    e200=c.ewm(span=200,adjust=False).mean().values
    up=(c.rolling(20).mean()+2*c.rolling(20).std()).values
    rs2=rsi(c,2)
    hlc3=(df['high']+df['low']+df['close'])/3
    esa=hlc3.ewm(span=9,adjust=False).mean();de=(hlc3-esa).abs().ewm(span=9,adjust=False).mean()
    ci=(hlc3-esa)/(0.015*de);wt1=ci.ewm(span=12,adjust=False).mean();wt2=wt1.rolling(3).mean()
    cv=c.values
    bb=np.zeros(n,bool);rsi2m=np.zeros(n,bool);vmc=np.zeros(n,bool)
    for i in range(1,n):
        if cv[i]>e200[i]:
            if cv[i-1]<=up[i-1] and cv[i]>up[i]: bb[i]=True
            if rs2[i-1]>=10 and rs2[i]<10: rsi2m[i]=True
            w1,w2=wt1.values,wt2.values
            if w1[i-1]<=w2[i-1] and w1[i]>w2[i] and w2[i]<=-53: vmc[i]=True
    streams={
      'BB-breakout': trail_long(df,bb,1.5,4.0),
      'VMC-oversold': trail_long(df,vmc,1.5,4.0),
      'RSI2-dip': fixed_rr_long(df,rsi2m,1.5,2.0),
      'FVG-RSI>50': fvg_rsi_trades(df),
    }
    return streams

def equity(trades,risk,months):
    if not trades: return None
    trades=sorted(trades,key=lambda t:t[1])
    eq=1.0;peak=1.0;dd=0
    for _,_,R in trades:
        eq*=(1+risk*R);peak=max(peak,eq);dd=max(dd,(peak-eq)/peak)
    return eq**(1/months)-1,dd,len(trades),eq

df=F.load(240);months=(df['dt'].iloc[-1]-df['dt'].iloc[0]).days/30.4
S=build(df)
print(f'BTC 4H, {months:.0f} міс. Окремі стріми (ризик 2%):')
allt=[]
for name,tr in S.items():
    Rs=np.array([t[2] for t in tr]);cut=int(len(Rs)*0.7)
    pm,dd,n,eq=equity(tr,0.02,months)
    print(f'  {name:14}| n={n:4} expR={Rs.mean():+.3f} OOS={Rs[cut:].mean():+.3f} | {pm:+.2%}/mo DD={dd:.0%}')
    allt+=tr
print('\nПУЛ (усі 4 разом), розгортка ризику:')
for risk in [0.015,0.02,0.025,0.03,0.04]:
    pm,dd,n,eq=equity(allt,risk,months)
    wk=n/(months*4.33)
    print(f'  ризик {risk:.1%}/угоду: {pm:+.2%}/міс  DD={dd:.0%}  n={n} ({wk:.1f}/тиж)')
