# Тест ТІЛЬКИ на ведмежих і бокових місяцях. Бичі місяці (BTC міс.зміна>+2%) виключені.
import numpy as np, pandas as pd, fvg_scan as F, mstruct as M
import squeeze_break as SB

btc1d=F.load(1440)
bm=btc1d.copy();bm['ym']=pd.to_datetime(bm['dt']).dt.to_period('M')
mc=bm.groupby('ym')['close'].last();mret=mc.pct_change()
bull=set(mret[mret>0.02].index.astype(str))
bear=set(mret[mret<-0.02].index.astype(str))
flat=set(mret[(mret>=-0.02)&(mret<=0.02)].index.astype(str))

def regof(t):
    ym=str(pd.Timestamp(t).to_period('M'))
    return 'bull' if ym in bull else ('bear' if ym in bear else 'flat')

def subset_stats(allt,keep,risk,label):
    sub=[(t,r) for t,r in allt if regof(t) in keep]
    sub=sorted(sub,key=lambda x:x[0])
    if len(sub)<15: print('  %s замало(n=%d)'%(label,len(sub)));return
    R=np.array([r for _,r in sub]);cut=int(len(R)*0.7)
    # рахуємо плюс.міс лише по місяцях цього режиму
    eq=1.0;rows=[]
    for t,r in sub: eq*=(1+risk*r);rows.append((pd.Timestamp(t),eq))
    e=pd.DataFrame(rows,columns=['t','e']);peak=np.maximum.accumulate(e['e'].values)
    dd=((peak-e['e'].values)/peak).max()
    e['ym']=e['t'].dt.to_period('M');mo=e.groupby('ym').agg(end=('e','last'))
    mo['start']=mo['end'].shift(1).fillna(1.0);mo['ret']=mo['end']/mo['start']-1
    Rs=np.sort(R)[::-1];tot=R.sum()
    print('  %-14s n=%3d win=%.2f expR=%+.3f IS=%+.2f OOS=%+.2f | плюс.міс=%.0f%%(%d) DD=%2.0f%% | без топ5 expR=%+.3f'%(
        label,len(R),(R>0).mean(),R.mean(),R[:cut].mean(),R[cut:].mean(),
        (mo.ret>0).mean()*100,len(mo),dd*100,Rs[5:].mean() if len(Rs)>5 else 0))

if __name__=='__main__':
    print('Місяців: бик=%d ведмідь=%d боковик=%d'%(len(bull),len(bear),len(flat)))
    btc4=F.load(240);eth1d=M.load_eth()
    print('\n=== SQUEEZE BREAKOUT, ТІЛЬКИ ведмідь+боковик (бик виключено), risk2% ===')
    for sq in [0.3,0.4]:
        for sm,tm in [(1.0,4.0),(1.5,6.0)]:
            allt=[]
            for df in [btc4,btc1d,eth1d]:
                allt+=SB.run_squeeze(df,box=20,squeeze_q=sq,sm=sm,tm=tm)
            print(' sq%.1f sm%.1f tm%.1f:'%(sq,sm,tm))
            subset_stats(allt,{'bear','flat'},0.02,'  ведмідь+боковик')
            subset_stats(allt,{'bear'},0.02,'  тільки ведмідь')
            subset_stats(allt,{'flat'},0.02,'  тільки боковик')
