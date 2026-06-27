"""OOS + walk-forward для структури ринку; комбінація з ADX+сесія; risk-sweep під 10%/міс@50%DD."""
import numpy as np
import pandas as pd
import lib_data as L
import lib_split as SP
import strategies as ST
import engine as E
import market_structure as MS

pd.set_option("display.width", 200)

btc15 = L.load_btc_15m()
is15, oos15 = SP.split(btc15)
is4 = ST.resample(is15, "4h"); oos4 = ST.resample(oos15, "4h"); full4 = ST.resample(btc15, "4h")

def struct_of(d, k): return MS.compute_structure(d, k)

# ---------- A) OOS для топ-IS кандидатів (параметри зафіксовані з IS) ----------
print("===== A) IS vs OOS для топ структурних кандидатів (risk 1%) =====")
cands = [
    dict(name="swing-BO (both,k3,struct,rr2)", k=3, mode="both", stop_mode="struct", rr=2.0),
    dict(name="BOS-cont (cont,k3,atr,rr2)",    k=3, mode="cont", stop_mode="atr",    rr=2.0),
    dict(name="swing-BO (both,k2,atr,rr2)",     k=2, mode="both", stop_mode="atr",     rr=2.0),
]
for cc in cands:
    out = []
    for d, tag in [(is4, "IS"), (oos4, "OOS")]:
        side, sd = MS.ms_signals(d, k=cc["k"], mode=cc["mode"], stop_mode=cc["stop_mode"],
                                 atr_mult=2.0, stop_cap_atr=4.0, rr=cc["rr"])
        m = E.backtest(d, side, sd, E.Config(rr=cc["rr"], risk_pct=0.01, bar_minutes=240)).metrics
        out.append((tag, m))
    print(f"\n{cc['name']}:")
    for tag, m in out:
        print(f"  {tag}: {E.fmt_metrics(m)}")

# ---------- helpers для фільтрів ----------
def adx_di(d, n=14):
    h, l = d["high"], d["low"]; up = h.diff(); dn = -l.diff()
    pdm = ((up>dn)&(up>0))*up; mdm = ((dn>up)&(dn>0))*dn
    tr = E.true_range(d); a = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi = 100*pdm.ewm(alpha=1/n, adjust=False).mean()/a; mdi = 100*mdm.ewm(alpha=1/n, adjust=False).mean()/a
    adx = (100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).ewm(alpha=1/n, adjust=False).mean()
    return adx.to_numpy(), pdi.to_numpy(), mdi.to_numpy()

def apply_filters(d, side, use_adx=True, use_sess=True):
    s = side.copy()
    if use_adx:
        adx, pdi, mdi = adx_di(d, 14)
        keep_long = (adx>25)&(pdi>mdi); keep_short = (adx>25)&(mdi>pdi)
        s[(s>0)&~keep_long] = 0; s[(s<0)&~keep_short] = 0
    if use_sess:
        hours = d.index.hour.to_numpy(); hn = np.roll(hours,-1)
        allowed = np.isin(hn,[0,4,8])
        s[~allowed] = 0
    return s

# ---------- B) Walk-forward структурного breakout (вибір k/mode/stop/rr) ----------
print("\n\n===== B) Walk-forward структурного breakout (risk 2%) =====")
YR=int(365*24/4); TRAIN,TEST=2*YR,1*YR
STRUCT_FULL={k:struct_of(full4,k) for k in [2,3]}; ATR_FULL=E.atr(full4,14).to_numpy()
def full_side(k,mode,stop_mode):
    return MS.ms_signals(full4,k=k,mode=mode,stop_mode=stop_mode,atr_mult=2.0,stop_cap_atr=4.0,
                         rr=2.0,struct=STRUCT_FULL[k],atr_arr=ATR_FULL)
SIDES={(k,mo,st):full_side(k,mo,st) for k in [2,3] for mo in ["cont","both"] for st in ["struct","atr"]}

def wf(filter_adx=False, filter_sess=False, risk=0.02, label=""):
    eq=10000.0; et,ev=[],[]; tt=[]; start=0
    while start+TRAIN+TEST<=len(full4):
        a,b=start,start+TRAIN; ta,tb=b,min(b+TEST,len(full4)); best=None
        for k in [2,3]:
            for mo in ["cont","both"]:
                for st in ["struct","atr"]:
                    side_full,sd_full=SIDES[(k,mo,st)]
                    s_tr=apply_filters(full4.iloc[a:b], side_full[a:b], filter_adx, filter_sess)
                    for rr in [2.0,3.0]:
                        m=E.backtest(full4.iloc[a:b],s_tr,sd_full[a:b],E.Config(rr=rr,risk_pct=0.01,bar_minutes=240)).metrics
                        if m["n_trades"]>=15 and (best is None or m["profit_factor"]>best[0]):
                            best=(m["profit_factor"],k,mo,st,rr)
        if best:
            _,k,mo,st,rr=best; side_full,sd_full=SIDES[(k,mo,st)]
            s_te=apply_filters(full4.iloc[ta:tb], side_full[ta:tb], filter_adx, filter_sess)
            r=E.backtest(full4.iloc[ta:tb],s_te,sd_full[ta:tb],E.Config(rr=rr,risk_pct=risk,bar_minutes=240,initial_equity=eq))
            for _,x in r.trades.iterrows(): et.append(x["exit_time"]); ev.append(x["equity"])
            if len(r.trades): eq=r.trades["equity"].iloc[-1]; tt.append(r.trades)
        start+=TEST
    if not tt: return None
    allt=pd.concat(tt); eqs=pd.Series(ev,index=pd.DatetimeIndex(et)); eqs=eqs[~eqs.index.duplicated(keep="last")]
    daily=eqs.resample("1D").last().ffill(); dd=(daily/daily.cummax()-1).min()
    yrs=(eqs.index[-1]-eqs.index[0]).days/365.25; cagr=(eqs.iloc[-1]/10000)**(1/yrs)-1
    mret=daily.resample("ME").last().pct_change().dropna(); dret=daily.pct_change().dropna()
    sh=np.sqrt(365)*dret.mean()/dret.std() if dret.std()>0 else 0
    pf=allt[allt.net>0].net.sum()/max(-allt[allt.net<=0].net.sum(),1e-9)
    print(f"  {label:34} угод={len(allt):3d} final×={eqs.iloc[-1]/10000:4.2f} CAGR={cagr*100:5.1f}% "
          f"avg_mo={mret.mean()*100:4.2f}% DD={dd*100:5.1f}% Sharpe={sh:.2f} PF={pf:.2f}")
    return dict(cagr=cagr, avg_mo=mret.mean(), dd=dd, sharpe=sh, final=eqs.iloc[-1]/10000)

wf(False, False, 0.02, "чистий structure-BO")
wf(True,  False, 0.02, "+ ADX25+DI")
wf(True,  True,  0.02, "+ ADX + сесія(00-12)")

# ---------- C) risk-sweep найкращого стека під 10%/міс@50%DD ----------
print("\n===== C) Risk-sweep стека (structure-BO + ADX + сесія) — чи реально 10%/міс@50%DD? =====")
print(f"{'risk%':>6}{'CAGR%':>8}{'avg_mo%':>9}{'maxDD%':>8}{'final×':>8}")
for risk in [0.02,0.05,0.08,0.10,0.15]:
    r=wf(True,True,risk,f"  (risk {risk*100:.0f}%)")
