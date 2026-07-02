"""ІСТИНА ВСЕРЕДИНІ БАРА (BTC, 15m за всю історію).
Питання: скільки прибутку FVG живе у «філ і тейк в одному 4h-барі», і яка
4h-конвенція чесніша: м'яка (тейк того ж бара можна) чи жорстка (лише з наступного)?
Метод: той самий список угод (fill-бар, entry/stop/target) -> прохід 15m-барами:
  1) чекаємо філа (15m low <= entry), 2) далі стоп/тейк у РЕАЛЬНІЙ послідовності
  (в межах 15m-бара песимістично: стоп першим). Порівнюємо exp: soft vs strict vs TRUTH.
Розв'язка застосовується і до бази (край) і до кандидата mid50+wait+ADX."""
import importlib.util, builtins, numpy as np, pandas as pd
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c72", "quant/72_avoid_losers.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print = _p
import lib_data as L, strategies as ST, engine as E
naive, adxv = m.naive, m.adxv
FEE, ES, SS = m.FEE, m.ES, m.SS

M15 = L.load_btc_15m()
D4 = ST.resample(M15, "4h")
m15_ts = np.array([naive(t).value for t in M15.index])
h15, l15 = M15["high"].to_numpy(), M15["low"].to_numpy()
d4_ts = np.array([naive(t).value for t in D4.index])
BAR4 = 4*3600*10**9

def fvg_trades(d, fvg_mid, min_wait, fvg_adx):
    """список FVG-угод: (fill4h_idx, si, entry, stop, target, D)."""
    o, h, l, c = [d[x].to_numpy() for x in ["open", "high", "low", "close"]]
    atr = E.atr(d, 14).to_numpy(); em = E.ema(d["close"], 200).to_numpy(); ax = adxv(d)
    n = len(c); S = []
    for k in range(2, n-1):
        for si in (1, -1):
            if si > 0 and not (h[k-2] < l[k] and c[k] > em[k]): continue
            if si < 0 and not (l[k-2] > h[k] and c[k] < em[k]): continue
            zt = l[k] if si > 0 else h[k]; zb = h[k-2] if si > 0 else l[k-2]
            entry = (zt + zb)/2 if fvg_mid else zt
            for j in range(k+1, min(k+21, n)):
                hit = l[j] <= entry if si > 0 else h[j] >= entry
                if not hit: continue
                if j - k <= min_wait: break
                trok = c[j] > em[j] if si > 0 else c[j] < em[j]
                if not trok: break
                if fvg_adx > 0 and not (np.isfinite(ax[j]) and ax[j] >= fvg_adx): break
                D = max(abs(entry - zb), 0.5*atr[j])
                S.append((j, si, entry, entry - si*D, entry + si*2*D, D)); break
    S.sort(key=lambda x: x[0])
    # одна-за-раз послідовність за м'якою конвенцією (для ідентичного списку угод)
    out = []; ou = -1
    hh, ll, cc = D4["high"].to_numpy(), D4["low"].to_numpy(), D4["close"].to_numpy()
    for j, si, en, sp, tg, D in S:
        if j <= ou: continue
        q = j; ex = None
        while q < n:
            if (ll[q] <= sp) if si > 0 else (hh[q] >= sp): ex = ("stop", q); break
            if (hh[q] >= tg) if si > 0 else (ll[q] <= tg): ex = ("tgt", q); break
            q += 1
        if ex is None: ex = ("eod", n-1)
        out.append((j, si, en, sp, tg, D, ex[0], ex[1])); ou = ex[1]
    return out

def R_of(si, en, exlvl, D, extype):
    enf = en*(1 + si*ES); exf = exlvl*(1 - si*SS) if extype == "stop" else exlvl
    return si*(exf - enf)/D - 2*FEE*(enf/D)

def truth_resolve(j4, si, en, sp, tg, D):
    """прохід 15m з початку 4h-бара j4: філ -> стоп/тейк у реальному порядку."""
    t0 = d4_ts[j4]
    b = np.searchsorted(m15_ts, t0, "left")
    filled = False
    while b < len(m15_ts):
        lo, hi = l15[b], h15[b]
        if not filled:
            if (lo <= en) if si > 0 else (hi >= en):
                filled = True
                # у 15m-барі філа: песимістично стоп -> тейк
                if (lo <= sp) if si > 0 else (hi >= sp): return "stop", sp
                if (hi >= tg) if si > 0 else (lo <= tg): return "tgt", tg
        else:
            if (lo <= sp) if si > 0 else (hi >= sp): return "stop", sp
            if (hi >= tg) if si > 0 else (lo <= tg): return "tgt", tg
        b += 1
    return "eod", float(M15["close"].iloc[-1])

for label, kw in [("БАЗА: край зони", dict(fvg_mid=False, min_wait=0, fvg_adx=0)),
                  ("КАНДИДАТ: mid50+wait>2+ADX20", dict(fvg_mid=True, min_wait=2, fvg_adx=20))]:
    TR = fvg_trades(D4, **kw)
    hh, ll = D4["high"].to_numpy(), D4["low"].to_numpy()
    soft = []; strict = []; truth = []; same_bar_tgt = 0; flips = {"tgt->stop": 0, "tgt->later": 0}
    n4 = len(D4)
    for j, si, en, sp, tg, D, ex_soft, exbar in TR:
        soft.append(R_of(si, en, sp if ex_soft == "stop" else (tg if ex_soft == "tgt" else D4["close"].iloc[-1]), D,
                         ex_soft if ex_soft != "eod" else "tgt"))
        # strict: тейк лише з наступного бара
        q = j; exs = None
        while q < n4:
            hs = (ll[q] <= sp) if si > 0 else (hh[q] >= sp)
            ht = (q > j) and ((hh[q] >= tg) if si > 0 else (ll[q] <= tg))
            if hs: exs = ("stop", sp); break
            if ht: exs = ("tgt", tg); break
            q += 1
        if exs is None: exs = ("eod", float(D4["close"].iloc[-1]))
        strict.append(R_of(si, en, exs[1], D, exs[0] if exs[0] != "eod" else "tgt"))
        # істина по 15m
        et, elvl = truth_resolve(j, si, en, sp, tg, D)
        truth.append(R_of(si, en, elvl, D, et if et != "eod" else "tgt"))
        if ex_soft == "tgt" and exbar == j:
            same_bar_tgt += 1
            if et == "stop": flips["tgt->stop"] += 1
    soft, strict, truth = map(np.array, (soft, strict, truth))
    print(f"\n=== {label} (BTC, n={len(TR)}) ===")
    print(f"  exp: м'яка {soft.mean():+.3f} | жорстка {strict.mean():+.3f} | ІСТИНА(15m) {truth.mean():+.3f}")
    print(f"  тейків у самому барі філа (м'яка): {same_bar_tgt} ({same_bar_tgt/len(TR)*100:.0f}% угод); "
          f"з них насправді СТОП: {flips['tgt->stop']}")
    print(f"  WR: м'яка {(soft>0).mean()*100:.0f}% | жорстка {(strict>0).mean()*100:.0f}% | істина {(truth>0).mean()*100:.0f}%")
print("\nВисновок: яка конвенція ближча до істини — та й судить усі варіанти.")
