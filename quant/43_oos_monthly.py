"""Середній місячний прибуток KC+FVG САМЕ НА НОВИХ (OOS) ДАНИХ.
Кожну монету ріжемо 60/40 за часом; IS відкидаємо, рахуємо лише OOS.
Чесно: послідовне компаундування, реальні витрати вже в R (з модуля 39)."""
import importlib.util, builtins, numpy as np, pandas as pd
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("c39","quant/39_combined_concentration.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
BASE=m.BASE

def naive(t):
    ts=pd.Timestamp(t)
    return ts.tz_localize(None) if ts.tzinfo is not None else ts

def collect(which):  # "IS" / "OOS" / "ALL"
    rows=[]
    for c,d in BASE.items():
        cut=naive(d.index[int(len(d)*0.6)])
        for t,r in (m.kc(d)+m.fvg(d)):
            tt=naive(t); oos=tt>=cut
            if which=="ALL" or (which=="OOS" and oos) or (which=="IS" and not oos):
                rows.append((tt,r))
    return pd.DataFrame(rows,columns=["t","r"]).sort_values("t").reset_index(drop=True)

def stats(T,risk):
    r=T["r"].values
    eq=np.cumprod(1+risk*r)
    s=pd.Series(eq,index=pd.DatetimeIndex(T["t"]))
    me=s.resample("ME").last().dropna()
    mret=me.pct_change().dropna()
    mret=pd.concat([pd.Series([me.iloc[0]-1],index=[me.index[0]]),mret])
    dd=((eq/np.maximum.accumulate(eq))-1).min()*100
    return dict(n=len(r),exp=r.mean(),avg=mret.mean()*100,med=mret.median()*100,
                pos=(mret>0).mean()*100,dd=dd,mucnt=len(mret),
                d0=T["t"].min().date(),d1=T["t"].max().date())

for which in ["IS","OOS"]:
    T=collect(which)
    for risk in [0.01,0.015]:
        s=stats(T,risk)
        print(f"{which} risk={risk*100:.1f}% | {s['d0']}..{s['d1']} ({s['mucnt']} міс) | "
              f"n={s['n']} exp={s['exp']:+.3f}R | сер.міс={s['avg']:+.2f}% медіана={s['med']:+.2f}% "
              f"| +міс={s['pos']:.0f}% | maxDD={s['dd']:+.0f}%")
    print()

# скільки це угод/міс на OOS
T=collect("OOS")
span=(T["t"].max()-T["t"].min()).days/30.44
print(f"OOS частота: {len(T)/span:.1f} угод/міс (по 3 монетах разом)")
print("\nПримітка: послідовне компаундування злитого потоку; реальна DD при одночасних")
print("позиціях вища (MTM ~+10пп). Лайв зазвичай нижчий за OOS — потрібен форвард-тест.")
