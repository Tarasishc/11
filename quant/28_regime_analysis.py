"""Профітніша на бичці чи ведмежці? Розмітка угод за макрорежимом BTC (денний)
і дохідність по режимах × напрямках. Нормування на тривалість (R/місяць)."""
import importlib.util, builtins
import numpy as np, pandas as pd
import lib_data as L, engine as E
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("r23","quant/23_reduce_dd.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
DATA=m.DATA

# --- макрорежим за BTC (денний) ---
btc_d=DATA["BTC"]["close"].resample("1D").last().dropna()
ema200=E.ema(btc_d,200); slope=ema200-ema200.shift(20)
regime=pd.Series("range",index=btc_d.index)
regime[(btc_d>ema200)&(slope>0)]="bull"
regime[(btc_d<ema200)&(slope<0)]="bear"
regime=regime.shift(1)  # без lookahead: режим попереднього дня
# тривалість кожного режиму (місяців)
days=regime.value_counts(); months={k:v/30.4 for k,v in days.items()}

# --- угоди combo KC+ADX>20 ---
rows=[]
for c,d in DATA.items():
    side,sd=m.kc_signals(d,adx_min=20)
    t=E.backtest(d,side,sd,E.Config(rr=2.0,risk_pct=0.01,bar_minutes=240)).trades
    if len(t): t=t.copy(); t["coin"]=c; rows.append(t[["entry_time","r_mult","coin","side"]])
T=pd.concat(rows,ignore_index=True).sort_values("entry_time").reset_index(drop=True)
# режим на момент входу
rday=regime.reindex(pd.to_datetime(T["entry_time"]).dt.normalize().dt.tz_localize(None) if T["entry_time"].dt.tz is None else pd.to_datetime(T["entry_time"]).dt.normalize(), method="ffill")
T["regime"]=regime.reindex(pd.DatetimeIndex(pd.to_datetime(T["entry_time"])).normalize(),method="ffill").values

print("="*60); print("ТРИВАЛІСТЬ РЕЖИМІВ (днів / місяців)"); print("="*60)
for r in ["bull","bear","range"]:
    print(f"  {r:6}: {int(days.get(r,0)):4d} днів (~{months.get(r,0):.0f} міс)")

print("\n"+"="*60); print("ДОХІДНІСТЬ ПО РЕЖИМАХ (R-простір, усі угоди)"); print("="*60)
print(f"  {'режим':7}{'n':>5}{'сумаR':>8}{'exp(R)':>8}{'WR%':>6}{'R/міс':>8}")
for r in ["bull","bear","range"]:
    g=T[T.regime==r]["r_mult"]
    if len(g):
        print(f"  {r:7}{len(g):5d}{g.sum():8.1f}{g.mean():8.3f}{(g>0).mean()*100:6.0f}{g.sum()/max(months.get(r,1),1):8.2f}")

print("\n"+"="*60); print("ЛОНГ vs ШОРТ по режимах (сумаR / expectancy)"); print("="*60)
print(f"  {'режим':7}{'L n':>5}{'L sumR':>8}{'L exp':>7}{'   ':>3}{'S n':>5}{'S sumR':>8}{'S exp':>7}")
for r in ["bull","bear","range"]:
    g=T[T.regime==r]
    Lg=g[g.side=="L"]["r_mult"]; Sg=g[g.side=="S"]["r_mult"]
    print(f"  {r:7}{len(Lg):5d}{Lg.sum():8.1f}{Lg.mean() if len(Lg) else 0:7.2f}   "
          f"{len(Sg):5d}{Sg.sum():8.1f}{Sg.mean() if len(Sg) else 0:7.2f}")

print("\n"+"="*60); print("ЗАГАЛОМ: лонг vs шорт"); print("="*60)
for s,nm in [("L","ЛОНГ"),("S","ШОРТ")]:
    g=T[T.side==s]["r_mult"]
    print(f"  {nm}: n={len(g)} сумаR={g.sum():.1f} exp={g.mean():+.3f} WR={(g>0).mean()*100:.0f}%")

print("\n"+"="*60); print("R/місяць — пряма відповідь 'бичка чи ведмежка'"); print("="*60)
for r in ["bull","bear","range"]:
    g=T[T.regime==r]["r_mult"]; rpm=g.sum()/max(months.get(r,1),1)
    print(f"  {r:7}: {rpm:.2f} R/міс  ({'найприбутковіше' if False else ''})")
best=max(["bull","bear","range"], key=lambda r: T[T.regime==r]['r_mult'].sum()/max(months.get(r,1),1))
print(f"  => найвища дохідність на одиницю часу: {best.upper()}")
