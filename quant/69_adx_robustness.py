"""Наскільки НАДІЙНИЙ фільтр ADX≥20 на FVG: розбивка по монетах і по роках.
Питання: це широкий ефект чи його тягне одна монета/один рік? Чесна перевірка
перед тим, як казати 'точно краще'. Дельта = exp(ADX≥20) - exp(ADX<20); >0 = фільтр корисний."""
import sys; sys.path.insert(0, "quant")
import importlib.util, builtins, numpy as np, pandas as pd
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c67", "quant/67_stopout_patterns.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print = _p
DF = m.DF

print("FVG-угоди: ADX<20 vs ADX≥20 — ПО МОНЕТАХ (exp R). Дельта>0 = фільтр корисний.\n")
print(f"{'мон':4s} {'сег':4s} | {'<20 n':>6} {'exp':>7} | {'≥20 n':>6} {'exp':>7} | {'дельта':>7}")
print("-"*56)
for coin in ["BTC", "ETH", "SOL", "BNB"]:
    for seg in ["IS", "OOS"]:
        s = DF[(DF.eng == "F") & (DF.coin == coin) & (DF.seg == seg)]
        lo, hi = s[s.adx < 20], s[s.adx >= 20]
        le = lo["R"].mean() if len(lo) else float("nan"); he = hi["R"].mean() if len(hi) else float("nan")
        print(f"{coin:4s} {seg:4s} | {len(lo):6d} {le:+7.3f} | {len(hi):6d} {he:+7.3f} | {he-le:+7.3f}")

print("\nFVG ADX<20 vs ≥20 — ПО РОКАХ (OOS). Чи стабільно з року в рік?\n")
o = DF[(DF.eng == "F") & (DF.seg == "OOS")].copy(); o["yr"] = pd.DatetimeIndex(o["ts"]).year
print(f"{'рік':5s} | {'<20 n':>6} {'exp':>7} | {'≥20 n':>6} {'exp':>7} | {'фільтр':>8}")
print("-"*50)
for yr, g in o.groupby("yr"):
    lo, hi = g[g.adx < 20], g[g.adx >= 20]
    lm = lo["R"].mean() if len(lo) else float("nan"); hm = hi["R"].mean() if len(hi) else float("nan")
    verdict = "корисний" if hm > lm else "ШКІДЛИВИЙ"
    if len(lo) < 5: verdict = "(мало n)"
    print(f"{yr:5d} | {len(lo):6d} {lm:+7.3f} | {len(hi):6d} {hm:+7.3f} | {verdict:>8}")

print("""
ЧЕСНИЙ ВИСНОВОК:
  + По МОНЕТАХ: усі 4 (BTC/ETH/SOL/BNB) на боці ADX≥20, і на IS, і на OOS -> ефект широкий.
  + ADX<20 на OOS збитковий на BTC/ETH/SOL; на BNB ~нуль (не збиток, просто гірше).
  − По РОКАХ: 3 з 4 років фільтр корисний, але у 2024 БУВ БИ ШКІДЛИВИЙ
    (низький-ADX FVG дав більше за високий). Тобто це нахил У СЕРЕДНЬОМУ, не щорічна гарантія.
  => Найнадійніша зміна з усіх, що пробували, і принципова (той самий ADX≥20, що вже в KC),
     але 'точно краще щороку' — НЕ можна стверджувати. Правду дасть лише форвард (демо).""")
