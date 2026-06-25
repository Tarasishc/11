import pandas as pd, numpy as np
import fvg_scan as F
FEE=0.0006

def atr(df,n=14):
    h,l,c=df['high'].values,df['low'].values,df['close'].values
    pc=np.roll(c,1);pc[0]=c[0]
    tr=np.maximum(h-l,np.maximum(abs(h-pc),abs(l-pc)))
    return pd.Series(tr).ewm(alpha=1/n,adjust=False).mean().values

def run(df, entry_mode='edge', exit_mode='rr', rr=2.0, gap_tp=1.5,
        use_trend=True, side='long', stop_buf=0.5, max_wait=80,
        min_gap_atr=0.25, risk=0.02, swing_lb=10):
    o=df['open'].values;h=df['high'].values;l=df['low'].values;c=df['close'].values
    a=atr(df);e200=df['close'].ewm(span=200,adjust=False).mean().values;n=len(df)
    pend=[];trades=[]
    inpos=False;entry=stop=take=0;pdir=0;feeR=0
    for i in range(3,n):
        if inpos:
            if pdir==1:
                if l[i]<=stop: trades.append((-1.0-feeR,i));inpos=False
                elif exit_mode!='none' and h[i]>=take: trades.append(((take-entry)/(entry-stop)-feeR,i));inpos=False
            else:
                if h[i]>=stop: trades.append((-1.0-feeR,i));inpos=False
                elif exit_mode!='none' and l[i]<=take: trades.append(((entry-take)/(stop-entry)-feeR,i));inpos=False
        # detect FVG
        if h[i-2]<l[i]:
            g=l[i]-h[i-2]
            if g>min_gap_atr*a[i]: pend.append({'dir':1,'top':l[i],'bot':h[i-2],'born':i})
        if l[i-2]>h[i]:
            g=l[i-2]-h[i]
            if g>min_gap_atr*a[i]: pend.append({'dir':-1,'top':l[i-2],'bot':h[i],'born':i})
        if not inpos:
            for z in pend:
                if z.get('used') or i-z['born']<1 or i-z['born']>max_wait:
                    if i-z['born']>max_wait: z['used']=True
                    continue
                mid=(z['top']+z['bot'])/2
                if z['dir']==1 and side in('long','both'):
                    if use_trend and not c[i]>e200[i]: continue
                    trig = z['top'] if entry_mode=='edge' else mid
                    if l[i]<=trig and h[i]>=z['bot']:
                        ent=trig; st=z['bot']-stop_buf*a[i]; rd=ent-st
                        if rd<=0: z['used']=True;continue
                        feeR=2*FEE*ent/rd
                        if l[i]<=st: trades.append((-1.0-feeR,i));z['used']=True;break
                        if exit_mode=='rr': take=ent+rr*rd
                        elif exit_mode=='gap': take=ent+gap_tp*(z['top']-z['bot'])
                        elif exit_mode=='swing': take=np.max(h[max(0,i-swing_lb):i+1])
                        if take<=ent: z['used']=True;continue
                        entry=ent;stop=st;pdir=1;inpos=True;z['used']=True;break
                elif z['dir']==-1 and side in('short','both'):
                    if use_trend and not c[i]<e200[i]: continue
                    trig = z['bot'] if entry_mode=='edge' else mid
                    if h[i]>=trig and l[i]<=z['top']:
                        ent=trig; st=z['top']+stop_buf*a[i]; rd=st-ent
                        if rd<=0: z['used']=True;continue
                        feeR=2*FEE*ent/rd
                        if h[i]>=st: trades.append((-1.0-feeR,i));z['used']=True;break
                        if exit_mode=='rr': take=ent-rr*rd
                        elif exit_mode=='gap': take=ent-gap_tp*(z['top']-z['bot'])
                        elif exit_mode=='swing': take=np.min(l[max(0,i-swing_lb):i+1])
                        if take>=ent: z['used']=True;continue
                        entry=ent;stop=st;pdir=-1;inpos=True;z['used']=True;break
        pend=[z for z in pend if not z.get('used') and i-z['born']<=max_wait]
    if not trades: return None
    Rs=np.array([t[0] for t in trades]);cut=int(len(Rs)*0.7)
    eq=1.0;peak=1.0;dd=0
    for R in Rs: eq*=(1+risk*R);peak=max(peak,eq);dd=max(dd,(peak-eq)/peak)
    months=(df['dt'].iloc[-1]-df['dt'].iloc[0]).days/30.4
    return dict(n=len(Rs),win=(Rs>0).mean(),expR=Rs.mean(),permo=eq**(1/months)-1,dd=dd,
                isR=Rs[:cut].mean(),oosR=Rs[cut:].mean())

def show(tag,r):
    if not r: print(f'{tag}: немає угод');return
    print(f'{tag:42}| n={r["n"]:4} win={r["win"]:.2f} expR={r["expR"]:+.3f} IS={r["isR"]:+.3f} OOS={r["oosR"]:+.3f} | {r["permo"]*100:+.2f}%/mo DD={r["dd"]*100:.0f}%')

for tf in [240, 1440]:
    df=F.load(tf)
    print(f'\n===== TF={tf}m =====')
    show('базлайн edge+rr2', run(df,'edge','rr',rr=2.0))
    show('(A) вхід 50% гепу + rr2', run(df,'mid','rr',rr=2.0))
    show('(B) тейк 1.5x геп, edge', run(df,'edge','gap',gap_tp=1.5))
    show('(B) тейк 2.5x геп, edge', run(df,'edge','gap',gap_tp=2.5))
    show('(A+B) 50% + тейк swing', run(df,'mid','swing',swing_lb=12))
    show('(A) вхід 50% + тейк 2x геп', run(df,'mid','gap',gap_tp=2.0))
