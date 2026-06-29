"""Зведення тестів саме по SOL: двигуни окремо, одна-на-монету, IS/OOS, місячне."""
import importlib.util, builtins, numpy as np, pandas as pd
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("c44","quant/44_one_per_coin.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
sol=m.BASE["SOL"]; naive=m.naive

kc=[(naive(ts),r) for _,_,ts,r in m.kc_tr(sol)]
fvg=[(naive(ts),r) for _,_,ts,r in m.fvg_tr(sol)]
opc=m.one_per_coin(sol)

def desc(name,trs):
    r=np.array([x[1] for x in trs])
    print(f"  {name:18s}: n={len(r):4d} exp={r.mean():+.3f}R WR={(r>0).mean()*100:.0f}% sumR={r.sum():.0f}")

print(f"SOL 4h · історія {sol.index.min().date()}..{sol.index.max().date()} · Binance тейкер 0.05%\n")
print("Двигуни окремо (усі угоди):")
desc("KC (пробій)", kc); desc("FVG (ретест)", fvg); desc("одна-на-монету", opc)

cut=naive(sol.index[int(len(sol)*0.6)])
isr=np.array([r for ts,r in opc if ts<cut]); oosr=np.array([r for ts,r in opc if ts>=cut])
print(f"\nIS/OOS (одна-на-монету), межа {cut.date()}:")
print(f"  IS : n={len(isr)} exp={isr.mean():+.3f}R WR={(isr>0).mean()*100:.0f}%")
print(f"  OOS: n={len(oosr)} exp={oosr.mean():+.3f}R WR={(oosr>0).mean()*100:.0f}%  <- невидимі дані")

def monthly(trs,risk):
    T=pd.DataFrame(trs,columns=["t","r"]).sort_values("t")
    r=T["r"].values;eq=np.cumprod(1+risk*r)
    me=pd.Series(eq,index=pd.DatetimeIndex(T["t"])).resample("ME").last().dropna()
    mret=me.pct_change().dropna();mret=pd.concat([pd.Series([me.iloc[0]-1],index=[me.index[0]]),mret])
    dd=((eq/np.maximum.accumulate(eq))-1).min()*100
    span=(T["t"].max()-T["t"].min()).days/30.44
    return mret.median()*100,(mret>0).mean()*100,dd,len(trs)/span
for risk in [0.01,0.015]:
    med,pos,dd,tpm=monthly(opc,risk)
    print(f"\nSOL окремо як стратегія, risk{risk*100:.1f}%: медіана={med:+.2f}%/міс +міс={pos:.0f}% DD={dd:.0f}% ({tpm:.1f} угод/міс)")
