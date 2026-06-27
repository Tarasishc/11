"""АУДИТ РЕАЛІСТИЧНОСТІ: чи збігається бектест із реальним ринком.
A) витрати/слипедж стрес  B) mark-to-market просадка (реальна внутрішньоугодова)
C) Monte-Carlo перетасування (розподіл DD)  D) корельований крах/ліквідація.
Конфіг: KC+ADX>20, BTC+ETH+SOL, vol-target+DD-throttle, risk 5% (точка 10%/міс@49%DD)."""
import importlib.util, builtins
import numpy as np, pandas as pd, heapq
import lib_data as L, strategies as ST, engine as E

_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("r23","quant/23_reduce_dd.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
builtins.print=_p

DATA=m.DATA; COINVOL=m.COINVOL
RISK=0.05

def gen_cost(fee,slip,funding,adx_min=20):
    rows=[]
    for c,d in DATA.items():
        side,sd=m.kc_signals(d,adx_min=adx_min)
        cfg=E.Config(rr=2.0,risk_pct=0.01,bar_minutes=240,fee=fee,slip=slip,funding_per_8h=funding)
        t=E.backtest(d,side,sd,cfg).trades
        if len(t):
            t=t.copy(); t["coin"]=c
            vs=COINVOL[c].reindex(pd.to_datetime(t["entry_time"])).clip(0.3,3).values
            t["volscale"]=(1.0/vs).clip(0.3,2.5)
            t["stop_dist"]=(t["entry"]-t["stop"]).abs()
            t["sidi"]=np.where(t["side"]=="L",1,-1)
            rows.append(t[["entry_time","exit_time","r_mult","coin","volscale","entry","stop_dist","sidi"]])
    return pd.concat(rows,ignore_index=True).sort_values("entry_time")

def sim_eq(T,risk,vol_target=True,dd_throttle=0.25,throttle_f=0.5,init=10000.0,record=False,max_conc=0):
    T=T.sort_values("entry_time").reset_index(drop=True); eq=init; peak=init; heap=[]
    ct=[T.entry_time.min()]; cv=[eq]; eq_at_entry=np.full(len(T),np.nan); sizes=np.full(len(T),np.nan)
    for i,r in T.iterrows():
        et=r["entry_time"]
        while heap and heap[0][0]<=et:
            xt,p=heapq.heappop(heap); eq+=p; peak=max(peak,eq); ct.append(xt);cv.append(eq)
        if max_conc and len(heap)>=max_conc:
            continue
        size=risk*eq
        if vol_target: size*=r["volscale"]
        if dd_throttle and eq<peak*(1-dd_throttle): size*=throttle_f
        eq_at_entry[i]=eq; sizes[i]=size
        heapq.heappush(heap,(r["exit_time"], r["r_mult"]*size))
    while heap:
        xt,p=heapq.heappop(heap); eq+=p; ct.append(xt);cv.append(eq)
    s=pd.Series(cv,index=pd.DatetimeIndex(ct)).sort_index(); s=s[~s.index.duplicated(keep="last")]
    if record: return s, eq_at_entry, sizes
    return s

def stats(s):
    d=s.resample("1D").last().ffill(); dd=(d/d.cummax()-1).min()
    mo=d.resample("ME").last().pct_change().dropna().mean()
    return mo,dd

print("="*66)
print("A) СТРЕС ВИТРАТ/СЛИПЕДЖУ (combo, risk 5%, avg_mo & DD)")
print("="*66)
print(f"  {'сценарій':32}{'fee':>6}{'slip':>6}{'avg_mo%':>9}{'maxDD%':>8}")
for name,fee,slip,fund in [
    ("базовий (мій бектест)",0.0005,0.0003,0.0001),
    ("+50% витрат",0.00075,0.00045,0.00015),
    ("2x витрат (альти реалістичніше)",0.0010,0.0006,0.0002),
    ("важкий слипедж стопів 0.10%",0.0005,0.0010,0.0001),
    ("песимістичний (taker .075 + slip .15)",0.00075,0.0015,0.0003)]:
    T=gen_cost(fee,slip,fund); s=sim_eq(T,RISK); mo,dd=stats(s)
    print(f"  {name:32}{fee*100:5.3f}%{slip*100:5.3f}%{mo*100:9.2f}{dd*100:8.0f}")

print("\n"+"="*66)
print("B) MARK-TO-MARKET ПРОСАДКА (реальна внутрішньоугодова, не лише по виходах)")
print("="*66)
T=gen_cost(0.0005,0.0003,0.0001)
s,eqent,sizes=sim_eq(T,RISK,record=True)
realized_daily=s.resample("1D").last().ffill()
grid=realized_daily.index
# денні OHLC по монетах, вирівняні до grid
CO={c:DATA[c]["close"].resample("1D").last().reindex(grid,method="ffill") for c in DATA}
LO={c:DATA[c]["low"].resample("1D").min().reindex(grid,method="ffill") for c in DATA}
HI={c:DATA[c]["high"].resample("1D").max().reindex(grid,method="ffill") for c in DATA}
add_close=np.zeros(len(grid)); add_worst=np.zeros(len(grid))
Tr=T.sort_values("entry_time").reset_index(drop=True)
for i,row in Tr.iterrows():
    s_idx=grid.searchsorted(row["entry_time"]); e_idx=grid.searchsorted(row["exit_time"])
    if e_idx<=s_idx: continue
    c=row["coin"]; p=row["entry"]; sd=row["stop_dist"]; si=row["sidi"]; sz=sizes[i]
    cl=CO[c].values[s_idx:e_idx]; ad=(LO[c].values[s_idx:e_idx] if si>0 else HI[c].values[s_idx:e_idx])
    add_close[s_idx:e_idx]+= si*(cl-p)/sd*sz
    add_worst[s_idx:e_idx]+= si*(ad-p)/sd*sz
mtm_close=realized_daily.values+add_close; mtm_worst=realized_daily.values+add_worst
def ddof(v):
    v=pd.Series(v,index=grid); return (v/v.cummax()-1).min()*100
print(f"  Просадка по реалізованому капіталу (як у звіті): {ddof(realized_daily.values):.0f}%")
print(f"  Просадка MTM по денних close (реалістична)     : {ddof(mtm_close):.0f}%")
print(f"  Просадка MTM по екстремумах (консерв. межа)     : {ddof(mtm_worst):.0f}%")
print("  => реальна DD ГІРША за реалізовану; орієнтуйся на MTM-close.")

print("\n"+"="*66)
print("C) MONTE-CARLO перетасування угод (DD/прибуток як розподіл, N=600)")
print("="*66)
rm=T.sort_values("entry_time")["r_mult"].values.copy()
rng=np.random.default_rng(42); B=8; dds=[]; mos=[]
Tc=T.sort_values("entry_time").reset_index(drop=True).copy()
for _ in range(600):
    blocks=[rm[i:i+B] for i in range(0,len(rm),B)]; rng.shuffle(blocks)
    Tc["r_mult"]=np.concatenate(blocks)[:len(rm)]
    e=sim_eq(Tc,RISK); mo,dd=stats(e); dds.append(dd*100); mos.append(mo*100)
dds=np.array(dds); mos=np.array(mos)
print(f"  maxDD:  медіана={np.median(dds):.0f}%  95-й перц(невдача)={np.percentile(dds,5):.0f}%  "
      f"найгірша={dds.min():.0f}%  P(DD гірше -60%)={(dds<-60).mean()*100:.0f}%")
print(f"  avg_mo: медіана={np.median(mos):.1f}%  5-й перц={np.percentile(mos,5):.1f}%")
print(f"  (фактичний порядок дав DD={ddof(realized_daily.values):.0f}% — це лише ОДИН шлях)")

print("\n"+"="*66)
print("D) КОРЕЛЬОВАНИЙ КРАХ / ЛІКВІДАЦІЯ (плече при risk 5%)")
print("="*66)
# валове плече = sum(open notional)/equity у часі
ev=[]
for i,row in Tr.iterrows():
    notion=sizes[i]/row["stop_dist"]*row["entry"]  # qty*entry
    ev.append((row["entry_time"],notion,eqent[i])); ev.append((row["exit_time"],-notion,None))
ev=sorted(ev,key=lambda x:x[0]); openN=0; maxlev=0; peak_t=None
for t,dn,eqe in ev:
    openN+=dn
    if eqe: lev=openN/eqe;
    if eqe and lev>maxlev: maxlev=lev; peak_t=t
print(f"  Пік валового плеча: ~{maxlev:.1f}x (одночасні позиції по 3 монетах)")
liq=1.0/maxlev*100
print(f"  Орієнтовний поріг ліквідації при піку: ~−{liq:.0f}% синхронного руху проти позицій")
# історичні синхронні денні падіння BTC+ETH+SOL
ret=pd.DataFrame({c:DATA[c]["close"].resample("1D").last().pct_change() for c in DATA}).dropna()
worst=(ret.mean(axis=1)).nsmallest(5)*100
print("  Найгірші синхронні денні рухи (середнє по 3 монетах):")
for d,v in worst.items(): print(f"     {d.date()}: {v:.0f}%")
print(f"  Найгірша MTM-просадка за 1 день у бектесті: {ddof(mtm_worst):.0f}% (повна крива)")
print("  ВИСНОВОК: при піку плеча синхронний обвал міг би наблизити до ліквідації ДО стопів —")
print("  бектест цього не моделює. Контроль: cap на одночасну експозицію / нижчий ризик.")

print("\n"+"="*66)
print("E) ВІДПОВІДАЛЬНА КОНФІГУРАЦІЯ: нижчий ризик + ліміт одночасних позицій")
print("="*66)
def peak_lev(T,sizes):
    Tr=T.sort_values("entry_time").reset_index(drop=True); ev=[]
    for i,row in Tr.iterrows():
        if np.isnan(sizes[i]): continue
        notion=sizes[i]/row["stop_dist"]*row["entry"]
        ev.append((row["entry_time"],notion,True,i)); ev.append((row["exit_time"],-notion,False,i))
    ev=sorted(ev,key=lambda x:x[0]); openN=0; ml=0
    # потрібна equity у часі — апроксимуємо eqent на вході
    for t,dn,isopen,i in ev:
        openN+=dn
        if isopen and not np.isnan(eqent_g[i]) and eqent_g[i]>0:
            ml=max(ml,openN/eqent_g[i])
    return ml
def mtm_dd(T,sizes,s):
    rd=s.resample("1D").last().ffill(); g=rd.index
    co={c:DATA[c]["close"].resample("1D").last().reindex(g,method="ffill") for c in DATA}
    ac=np.zeros(len(g)); Tr=T.sort_values("entry_time").reset_index(drop=True)
    for i,row in Tr.iterrows():
        if np.isnan(sizes[i]): continue
        a=g.searchsorted(row["entry_time"]); b=g.searchsorted(row["exit_time"])
        if b<=a: continue
        ac[a:b]+= row["sidi"]*(co[row["coin"]].values[a:b]-row["entry"])/row["stop_dist"]*sizes[i]
    v=pd.Series(rd.values+ac,index=g); return (v/v.cummax()-1).min()*100

T=gen_cost(0.0005,0.0003,0.0001)
print(f"  {'конфіг':34}{'avg_mo%':>9}{'realDD%':>8}{'MTM DD%':>9}{'плече':>7}")
for risk,mc in [(0.05,0),(0.03,0),(0.03,3),(0.02,3),(0.02,2),(0.03,2)]:
    s,eqent_g,sizes=sim_eq(T,risk,max_conc=mc,record=True)
    mo,dd=stats(s); md=mtm_dd(T,sizes,s); lev=peak_lev(T,sizes)
    lbl=f"risk {risk*100:.0f}% + cap {mc if mc else '∞'} одночас."
    print(f"  {lbl:34}{mo*100:9.2f}{dd*100:8.0f}{md:9.0f}{lev:7.1f}x")
print("\n  Орієнтир: тримати MTM DD<=55-60% і плече<=4-5x -> risk ~2-3% + cap 2-3 позиції.")
