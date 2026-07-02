"""НОВА СТРАТЕГІЯ ДЛЯ BTC: три структурно різні сім'ї (не price-action входи).
  A) TSMOM: знак ret за N днів -> завжди-в-позиції у той бік (daily, вхід на open)
  B) VolBreakout дня: стоп-вхід open+k*ATR1D, стоп=open, вихід на close дня (15m-істина)
  C) Donchian 55/20 (черепахи): пробій 55д -> вхід; вихід на протилежному 20д каналі
  D) Buy&Hold — бенчмарк, який треба обґрунтувати.
Витрати: тейкер 0.05% + слип 0.05% на сторону (фліп = 2 сторони). IS 60% / OOS 40%.
Вибір параметрів ЛИШЕ на IS (мінімальні сітки), OOS — один погляд. Чесність > результат."""
import numpy as np, pandas as pd
import lib_data as L, strategies as ST

COST_SIDE = 0.001                                  # 0.05% fee + 0.05% slip
M15 = L.load_btc_15m()
D1 = ST.resample(M15, "1D")
n1 = len(D1); cut_i = int(n1*0.6); cut_ts = D1.index[cut_i]
o1, h1, l1, c1 = [D1[x].to_numpy() for x in ["open", "high", "low", "close"]]
tr = np.maximum(h1-l1, np.maximum(abs(h1-np.roll(c1, 1)), abs(l1-np.roll(c1, 1)))); tr[0] = h1[0]-l1[0]
atr1 = pd.Series(tr).ewm(alpha=1/14, adjust=False).mean().to_numpy()
m15_ts = M15.index.values; h15, l15 = M15["high"].to_numpy(), M15["low"].to_numpy()
d1_ts = D1.index.values

def mstats(dates, rets):
    s = pd.Series(rets, index=pd.DatetimeIndex(dates))
    eq = (1+s).cumprod()
    me = eq.resample("ME").last().dropna()
    mr = me.pct_change().dropna(); mr = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mr])*100
    dd = ((eq/eq.cummax())-1).min()*100
    shp = mr.mean()/mr.std()*np.sqrt(12) if mr.std() > 0 else 0
    return dict(avg=mr.mean(), med=mr.median(), pos=(mr > 0).mean()*100, dd=dd,
                worst=mr.min(), sh=shp, mr=mr)

def seg(dates, rets, which):
    m = np.array([(pd.Timestamp(d) >= cut_ts) for d in dates])
    keep = m if which == "OOS" else ~m
    return [d for d, k in zip(dates, keep) if k], [r for r, k in zip(rets, keep) if k]

# ---------- A) TSMOM ----------
def tsmom(N):
    dates, rets = [], []; pos = 0
    for t in range(N, n1-1):
        sig = 1 if c1[t] > c1[t-N] else -1
        r = pos * (c1[t+1]/c1[t] - 1)              # позиція, встановлена ВЧОРА, їде сьогодні->завтра? ні:
        # позиція визначена на close t, їде через день t+1 (open->close ~ close_t..close_t+1)
        cost = 2*COST_SIDE if sig != pos else 0.0
        r = sig * (c1[t+1]/c1[t] - 1) - cost
        pos = sig
        dates.append(D1.index[t+1]); rets.append(r)
    return dates, rets

# ---------- B) VolBreakout дня (15m-істина всередині дня) ----------
def volbreak(k):
    dates, rets = [], []
    for t in range(15, n1-1):
        a = atr1[t-1]
        if not np.isfinite(a) or a <= 0: continue
        up, dn = o1[t] + k*a, o1[t] - k*a
        b0 = np.searchsorted(m15_ts, d1_ts[t], "left")
        b1 = np.searchsorted(m15_ts, d1_ts[t+1] if t+1 < n1 else m15_ts[-1], "left")
        pos = 0; entry = stop = 0.0; ret = None
        for b in range(b0, min(b1, len(m15_ts))):
            if pos == 0:
                if h15[b] >= up: pos, entry, stop = 1, up*(1+COST_SIDE), o1[t]
                elif l15[b] <= dn: pos, entry, stop = -1, dn*(1-COST_SIDE), o1[t]
                if pos and ((l15[b] <= stop) if pos > 0 else (h15[b] >= stop)):   # тригер і стоп в 1 барі -> песимізм
                    ret = pos*(stop/entry - 1) - COST_SIDE; break
            else:
                if (l15[b] <= stop) if pos > 0 else (h15[b] >= stop):
                    ret = pos*(stop/entry - 1) - COST_SIDE; break
        if pos and ret is None: ret = pos*(c1[t]/entry - 1) - COST_SIDE          # вихід на close дня
        if pos: dates.append(D1.index[t]); rets.append(ret)
    return dates, rets

