"""Binance vs Bybit комісії на нашій стратегії (OOS, 3 монети, одна-на-монету, risk1.5%).
Binance не-VIP: maker 0.02% / taker 0.05% (BNB -10% -> 0.018% / 0.045%).
Bybit не-VIP:   maker 0.036% / taker 0.1%."""
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

sc=[("BINANCE тейкер 0.05% (усе маркетом)",0.0005,0.0003),
    ("BINANCE тейкер 0.045% з BNB",0.00045,0.0003),
    ("BINANCE мейкер 0.02% (усе лімітками)",0.0002,0.0001),
    ("BINANCE мейкер 0.018% з BNB",0.00018,0.0001),
    ("---",None,None),
    ("BYBIT тейкер 0.10% (усе маркетом)",0.0010,0.0003),
    ("BYBIT мейкер 0.036% (усе лімітками)",0.00036,0.0001)]
print("OOS · 3 монети · одна-на-монету · risk 1.5% — Binance проти Bybit:\n")
for name,fee,slip in sc:
    if fee is None: print("  "+"-"*60); continue
    m.FEE=fee;m.SLIP=slip
    e,med,pos,dd=stats(oos())
    print(f"  {name:38s}: exp={e:+.3f}R  медіана={med:+.2f}%/міс  +міс={pos:.0f}%  DD={dd:.0f}%")
print("\nBinance тейкер 0.05% = точно моє припущення в бектесті -> числа з бектесту чесні.")
print("Реальність на Binance: KC=тейкер 0.05%, FVG=мейкер 0.02% -> навіть трохи краще.")
