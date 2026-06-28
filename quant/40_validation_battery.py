"""Батарея незалежних перевірок KC+FVG: чи едж справжній.
A) стабільність по періодах  B) held-out монета MNT  C) контроль випадковими входами
D) стрес витрат  E) Monte-Carlo просадки."""
import importlib.util, builtins, numpy as np, pandas as pd
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("c39","quant/39_combined_concentration.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
import lib_data as L, strategies as ST, engine as E
BASE=m.BASE

def combined(d):
    return [r for _,r in m.kc(d)]+[r for _,r in m.fvg(d)]
def combined_t(d):
    return m.kc(d)+m.fvg(d)

print("="*64);print("A) СТАБІЛЬНІСТЬ ПО ПЕРІОДАХ (3 незалежні відрізки)");print("="*64)
allt=[]
for c,d in BASE.items(): allt+=combined_t(d)
T=pd.DataFrame(allt,columns=["t","r"]); T["t"]=pd.to_datetime(T["t"])
for lo,hi in [("2017","2020"),("2020","2023"),("2023","2027")]:
    g=T[(T.t>=lo)&(T.t<hi)]["r"]
    print(f"  {lo}-{hi}: n={len(g):4d} expectancy={g.mean():+.3f}R WR={(g>0).mean()*100:.0f}% sumR={g.sum():.0f}")

print("\n"+"="*64);print("B) HELD-OUT МОНЕТА MNT (параметри не підбирались на ній)");print("="*64)
mnt=L.load_any("quant/data/mnt_4h.csv")
r=np.array(combined(mnt))
print(f"  MNT: n={len(r)} expectancy={r.mean():+.3f}R WR={(r>0).mean()*100:.0f}% sumR={r.sum():.0f}  "
      f"{'едж є' if r.mean()>0.1 else 'слабко'}")

print("\n"+"="*64);print("C) КОНТРОЛЬ ВИПАДКОВИМИ ВХОДАМИ (движок чесний?)");print("="*64)
FEE,SLIP=m.FEE,m.SLIP
def rand_scan(d,n_sig,seed):
    o,h,l,c=[d[x].to_numpy() for x in ["open","high","low","close"]];atr=E.atr(d,14).to_numpy();N=len(c)
    rng=np.random.default_rng(seed);R=[];used=np.zeros(N,bool)
    idxs=rng.choice(range(210,N-1),size=min(n_sig,N-300),replace=False)
    for i in sorted(idxs):
        if not np.isfinite(atr[i]) or atr[i]<=0: continue
        si=rng.choice([1,-1]);D=2*atr[i];eb=i+1;en=o[eb]*(1+SLIP) if si>0 else o[eb]*(1-SLIP)
        st=en-si*D;tg=en+si*2*D;j=eb;rr=None
        while j<N:
            if (l[j]<=st) if si>0 else (h[j]>=st): ex=st*(1-SLIP) if si>0 else st*(1+SLIP);rr=si*(ex-en)/D-2*FEE*(en/D);break
            if (h[j]>=tg) if si>0 else (l[j]<=tg): rr=2-2*FEE*(en/D);break
            j+=1
        if rr is None: rr=si*(c[-1]-en)/D
        R.append(rr)
    return R
nstrat=sum(len(combined(d)) for d in BASE.values())//3
exps=[]
for seed in range(10):
    rr=[]
    for c,d in BASE.items(): rr+=rand_scan(d,nstrat,seed)
    exps.append(np.mean(rr))
print(f"  Випадкові входи (10 сідів): сер.expectancy={np.mean(exps):+.3f}R (має бути ~0/мінус через витрати)")
print(f"  СТРАТЕГІЯ KC+FVG: expectancy=+0.284R")
print(f"  => різниця {0.284-np.mean(exps):+.3f}R — це і є реальний едж (не артефакт движка)")

print("\n"+"="*64);print("D) СТРЕС ВИТРАТ (×1, ×2, ×3 комісії+слипедж)");print("="*64)
for mult in [1,2,3]:
    m.FEE=0.0005*mult; m.SLIP=0.0003*mult
    rr=[]
    for c,d in BASE.items(): rr+=combined(d)
    r=np.array(rr); print(f"  ×{mult} витрат: expectancy={r.mean():+.3f}R WR={(r>0).mean()*100:.0f}% {'OK' if r.mean()>0 else 'ЗБИТОК'}")
m.FEE,m.SLIP=FEE,SLIP

print("\n"+"="*64);print("E) MONTE-CARLO просадки (1000 перетасувань порядку угод)");print("="*64)
rr=[]
for c,d in BASE.items(): rr+=combined(d)
r=np.array(rr); rng=np.random.default_rng(1); dds=[]
for _ in range(1000):
    p=rng.permutation(r); eq=np.cumprod(1+0.01*p); dd=(eq/np.maximum.accumulate(eq)-1).min()*100; dds.append(dd)
print(f"  maxDD (риск1%/угода, R-простір): медіана={np.median(dds):.0f}% 5й перц={np.percentile(dds,5):.0f}% найгірша={min(dds):.0f}%")
print(f"  Підсумок батареї нижче.")
