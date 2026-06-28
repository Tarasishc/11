"""Найдовші серії плюсових/мінусових МІСЯЦІВ + у яких ринкових режимах.
Combo KC+ADX>20, BTC+ETH+SOL, risk 3%, vol-target+DD-throttle."""
import importlib.util, builtins
import numpy as np, pandas as pd
import engine as E
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("r23","quant/23_reduce_dd.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
DATA=m.DATA; COINVOL=m.COINVOL

def adx14(d):
    h,l=d["high"],d["low"];up=h.diff();dn=-l.diff()
    pdm=((up>dn)&(up>0))*up;mdm=((dn>up)&(dn>0))*dn;tr=E.true_range(d);a=tr.ewm(alpha=1/14,adjust=False).mean()
    pdi=100*pdm.ewm(alpha=1/14,adjust=False).mean()/a;mdi=100*mdm.ewm(alpha=1/14,adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).ewm(alpha=1/14,adjust=False).mean()

rows=[]
for c in ["BTC","ETH","SOL"]:
    d=DATA[c]; cl=d["close"]; mid=E.ema(cl,20); band=2*E.atr(d,10)
    side=np.zeros(len(d)); side[((cl>mid+band)&(cl>E.ema(cl,200))).to_numpy()]=1
    side[((cl<mid-band)&(cl<E.ema(cl,200))).to_numpy()]=-1; side[adx14(d).to_numpy()<20]=0
    t=E.backtest(d,side,(E.atr(d,14)*2).to_numpy(),E.Config(rr=2.0,risk_pct=0.01,bar_minutes=240)).trades
    if len(t):
        t=t.copy();t["coin"]=c;vs=COINVOL[c].reindex(pd.to_datetime(t["entry_time"])).clip(0.3,3).values
        t["volscale"]=(1.0/vs).clip(0.3,2.5); rows.append(t[["entry_time","exit_time","r_mult","coin","volscale"]])
T=pd.concat(rows,ignore_index=True).sort_values("entry_time")
eq=m.sim(T,0.03,vol_target=True,dd_throttle=0.25)
daily=eq.resample("1D").last().ffill()
mret=daily.resample("ME").last().pct_change().dropna()

# режим BTC по місяцях
btc_d=DATA["BTC"]["close"].resample("1D").last().dropna()
e200=E.ema(btc_d,200); slope=e200-e200.shift(20)
reg=pd.Series("боковик",index=btc_d.index)
reg[(btc_d>e200)&(slope>0)]="бичка"; reg[(btc_d<e200)&(slope<0)]="ведмежка"
reg_m=reg.resample("ME").agg(lambda x: x.value_counts().index[0] if len(x) else "?")

def regime_of(months):
    rs=[reg_m.get(mm,"?") for mm in months]
    vc=pd.Series(rs).value_counts()
    return ", ".join(f"{k}" for k in vc.index[:2]) if len(vc) else "?"

# серії
def streaks(mret, positive=True):
    res=[]; cur=[]
    for dt,v in mret.items():
        if (v>0)==positive: cur.append((dt,v))
        else:
            if cur: res.append(cur); cur=[]
    if cur: res.append(cur)
    return res

print(f"Місяців усього: {len(mret)} | плюсових: {(mret>0).sum()} ({(mret>0).mean()*100:.0f}%) | "
      f"мінусових: {(mret<=0).sum()}")

for positive,label in [(False,"МІНУСОВИХ"),(True,"ПЛЮСОВИХ")]:
    ss=streaks(mret,positive)
    ss_sorted=sorted(ss,key=len,reverse=True)
    longest=ss_sorted[0]
    months=[d for d,_ in longest]; cum=np.prod([1+v for _,v in longest])-1
    print(f"\n=== Найдовша серія {label} місяців: {len(longest)} поспіль ===")
    print(f"  Період: {months[0].strftime('%Y-%m')} → {months[-1].strftime('%Y-%m')}")
    print(f"  Сумарно за серію (risk3%): {cum*100:+.0f}%")
    print(f"  Ринковий режим: {regime_of(months)}")
    print(f"  Топ-5 найдовших серій {label}:")
    for s in ss_sorted[:5]:
        mo=[d for d,_ in s]; cc=np.prod([1+v for _,v in s])-1
        print(f"     {len(s)} міс  {mo[0].strftime('%Y-%m')}→{mo[-1].strftime('%Y-%m')}  "
              f"{cc*100:+5.0f}%  [{regime_of(mo)}]")

# розподіл довжин мінусових серій
neg=streaks(mret,False); lens=[len(s) for s in neg]
print(f"\nМінусові серії: всього {len(neg)} | сер.довжина {np.mean(lens):.1f} | "
      f"розподіл: 1міс={lens.count(1)} 2міс={lens.count(2)} 3міс={lens.count(3)} 4+={sum(1 for x in lens if x>=4)}")
