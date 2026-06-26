# Причинний трендовий пул із ЧАСТКОВОЮ фіксацією (50% на +1R, решта трейл).
# Знахідка: часткова фіксація піднімає плюсові місяці 39%->64%, вінрейт 25%->57%,
# знижує DD, зберігаючи двозначний %/міс. Це найкращий чесний (causal, 5bps) профіль
# на доступних даних (BTC+ETH денні + BTC 4H). Стеля ~64% плюс.міс через кореляцію крипти.
import numpy as np, pandas as pd, fvg_scan as F, causal_engine as E
FEE=0.0006
def atr(df,n=14):
    h,l,c=df['high'].values,df['low'].values,df['close'].values
    pc=np.roll(c,1);pc[0]=c[0];tr=np.maximum(h-l,np.maximum(abs(h-pc),abs(l-pc)))
    return pd.Series(tr).ewm(alpha=1/n,adjust=False).mean().values
def run_partial(df,sigL,sigS,stop_mult=2.0,trail_mult=6.0,part=0.5,tp1=1.0,slip_bps=5):
    o,h,l,c=df['open'].values,df['high'].values,df['low'].values,df['close'].values
    a=atr(df);n=len(df);dt=df['dt'].values;slip=slip_bps/1e4
    tr=[];pos=0;entry=stop=feeR=ext=initR=0;pend=0;took=False
    for i in range(1,n):
        if pos==0 and pend!=0 and a[i]>0:
            if pend==1: entry=o[i]*(1+slip);initR=stop_mult*a[i];stop=entry-initR;ext=h[i]
            else: entry=o[i]*(1-slip);initR=stop_mult*a[i];stop=entry+initR;ext=l[i]
            feeR=2*FEE*entry/initR;pos=pend;pend=0;took=False
        if pos==1:
            if not took and h[i]>=entry+tp1*initR: tr.append((dt[i],part*(tp1-feeR)));took=True
            ext=max(ext,h[i]);stop=max(stop,ext-trail_mult*a[i])
            if l[i]<=stop: tr.append((dt[i],((1-part) if took else 1.0)*((stop-entry)/initR-feeR)));pos=0
        elif pos==-1:
            if not took and l[i]<=entry-tp1*initR: tr.append((dt[i],part*(tp1-feeR)));took=True
            ext=min(ext,l[i]);stop=min(stop,ext+trail_mult*a[i])
            if h[i]>=stop: tr.append((dt[i],((1-part) if took else 1.0)*((entry-stop)/initR-feeR)));pos=0
        if pos==0 and pend==0:
            if sigL[i]: pend=1
            elif sigS[i]: pend=-1
    return tr
