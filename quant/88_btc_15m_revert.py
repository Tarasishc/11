"""Реверсія BTC 15m у ПРИРОДНОМУ вигляді (ціль не фіксований RR, а рівень):
  MEAN — вхід за краєм Боллінджера, ціль = середина(SMA20), стоп 1×ATR за входом
  OSC  — вхід за краєм, ціль = ПРОТИЛЕЖНИЙ край смуги, стоп 1×ATR
Це показує, чи є реверсія взагалі (нехай з низьким/змінним RR), навіть якщо
фіксований RR2/3 (скрипт 87) не працює. IS/OOS, реальні витрати, песимізм.
Ключове: exp у R (net/ризик) + РЕАЛІЗОВАНИЙ RR + WR. Приймаємо лише OOS exp>0."""
import numpy as np, pandas as pd
import lib_data as L

FEE, ES, SS = 0.0005, 0.0002, 0.0005
ADX_MAX = 20
d = L.load_btc_15m()
o, h, l, c = [d[x].to_numpy(dtype=float) for x in ["open", "high", "low", "close"]]
n = len(c); idx = pd.DatetimeIndex(d.index); ts = idx.tz_localize(None) if idx.tz is not None else idx
def rma(x, p): return pd.Series(x).ewm(alpha=1/p, adjust=False).mean().to_numpy()
pc = np.concatenate([[c[0]], c[:-1]]); tr = np.maximum(h-l, np.maximum(np.abs(h-pc), np.abs(l-pc))); atr = rma(tr, 14)
up = np.concatenate([[0], np.diff(h)]); dn = np.concatenate([[0], -np.diff(l)])
pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
pdi = 100*rma(pdm, 14)/atr; mdi = 100*rma(mdm, 14)/atr
adx = rma(100*np.abs(pdi-mdi)/np.where(pdi+mdi == 0, np.nan, pdi+mdi), 14)
ma = pd.Series(c).rolling(20).mean().to_numpy(); sd = pd.Series(c).rolling(20).std().to_numpy()
bb_up, bb_lo = ma+2*sd, ma-2*sd
cut = ts[int(n*0.6)]

def sim(target_kind, regime=True, max_hold=96):
    """target_kind: 'mean' -> SMA20; 'osc' -> протилежний край. max_hold=96 барів (1 доба)."""
    rows = []; i = 210
    rng = adx < ADX_MAX
    while i < n-1:
        si = 0
        if np.isfinite(atr[i]) and atr[i] > 0 and (rng[i] or not regime):
            if c[i] < bb_lo[i]: si = 1
            elif c[i] > bb_up[i]: si = -1
        if si == 0: i += 1; continue
        eb = i+1; en = o[eb]*(1 + si*ES); D = atr[i]
        stop = en - si*D
        tgt = ma[i] if target_kind == "mean" else (bb_up[i] if si > 0 else bb_lo[i])
        if (si > 0 and tgt <= en) or (si < 0 and tgt >= en): i += 1; continue   # ціль не в бік прибутку
        j = eb; ex = None
        while j < n and j - eb < max_hold:
            hs = (l[j] <= stop) if si > 0 else (h[j] >= stop)
            ht = (h[j] >= tgt) if si > 0 else (l[j] <= tgt)
            if hs: ex = ("stop", stop, j); break
            if ht: ex = ("tgt", tgt, j); break
            j += 1
        if ex is None: ex = ("time", c[min(j, n-1)], min(j, n-1))
        exf = ex[1]*(1 - si*SS) if ex[0] == "stop" else ex[1]
        R = si*(exf-en)/D - 2*FEE*(en/D)
        rr_real = abs(tgt-en)/D
        rows.append((ts[eb], R, rr_real, ex[0])); i = ex[2] + 1
    return pd.DataFrame(rows, columns=["t", "R", "rr", "ex"])

print(f"BTC 15m реверсія природна (край Боллінджера -> рівень), ADX<{ADX_MAX}, стоп 1×ATR, песимізм.")
print(f"Витрати fee {FEE*100:.2f}%/сторону. IS/OOS зріз {cut.date()}. Приймаємо лише OOS exp>0.\n")
print(f"{'ціль':6s} {'рег':4s} | {'IS n':>6} {'IS exp':>7} {'IS WR':>5} {'RRсер':>5} | {'OOS n':>6} {'OOS exp':>8} {'OOS WR':>6}")
print("-"*88)
for tk, lbl in [("mean", "серед"), ("osc", "проткрай")]:
    for regime in [True, False]:
        T = sim(tk, regime)
        iss = T[T.t < cut]; oos = T[T.t >= cut]
        vis = "✓" if len(oos) and oos["R"].mean() > 0 else ""
        print(f"{lbl:6s} {'ADX<20' if regime else 'усі':6s} | {len(iss):6d} {iss['R'].mean():+7.3f} "
              f"{(iss['R']>0).mean()*100:4.0f}% {iss['rr'].mean():5.2f} | {len(oos):6d} {oos['R'].mean():+8.3f} "
              f"{(oos['R']>0).mean()*100:5.0f}% {vis}")
    print()
print("Якщо і тут OOS≤0 -> реверсії на BTC 15m нема (навіть у природному RR).")
print("(WR високий + RRсер<1 і exp>0 було б справжньою реверсією — інший профіль, ніж RR2/3.)")
