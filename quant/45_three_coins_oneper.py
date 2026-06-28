"""Повна картина: 3 монети (BTC+ETH+SOL), ОДНА позиція на монету (реально руками).
Внесок кожної монети + портфель на всьому періоді й на OOS, risk 1% та 1.5%."""
import importlib.util, builtins, numpy as np, pandas as pd
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("c44","quant/44_one_per_coin.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
BASE=m.BASE; one_per_coin=m.one_per_coin; naive=m.naive

def mstats(rows,risk):
    T=pd.DataFrame(rows,columns=["t","r"]).sort_values("t")
    r=T["r"].values; eq=np.cumprod(1+risk*r)
    me=pd.Series(eq,index=pd.DatetimeIndex(T["t"])).resample("ME").last().dropna()
    mret=me.pct_change().dropna(); mret=pd.concat([pd.Series([me.iloc[0]-1],index=[me.index[0]]),mret])
    dd=((eq/np.maximum.accumulate(eq))-1).min()*100
    span=(T["t"].max()-T["t"].min()).days/30.44
    return dict(n=len(r),exp=r.mean(),avg=mret.mean()*100,med=mret.median()*100,
                pos=(mret>0).mean()*100,dd=dd,tpm=len(r)/span,mo=len(mret),
                d0=T["t"].min().date(),d1=T["t"].max().date(),mult=eq[-1])

print("Внесок кожної монети (одна-на-монету, увесь період):")
for c,d in BASE.items():
    r=np.array([x[1] for x in one_per_coin(d)])
    print(f"  {c}: угод={len(r):4d}  exp={r.mean():+.3f}R  WR={(r>0).mean()*100:.0f}%  sumR={r.sum():.0f}")

def collect(which):
    rows=[]
    for c,d in BASE.items():
        cut=naive(d.index[int(len(d)*0.6)])
        rows+=[(ts,r) for ts,r in one_per_coin(d) if which=="ALL" or ts>=cut]
    return rows

for which in ["ALL","OOS"]:
    print(f"\n{which} — портфель 3 монети, одна позиція на монету:")
    for risk in [0.01,0.015]:
        s=mstats(collect(which),risk)
        print(f"  risk {risk*100:.1f}% | {s['d0']}..{s['d1']} ({s['mo']}міс) | n={s['n']} ({s['tpm']:.1f}/міс) exp={s['exp']:+.3f}R | "
              f"сер.міс={s['avg']:+.2f}% мед={s['med']:+.2f}% +міс={s['pos']:.0f}% | DD={s['dd']:+.0f}%")

print("\nУвага: до 3 позицій одночасно (по різних монетах) — це ок на біржі.")
print("Реалізована DD занижує одночасну; реальна MTM ~ +10пп. Лайв нижчий — форвард-тест.")
