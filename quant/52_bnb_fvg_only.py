"""4 монети, але на BNB лишаємо ТІЛЬКИ FVG (KC на BNB слабкий).
Порівняння OOS: 3 монети / 4 з BNB(KC+FVG) / 4 з BNB(тільки FVG)."""
import importlib.util, builtins, numpy as np, pandas as pd
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("c44","quant/44_one_per_coin.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
import lib_data as L
naive=m.naive; BASE3=m.BASE
bnb=L.load_any("quant/data/bnb_4h.csv")

def fvg_only(d): return [(naive(ts),r) for _,_,ts,r in m.fvg_tr(d)]
def opc(d):      return m.one_per_coin(d)

def oos_rows(cb):
    rows=[]
    for d,builder in cb:
        cut=naive(d.index[int(len(d)*0.6)])
        rows+=[(ts,r) for ts,r in builder(d) if ts>=cut]
    return pd.DataFrame(rows,columns=["t","r"]).sort_values("t")
def stats(T,risk):
    r=T["r"].values;eq=np.cumprod(1+risk*r)
    me=pd.Series(eq,index=pd.DatetimeIndex(T["t"])).resample("ME").last().dropna()
    mret=me.pct_change().dropna();mret=pd.concat([pd.Series([me.iloc[0]-1],index=[me.index[0]]),mret])
    dd=((eq/np.maximum.accumulate(eq))-1).min()*100
    return len(r),r.mean(),mret.median()*100,(mret>0).mean()*100,dd

majors=[(BASE3["BTC"],opc),(BASE3["ETH"],opc),(BASE3["SOL"],opc)]
configs=[("3 монети (BTC+ETH+SOL)",majors),
         ("4 монети: BNB одна-на-монету",majors+[(bnb,opc)]),
         ("4 монети: BNB тільки FVG",majors+[(bnb,fvg_only)])]
print("OOS портфель, Binance тейкер 0.05%:\n")
for name,cb in configs:
    for risk in [0.01,0.015]:
        n,exp,med,pos,dd=stats(oos_rows(cb),risk)
        print(f"  {name:30s} r{risk*100:.1f}% | n={n} exp={exp:+.3f}R | med={med:+.2f}%/міс +міс={pos:.0f}% DD={dd:.0f}% | ret/DD={med/abs(dd):.2f}")
    print()

print("Внесок BNB окремо (OOS):")
cut=naive(bnb.index[int(len(bnb)*0.6)])
for nm,b in [("одна-на-монету (KC+FVG)",opc),("тільки FVG",fvg_only)]:
    r=np.array([r for ts,r in b(bnb) if ts>=cut])
    print(f"  {nm:24s}: n={len(r)} exp={r.mean():+.3f}R WR={(r>0).mean()*100:.0f}%")
