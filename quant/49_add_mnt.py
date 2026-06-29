"""Додаємо MNT (held-out монета) у портфель. MNT окремо + 4 монети проти 3.
OOS, одна-на-монету, Binance тейкер 0.05%."""
import importlib.util, builtins, numpy as np, pandas as pd
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("c44","quant/44_one_per_coin.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
import lib_data as L
BASE3=m.BASE; naive=m.naive; one_per_coin=m.one_per_coin
mnt=L.load_any("quant/data/mnt_4h.csv")
BASE4=dict(BASE3); BASE4["MNT"]=mnt

print("MNT окремо (одна-на-монету, увесь її період):")
r=np.array([x[1] for x in one_per_coin(mnt)])
print(f"  історія MNT: {mnt.index.min().date()}..{mnt.index.max().date()}")
print(f"  n={len(r)} exp={r.mean():+.3f}R WR={(r>0).mean()*100:.0f}% sumR={r.sum():.0f}\n")

def collect(base,which):
    rows=[]
    for c,d in base.items():
        cut=naive(d.index[int(len(d)*0.6)])
        rows+=[(ts,rr) for ts,rr in one_per_coin(d) if which=="ALL" or ts>=cut]
    return pd.DataFrame(rows,columns=["t","r"]).sort_values("t")

def stats(T,risk):
    r=T["r"].values;eq=np.cumprod(1+risk*r)
    me=pd.Series(eq,index=pd.DatetimeIndex(T["t"])).resample("ME").last().dropna()
    mret=me.pct_change().dropna();mret=pd.concat([pd.Series([me.iloc[0]-1],index=[me.index[0]]),mret])
    dd=((eq/np.maximum.accumulate(eq))-1).min()*100
    span=(T["t"].max()-T["t"].min()).days/30.44
    return len(r),r.mean(),mret.median()*100,(mret>0).mean()*100,dd,len(T)/span

print("OOS портфель, одна-на-монету, Binance тейкер 0.05%:")
for tag,base in [("3 монети (BTC+ETH+SOL)",BASE3),("4 монети (+MNT)    ",BASE4)]:
    for risk in [0.01,0.015]:
        n,exp,med,pos,dd,tpm=stats(collect(base,"OOS"),risk)
        print(f"  {tag} risk{risk*100:.1f}% | n={n} ({tpm:.1f}/міс) exp={exp:+.3f}R | med={med:+.2f}%/міс +міс={pos:.0f}% DD={dd:.0f}%")

print("\nMNT — менш ліквідна (запуск ~2023), реальний слипедж вищий за BTC,")
print("тому її число в лайві буде гіршим за бектест більше, ніж у мейджорів.")