# ---------- C) Donchian ----------
def donchian(ne, nx):
    dates, rets = [], []; pos = 0
    hh = pd.Series(h1).rolling(ne).max().shift(1).to_numpy()
    ll = pd.Series(l1).rolling(ne).min().shift(1).to_numpy()
    xh = pd.Series(h1).rolling(nx).max().shift(1).to_numpy()
    xl = pd.Series(l1).rolling(nx).min().shift(1).to_numpy()
    for t in range(ne+1, n1-1):
        new = pos
        if pos <= 0 and c1[t] > hh[t]: new = 1
        elif pos >= 0 and c1[t] < ll[t]: new = -1
        elif pos > 0 and c1[t] < xl[t]: new = 0
        elif pos < 0 and c1[t] > xh[t]: new = 0
        sides = abs(new - pos)                      # 0/1/2 сторони
        r = new * (c1[t+1]/c1[t] - 1) - sides*COST_SIDE
        pos = new
        dates.append(D1.index[t+1]); rets.append(r)
    return dates, rets

def show(name, dates, rets, pick_note=""):
    for which in ["IS", "OOS"]:
        d, r = seg(dates, rets, which)
        if not d: continue
        x = mstats(d, r)
        print(f"{name:26s} {which:4s} | сер {x['avg']:+6.2f}% мед {x['med']:+6.2f}% +міс {x['pos']:3.0f}% "
              f"DD {x['dd']:5.0f}% найг {x['worst']:+6.1f}% Шарп {x['sh']:+4.1f} {pick_note}")
    print()
    return mstats(*seg(dates, rets, "IS"))["sh"]

print(f"BTC 1D, {D1.index[0].date()}..{D1.index[-1].date()}, IS/OOS зріз {pd.Timestamp(cut_ts).date()}, "
      f"витрати {COST_SIDE*100:.2f}%/сторону\n")
print("D) Buy&Hold (бенчмарк):")
show("  BnH", list(D1.index[1:]), list(c1[1:]/c1[:-1]-1))

print("A) TSMOM (вибір N на IS):")
best = (-9, None)
for N in [10, 20, 30, 60, 90]:
    sh = show(f"  TSMOM N={N}", *tsmom(N))
    if sh > best[0]: best = (sh, N)
print(f"  -> обрано на IS: N={best[1]}\n")

print("B) VolBreakout дня (вибір k на IS):")
bestb = (-9, None)
for k in [0.5, 0.8, 1.2]:
    sh = show(f"  VB k={k}", *volbreak(k))
    if sh > bestb[0]: bestb = (sh, k)
print(f"  -> обрано на IS: k={bestb[1]}\n")

print("C) Donchian (вибір на IS):")
bestc = (-9, None)
for ne, nx in [(55, 20), (20, 10)]:
    sh = show(f"  Donch {ne}/{nx}", *donchian(ne, nx))
    if sh > bestc[0]: bestc = (sh, (ne, nx))
print(f"  -> обрано на IS: {bestc[1]}\n")

# по роках OOS для IS-переможців
print("ПО РОКАХ (OOS) для IS-переможців:")
for name, (dates, rets) in [("TSMOM", tsmom(best[1])), ("VolBreak", volbreak(bestb[1])),
                            ("Donchian", donchian(*bestc[1])), ("BnH", (list(D1.index[1:]), list(c1[1:]/c1[:-1]-1)))]:
    d, r = seg(dates, rets, "OOS")
    s = pd.Series(r, index=pd.DatetimeIndex(d))
    out = []
    for yr, g in s.groupby(s.index.year):
        out.append(f"{yr}:{(1+g).prod()-1:+.0%}")
    print(f"  {name:9s} " + "  ".join(out))
