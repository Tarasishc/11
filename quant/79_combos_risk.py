"""КОМБІНАЦІЇ МОНЕТ І РИЗИКУ під 15m-істиною (пакет mid50+wait>2+ADX20).
Питання користувача: чи витягнемо 5-10%/міс? Прибрати мінусові монети?
Дати BTC більший ризик?
ДИСЦИПЛІНА: конфіг обираємо за IS-істиною, звітуємо OOS для всіх (з попередженням).
Драбина ризику -> чесна ціна кожного рівня прибутку просадкою.
ЗАПУСК НА VPS: venv/bin/python quant/79_combos_risk.py  (потрібні *_15m.csv)"""
import importlib.util, builtins, os
import numpy as np, pandas as pd
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c78", "quant/78_truth_all_coins.py")
c78 = importlib.util.module_from_spec(spec); spec.loader.exec_module(c78); builtins.print = _p
import lib_data as L, strategies as ST

coin_truth, naive = c78.coin_truth, c78.naive
CFG = [("BTC", "KF", None, "quant/data/btc_15m.csv"),
       ("ETH", "KF", "quant/data/eth_4h.csv", "quant/data/eth_15m.csv"),
       ("SOL", "KF", "quant/data/sol_4h.csv", "quant/data/sol_15m.csv"),
       ("BNB", "F",  "quant/data/bnb_4h.csv", "quant/data/bnb_15m.csv")]

TR = {}                                       # coin -> DataFrame(ts, tag, R, seg) під ПАКЕТОМ
for coin, eng, f4, f15 in CFG:
    if not os.path.exists(f15):
        print(f"{coin}: немає {f15} — пропущено"); continue
    if coin == "BTC":
        m15 = L.load_btc_15m(); d4 = ST.resample(m15, "4h")
    else:
        m15 = L.load_any(f15); d4 = L.load_any(f4)
    TR[coin] = coin_truth(d4, m15, eng, pkg=True)

print("Пер-монетна ІСТИНА (пакет): IS vs OOS exp\n")
print(f"{'мон':4s} | {'IS n':>5} {'IS exp':>7} | {'OOS n':>5} {'OOS exp':>8}")
is_exp = {}
for coin, T in TR.items():
    i_ = T[T.seg == "IS"]["R"]; o_ = T[T.seg == "OOS"]["R"]
    is_exp[coin] = i_.mean() if len(i_) else 0.0
    print(f"{coin:4s} | {len(i_):5d} {i_.mean():+7.3f} | {len(o_):5d} {o_.mean():+8.3f}")

def sim(cfg_weights, seg, base_risk=0.01):
    """компаундинг: eq *= 1 + base_risk*w_coin*R, угоди усіх монет за часом."""
    rows = []
    for coin, w in cfg_weights.items():
        if coin not in TR: return None
        T = TR[coin]
        s = T if seg == "ALL" else T[T.seg == seg]
        rows += [(ts, w, R) for ts, R in zip(s["ts"], s["R"])]
    rows.sort(key=lambda x: x[0])
    eq = 1.0; times = []; vals = []
    for ts, w, R in rows:
        eq *= (1 + base_risk*w*R); times.append(ts); vals.append(eq)
    e = pd.Series(vals, index=pd.DatetimeIndex(times))
    e = e[~e.index.duplicated(keep="last")]
    me = e.resample("ME").last().dropna()
    mr = me.pct_change().dropna(); mr = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mr])*100
    dd = ((e/e.cummax())-1).min()*100
    return dict(n=len(rows), avg=mr.mean(), med=mr.median(), pos=(mr > 0).mean()*100,
                dd=dd, worst=mr.min(), best=mr.max(),
                tpm=len(rows)/max((times[-1]-times[0]).days/30.44, 1e-9))

# ваги за IS-exp (нормовані на середнє=1, кліп 0.5..2, монети з IS<=0 виключено)
pos_is = {c: v for c, v in is_exp.items() if v > 0}
mean_is = np.mean(list(pos_is.values())) if pos_is else 1
w_is = {c: float(np.clip(v/mean_is, 0.5, 2.0)) for c, v in pos_is.items()}

CONFIGS = [("BTC+ETH+SOL рівний", {"BTC": 1, "ETH": 1, "SOL": 1}),
           ("всі 4 рівний",       {"BTC": 1, "ETH": 1, "SOL": 1, "BNB": 1}),
           ("ETH+SOL",            {"ETH": 1, "SOL": 1}),
           ("BTC x2 (ідея юзера)", {"BTC": 2, "ETH": 1, "SOL": 1}),
           ("ваги за IS-exp",     w_is)]
print("\nКОНФІГИ (risk 1%/угоду x вага): вибираємо за IS, OOS — суддя\n")
print(f"{'конфіг':22s} {'сег':4s} | {'сер/міс':>8} {'мед':>6} {'+міс':>5} {'DD':>5} {'найг.міс':>8} {'уг/міс':>6}")
print("-"*80)
ranked = []
for name, w in CONFIGS:
    ok = all(c in TR for c in w)
    if not ok:
        print(f"{name:22s} — бракує монет, пропущено"); continue
    for seg in ["IS", "OOS"]:
        x = sim(w, seg)
        print(f"{name:22s} {seg:4s} | {x['avg']:+7.2f}% {x['med']:+5.2f}% {x['pos']:4.0f}% {x['dd']:4.0f}% {x['worst']:+7.1f}% {x['tpm']:6.1f}")
        if seg == "IS": ranked.append((x["avg"], name, w))
    print()

ranked.sort(reverse=True)
best_name, best_w = ranked[0][1], ranked[0][2]
print(f"ОБРАНО за IS: {best_name}  (ваги {best_w})\n")

print(f"ДРАБИНА РИЗИКУ для «{best_name}» (OOS-істина — чесна ціна прибутку):\n")
print(f"{'risk':>5} | {'сер/міс':>8} {'медіана':>8} {'+міс':>5} {'maxDD':>6} {'найг.міс':>8}")
print("-"*52)
for rk in [0.01, 0.015, 0.02, 0.025, 0.03]:
    x = sim(best_w, "OOS", base_risk=rk)
    print(f"{rk*100:4.1f}% | {x['avg']:+7.2f}% {x['med']:+7.2f}% {x['pos']:4.0f}% {x['dd']:5.0f}% {x['worst']:+7.1f}%")
print("\nПам'ятай: DD тут по закритих угодах; жива MTM-просадка глибша на кілька пп.")
print("15m-оцінка песимістична (неоднозначний бар = стоп) -> реальність не гірша за ці цифри.")
