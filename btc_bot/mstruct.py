import pandas as pd, numpy as np, fvg_scan as F, causal_engine as E
# Фрактальні свінги (causal: підтверджені через k барів). Трендова структура HH/HL.
def swings(df,k=3):
    h,l=df['high'].values,df['low'].values;n=len(df)
    sh=np.full(n,np.nan);sl=np.full(n,np.nan)
    for i in range(k,n-k):
        if h[i]==max(h[i-k:i+k+1]) and h[i]>max(h[i-k:i]) : sh[i]=h[i]
        if l[i]==min(l[i-k:i+k+1]) and l[i]<min(l[i-k:i]) : sl[i]=l[i]
    return sh,sl

def signals_ms(df,k=3):
    h,l,c=df['high'].values,df['low'].values,df['close'].values;n=len(df)
    sh,sl=swings(df,k)
    # останній підтверджений свінг (доступний лише через k барів — causal)
    lastSH=np.full(n,np.nan);lastSL=np.full(n,np.nan)
    prevSH=np.full(n,np.nan);prevSL=np.full(n,np.nan)
    cSH=cSL=pSH=pSL=np.nan
    for i in range(n):
        j=i-k  # свінг на барі j підтверджується аж на i
        if j>=0:
            if not np.isnan(sh[j]): pSH=cSH;cSH=sh[j]
            if not np.isnan(sl[j]): pSL=cSL;cSL=sl[j]
        lastSH[i]=cSH;lastSL[i]=cSL;prevSH[i]=pSH;prevSL[i]=pSL
    up=(lastSH>prevSH)&(lastSL>prevSL)   # HH+HL
    dn=(lastSH<prevSH)&(lastSL<prevSL)   # LH+LL
    cp=np.roll(c,1)
    # BOS: закриття тіла над останнім свінг-high (у апструктурі) = продовження
    bos_L=up&(c>lastSH)&(cp<=lastSH)
    bos_S=dn&(c<lastSL)&(cp>=lastSL)
    return {'bosL':bos_L,'bosS':bos_S,'upTrend':up,'dnTrend':dn,'lastSH':lastSH,'lastSL':lastSL}

def posmonths(allt,risk,months=106.0):
    allt=sorted(allt,key=lambda x:x[0]);eq=1.0;rows=[]
    for t,R in allt: eq*=(1+risk*R);rows.append((pd.Timestamp(t),eq))
    e=pd.DataFrame(rows,columns=['t','e']);peak=np.maximum.accumulate(e['e'].values)
    dd=((peak-e['e'].values)/peak).max()
    e['ym']=e['t'].dt.to_period('M');mo=e.groupby('ym').agg(end=('e','last')).reset_index()
    mo['start']=mo['end'].shift(1).fillna(1.0);mo['ret']=mo['end']/mo['start']-1
    return (eq**(1/months)-1),dd,(mo.ret>0).mean(),len(mo),mo

if __name__=='__main__':
    print('Market-structure BOS (causal, 5bps). Метрика: %плюсових місяців')
    for tf in [60,240]:
        df=F.load(tf);S=signals_ms(df,3)
        for sm,tm in [(1.5,4.0),(2.0,6.0)]:
            tr=E.run(df,S['bosL'],S['bosS'],stop_mult=sm,exit_mode='trail',trail_mult=tm,slip_bps=5)
            d=E.stats(tr,0.02,ret=True)
            if d:
                dd,trades=d
                pm,ddv,posm,nmo,_=posmonths(trades,0.02)
                print('%4dm BOS sm%.1f tm%.1f | n=%4d expR=%+.3f OOS=%+.3f | %+5.2f%%/mo DD=%2.0f%% | плюс.міс=%.0f%% (%d)'%(
                    tf,sm,tm,dd['n'],dd['expR'],dd['OOS'],pm*100,ddv*100,posm*100,nmo))
