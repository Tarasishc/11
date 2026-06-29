"""Чи виживає стратегія на ДЕННОМУ ТФ (передумова для тесту на акціях)?
Ті самі механічні правила, але 1D. Чесно IS/OOS, крипта."""
import importlib.util, builtins, numpy as np, pandas as pd
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c60", "quant/60_stop_width.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print = _p
import lib_data as L, strategies as ST
taken, ENG = m.taken, m.ENG

D1 = {"BTC": ST.resample(L.load_btc_15m(), "1d"),
      "ETH": ST.resample(L.load_any("quant/data/eth_4h.csv"), "1d"),
      "SOL": ST.resample(L.load_any("quant/data/sol_4h.csv"), "1d"),
      "BNB": ST.resample(L.load_any("quant/data/bnb_4h.csv"), "1d")}
CUT = pd.Timestamp("2022-12-10")

print("Стратегія на ДЕННОМУ ТФ (1D), ті самі правила, IS/OOS:\n")
print(f"{'монета':6s} | {'n':>4} {'IS exp':>7} {'OOS exp':>8} {'OOS WR':>7}")
print("-"*42)
allis, alloos = [], []
for coin, d in D1.items():
    rows = []
    for ts, si, raw, D, extype, exlvl in taken(d, ENG[coin], 2.0, 0.5):
        en = raw; ex = exlvl
        r = si*(ex-en)/D - 2*0.0005*(en/D)
        rows.append((ts, r))
    T = pd.DataFrame(rows, columns=["t", "r"])
    iss = T[T["t"] < CUT]["r"].values; oos = T[T["t"] >= CUT]["r"].values
    allis += list(iss); alloos += list(oos)
    print(f"{coin:6s} | {len(T):4d} {iss.mean() if len(iss) else 0:+7.3f} {oos.mean() if len(oos) else 0:+8.3f} {(oos>0).mean()*100 if len(oos) else 0:6.0f}%")
ai, ao = np.array(allis), np.array(alloos)
print("-"*42)
print(f"{'РАЗОМ':6s} | {len(ai)+len(ao):4d} {ai.mean():+7.3f} {ao.mean():+8.3f} {(ao>0).mean()*100:6.0f}%")
print(f"\nДля порівняння на 4h було ~+0.17R OOS. Якщо тут теж плюс -> стратегія")
print("не лише 4h-специфічна, і тест на акціях (1D) виправданий.")
