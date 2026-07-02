"""ПОШУК РОБОЧОГО НА BTC під 15m-істиною. Результат: НЕ ЗНАЙДЕНО (чесно).
  1) KC-only 4h:  IS +0.117 -> OOS -0.012 (нуль; по роках знак стрибає)
  2) 1D база:     IS +0.268 -> OOS +0.041 (1.8 уг/міс -> ~+0.07%/міс — економічно нічого)
  3) 1D пакет:    IS +0.206 -> OOS -0.016 (4h-тюнінг не переноситься на 1D)
Висновок: BTC — найефективніший ринок крипти, наш едж там не живе.
Конфіг ETH+SOL лишається. Той 'BTC пакет OOS +0.117' з 78 — підмножина
223 угод у міксі (без причинного механізму) = тонкий лід, не підстава повертати BTC."""
import importlib.util, builtins, numpy as np, pandas as pd
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c78", "quant/78_truth_all_coins.py")
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c); builtins.print = _p
import lib_data as L, strategies as ST

m15 = L.load_btc_15m()
for tf, d in [("4h", ST.resample(m15, "4h")), ("1D", ST.resample(m15, "1D"))]:
    for lbl, eng, pkg in [("KC+FVG база", "KF", False), ("KC+FVG пакет", "KF", True), ("KC-only", "K", False)]:
        T = c.coin_truth(d, m15, eng, pkg)
        row = f"BTC {tf} {lbl:13s}"
        for seg in ["IS", "OOS"]:
            s = T[T.seg == seg]
            row += f" | {seg} n={len(s):4d} exp={s['R'].mean() if len(s) else float('nan'):+.3f}"
        print(row)
    print()
print("Вердикт: на BTC стабільного еджу НЕМА (усі OOS ~0). Лишаємось на ETH+SOL.")
