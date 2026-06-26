# Чесний розклад по режимах ринку + окремі стратегії для ВЕДМЕДЯ і БОКОВИКА.
# Режим за нахилом EMA200 на денному BTC: up / down / flat (за |нахил| і ціна vs EMA).
import numpy as np, pandas as pd, fvg_scan as F
import mstruct as M, partial_pool as P

def atr(df,n=14):
    h,l,c=df['high'].values,df['low'].values,df['close'].values
    pc=np.roll(c,1);pc[0]=c[0];tr=np.maximum(h-l,np.maximum(abs(h-pc),abs(l-pc)))
    return pd.Series(tr).ewm(alpha=1/n,adjust=False).mean().values

def regime(df, slope_win=20, flat_thr=0.003):
    # на кожному барі: нахил EMA200 за останні slope_win барів (норм. на ціну)
    c=df['close'].values
    e=pd.Series(c).ewm(span=200,adjust=False).mean().values
    sl=(e-np.roll(e,slope_win))/np.roll(e,slope_win)/slope_win
    reg=np.where(sl>flat_thr,'up',np.where(sl<-flat_thr,'down','flat'))
    reg[:slope_win+1]='flat'
    return reg, e, sl

btc1d=F.load(1440)
reg,e,sl=regime(btc1d)
# скільки часу ринок у кожному режимі
vc=pd.Series(reg).value_counts(normalize=True)
print('=== Частка часу по режимах (денний BTC) ===')
for k in ['up','down','flat']: print('  %-5s %.0f%%'%(k,vc.get(k,0)*100))

# дохідність buy&hold у кожному режимі (скільки можна було б зробити лонгом / втратити)
c=btc1d['close'].values;ret=np.diff(np.log(c));rr=reg[1:]
print('\n=== Сумарний рух ціни у кожному режимі (log-ret) ===')
for k in ['up','down','flat']:
    m=rr==k;print('  %-5s сума=%+.2f  бары=%d'%(k,ret[m].sum(),m.sum()))

# ----- ВЕДМІДЬ: шорт BOS у даунтренді -----
print('\n=== ВЕДМІДЬ: шорт по BOS коли close<EMA200, тільки down-режим ===')
def short_bear(df,risk=0.05,part=0.5,tp1=1.5,sm=2.0,tm=6.0,use_regime=True):
    S=M.signals_ms(df,3);c=df['close'].values
    e=pd.Series(c).ewm(span=200,adjust=False).mean().values
    rg,_,_=regime(df)
    sS=S['bosS']&(c<e)
    if use_regime: sS=sS&(rg=='down')
    NO=np.zeros(len(df),bool)
    return sorted(P.run_partial(df,NO,sS,sm,tm,part,tp1,slip_bps=5),key=lambda x:x[0])
for tf in [240,1440]:
    df=F.load(tf)
    for ureg in [False,True]:
        a=short_bear(df,use_regime=ureg)
        if len(a)<10: print('  TF%d reg=%s замало(n=%d)'%(tf,ureg,len(a)));continue
        R=np.array([r for _,r in a]);pm,dd,posm,nmo,_=M.posmonths(a,0.05)
        print('  TF%4d down-filter=%-5s | n=%3d win=%.2f expR=%+.3f | %+5.2f%%/mo DD=%2.0f%% плюс.міс=%.0f%%'%(
            tf,str(ureg),len(a),(R>0).mean(),R.mean(),pm*100,dd*100,posm*100))

# ----- БОКОВИК: mean-reversion у flat-режимі -----
print('\n=== БОКОВИК: RSI mean-reversion тільки у flat-режимі ===')
def rsi(c,n=14):
    s=pd.Series(c);d=s.diff();up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean()
    dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean();return (100-100/(1+up/dn)).values
def mr_flat(df,lo=30,hi=70,sm=1.5,rr=1.5,risk=0.02):
    o,h,l,c=df['open'].values,df['high'].values,df['low'].values,df['close'].values
    a=atr(df);rs=rsi(c);rg,_,_=regime(df);n=len(df);dt=df['dt'].values
    tr=[];pos=0;entry=stop=take=feeR=0;pend=0
    for i in range(1,n):
        if pos==0 and pend!=0 and a[i]>0:
            if pend==1: entry=o[i];stop=entry-sm*a[i];take=entry+rr*sm*a[i]
            else: entry=o[i];stop=entry+sm*a[i];take=entry-rr*sm*a[i]
            feeR=2*0.0006*entry/(sm*a[i]);pos=pend;pend=0
        if pos==1:
            if l[i]<=stop: tr.append((dt[i],-1-feeR));pos=0
            elif h[i]>=take: tr.append((dt[i],rr-feeR));pos=0
        elif pos==-1:
            if h[i]>=stop: tr.append((dt[i],-1-feeR));pos=0
            elif l[i]<=take: tr.append((dt[i],rr-feeR));pos=0
        if pos==0 and pend==0 and rg[i]=='flat':
            if rs[i-1]>=lo and rs[i]<lo: pend=1
            elif rs[i-1]<=hi and rs[i]>hi: pend=-1
    return sorted(tr,key=lambda x:x[0])
for tf in [60,240]:
    df=F.load(tf)
    for lo,hi in [(30,70),(25,75),(20,80)]:
        a=mr_flat(df,lo,hi)
        if len(a)<20: continue
        R=np.array([r for _,r in a]);pm,dd,posm,nmo,_=M.posmonths(a,0.02)
        cut=int(len(R)*0.7)
        print('  TF%4d RSI%d/%d | n=%3d win=%.2f expR=%+.3f IS=%+.2f OOS=%+.2f | %+5.2f%%/mo DD=%2.0f%% плюс=%.0f%%'%(
            tf,lo,hi,len(a),(R>0).mean(),R.mean(),R[:cut].mean(),R[cut:].mean(),pm*100,dd*100,posm*100))
