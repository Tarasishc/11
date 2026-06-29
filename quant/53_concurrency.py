"""РЕАЛЬНИЙ ризик одночасних позицій у портфелі 4 монети (BNB=тільки FVG).
Скільки позицій бувають відкриті РАЗОМ, який % часу, і яке сумарне плече ->
чи є загроза ліквідації."""
import importlib.util, builtins, numpy as np, pandas as pd
from collections import defaultdict
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("c44","quant/44_one_per_coin.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
import lib_data as L, engine as E
BASE3=m.BASE; bnb=L.load_any("quant/data/bnb_4h.csv")

def taken_majors(d):           # одна-на-монету: (вхід, вихід)
    trs=sorted(m.kc_tr(d)+m.fvg_tr(d),key=lambda x:x[0]); idx=d.index; out=[]; ou=-1
    for eb,xb,ts,r in trs:
        if eb>ou: out.append((idx[eb],idx[xb])); ou=xb
    return out
def taken_fvg(d):
    idx=d.index; return [(idx[eb],idx[xb]) for eb,xb,ts,r in m.fvg_tr(d)]

intervals=[]
for c in ["BTC","ETH","SOL"]: intervals+=taken_majors(BASE3[c])
intervals+=taken_fvg(bnb)

ev=sorted([(pd.Timestamp(e),1) for e,x in intervals]+[(pd.Timestamp(x),-1) for e,x in intervals])
cur=0; mx=0; dur=defaultdict(float); prev=None
for t,delta in ev:
    if prev is not None: dur[cur]+=(t-prev).total_seconds()
    cur+=delta; mx=max(mx,cur); prev=t
tot=sum(dur.values())
print(f"Усього угод у портфелі (увесь період): {len(intervals)}")
print(f"МАКС одночасно відкритих позицій: {mx} (монет у портфелі: 4)\n")
print("Скільки часу скільки позицій відкрито РАЗОМ:")
for k in sorted(dur): print(f"  {k} поз: {dur[k]/tot*100:5.1f}% часу")
opent=sum(v for k,v in dur.items() if k>0)/tot*100
print(f"  (хоч одна відкрита: {opent:.0f}% часу)\n")

print("Типова дистанція стопа і плече (risk 1.5%/угода):")
for c,d in list(BASE3.items())+[("BNB",bnb)]:
    s=(E.atr(d,14)/d["close"]).median()*100
    print(f"  {c}: ATR14≈{s:.1f}% -> стоп≈{s:.1f}-{2*s:.1f}% -> плече/угоду ≈ {1.5/(1.5*s/100*100/1.5):.1f}x"
          if False else f"  {c}: ATR14≈{s:.1f}% -> стоп KC≈{2*s:.1f}%, FVG≈{s:.1f}%")
# плече: notional/equity = risk% / stop%
print("\nОцінка плеча при risk 1.5%/угода:")
for stop in [2,3,4]:
    notional=1.5/stop
    print(f"  стоп {stop}%: нотіонал/угоду ≈ {notional*100:.0f}% екв -> {mx} угод разом ≈ {notional*mx:.1f}x плеча, "
          f"максимум під ризиком {1.5*mx:.1f}% екв")
