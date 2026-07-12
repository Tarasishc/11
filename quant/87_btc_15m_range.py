"""MEAN-REVERSION на БОКОВИКУ, BTC 15m, локально. RR 1:2 та 1:3.
Гіпотеза: у діапазоні (ADX низький) ціна вертається від країв до середини.
Кандидати входу (усі гейтяться регім-фільтром «не тренд»):
  BB   — закриття за смугою Боллінджера(20,2) -> фейд
  RSI2 — RSI(2) екстремум (<5 / >95) -> фейд
  DON  — дотик локального Donchian(20) краю -> фейд
Стоп = 1×ATR14 за входом; ціль = RR×стоп. Вхід на open наступного бару.
Внутрішньобар: песимістично (стоп першим). Реальні витрати. IS/OOS 60/40.
ДИСЦИПЛІНА: приймаємо ЛИШЕ якщо OOS exp>0 після витрат. Дані локальні (без мережі)."""
import numpy as np, pandas as pd
import lib_data as L

FEE, ES, SS = 0.0005, 0.0002, 0.0005          # тейкер/сторону, слип входу, слип стопа (15m BTC ліквідний)
ADX_MAX = 20                                   # «боковик» = ADX < 20 (дзеркало нашого тренд-фільтра)

d = L.load_btc_15m()
o, h, l, c = [d[x].to_numpy(dtype=float) for x in ["open", "high", "low", "close"]]
n = len(c); idx = pd.DatetimeIndex(d.index)
ts = idx.tz_localize(None) if idx.tz is not None else idx

def ema(x, p): return pd.Series(x).ewm(span=p, adjust=False).mean().to_numpy()
def rma(x, p): return pd.Series(x).ewm(alpha=1/p, adjust=False).mean().to_numpy()
pc = np.concatenate([[c[0]], c[:-1]])
tr = np.maximum(h-l, np.maximum(np.abs(h-pc), np.abs(l-pc)))
atr = rma(tr, 14)
up = np.concatenate([[0], np.diff(h)]); dn = np.concatenate([[0], -np.diff(l)])
pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
pdi = 100*rma(pdm, 14)/atr; mdi = 100*rma(mdm, 14)/atr
adx = rma(100*np.abs(pdi-mdi)/np.where(pdi+mdi == 0, np.nan, pdi+mdi), 14)
ma = pd.Series(c).rolling(20).mean().to_numpy(); sd = pd.Series(c).rolling(20).std().to_numpy()
bb_up, bb_lo = ma+2*sd, ma-2*sd
dd = c - np.concatenate([[c[0]], c[:-1]]); upv = np.clip(dd, 0, None); dnv = np.clip(-dd, 0, None)
rsi2 = 100 - 100/(1 + rma(upv, 2)/np.where(rma(dnv, 2) == 0, np.nan, rma(dnv, 2)))
don_hi = pd.Series(h).rolling(20).max().shift(1).to_numpy(); don_lo = pd.Series(l).rolling(20).min().shift(1).to_numpy()

def signals(kind):
    """-> масив side по барах (0/+1/-1) з регім-фільтром боковика."""
    s = np.zeros(n)
    rng = adx < ADX_MAX
    if kind == "BB":
        s[(c < bb_lo) & rng] = 1; s[(c > bb_up) & rng] = -1
    elif kind == "RSI2":
        s[(rsi2 < 5) & rng] = 1; s[(rsi2 > 95) & rng] = -1
    elif kind == "DON":
        s[(l <= don_lo) & rng] = 1; s[(h >= don_hi) & rng] = -1
    return s

def sim(kind, rr, regime=True):
    side = signals(kind) if regime else signals_noregime(kind)
    rows = []; i = 210
    while i < n-1:
        si = side[i]
        if si == 0 or not np.isfinite(atr[i]) or atr[i] <= 0: i += 1; continue
        eb = i+1; en = o[eb]*(1 + si*ES); D = atr[i]
        stop = en - si*D; tgt = en + si*rr*D; j = eb; ex = None
        while j < n:
            hs = (l[j] <= stop) if si > 0 else (h[j] >= stop)
            ht = (h[j] >= tgt) if si > 0 else (l[j] <= tgt)
            if hs: ex = ("stop", stop, j); break        # песимізм: стоп першим
            if ht: ex = ("tgt", tgt, j); break
            j += 1
        if ex is None: ex = ("eod", c[-1], n-1)
        exf = ex[1]*(1 - si*SS) if ex[0] == "stop" else ex[1]
        R = si*(exf-en)/D - 2*FEE*(en/D)
        rows.append((ts[eb], R)); i = ex[2] + 1
    return pd.DataFrame(rows, columns=["t", "R"])

def signals_noregime(kind):
    s = np.zeros(n)
    if kind == "BB": s[c < bb_lo] = 1; s[c > bb_up] = -1
    elif kind == "RSI2": s[rsi2 < 5] = 1; s[rsi2 > 95] = -1
    elif kind == "DON": s[l <= don_lo] = 1; s[h >= don_hi] = -1
    return s

cut = ts[int(n*0.6)]
def rep(T):
    T = T.dropna()
    iss = T[T.t < cut]["R"]; oos = T[T.t >= cut]["R"]
    def line(x):
        if not len(x): return "  —"
        span = max((x.index[-1]-x.index[0]) if False else 1, 1)
        return f"n={len(x):5d} exp={x.mean():+.3f} WR={(x>0).mean()*100:2.0f}%"
    om = ""
    if len(oos):
        span = max((oos.index.max()-oos.index.min()) if False else 1, 1)
    return iss, oos

print(f"BTC 15m mean-reversion на боковику (ADX<{ADX_MAX}), стоп=1×ATR, вхід next open, песимізм.\n"
      f"Витрати: fee {FEE*100:.2f}%/сторону + слип. IS/OOS зріз {cut.date()}. Приймаємо лише OOS exp>0.\n")
print(f"{'канд.':6s} {'RR':>4} {'рег':4s} | {'IS n':>6} {'IS exp':>7} {'IS WR':>5} | {'OOS n':>6} {'OOS exp':>8} {'OOS WR':>6} | уг/міс")
print("-"*94)
span_days = (ts[-1]-ts[0]).days
for kind in ["BB", "RSI2", "DON"]:
    for rr in [2.0, 3.0]:
        T = sim(kind, rr)
        iss = T[T.t < cut]["R"]; oos = T[T.t >= cut]["R"]
        tpm = len(T)/(span_days/30.44)
        vis = "✓" if len(oos) and oos.mean() > 0 else ""
        print(f"{kind:6s} {rr:4.0f} {'так':4s} | {len(iss):6d} {iss.mean():+7.3f} {(iss>0).mean()*100:4.0f}% | "
              f"{len(oos):6d} {oos.mean():+8.3f} {(oos>0).mean()*100:5.0f}% | {tpm:5.1f} {vis}")
    # контроль: без регім-фільтра (щоб бачити, чи фільтр боковика взагалі допомагає)
    Tn = sim(kind, 2.0, regime=False); on = Tn[Tn.t >= cut]["R"]
    print(f"{kind:6s} {2:4.0f} {'НІ':4s} | {'':6s} {'':7s} {'':5s} | {len(on):6d} {on.mean():+8.3f} {(on>0).mean()*100:5.0f}% | (без фільтра)")
    print()
print("Нагадування: RR≥2 на реверсії — важко (ціль далеко); якщо OOS скрізь ≤0 -> едж не тут.")
