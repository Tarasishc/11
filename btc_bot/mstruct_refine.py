# Вдосконалення фрактальної стратегії: фільтри тренду EMA, мульти-ТФ конфлюенс,
# фільтр сили свінгу, фільтр близькості входу до свінгу. Усе causal, partial-exit.
import numpy as np, pandas as pd, fvg_scan as F, causal_engine as E
import mstruct as M, partial_pool as P

def ema(c,n): return pd.Series(c).ewm(span=n,adjust=False).mean().values

def filt_signals(df,k=3,trend_ema=0,combo='bos+choch'):
    S=M.signals_ms(df,k); C=M.signals_choch(df,k)
    c=df['close'].values
    if combo=='bos': L=S['bosL'].copy();Sx=S['bosS'].copy()
    elif combo=='choch': L=C['chochL'].copy();Sx=C['chochS'].copy()
    else: L=S['bosL']|C['chochL'];Sx=S['bosS']|C['chochS']
    if trend_ema>0:
        e=ema(c,trend_ema)
        L=L&(c>e); Sx=Sx&(c<e)
    return L,Sx

def run_pool(specs,k,trend_ema,combo,part,tp1,sm,tm):
    allt=[]
    for df in specs:
        L,Sx=filt_signals(df,k,trend_ema,combo)
        allt+=P.run_partial(df,L,Sx,sm,tm,part,tp1)
    return allt

if __name__=='__main__':
    btc4=F.load(240); btc1d=F.load(1440); eth1d=M.load_eth()
    specs=[btc4,btc1d,eth1d]
    print('Пул BTC4H+1D+ETH1D, partial part0.5 tp1.0, sm2.0 tm6.0, causal 5bps')
    print('=== фільтр тренду EMA на сигналах ===')
    for combo in ['bos','bos+choch']:
        for te in [0,100,200]:
            allt=run_pool(specs,3,te,combo,0.5,1.0,2.0,6.0)
            if len(allt)<30: continue
            Rs=np.array([r for _,r in allt])
            pm,dd,posm,nmo,_=M.posmonths(allt,0.02)
            print('%-10s emaT%3d | n=%4d win=%.2f | %+5.2f%%/mo DD=%2.0f%% плюс.міс=%.0f%%(%d) | %.1f/тиж'%(
                combo,te,len(allt),(Rs>0).mean(),pm*100,dd*100,posm*100,nmo,len(allt)/(nmo*4.345)))

    def oos(allt):
        a=sorted(allt,key=lambda x:x[0]);R=np.array([r for _,r in a]);cut=int(len(R)*0.7)
        return R[:cut].mean(),R[cut:].mean()
    print('\n=== LONG-ONLY деталі + OOS + варіації EMA/combo ===')
    for combo in ['bos','bos+choch']:
        for te in [150,200,300]:
            for part,tp1 in [(0.5,1.0),(0.5,1.5)]:
                allt=[]
                for df in specs:
                    L,Sx=filt_signals(df,3,te,combo)
                    allt+=P.run_partial(df,L,np.zeros(len(df),bool),2.0,6.0,part,tp1)
                if len(allt)<30: continue
                Rs=np.array([r for _,r in allt]);isR,oR=oos(allt)
                pm,dd,posm,nmo,_=M.posmonths(allt,0.02)
                print('%-9s ema%3d p%.1f tp%.1f | n=%3d win=%.2f IS=%+.2f OOS=%+.2f | %+4.2f%%/mo DD=%2.0f%% плюс=%.0f%%(%d) %.1f/тиж'%(
                    combo,te,part,tp1,len(allt),(Rs>0).mean(),isR,oR,pm*100,dd*100,posm*100,nmo,len(allt)/(nmo*4.345)))

    print('\n=== свіп part/tp (long+short та long-only) ===')
    for lo in [False,True]:
        for part,tp1 in [(0.4,1.0),(0.5,1.0),(0.5,1.5),(0.6,1.5)]:
            allt=[]
            for df in specs:
                L,Sx=filt_signals(df,3,200,'bos+choch')
                if lo: Sx=np.zeros(len(df),bool)
                allt+=P.run_partial(df,L,Sx,2.0,6.0,part,tp1)
            if len(allt)<30: continue
            Rs=np.array([r for _,r in allt])
            pm,dd,posm,nmo,_=M.posmonths(allt,0.02)
            print('%s part%.1f tp%.1f | n=%4d win=%.2f | %+5.2f%%/mo DD=%2.0f%% плюс.міс=%.0f%%(%d) | %.1f/тиж'%(
                'LONGonly' if lo else 'L+S     ',part,tp1,len(allt),(Rs>0).mean(),pm*100,dd*100,posm*100,nmo,len(allt)/(nmo*4.345)))
