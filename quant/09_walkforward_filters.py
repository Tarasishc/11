"""Чесний walk-forward з вибором трендового фільтра (прибираємо data-snooping).

Метод:
  * Усі індикатори рахуються на ПОВНОМУ 4h-ряді, далі нарізаємо вікна -> немає
    контамінації прогріву на межах.
  * Вікна: train 2 роки, test 1 рік, крок 1 рік.
  * Усередині кожного train обираємо найкращий конфіг за profit_factor
    (з гейтом мін. угод). Застосовуємо НАОСЛІП до наступного test.
  * Єдиний капітал, що компаундиться через усі test-вікна (ризик 2%).

Два режими:
  A) per-filter: фільтр зафіксовано, підбираються лише n/atr/rr (apples-to-apples).
  B) auto-all : алгоритм обирає й фільтр теж (чи можна взагалі знати фільтр наперед?).
"""
import numpy as np
import pandas as pd
import lib_data as L
import strategies as ST
import engine as E

pd.set_option("display.width", 220)

btc15 = L.load_btc_15m()
full4 = ST.resample(btc15, "4h")
c = full4["close"]
atr14 = E.atr(full4, 14)


def filt_masks(d):
    cc = d["close"]
    out = {}
    out["none"] = (pd.Series(True, index=d.index), pd.Series(True, index=d.index))
    e200 = E.ema(cc, 200)
    out["EMA200"] = (cc > e200, cc < e200)
    ef, es = E.ema(cc, 50), E.ema(cc, 200)
    out["EMA50x200"] = (ef > es, ef < es)
    adx, pdi, mdi = ST_di(d, 14)
    out["ADX25+DI"] = ((adx > 25) & (pdi > mdi), (adx > 25) & (mdi > pdi))
    cd = cc.resample("1D", label="left", closed="left").last().dropna()
    ed = E.ema(cd, 200)
    upd = (cd > ed).shift(1); dnd = (cd < ed).shift(1)
    out["HTF_d>EMA200"] = (upd.reindex(d.index, method="ffill").fillna(False).astype(bool),
                            dnd.reindex(d.index, method="ffill").fillna(False).astype(bool))
    return out


def ST_di(d, n=14):
    h, l = d["high"], d["low"]
    up = h.diff(); dn = -l.diff()
    pdm = ((up > dn) & (up > 0)) * up
    mdm = ((dn > up) & (dn > 0)) * dn
    tr = E.true_range(d)
    a = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi = 100 * pdm.ewm(alpha=1/n, adjust=False).mean() / a
    mdi = 100 * mdm.ewm(alpha=1/n, adjust=False).mean() / a
    adx = (100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)).ewm(alpha=1/n, adjust=False).mean()
    return adx, pdi, mdi


MASKS = filt_masks(full4)
DON = {n: (E.donchian_high(full4, n).shift(1), E.donchian_low(full4, n).shift(1)) for n in [50, 80]}

FILTERS = ["none", "EMA200", "EMA50x200", "ADX25+DI", "HTF_d>EMA200"]
GN, GA, GR = [50, 80], [2.0, 3.0], [2.0, 3.0]
RISK = 0.02
YR = int(365 * 24 / 4)            # 4h барів у році
TRAIN, TEST, STEP = 2 * YR, 1 * YR, 1 * YR
MIN_TR = 20


def side_array(filt, n):
    up, dn = MASKS[filt]
    dh, dl = DON[n]
    long = (c > dh) & up
    short = (c < dl) & dn
    s = np.zeros(len(full4))
    s[long.to_numpy()] = 1
    s[short.to_numpy()] = -1
    return s


# кеш side-масивів
SIDE = {(f, n): side_array(f, n) for f in FILTERS for n in GN}
ATR_NP = atr14.to_numpy()


def bt_window(a, b, filt, n, am, rr, risk, eq0):
    d = full4.iloc[a:b]
    side = SIDE[(filt, n)][a:b]
    sd = ATR_NP[a:b] * am
    cfg = E.Config(rr=rr, risk_pct=risk, bar_minutes=240, initial_equity=eq0)
    return E.backtest(d, side, sd, cfg)


def select_on_train(a, b, filters):
    """Найкращий (filt,n,am,rr) за PF на train (гейт мін.угод)."""
    best = None
    for f in filters:
        for n in GN:
            for am in GA:
                for rr in GR:
                    m = bt_window(a, b, f, n, am, rr, 0.01, 10000).metrics
                    if m["n_trades"] >= MIN_TR and (best is None or m["profit_factor"] > best[0]):
                        best = (m["profit_factor"], f, n, am, rr)
    return best


