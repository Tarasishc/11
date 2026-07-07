"""ЧИ Є ЕДЖ у фандинг-диференціалі OKX vs Binance (delta-neutral)?
Вимір ПЕРЕД будь-якою побудовою бота. Тягне історію funding з обох бірж,
вирівнює по 8-годинних вікнах, рахує диференціал і чесно віднімає комісії.
Стратегія-кандидат: шорт там, де фандинг вищий + лонг там, де нижчий; тримаємо,
поки |diff| > поріг; при конвергенції/фліпі — вихід (4 тейкер-філи на круг).

ДИСЦИПЛІНА: поріг входу обираємо на IS, вердикт — OOS. Приймаємо лише якщо
net edge (після комісій) додатний і на IS, і на OOS.
ЗАПУСК НА VPS (потрібен доступ до OKX+Binance): venv/bin/python quant/86_funding_arb.py
"""
import numpy as np, pandas as pd
try:
    import ccxt
except Exception:
    ccxt = None

FEE_TAKER = 0.0005          # ~0.05% тейкер/філ (2 біржі); 4 філи на повний цикл
SYMS = {"BTC": ("BTC/USDT", "BTC/USDT:USDT"),
        "ETH": ("ETH/USDT", "ETH/USDT:USDT"),
        "SOL": ("SOL/USDT", "SOL/USDT:USDT")}
SINCE = "2023-01-01T00:00:00Z"

def fetch_funding(ex, symbol):
    since = ex.parse8601(SINCE); rows = []
    while True:
        try:
            b = ex.fetch_funding_rate_history(symbol, since=since, limit=1000)
        except Exception as e:
            print("  ", ex.id, symbol, "err:", e); break
        if not b: break
        rows += [(x["timestamp"], float(x["fundingRate"])) for x in b]
        last = b[-1]["timestamp"]
        if last == since or len(b) < 50: break
        since = last + 1
    s = pd.Series({t: r for t, r in rows})
    s.index = pd.to_datetime(s.index, unit="ms")
    # округлення до 8-год вікна для вирівнювання між біржами
    return s.groupby(s.index.floor("8h")).last().sort_index()

def analyze(coin, bn, ok):
    idx = bn.index.intersection(ok.index)
    if len(idx) < 100:
        print(f"{coin}: замало спільних вікон ({len(idx)})"); return
    d = (bn[idx] - ok[idx])                        # диференціал за вікно (частка нотіоналу/ногу)
    cut = idx[int(len(idx)*0.6)]
    print(f"\n{coin}: спільних 8h-вікон {len(idx)} | {idx[0].date()}..{idx[-1].date()}")
    print(f"  |diff| сер {d.abs().mean()*100:.4f}% | медіана {d.abs().median()*100:.4f}% | "
          f"95-й перц {d.abs().quantile(.95)*100:.4f}% (за 8 год)")
    # проста стратегія: тримати нейтраль поки |diff|>=thr; збираємо diff щовікна; 4 філи/цикл
    def net(seg, thr):
        held = 0; cyc = 0; coll = 0.0
        for v in seg:
            if held == 0 and abs(v) >= thr: held = np.sign(v); cyc += 1  # відкрились
            if held != 0: coll += held * v                                # збираємо diff
            if held != 0 and abs(v) < thr*0.3: held = 0                   # конвергенція -> вихід
        gross = coll; fees = cyc * 4 * FEE_TAKER                          # 4 тейкер-філи на цикл
        return gross - fees, cyc
    print(f"  {'поріг(8h)':>10} | {'IS net/рік':>11} {'циклів':>6} | {'OOS net/рік':>12} {'циклів':>6}")
    for thr in [0.0003, 0.0005, 0.001]:
        out = []
        for seg, lbl in [(d[idx < cut], "IS"), (d[idx >= cut], "OOS")]:
            n, cyc = net(seg.values, thr)
            yrs = max((seg.index[-1]-seg.index[0]).days/365, 0.1)
            out.append((n/yrs*100, cyc))              # net у % на РІК на задіяний нотіонал/ногу
        vis = "✓" if out[0][0] > 0 and out[1][0] > 0 else ""
        print(f"  {thr*100:9.3f}% | {out[0][0]:+10.1f}% {out[0][1]:6d} | {out[1][0]:+11.1f}% {out[1][1]:6d} {vis}")

if __name__ == "__main__":
    if ccxt is None: raise SystemExit("немає ccxt")
    bnc = ccxt.binance({"options": {"defaultType": "future"}, "enableRateLimit": True})
    okx = ccxt.okx({"enableRateLimit": True})
    print("Фандинг-диференціал OKX vs Binance, net після комісій (4×%.3f%% на цикл)\n"
          "Приймаємо лише якщо OOS net/рік > 0. Пам'ятай: тут НЕ враховано legging-ризик,\n"
          "маржу на 2 біржах і те, що при фліпі фандингу платиш на обох ногах." % (FEE_TAKER*100,))
    for coin, (bsym, osym) in SYMS.items():
        try:
            bn = fetch_funding(bnc, bsym); ok = fetch_funding(okx, osym)
            analyze(coin, bn, ok)
        except Exception as e:
            print(f"{coin}: помилка {e}")
    print("\nЯкщо OOS скрізь ~0/мінус -> едж з'їдений, бота НЕ будуємо (як carry у 2025).")
