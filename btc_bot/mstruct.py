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

def signals_choch(df,k=3,sweepATR=0.25):
    # CHoCH (розворот) з підтвердженням через liquidity sweep: спершу wick проколює
    # останній свінг-лоу/хай (стоп-хант), close лишається з боку старого тренду,
    # потім CHoCH - перший злам структури у протилежний бік. Дзеркально для шорт.
    h,l,c=df['high'].values,df['low'].values,df['close'].values;n=len(df)
    a=E.atr(df)
    sh,sl=swings(df,k)
    lastSH=np.full(n,np.nan);lastSL=np.full(n,np.nan)
    prevSH=np.full(n,np.nan);prevSL=np.full(n,np.nan)
    cSH=cSL=pSH=pSL=np.nan
    for i in range(n):
        j=i-k
        if j>=0:
            if not np.isnan(sh[j]): pSH=cSH;cSH=sh[j]
            if not np.isnan(sl[j]): pSL=cSL;cSL=sl[j]
        lastSH[i]=cSH;lastSL[i]=cSL;prevSH[i]=pSH;prevSL[i]=pSL
    up=(lastSH>prevSH)&(lastSL>prevSL)
    dn=(lastSH<prevSH)&(lastSL<prevSL)
    cp=np.roll(c,1)
    chochL=np.zeros(n,bool);chochS=np.zeros(n,bool)
    sweptLow=False;sweptHigh=False
    for i in range(1,n):
        if dn[i] and not np.isnan(lastSL[i]) and l[i]<lastSL[i]-sweepATR*a[i] and c[i]>lastSL[i]:
            sweptLow=True
        if up[i] and not np.isnan(lastSH[i]) and h[i]>lastSH[i]+sweepATR*a[i] and c[i]<lastSH[i]:
            sweptHigh=True
        if dn[i] and sweptLow and c[i]>lastSH[i] and cp[i]<=lastSH[i]:
            chochL[i]=True; sweptLow=False
        if up[i] and sweptHigh and c[i]<lastSL[i] and cp[i]>=lastSL[i]:
            chochS[i]=True; sweptHigh=False
    return {'chochL':chochL,'chochS':chochS}

def posmonths(allt,risk,months=106.0):
    allt=sorted(allt,key=lambda x:x[0]);eq=1.0;rows=[]
    for t,R in allt: eq*=(1+risk*R);rows.append((pd.Timestamp(t),eq))
    e=pd.DataFrame(rows,columns=['t','e']);peak=np.maximum.accumulate(e['e'].values)
    dd=((peak-e['e'].values)/peak).max()
    e['ym']=e['t'].dt.to_period('M');mo=e.groupby('ym').agg(end=('e','last')).reset_index()
    mo['start']=mo['end'].shift(1).fillna(1.0);mo['ret']=mo['end']/mo['start']-1
    return (eq**(1/months)-1),dd,(mo.ret>0).mean(),len(mo),mo

def load_eth():
    p='/root/.claude/uploads/26e5ea76-e39e-5900-871b-43ddd9468ab1/1becf9f0-ETH_1D_tradingview_coinmarketcap.csv'
    d=pd.read_csv(p,sep=';')
    d.columns=[x.strip().strip('"').lower() for x in d.columns]
    d['dt']=pd.to_datetime(d['time'].astype(str).str.strip('"'))
    d=d.rename(columns={'volume':'vol'})
    return d[['dt','open','high','low','close','vol']].sort_values('dt').reset_index(drop=True)

if __name__=='__main__':
    import partial_pool as P
    print('=== BOS (trail-only, базовий) ===')
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

    print('\n=== CHoCH+sweep (trail-only) ===')
    for tf in [60,240,1440]:
        df=F.load(tf) if tf!=1440 else F.load(1440)
        for k in [3,5]:
            S=signals_choch(df,k)
            for sm,tm in [(1.5,4.0),(2.0,6.0)]:
                tr=E.run(df,S['chochL'],S['chochS'],stop_mult=sm,exit_mode='trail',trail_mult=tm,slip_bps=5)
                d=E.stats(tr,0.02,ret=True)
                if d:
                    dd,trades=d
                    pm,ddv,posm,nmo,_=posmonths(trades,0.02)
                    print('%4dm CHoCH k%d sm%.1f tm%.1f | n=%4d expR=%+.3f OOS=%+.3f | %+5.2f%%/mo DD=%2.0f%% | плюс.міс=%.0f%% (%d)'%(
                        tf,k,sm,tm,dd['n'],dd['expR'],dd['OOS'],pm*100,ddv*100,posm*100,nmo))

    print('\n=== BOS+CHoCH комбо з ЧАСТКОВОЮ фіксацією (partial_pool), пул BTC 4H+1D + ETH 1D ===')
    btc4=F.load(240); btc1d=F.load(1440); eth1d=load_eth()
    for k in [3,5]:
        Sb4=signals_ms(btc4,k); Cb4=signals_choch(btc4,k)
        Sb1=signals_ms(btc1d,k); Cb1=signals_choch(btc1d,k)
        Se1=signals_ms(eth1d,k); Ce1=signals_choch(eth1d,k)
        for part,tp1 in [(0.5,1.0),(0.6,1.0),(0.5,0.7)]:
            for sm,tm in [(1.5,4.0),(2.0,6.0)]:
                allt=[]
                allt+=P.run_partial(btc4,Sb4['bosL']|Cb4['chochL'],Sb4['bosS']|Cb4['chochS'],sm,tm,part,tp1)
                allt+=P.run_partial(btc1d,Sb1['bosL']|Cb1['chochL'],Sb1['bosS']|Cb1['chochS'],sm,tm,part,tp1)
                allt+=P.run_partial(eth1d,Se1['bosL']|Ce1['chochL'],Se1['bosS']|Ce1['chochS'],sm,tm,part,tp1)
                if len(allt)<30: continue
                Rs=np.array([r for _,r in allt])
                pm,ddv,posm,nmo,_=posmonths(allt,0.02)
                wk=len(allt)/(nmo*4.345) if nmo else 0
                print('k%d part%.1f tp%.1f sm%.1f tm%.1f | n=%4d win=%.2f | %+5.2f%%/mo DD=%2.0f%% плюс.міс=%.0f%%(%d) | %.1f угод/тиж'%(
                    k,part,tp1,sm,tm,len(allt),(Rs>0).mean(),pm*100,ddv*100,posm*100,nmo,wk))
