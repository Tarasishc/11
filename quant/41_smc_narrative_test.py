"""Механізація СУТІ Narrative (AlexxxFX): Premium/Discount + liquidity sweep фрактала
-> розворот до протилежної зони. Це reversal-примітив. Чесно: D1 + H4, R-простір, IS/OOS.
Очікування: реверси були слабкі (§11/§35) — перевіряємо, чи тут інакше."""
import numpy as np, pandas as pd
import lib_data as L, strategies as ST, engine as E, market_structure as MS

def load(name):
    if name=="BTC": return L.load_btc_15m()
    return L.load_any(f"quant/data/{name.lower()}_4h.csv")

def smc_signals(d, range_lb=40, rr=2.0):
    """Premium/Discount via dealing range; sweep останнього swing + rejection -> reversal."""
    st=MS.compute_structure(d,2); cSH,cSL=st["cur_SH"],st["cur_SL"]
    h,l,c=d["high"].to_numpy(),d["low"].to_numpy(),d["close"].to_numpy()
    rng_hi=pd.Series(h).rolling(range_lb).max().to_numpy()
    rng_lo=pd.Series(l).rolling(range_lb).min().to_numpy()
    mid=(rng_hi+rng_lo)/2
    a=E.atr(d,14).to_numpy(); n=len(d); side=np.zeros(n); sd=np.full(n,np.nan)
    prem=c>mid; disc=c<mid
    for i in range(n):
        if not np.isfinite(cSH[i]) or not np.isfinite(a[i]): continue
        # SHORT: у Premium ціна зняла swing high (sweep) і закрилась назад нижче (rejection)
        if prem[i] and h[i]>cSH[i] and c[i]<cSH[i]:
            side[i]=-1; sd[i]=max(h[i]-c[i]+0.2*a[i], 0.5*a[i])
        # LONG: у Discount зняла swing low і закрилась назад вище
        elif disc[i] and l[i]<cSL[i] and c[i]>cSL[i]:
            side[i]=1; sd[i]=max(c[i]-l[i]+0.2*a[i], 0.5*a[i])
    return side, sd

print("Механізована суть Narrative (premium/discount + sweep reversal), RR2:\n")
for tf,bmin in [("1d",1440),("4h",240)]:
    print(f"--- ТФ {tf} ---")
    allm=[]
    for coin in ["BTC","ETH","SOL"]:
        d=ST.resample(load(coin),tf)
        side,sd=smc_signals(d)
        m=E.backtest(d,side,sd,E.Config(rr=2.0,risk_pct=0.01,bar_minutes=bmin)).metrics
        allm.append((coin,m))
        print(f"  {coin}: n={m['n_trades']:3d} exp={m['expectancy_R']:+.3f} WR={m['win_rate']*100:.0f}% PF={m['profit_factor']:.2f} avg_mo={m['avg_monthly']*100:.2f}%")
    print()

# IS/OOS на D1 разом
print("IS/OOS (D1, 3 монети разом):")
import lib_split as SP
for tag in ["IS","OOS"]:
    rr=[]
    for coin in ["BTC","ETH","SOL"]:
        d=ST.resample(load(coin),"1d"); isd,oosd=SP.split(d,0.6); dd=isd if tag=="IS" else oosd
        side,sd=smc_signals(dd)
        t=E.backtest(dd,side,sd,E.Config(rr=2.0,risk_pct=0.01,bar_minutes=1440)).trades
        if len(t): rr.append(t["r_mult"].values)
    r=np.concatenate(rr) if rr else np.array([0])
    print(f"  {tag}: n={len(r)} exp={r.mean():+.3f}R WR={(r>0).mean()*100:.0f}%")
print("\n(Порівняння: FVG +0.28R, KC +0.28R. Дивимось, чи Narrative-реверс конкурентний.)")
