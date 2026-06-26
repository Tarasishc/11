"""Відповідь на питання: чому лише EMA200? Тест РІЗНИХ трендових фільтрів.
Усе інше зафіксовано (H2 breakout, 4h, n=80, ATR×2, RR=3, risk 1%).
Міняємо ТІЛЬКИ спосіб визначення тренду і дивимось IS vs OOS."""
import numpy as np
import pandas as pd
import lib_data as L
import lib_split as SP
import strategies as ST
import engine as E

pd.set_option("display.width", 220)

btc15 = L.load_btc_15m()
is15, oos15 = SP.split(btc15)
is4 = ST.resample(is15, "4h")
oos4 = ST.resample(oos15, "4h")

N, ATRM, RR, ATR_N = 80, 2.0, 3.0, 14


def di_components(d, n=14):
    h, l = d["high"], d["low"]
    up = h.diff(); dn = -l.diff()
    plus_dm = ((up > dn) & (up > 0)) * up
    minus_dm = ((dn > up) & (dn > 0)) * dn
    tr = E.true_range(d)
    atr_ = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi = 100 * plus_dm.ewm(alpha=1/n, adjust=False).mean() / atr_
    mdi = 100 * minus_dm.ewm(alpha=1/n, adjust=False).mean() / atr_
    adx = (100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)).ewm(alpha=1/n, adjust=False).mean()
    return adx, pdi, mdi


def htf_trend(d, rule="1D", ema_n=50):
    """Тренд зі СТАРШОГО ТФ (без lookahead: беремо попередній завершений бар)."""
    c = d["close"].resample(rule, label="left", closed="left").last().dropna()
    e = E.ema(c, ema_n)
    up_d = (c > e).shift(1)
    dn_d = (c < e).shift(1)
    up = up_d.reindex(d.index, method="ffill").fillna(False).astype(bool)
    dn = dn_d.reindex(d.index, method="ffill").fillna(False).astype(bool)
    return up, dn


def trend_filters(d):
    c = d["close"]
    F = {}
    F["none (без фільтра)"] = (pd.Series(True, index=d.index), pd.Series(True, index=d.index))
    for k in [50, 100, 150, 200, 300]:
        e = E.ema(c, k)
        F[f"price vs EMA{k}"] = (c > e, c < e)
    s = E.sma(c, 200)
    F["price vs SMA200"] = (c > s, c < s)
    ef, es = E.ema(c, 50), E.ema(c, 200)
    F["EMA50 vs EMA200 (cross)"] = (ef > es, ef < es)
    e200 = E.ema(c, 200)
    F["EMA200 slope (нахил, 10 барів)"] = (e200 > e200.shift(10), e200 < e200.shift(10))
    # комбо: ціна над EMA200 І EMA200 росте
    F["EMA200 + нахил (обидва)"] = ((c > e200) & (e200 > e200.shift(10)),
                                    (c < e200) & (e200 < e200.shift(10)))
    adx, pdi, mdi = di_components(d, 14)
    F["ADX>20 + DI напрям"] = ((adx > 20) & (pdi > mdi), (adx > 20) & (mdi > pdi))
    F["ADX>25 + DI напрям"] = ((adx > 25) & (pdi > mdi), (adx > 25) & (mdi > pdi))
    F["HTF: daily>EMA50"] = htf_trend(d, "1D", 50)
    F["HTF: daily>EMA200"] = htf_trend(d, "1D", 200)
    return F


def run(d, up, dn):
    dh = E.donchian_high(d, N).shift(1)
    dl = E.donchian_low(d, N).shift(1)
    a = E.atr(d, ATR_N)
    long = (d["close"] > dh) & up.reindex(d.index).fillna(False)
    short = (d["close"] < dl) & dn.reindex(d.index).fillna(False)
    side = np.zeros(len(d))
    side[long.to_numpy()] = 1
    side[short.to_numpy()] = -1
    cfg = E.Config(rr=RR, risk_pct=0.01, bar_minutes=240)
    return E.backtest(d, side, (a * ATRM).to_numpy(), cfg).metrics


Fis = trend_filters(is4)
Foos = trend_filters(oos4)

print(f"{'Трендовий фільтр':32} | {'IS:trades':>9} {'PF':>5} {'Shrp':>5} {'E[R]':>6} | "
      f"{'OOS:trades':>10} {'PF':>5} {'Shrp':>5} {'E[R]':>6} {'avg_mo%':>7} {'maxDD%':>7}")
print("-" * 120)
rows = []
for name in Fis:
    mi = run(is4, *Fis[name])
    mo = run(oos4, *Foos[name])
    rows.append((name, mi, mo))
    print(f"{name:32} | {mi['n_trades']:9d} {mi['profit_factor']:5.2f} {mi['sharpe']:5.2f} "
          f"{mi['expectancy_R']:6.3f} | {mo['n_trades']:10d} {mo['profit_factor']:5.2f} "
          f"{mo['sharpe']:5.2f} {mo['expectancy_R']:6.3f} {mo['avg_monthly']*100:7.2f} {mo['max_dd']*100:7.1f}")

# зведення: чи деградує едж на OOS у ВСІХ фільтрах
oos_pf = [r[2]["profit_factor"] for r in rows]
is_pf = [r[1]["profit_factor"] for r in rows]
print("-" * 120)
print(f"IS  PF: медіана={np.median(is_pf):.2f}  min={min(is_pf):.2f}  max={max(is_pf):.2f}")
print(f"OOS PF: медіана={np.median(oos_pf):.2f}  min={min(oos_pf):.2f}  max={max(oos_pf):.2f}  "
      f"| прибуткових (PF>1.1) на OOS: {sum(p>1.1 for p in oos_pf)}/{len(oos_pf)}")