def walkforward(filters, label):
    eq = 10000.0
    eq_t, eq_v = [], []
    test_trades = []
    log = []
    start = 0
    while start + TRAIN + TEST <= len(full4):
        a, b = start, start + TRAIN
        ta, tb = b, min(b + TEST, len(full4))
        best = select_on_train(a, b, filters)
        if best is None:
            start += STEP; continue
        _, bf, bn, bam, brr = best
        res = bt_window(ta, tb, bf, bn, bam, brr, RISK, eq)
        if len(res.trades):
            for _, r in res.trades.iterrows():
                eq_t.append(r["exit_time"]); eq_v.append(r["equity"])
            eq = res.trades["equity"].iloc[-1]
            test_trades.append(res.trades)
        m = res.metrics
        log.append(dict(test_from=str(full4.index[ta].date()), test_to=str(full4.index[tb-1].date()),
                        pick=f"{bf}/n{bn}/a{bam}/rr{brr}", trades=m["n_trades"],
                        ret=round(m["total_return"], 3), PF=round(m["profit_factor"], 2)))
        start += STEP

    if not test_trades:
        return None
    tt = pd.concat(test_trades)
    eqs = pd.Series(eq_v, index=pd.DatetimeIndex(eq_t))
    eqs = eqs[~eqs.index.duplicated(keep="last")]
    daily = eqs.resample("1D").last().ffill()
    dd = (daily / daily.cummax() - 1).min()
    yrs = (eqs.index[-1] - eqs.index[0]).days / 365.25
    cagr = (eqs.iloc[-1] / 10000) ** (1 / yrs) - 1
    mret = daily.resample("ME").last().pct_change().dropna()
    dret = daily.pct_change().dropna()
    sharpe = np.sqrt(365) * dret.mean() / dret.std() if dret.std() > 0 else 0
    pf = tt[tt.net > 0].net.sum() / max(-tt[tt.net <= 0].net.sum(), 1e-9)
    return dict(label=label, trades=len(tt), final=eqs.iloc[-1], cagr=cagr,
                avg_mo=mret.mean(), maxdd=dd, sharpe=sharpe, wr=(tt.net > 0).mean(),
                pf=pf, log=log)


print(f"4h барів={len(full4)}  вікна: train={TRAIN}(2р) test={TEST}(1р) step={STEP}(1р)\n")
print("===== A) PER-FILTER walk-forward (фільтр фіксований, підбір n/atr/rr) =====")
print(f"{'фільтр':14} {'trades':>6} {'final×':>7} {'CAGR%':>7} {'avg_mo%':>8} {'maxDD%':>7} {'Sharpe':>7} {'WR%':>5} {'PF':>5}")
results = {}
for f in FILTERS:
    r = walkforward([f], f)
    results[f] = r
    if r:
        print(f"{f:14} {r['trades']:6d} {r['final']/10000:7.2f} {r['cagr']*100:7.1f} "
              f"{r['avg_mo']*100:8.2f} {r['maxdd']*100:7.1f} {r['sharpe']:7.2f} "
              f"{r['wr']*100:5.1f} {r['pf']:5.2f}")

print("\n===== B) AUTO-ALL walk-forward (алгоритм обирає Й фільтр теж) =====")
rb = walkforward(FILTERS, "AUTO")
if rb:
    print(f"{'AUTO':14} {rb['trades']:6d} {rb['final']/10000:7.2f} {rb['cagr']*100:7.1f} "
          f"{rb['avg_mo']*100:8.2f} {rb['maxdd']*100:7.1f} {rb['sharpe']:7.2f} "
          f"{rb['wr']*100:5.1f} {rb['pf']:5.2f}")
    print("\nЩо алгоритм обирав на кожному test-вікні (видно нестабільність вибору):")
    print(pd.DataFrame(rb["log"]).to_string(index=False))

print("\n===== Порівняння з фіксованим EMA200 (як у звіті) =====")
print("Якщо ADX25+DI / HTF стабільно кращі за EMA200 і none на test-вікнах -> едж від фільтра реальний.")
print("Якщо AUTO не б'є найкращий фіксований -> наперед знати потрібний фільтр не вдається.")
