"""ДВІ ІДЕЇ З ЛІТЕРАТУРИ (перевірка на наших даних, подвійний бар'єр IS/OOS + витрати):
  A) ВІКЕНД-МОМЕНТУМ (paper 2025: 7д моментум на вихідних сильніший, особливо альти):
     напрям = знак ret за 7 днів; тримаємо у цей бік Сб+Нд; порівнюємо з буднями.
  B) «ЛІКВІДАЦІЙНИЙ» БАР (проксі каскаду): 4h бар з довгим гнотом проти руху
     (гніт > 1.5×тіла і > 1×ATR) + об'єм > 3×СМА20(об'єму) -> реверсія N барів.
Витрати 0.15%/круг. Монети: BTC,ETH,SOL,BNB (+MNT де є)."""
import numpy as np, pandas as pd
import lib_data as L, strategies as ST, engine as E

COST_RT = 0.0015
def dly(d): return d["close"].resample("1D").last().dropna()
BASE = {"BTC": ST.resample(L.load_btc_15m(), "4h"), "ETH": L.load_any("quant/data/eth_4h.csv"),
        "SOL": L.load_any("quant/data/sol_4h.csv"), "BNB": L.load_any("quant/data/bnb_4h.csv"),
        "MNT": L.load_any("quant/data/mnt_4h.csv")}

print("A) ВІКЕНД-МОМЕНТУМ (7д): сер. %/день у напрямку моментуму\n")
print(f"{'мон':4s} | {'IS вікенд':>9} {'IS будні':>9} | {'OOS вікенд':>10} {'OOS будні':>9} | вердикт")
print("-"*72)
for coin, d4 in BASE.items():
    c = dly(d4); r = c.pct_change().dropna()
    mom = np.sign(c.pct_change(7)).shift(1).reindex(r.index)      # напрям на вчора
    strat = (mom*r).dropna()
    cut = strat.index[int(len(strat)*0.6)]
    vals = {}
    for which in ["IS", "OOS"]:
        s = strat[strat.index < cut] if which == "IS" else strat[strat.index >= cut]
        we = s[s.index.weekday >= 5].mean()*100; wd = s[s.index.weekday < 5].mean()*100
        vals[which] = (we, wd)
    ok = np.sign(vals["IS"][0]) == np.sign(vals["OOS"][0]) and \
         min(abs(vals["IS"][0]), abs(vals["OOS"][0])) > COST_RT/2*100    # 1 круг на 2 дні вікенду
    print(f"{coin:4s} | {vals['IS'][0]:+8.3f}% {vals['IS'][1]:+8.3f}% | {vals['OOS'][0]:+9.3f}% "
          f"{vals['OOS'][1]:+8.3f}% | {'ПРОЙШОВ' if ok else '—'}")
print("\n(тредабельний варіант: вхід Сб 00:00 у бік 7д-моментуму, вихід Пн 00:00 = 1 круг/тиждень)\n")

print("B) «ЛІКВІДАЦІЙНИЙ» БАР 4h (гніт+об'єм) -> реверсія:\n")
print(f"{'мон':4s} {'бік':5s} | {'IS n':>5} {'IS %':>7} | {'OOS n':>5} {'OOS %':>7} | вердикт (вихід через 2 бари)")
print("-"*78)
for coin, d in BASE.items():
    o, h, l, c, v = [d[x].to_numpy() for x in ["open", "high", "low", "close", "vol"]] if "vol" in d else (None,)*5
    if o is None: print(f"{coin:4s} — нема об'єму, пропуск"); continue
    atr = E.atr(d, 14).to_numpy()
    vma = pd.Series(v).rolling(20).mean().to_numpy()
    n = len(c); cut_i = int(n*0.6)
    for side, lbl in [(1, "long"), (-1, "short")]:
        rets = {"IS": [], "OOS": []}
        for i in range(20, n-3):
            if not np.isfinite(atr[i]) or not np.isfinite(vma[i]) or vma[i] <= 0: continue
            body = abs(c[i]-o[i])
            wick = (min(o[i], c[i]) - l[i]) if side > 0 else (h[i] - max(o[i], c[i]))
            if wick > 1.5*body and wick > 1.0*atr[i] and v[i] > 3*vma[i]:
                r = side*(c[i+2]/c[i] - 1) - COST_RT          # вхід close i, вихід close i+2
                rets["OOS" if i >= cut_i else "IS"].append(r)
        i_ = np.mean(rets["IS"])*100 if rets["IS"] else float("nan")
        o_ = np.mean(rets["OOS"])*100 if rets["OOS"] else float("nan")
        ok = len(rets["IS"]) > 30 and len(rets["OOS"]) > 30 and np.sign(i_) == np.sign(o_) \
             and min(abs(i_), abs(o_)) > COST_RT*100 and i_ > 0
        print(f"{coin:4s} {lbl:5s} | {len(rets['IS']):5d} {i_:+7.3f} | {len(rets['OOS']):5d} {o_:+7.3f} | "
              f"{'ПРОЙШОВ' if ok else '—'}")
print("\nВердикт за фактами вище.")
