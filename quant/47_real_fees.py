"""Чи витримує стратегія РЕАЛЬНІ комісії Bybit (не-VIP, деривативи)?
Тейкер 0.1%/сторону (ринковий), мейкер 0.036% (лімітний) проти мого 0.05%.
OOS, 3 монети, одна-на-монету, risk 1.5%."""
import importlib.util, builtins, numpy as np, pandas as pd
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("c44","quant/44_one_per_coin.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
BASE=m.BASE; naive=m.naive

def oos():
    rows=[]
    for c,d in BASE.items():
        cut=naive(d.index[int(len(d)*0.6)])
        rows+=[(ts,r) for ts,r in m.one_per_coin(d) if ts>=cut]
    return pd.DataFrame(rows,columns=["t","r"]).sort_values("t")

def stats(T,risk=0.015):
    r=T["r"].values;eq=np.cumprod(1+risk*r)
    me=pd.Series(eq,index=pd.DatetimeIndex(T["t"])).resample("ME").last().dropna()
    mret=me.pct_change().dropna();mret=pd.concat([pd.Series([me.iloc[0]-1],index=[me.index[0]]),mret])
    dd=((eq/np.maximum.accumulate(eq))-1).min()*100
    return r.mean(),mret.median()*100,(mret>0).mean()*100,dd

sc=[("Бектест (моє припущення 0.05%/сторону)",0.0005,0.0003),
    ("Bybit ТЕЙКЕР 0.10%/сторону (ринкові, як KC)",0.0010,0.0003),
    ("Bybit тейкер з MNT-знижкою 0.09%",0.0009,0.0003),
    ("Bybit МЕЙКЕР 0.036%/сторону (лімітки, як FVG)",0.00036,0.0001)]
print("OOS · 3 монети · одна-на-монету · risk 1.5% — вплив реальних комісій:\n")
for name,fee,slip in sc:
    m.FEE=fee;m.SLIP=slip
    e,med,pos,dd=stats(oos())
    print(f"  {name:46s}: exp={e:+.3f}R  медіана={med:+.2f}%/міс  +міс={pos:.0f}%  DD={dd:.0f}%")
print("\nРеальність: KC=тейкер(дорожче), FVG=мейкер(дешевше) — десь між рядками 1-2.")
print("«Тейкер 0.10%» — чесний консервативний орієнтир (наче все маркетом).")
