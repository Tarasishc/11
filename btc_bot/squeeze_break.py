# Пробій боковика (squeeze breakout) у БУДЬ-ЯКИЙ бік зі стопом.
# Ідея: знайти стиснення (вузький діапазон/низька волатильність = боковик),
# зайти на пробої межі коробки в той бік, куди пробило. Стоп - інша межа.
# Працює і в боковику, і у ведмеді (шорт на пробій вниз). Двосторонній.
# Перевіряємо: causal, прослизання, по роках, ЗАЛЕЖНІСТЬ ВІД ВИКИДІВ.
import numpy as np, pandas as pd, fvg_scan as F, mstruct as M

def atr(df,n=14):
    h,l,c=df['high'].values,df['low'].values,df['close'].values
    pc=np.roll(c,1);pc[0]=c[0];tr=np.maximum(h-l,np.maximum(abs(h-pc),abs(l-pc)))
    return pd.Series(tr).ewm(alpha=1/n,adjust=False).mean().values

def run_squeeze(df, box=20, squeeze_q=0.4, sm=1.0, part=0.5, tp1=1.5, tm=4.0,
                slip_bps=5, lookback=200):
    o,h,l,c=df['open'].values,df['high'].values,df['low'].values,df['close'].values
    a=atr(df);n=len(df);dt=df['dt'].values;slip=slip_bps/1e4
    # коробка: highest/lowest за box барів (зсув 1 - causal)
    hh=pd.Series(h).rolling(box).max().shift(1).values
    ll=pd.Series(l).rolling(box).min().shift(1).values
    width=(hh-ll)/c  # відносна ширина коробки
    # squeeze = ширина в нижньому квантилі за ковзним вікном
    wq=pd.Series(width).rolling(lookback).quantile(squeeze_q).values
    tr=[];pos=0;entry=stop=feeR=ext=initR=0;pend=0;pdir=0;took=False
    for i in range(1,n):
        if pos==0 and pend!=0 and a[i]>0:
            risk=sm*a[i]
            if pend==1: entry=o[i]*(1+slip);stop=entry-risk;ext=h[i]
            else: entry=o[i]*(1-slip);stop=entry+risk;ext=l[i]
            initR=risk;feeR=2*0.0006*entry/risk;pos=pend;pdir=pend;pend=0;took=False
        if pos==1:
            if not took and h[i]>=entry+tp1*initR: tr.append((dt[i],part*(tp1-feeR)));took=True
            ext=max(ext,h[i]);stop=max(stop,ext-tm*a[i])
            if l[i]<=stop: tr.append((dt[i],((1-part) if took else 1.0)*((stop-entry)/initR-feeR)));pos=0
        elif pos==-1:
            if not took and l[i]<=entry-tp1*initR: tr.append((dt[i],part*(tp1-feeR)));took=True
            ext=min(ext,l[i]);stop=min(stop,ext+tm*a[i])
            if h[i]>=stop: tr.append((dt[i],((1-part) if took else 1.0)*((entry-stop)/initR-feeR)));pos=0
        if pos==0 and pend==0 and not np.isnan(wq[i]) and width[i]<=wq[i] and a[i]>0:
            # боковик підтверджено (вузька коробка). Пробій межі тілом close.
            if c[i]>hh[i]: pend=1
            elif c[i]<ll[i]: pend=-1
    return sorted(tr,key=lambda x:x[0])

def report(a,risk,label):
    if len(a)<20: print('  %s замало(n=%d)'%(label,len(a)));return
    R=np.array([r for _,r in a]);cut=int(len(R)*0.7)
    pm,dd,posm,nmo,_=M.posmonths(a,risk)
    print('  %-22s n=%3d win=%.2f expR=%+.3f IS=%+.2f OOS=%+.2f | %+5.2f%%/mo DD=%2.0f%% плюс=%.0f%%'%(
        label,len(a),(R>0).mean(),R.mean(),R[:cut].mean(),R[cut:].mean(),pm*100,dd*100,posm*100))

if __name__=='__main__':
    print('=== SQUEEZE BREAKOUT двосторонній, causal 5bps, risk2% ===')
    for tf in [60,240,1440]:
        df=F.load(tf)
        for sq in [0.3,0.4]:
            for sm,tm in [(1.0,4.0),(1.5,6.0)]:
                a=run_squeeze(df,box=20,squeeze_q=sq,sm=sm,tm=tm)
                report(a,0.02,'TF%d sq%.1f sm%.1f tm%.1f'%(tf,sq,sm,tm))
    print('\n=== ПУЛ BTC4H+BTC1D+ETH1D (sq0.3 sm1.5 tm6.0) ===')
    btc4=F.load(240);btc1d=F.load(1440);eth1d=M.load_eth()
    allt=[]
    for df in [btc4,btc1d,eth1d]:
        allt+=run_squeeze(df,box=20,squeeze_q=0.3,sm=1.5,tm=6.0)
    allt=sorted(allt,key=lambda x:x[0])
    report(allt,0.02,'ПУЛ')
    R=np.array([r for _,r in allt]);Rs=np.sort(R)[::-1];tot=R.sum()
    print('  --- викиди: усього R=%.1f, топ-3=%.0f%% топ-5=%.0f%% топ-10=%.0f%%'%(
        tot,Rs[:3].sum()/tot*100,Rs[:5].sum()/tot*100,Rs[:10].sum()/tot*100))
    for cut in [3,5,10]:
        print('    без топ-%d: expR=%+.3f'%(cut,np.sort(R)[::-1][cut:].mean()))

    print('\n=== доходність по роках (пул, risk2%) ===')
    dd=pd.DataFrame([(pd.Timestamp(t).year,r) for t,r in allt],columns=['y','R'])
    for y,g in dd.groupby('y'):
        eq=1.0
        for r in g['R']: eq*=(1+0.02*r)
        print('    %d | угод=%3d  %+6.1f%%'%(y,len(g),(eq-1)*100))

    print('\n=== доходність у ВЕДМЕЖІ/БОКОВІ місяці (BTC місячний знак) ===')
    bm=btc1d.copy();bm['ym']=pd.to_datetime(bm['dt']).dt.to_period('M')
    mc=bm.groupby('ym')['close'].last();mret=mc.pct_change()
    bear=set(mret[mret<-0.02].index.astype(str));flat=set(mret[(mret>=-0.02)&(mret<=0.02)].index.astype(str))
    eqB=eqF=1.0;nB=nF=0
    for t,r in allt:
        ym=str(pd.Timestamp(t).to_period('M'))
        if ym in bear: eqB*=(1+0.02*r);nB+=1
        elif ym in flat: eqF*=(1+0.02*r);nF+=1
    print('    у ведмежі міс: %+.1f%% (%d угод)'%((eqB-1)*100,nB))
    print('    у боковi міс:  %+.1f%% (%d угод)'%((eqF-1)*100,nF))
