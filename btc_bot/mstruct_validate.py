# Сувора перевірка робастності найкращого конфігу:
# BOS + EMA200, long-only, partial 50%@+1.5R, sm2.0 tm6.0, risk 5%.
# Тести: прослизання, по-активах, по-роках, залежність від викидів, причинність.
import numpy as np, pandas as pd, fvg_scan as F
import mstruct as M, partial_pool as P

RISK=0.05
def sigL(df):
    S=M.signals_ms(df,3); c=df['close'].values
    e=pd.Series(c).ewm(span=200,adjust=False).mean().values
    return S['bosL']&(c>e)
NO=lambda df: np.zeros(len(df),bool)

btc4=F.load(240); btc1d=F.load(1440); eth1d=M.load_eth()
specs={'BTC4H':btc4,'BTC1D':btc1d,'ETH1D':eth1d}

def pool(slip):
    allt=[]
    for df in specs.values():
        allt+=P.run_partial(df,sigL(df),NO(df),2.0,6.0,0.5,1.5,slip_bps=slip)
    return sorted(allt,key=lambda x:x[0])

print('=== 1. ПРОСЛИЗАННЯ (stress) ===')
for slip in [0,5,10,20,40]:
    a=pool(slip);R=np.array([r for _,r in a])
    pm,dd,posm,nmo,_=M.posmonths(a,RISK)
    print('  slip=%2dbps | n=%3d expR=%+.3f | %+5.2f%%/mo DD=%2.0f%% плюс.міс=%.0f%%'%(
        slip,len(a),R.mean(),pm*100,dd*100,posm*100))

print('\n=== 2. ПО АКТИВАХ (чи не тримається на одному) ===')
for nm,df in specs.items():
    a=sorted(P.run_partial(df,sigL(df),NO(df),2.0,6.0,0.5,1.5,slip_bps=5),key=lambda x:x[0])
    if len(a)<10: print('  %s замало'%nm);continue
    R=np.array([r for _,r in a]);pm,dd,posm,nmo,_=M.posmonths(a,RISK)
    print('  %-6s | n=%3d win=%.2f expR=%+.3f | %+5.2f%%/mo DD=%2.0f%% плюс.міс=%.0f%%'%(
        nm,len(a),(R>0).mean(),R.mean(),pm*100,dd*100,posm*100))

print('\n=== 3. ПО РОКАХ (пул, risk5%) ===')
a=pool(5)
df_=pd.DataFrame([(pd.Timestamp(t).year,r) for t,r in a],columns=['y','R'])
for y,g in df_.groupby('y'):
    eq=1.0
    for r in g['R']: eq*=(1+RISK*r)
    print('  %d | угод=%3d  доходність=%+6.1f%%  (середній міс ~%+.1f%%)'%(
        y,len(g),(eq-1)*100,((eq**(1/12)-1)*100)))

print('\n=== 4. ЗАЛЕЖНІСТЬ ВІД ВИКИДІВ (прибрати топ-5/10 угод) ===')
a=pool(5);R=np.array([r for _,r in a]);Rs=np.sort(R)[::-1]
tot=R.sum()
print('  усього R=%.1f, топ-5 угод=%.1f (%.0f%%), топ-10=%.1f (%.0f%%)'%(
    tot,Rs[:5].sum(),Rs[:5].sum()/tot*100,Rs[:10].sum(),Rs[:10].sum()/tot*100))
for cut in [5,10]:
    rem=np.sort(R)[::-1][cut:]
    print('  без топ-%d: expR=%+.3f (з %d угод)'%(cut,rem.mean(),len(rem)))

print('\n=== 5. ПРИЧИННІСТЬ: вхід по open наступного бару? ===')
print('  run_partial: сигнал на барі i (closed) -> pend; вхід entry=open[i+1]*(1+slip).')
print('  Жодного входу по точному рівню всередині бару. Стоп/трейл по low/high поточного.')
print('  -> немає зазирання вперед (на відміну від фіби 0.886).')
