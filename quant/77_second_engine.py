"""ДРУГИЙ ДВИЖОК (інша сім'я, диверсифікація до тренд-континуації):
  1) RSI2-MR: відкат-викуп у тренді (c>EMA200 і RSI(2)<10 -> лонг; дзеркально шорт)
  2) FADE: невдалий пробій Кельтнера (закриття за межею -> наступне назад усередину -> фейд)
Обидва: вхід МАРКЕТОМ на open наступного бара (без ambiguity філа), стоп ATR, RR2.
Вердикт: приймаємо ЛИШЕ якщо OOS-плюс і в м'якій, і в ЖОРСТКІЙ (тейк з наступного бара)
конвенції — після уроку 74/75 про внутрішньобарний оптимізм."""
import importlib.util, builtins, numpy as np, pandas as pd
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c72", "quant/72_avoid_losers.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print = _p
BASE, naive, adxv = m.BASE, m.naive, m.adxv
FEE, ES, SS = m.FEE, m.ES, m.SS
import engine as E

def rsi2_setups(d):
    c = d["close"]; o = d["open"].to_numpy()
    r2 = E.rsi(c, 2).to_numpy(); em = E.ema(c, 200).to_numpy()
    atr = E.atr(d, 14).to_numpy(); cc = c.to_numpy(); n = len(cc); S = []
    for i in range(210, n-1):
        if not np.isfinite(atr[i]) or not np.isfinite(r2[i]): continue
        if cc[i] > em[i] and r2[i] < 10: S.append((i+1, 1, o[i+1], 2.0*atr[i]))
        if cc[i] < em[i] and r2[i] > 90: S.append((i+1, -1, o[i+1], 2.0*atr[i]))
    return S

def fade_setups(d):
    cl = d["close"]; o, h, l, c = [d[x].to_numpy() for x in ["open", "high", "low", "close"]]
    mid = E.ema(cl, 20); band = 2*E.atr(d, 10)
    up = (mid + band).to_numpy(); lo_ = (mid - band).to_numpy()
    atr = E.atr(d, 14).to_numpy(); n = len(c); S = []
    for i in range(210, n-1):
        if not np.isfinite(atr[i]): continue
        if c[i-1] > up[i-1] and c[i] < up[i]:                   # пробій угору провалився -> шорт
            ext = max(h[i-1], h[i]); en = o[i+1]
            S.append((i+1, -1, en, max(ext - en, 0.5*atr[i])))
        if c[i-1] < lo_[i-1] and c[i] > lo_[i]:                 # пробій униз провалився -> лонг
            ext = min(l[i-1], l[i]); en = o[i+1]
            S.append((i+1, 1, en, max(en - ext, 0.5*atr[i])))
    return S

def run(setup_fn, strict):
    rows = []
    for coin, d in BASE.items():
        h, l, c = [d[x].to_numpy() for x in ["high", "low", "close"]]; n = len(c)
        cut = naive(d.index[int(len(d)*0.6)])
        S = sorted(setup_fn(d), key=lambda x: x[0]); ou = -1
        for eb, si, raw, D in S:
            if eb <= ou or D <= 0: continue
            stop = raw - si*D; tgt = raw + si*2.0*D; j = eb; ex = None
            while j < n:
                hs = (l[j] <= stop) if si > 0 else (h[j] >= stop)
                ht = ((j > eb) if strict else True) and ((h[j] >= tgt) if si > 0 else (l[j] <= tgt))
                if hs: ex = ("stop", stop, j); break
                if ht: ex = ("tgt", tgt, j); break
                j += 1
            if ex is None: ex = ("eod", c[-1], n-1)
            en = raw*(1 + si*ES); exf = ex[1]*(1 - si*SS) if ex[0] == "stop" else ex[1]
            R = si*(exf-en)/D - 2*FEE*(en/D)
            rows.append(("OOS" if naive(d.index[eb]) >= cut else "IS", R)); ou = ex[2]
    T = pd.DataFrame(rows, columns=["seg", "R"])
    out = {}
    for seg in ["IS", "OOS"]:
        s = T[T.seg == seg]["R"]
        out[seg] = (len(s), s.mean(), (s > 0).mean()*100)
    return out

print("КАНДИДАТИ НА ДРУГИЙ ДВИЖОК (4 монети 4h, реалістичні витрати, RR2)\n")
print(f"{'движок':10s} {'конвенція':9s} | {'n IS':>5} {'exp IS':>7} {'WR':>4} | {'n OOS':>5} {'exp OOS':>8} {'WR':>4}")
print("-"*72)
for name, fn in [("RSI2-MR", rsi2_setups), ("FADE-KC", fade_setups)]:
    for conv, strict in [("м'яка", False), ("жорстка", True)]:
        r = run(fn, strict)
        print(f"{name:10s} {conv:9s} | {r['IS'][0]:5d} {r['IS'][1]:+7.3f} {r['IS'][2]:3.0f}% | "
              f"{r['OOS'][0]:5d} {r['OOS'][1]:+8.3f} {r['OOS'][2]:3.0f}%")
    print()
print("Критерій прийняття: OOS-плюс в ОБОХ конвенціях (інакше едж живе у внутрішньобарному оптимізмі).")
