"""Перевірка ФЛЕТ-ФІЛЬТРІВ: чи прибирання боковика покращує combo.
Метрика MAR=avg_mo/|DD|, чесно IS/OOS. Combo KC+ADX>20 + vol-target + DD-throttle, risk 3%."""
import importlib.util, builtins
import numpy as np, pandas as pd
import engine as E
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("r23","quant/23_reduce_dd.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
DATA=m.DATA; COINVOL=m.COINVOL

def eff_ratio(c,n=20):
    return (c-c.shift(n)).abs()/c.diff().abs().rolling(n).sum()

def choppiness(d,n=14):
    atr_sum=E.true_range(d).rolling(n).sum()
    rng=d["high"].rolling(n).max()-d["low"].rolling(n).min()
    return 100*np.log10(atr_sum/rng)/np.log10(n)

def gen_flat(adx_min=20, er_min=0.0, slope_k=0, slope_min=0.0, ci_max=0.0, adx_only=0):
    rows=[]
    for c,d in DATA.items():
        side,sd=m.kc_signals(d,adx_min=(adx_only if adx_only else adx_min))
        cl=d["close"]
        if er_min>0:
            side[eff_ratio(cl,20).to_numpy()<er_min]=0
        if slope_min>0:
            e2=E.ema(cl,200); sl=((e2-e2.shift(slope_k))/e2).to_numpy()
            side[(side>0)&~(sl>slope_min)]=0; side[(side<0)&~(sl<-slope_min)]=0
        if ci_max>0:
            side[choppiness(d,14).to_numpy()>ci_max]=0
        t=E.backtest(d,side,sd,E.Config(rr=2.0,risk_pct=0.01,bar_minutes=240)).trades
        if len(t):
            t=t.copy(); t["coin"]=c
            vs=COINVOL[c].reindex(pd.to_datetime(t["entry_time"])).clip(0.3,3).values
            t["volscale"]=(1.0/vs).clip(0.3,2.5)
            rows.append(t[["entry_time","exit_time","r_mult","coin","volscale"]])
    return pd.concat(rows,ignore_index=True).sort_values("entry_time")

def ev(T,label):
    eq=m.sim(T,0.03,vol_target=True,dd_throttle=0.25); mo,dd,_=m.met(eq); mar=mo/abs(dd) if dd<0 else 0
    k=int(len(T)*0.6); cut=T.entry_time.iloc[k]
    eqo=m.sim(T[T.entry_time>=cut],0.03,vol_target=True,dd_throttle=0.25); moo,ddo,_=m.met(eqo)
    print(f"  {label:34} n={len(T):4d} | avg_mo={mo*100:5.2f}% DD={dd*100:5.0f}% MAR={mar:.3f} "
          f"| OOS {moo*100:4.1f}%/{ddo*100:4.0f}%")
    return mar

print("ФЛЕТ-ФІЛЬТРИ (combo, risk 3%, vol-target+DD-throttle):\n")
base=gen_flat(); ev(base,"baseline (ADX>20)")
ev(gen_flat(adx_only=25),"ADX>25 (сильніший тренд)")
ev(gen_flat(adx_only=30),"ADX>30")
ev(gen_flat(er_min=0.25),"+Efficiency Ratio>0.25")
ev(gen_flat(er_min=0.30),"+Efficiency Ratio>0.30")
ev(gen_flat(ci_max=60),"+Choppiness<60")
ev(gen_flat(ci_max=55),"+Choppiness<55")
ev(gen_flat(slope_k=30,slope_min=0.01),"+EMA200 нахил >1%/30барів")
ev(gen_flat(slope_k=50,slope_min=0.02),"+EMA200 нахил >2%/50барів")
print("\nКОМБО флет-фільтрів:")
ev(gen_flat(er_min=0.25,ci_max=60),"ER>0.25 & Chop<60")
ev(gen_flat(adx_only=25,er_min=0.25),"ADX>25 & ER>0.25")
