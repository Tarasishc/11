"""Покращити % прибуткових місяців. Тести: трендова MA (не лише EMA200), RR, к-сть монет.
Метрика: % плюсових МІСЯЦІВ по портфельному капіталу + avg_mo/DD/MAR, чесно IS/OOS.
Також: скільки угод на тиждень."""
import importlib.util, builtins
import numpy as np, pandas as pd
import engine as E
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("r23","quant/23_reduce_dd.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
DATA=dict(m.DATA); COINVOL=dict(m.COINVOL)
import lib_data as L
DATA["MNT"]=L.load_any("quant/data/mnt_4h.csv")
_v=DATA["MNT"]["close"].pct_change().rolling(30).std().shift(1); COINVOL["MNT"]=_v/_v.median()

def adx14(d):
    h,l=d["high"],d["low"];up=h.diff();dn=-l.diff()
    pdm=((up>dn)&(up>0))*up;mdm=((dn>up)&(dn>0))*dn;tr=E.true_range(d);a=tr.ewm(alpha=1/14,adjust=False).mean()
    pdi=100*pdm.ewm(alpha=1/14,adjust=False).mean()/a;mdi=100*mdm.ewm(alpha=1/14,adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).ewm(alpha=1/14,adjust=False).mean()

def gen(coins, ema_trend=200, ma="ema", rr=2.0, adx_min=20, kc_mult=2.0):
    rows=[]
    for c in coins:
        d=DATA[c]; cl=d["close"]
        mid=E.ema(cl,20); band=kc_mult*E.atr(d,10); up=mid+band; lo=mid-band
        trend=E.ema(cl,ema_trend) if ma=="ema" else E.sma(cl,ema_trend)
        ax=adx14(d).to_numpy()
        side=np.zeros(len(d))
        side[((cl>up)&(cl>trend)).to_numpy()]=1; side[((cl<lo)&(cl<trend)).to_numpy()]=-1
        side[ax<adx_min]=0
        t=E.backtest(d,side,(E.atr(d,14)*2.0).to_numpy(),E.Config(rr=rr,risk_pct=0.01,bar_minutes=240)).trades
        if len(t):
            t=t.copy(); t["coin"]=c
            vs=COINVOL[c].reindex(pd.to_datetime(t["entry_time"])).clip(0.3,3).values
            t["volscale"]=(1.0/vs).clip(0.3,2.5)
            rows.append(t[["entry_time","exit_time","r_mult","coin","volscale"]])
    return pd.concat(rows,ignore_index=True).sort_values("entry_time")

def monthly_pct(eq):
    d=eq.resample("1D").last().ffill(); mr=d.resample("ME").last().pct_change().dropna()
    return (mr>0).mean()*100, mr.mean()*100, (d/d.cummax()-1).min()*100

def ev(T,label):
    eq=m.sim(T,0.03,vol_target=True,dd_throttle=0.25); pos,mo,dd=monthly_pct(eq); mar=mo/abs(dd) if dd!=0 else 0
    k=int(len(T)*0.6); cut=T.entry_time.iloc[k]
    eqo=m.sim(T[T.entry_time>=cut],0.03,vol_target=True,dd_throttle=0.25); poso,moo,_=monthly_pct(eqo)
    print(f"  {label:30} n={len(T):4d} | плюс.міс={pos:.0f}% avg_mo={mo:.2f}% DD={dd:.0f}% MAR={mar:.3f} | OOS плюс.міс={poso:.0f}%")

# --- угод на тиждень ---
print("="*60); print("СКІЛЬКИ УГОД НА ТИЖДЕНЬ"); print("="*60)
base=gen(["BTC","ETH","SOL"])
for c in ["BTC","ETH","SOL"]:
    g=base[base.coin==c]; span=(pd.to_datetime(g.entry_time.max())-pd.to_datetime(g.entry_time.min())).days/7
    print(f"  {c}: {len(g)} угод за ~{span:.0f} тижнів = {len(g)/span:.2f}/тиждень")
# у 3-монетну еру (від старту наймолодшої = SOL 2021-10)
start=pd.Timestamp("2021-10-15",tz="UTC")
era=base[pd.to_datetime(base.entry_time)>=start]
wk=(pd.to_datetime(era.entry_time.max())-start)/np.timedelta64(1,"W")
print(f"  РАЗОМ (3 монети, з 2021-10): {len(era)} угод за ~{wk:.0f} тижнів = {len(era)/wk:.2f}/тиждень (~{len(era)/wk*4.3:.1f}/міс)")

print("\n"+"="*60); print("БАЗА"); print("="*60)
ev(base,"baseline KC+EMA200, RR2, 3 монети")

print("\n"+"="*60); print("ІНША ТРЕНДОВА СЕРЕДНЯ (замість EMA200)"); print("="*60)
for et in [100,150,250,300]:
    ev(gen(["BTC","ETH","SOL"],ema_trend=et),f"EMA{et}")
ev(gen(["BTC","ETH","SOL"],ema_trend=200,ma="sma"),"SMA200")
ev(gen(["BTC","ETH","SOL"],ema_trend=100,ma="sma"),"SMA100")

print("\n"+"="*60); print("ІНШИЙ RR (нижчий RR = вищий win% = більше плюс.місяців?)"); print("="*60)
for rr in [1.5,2.0,2.5,3.0]:
    ev(gen(["BTC","ETH","SOL"],rr=rr),f"RR={rr}")

print("\n"+"="*60); print("БІЛЬШЕ МОНЕТ (4 з MNT) vs 3 — головний важіль стабільності"); print("="*60)
ev(gen(["BTC","ETH","SOL"]),"3 монети")
ev(gen(["BTC","ETH","SOL","MNT"]),"4 монети (+MNT)")
