"""ФАНДИНГ-ЕКСТРЕМУМИ (контраріан): чи прогнозує перекіс натовпу форвард-дохідність?
Гіпотеза з літератури: екстремально ВИСОКИЙ фандинг = перевантажені лонги -> корекція
(шорт-сигнал); екстремально НИЗЬКИЙ/від'ємний = перевантажені шорти -> сквіз (лонг).
Метод: денний сумарний фандинг; пороги = перцентилі, пораховані ЛИШЕ на IS (без підглядання);
форвард 1д і 3д; подвійний бар'єр: знак IS=OOS + перекриває витрати 0.15%/круг.
ЗАПУСК НА VPS: venv/bin/python quant/85_funding_test.py  (спершу data/fetch_funding.py)"""
import os
import numpy as np, pandas as pd
import lib_data as L

COST_RT = 0.0015
COINS = [("BTC", "quant/data/btc_funding.csv", "quant/data/btc_15m.csv"),
         ("ETH", "quant/data/eth_funding.csv", "quant/data/eth_4h.csv"),
         ("SOL", "quant/data/sol_funding.csv", "quant/data/sol_4h.csv"),
         ("BNB", "quant/data/bnb_funding.csv", "quant/data/bnb_4h.csv")]

def daily_close(path):
    if "15m" in path:
        import strategies as ST
        return ST.resample(L.load_btc_15m(), "1D")["close"]
    return L.load_any(path)["close"].resample("1D").last().dropna()

print("ФАНДИНГ-КОНТРАРІАН: пороги p10/p90 з IS; форвардні 1д/3д доходності\n")
for coin, fpath, ppath in COINS:
    if not os.path.exists(fpath):
        print(f"{coin}: немає {fpath} — спершу data/fetch_funding.py"); continue
    f = pd.read_csv(fpath)
    f["dt"] = pd.to_datetime(f["ts"], unit="ms", utc=True)
    fd = f.set_index("dt")["rate"].astype(float).resample("1D").sum().dropna()   # сумарний фандинг дня
    c = daily_close(ppath)
    c.index = pd.DatetimeIndex(c.index).tz_localize(None) if c.index.tz is None else pd.DatetimeIndex(c.index)
    fd.index = fd.index.tz_localize(None) if fd.index.tz is not None else fd.index
    ci = c.copy(); ci.index = pd.DatetimeIndex(ci.index).tz_localize(None) if getattr(ci.index, 'tz', None) is not None else ci.index
    idx = fd.index.intersection(ci.index)
    fd = fd[idx]; px = ci[idx]
    r1 = px.pct_change().shift(-1)[idx]                     # завтрашній день
    r3 = px.pct_change(3).shift(-3)[idx]                    # наступні 3 дні
    cut = idx[int(len(idx)*0.6)]
    is_m = idx < cut
    p10, p90 = fd[is_m].quantile(0.10), fd[is_m].quantile(0.90)   # пороги ЛИШЕ з IS
    print(f"{coin}: днів {len(idx)} | IS-пороги фандингу: p10={p10*100:+.3f}%/д p90={p90*100:+.3f}%/д")
    for lbl, mask, sgn in [("фандинг>p90 -> ШОРТ", fd > p90, -1), ("фандинг<p10 -> ЛОНГ", fd < p10, +1)]:
        row = f"   {lbl:22s}"
        oks = []
        for hor, rr, days in [("1д", r1, 1), ("3д", r3, 3)]:
            i_ = (sgn*rr)[mask & is_m].mean()*100
            o_ = (sgn*rr)[mask & ~is_m].mean()*100
            ni = int((mask & is_m).sum()); no = int((mask & ~is_m).sum())
            ok = ni > 30 and no > 30 and np.sign(i_) == np.sign(o_) and \
                 min(abs(i_), abs(o_)) > COST_RT*100 and i_ > 0
            oks.append(ok)
            row += f" | {hor}: IS {i_:+.2f}% (n={ni}) OOS {o_:+.2f}% (n={no}) {'✓' if ok else '—'}"
        print(row)
    print()
print("✓ = пройшло подвійний бар'єр (знак IS=OOS, >витрат, вибірка достатня).")
