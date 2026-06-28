"""Чи прибутковіше брати САМЕ FVG (без KC)? Чесне порівняння трьох двигунів
на BTC+ETH+SOL 4h, RR2: per-trade, частота, місячний %, DD, Sharpe, %+міс.
Дві бази порівняння: (1) однаковий risk 1%/угода; (2) однаковий бюджет DD≈44%."""
import importlib.util, builtins, numpy as np, pandas as pd
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("c39","quant/39_combined_concentration.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
BASE=m.BASE

def collect(which):
    rows=[]
    for c,d in BASE.items():
        if which in ("KC","BOTH"):
            for t,r in m.kc(d): rows.append((t,r))
        if which in ("FVG","BOTH"):
            for t,r in m.fvg(d): rows.append((t,r))
    T=pd.DataFrame(rows,columns=["t","r"]).sort_values("t").reset_index(drop=True)
    T["t"]=pd.to_datetime(T["t"]); return T

def eq_curve(r,risk): return np.cumprod(1+risk*r)
def maxdd(eq): return ((eq/np.maximum.accumulate(eq))-1).min()*100

def monthly(T,risk):
    eq=eq_curve(T["r"].values,risk)
    s=pd.Series(eq,index=T["t"]); me=s.resample("ME").last().dropna()
    mret=me.pct_change().dropna()
    mret=pd.concat([pd.Series([me.iloc[0]-1],index=[me.index[0]]),mret])
    return eq,mret

def report(T,label,risk):
    r=T["r"].values; n=len(r); wr=(r>0).mean()*100; exp=r.mean()
    eq,mret=monthly(T,risk)
    avg=mret.mean()*100; med=mret.median()*100; pos=(mret>0).mean()*100
    dd=maxdd(eq); sh=mret.mean()/mret.std()*np.sqrt(12) if mret.std()>0 else 0
    span=(T["t"].iloc[-1]-T["t"].iloc[0]).days/30.44; tpm=n/span
    print(f"  {label:9s} risk={risk*100:.1f}% | n={n:4d} ({tpm:4.1f}/міс) exp={exp:+.3f}R WR={wr:.0f}% | "
          f"міс avg={avg:+.2f}% med={med:+.2f}% +міс={pos:.0f}% | DD={dd:+.0f}% Sharpe={sh:.2f} | ×{eq[-1]:.1f}")
    return dd

ENG=[("KC","KC-only"),("FVG","FVG-only"),("BOTH","KC+FVG")]
Ts={w:collect(w) for w,_ in ENG}

print("="*96);print("БАЗА 1 — однаковий risk 1%/угода (apples-to-apples):");print("="*96)
dd1={}
for w,lbl in ENG: dd1[w]=report(Ts[w],lbl,0.01)

print("\n"+"="*96);print("БАЗА 2 — однаковий бюджет просадки DD≈44% (скільки тоді /міс):");print("="*96)
for w,lbl in ENG:
    risk=min(0.01*44/abs(dd1[w]),0.06)   # лінійна нормалізація ризику під DD44, стеля 6%
    report(Ts[w],lbl,risk)

print("\n(Послідовне компаундування за часом; угоди різних монет накладаються —")
print(" абсолютна DD у реалі трохи вища, але порівняння двигунів між собою чесне.)")
