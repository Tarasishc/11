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

def collect(df,rr=2.0,stop_buf=0.5,max_wait=80,min_gap_atr=0.25):
    o=df['open'].values;h=df['high'].values;l=df['low'].values;c=df['close'].values;v=df['vol'].values
    a=atr(df);e200=df['close'].ewm(span=200,adjust=False).mean().values
    e50=df['close'].ewm(span=50,adjust=False).mean().values
    rs=rsi(df['close']);vma=pd.Series(v).rolling(20).mean().values;n=len(df)
    pend=[];rows=[];inpos=False;entry=stop=feeR=0;pdir=0;ctx=None
    for i in range(3,n):
        if inpos:
            R=None
            if l[i]<=stop: R=-1.0-feeR
            elif h[i]>=entry+rr*(entry-stop): R=rr-feeR
            if R is not None:
                rows.append({**ctx,'R':R,'exit':i});inpos=False
        if h[i-2]<l[i]:
            g=l[i]-h[i-2]
            if g>min_gap_atr*a[i]: pend.append({'top':l[i],'bot':h[i-2],'born':i,'gatr':g/a[i],'gvol':v[i]/vma[i] if vma[i]>0 else 1})
        if not inpos:
            for z in pend:
                if z.get('used') or i-z['born']<1 or i-z['born']>max_wait:
                    if i-z['born']>max_wait: z['used']=True
                    continue
                if not c[i]>e200[i]: continue
                if l[i]<=z['top'] and h[i]>=z['bot']:
                    ent=z['top'];st=z['bot']-stop_buf*a[i];rd=ent-st
                    if rd<=0: z['used']=True;continue
                    feeR=2*FEE*ent/rd
                    if l[i]<=st: rows.append({'gatr':z['gatr'],'gvol':z['gvol'],'rsi':rs[i],'ext200':(c[i]-e200[i])/e200[i],'wait':i-z['born'],'strong':int(e50[i]>e200[i]),'R':-1.0-feeR,'exit':i});z['used']=True;break
                    ctx={'gatr':z['gatr'],'gvol':z['gvol'],'rsi':rs[i],'ext200':(c[i]-e200[i])/e200[i],'wait':i-z['born'],'strong':int(e50[i]>e200[i])}
                    entry=ent;stop=st;pdir=1;inpos=True;z['used']=True;break
        pend=[z for z in pend if not z.get('used') and i-z['born']<=max_wait]
    return pd.DataFrame(rows)

def ev(d,label):
    if len(d)<25: print(f'{label:38}| n={len(d):4} (замало)');return
    cut=int(len(d)*0.7);Rs=d['R'].values
    isR=Rs[:cut].mean();oosR=Rs[cut:].mean()
    print(f'{label:38}| n={len(d):4} win={(Rs>0).mean():.2f} expR={Rs.mean():+.3f} IS={isR:+.3f} OOS={oosR:+.3f}')

df=F.load(240);d=collect(df)
d=d.sort_values('exit').reset_index(drop=True)
print(f'BTC 4H, FVG-long base: n={len(d)}\n')
ev(d,'БАЗА (всі угоди)')
print('-- фільтри підтвердження --')
ev(d[d.gatr>=0.5],'геп великий (>=0.5 ATR)')
ev(d[d.gatr>=1.0],'геп дуже великий (>=1 ATR)')
ev(d[d.gvol>=1.2],'імпульс на обсязі (vol>=1.2x)')
ev(d[d.gvol>=1.5],'імпульс на обсязі (vol>=1.5x)')
ev(d[d.rsi<60],'RSI<60 на вході (не перекуп)')
ev(d[d.rsi<50],'RSI<50 на вході')
ev(d[d.rsi>50],'RSI>50 (моментум вгору)')
ev(d[d.ext200<0.10],'не розтягнуто (<10% над EMA200)')
ev(d[d.ext200<0.05],'не розтягнуто (<5% над EMA200)')
ev(d[d.wait<=10],'швидке повернення (<=10 барів)')
ev(d[d.wait>=20],'повільне повернення (>=20 барів)')
ev(d[d.strong==1],'сильний тренд (EMA50>EMA200)')
print('-- комбо --')
ev(d[(d.strong==1)&(d.rsi<60)],'сильний тренд + RSI<60')
ev(d[(d.strong==1)&(d.gatr>=0.5)&(d.rsi<60)],'тренд+геп>=0.5+RSI<60')
ev(d[(d.strong==1)&(d.ext200<0.10)&(d.gvol>=1.2)],'тренд+не розтягн+обсяг')
