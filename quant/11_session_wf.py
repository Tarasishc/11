"""Чесний тест сесійного фільтра у walk-forward.
ADX25+DI breakout 4h, фільтр сесії фіксований, у вікні підбираються лише n/atr/rr.
Сесія визначається за ГОДИНОЮ ВХОДУ (UTC). 4h-бари: 0,4,8,12,16,20."""
import numpy as np
import pandas as pd
import lib_data as L
import strategies as ST
import engine as E

btc15 = L.load_btc_15m()
full4 = ST.resample(btc15, "4h")
c = full4["close"]
atr14 = E.atr(full4, 14)
hours = full4.index.hour.to_numpy()
hour_next = np.roll(hours, -1)   # година бара ВХОДУ (i+1)

def adx_di(d, n=14):
    h, l = d["high"], d["low"]; up = h.diff(); dn = -l.diff()
    pdm = ((up > dn) & (up > 0)) * up; mdm = ((dn > up) & (dn > 0)) * dn
    tr = E.true_range(d); a = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi = 100*pdm.ewm(alpha=1/n, adjust=False).mean()/a
    mdi = 100*mdm.ewm(alpha=1/n, adjust=False).mean()/a
    adx = (100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)).ewm(alpha=1/n, adjust=False).mean()
    return adx, pdi, mdi

adx, pdi, mdi = adx_di(full4, 14)
up = ((adx > 25) & (pdi > mdi)).to_numpy()
dn = ((adx > 25) & (mdi > pdi)).to_numpy()
DON = {n: (E.donchian_high(full4, n).shift(1).to_numpy(),
           E.donchian_low(full4, n).shift(1).to_numpy()) for n in [50, 80]}
ATR_NP = atr14.to_numpy()

def side_arr(n, allowed):
    dh, dl = DON[n]
    long = (c.to_numpy() > dh) & up
    short = (c.to_numpy() < dl) & dn
    s = np.zeros(len(full4))
    s[long] = 1; s[short] = -1
    if allowed is not None:
        mask = np.isin(hour_next, allowed)
        s[~mask] = 0
    return s

YR = int(365*24/4); TRAIN, TEST = 2*YR, 1*YR
GN, GA, GR = [50, 80], [2.0, 3.0], [2.0, 3.0]
RISK = 0.02

SESSIONS = {
    "ALL (всі години)":        [0, 4, 8, 12, 16, 20],
    "Asia/EU (00-12 UTC)":     [0, 4, 8],
    "skip US (без 12,16)":     [0, 4, 8, 20],
    "US only (12,16,20)":      [12, 16, 20],
}
SIDE = {(s, n): side_arr(n, h) for s, h in SESSIONS.items() for n in GN}

def bt(a, b, key, n, am, rr, risk, eq):
    return E.backtest(full4.iloc[a:b], SIDE[(key, n)][a:b], ATR_NP[a:b]*am,
                      E.Config(rr=rr, risk_pct=risk, bar_minutes=240, initial_equity=eq))

def wf(key, risk=RISK):
    eq = 10000.0; et, ev = [], []; tt = []; start = 0
    while start + TRAIN + TEST <= len(full4):
        a, b = start, start+TRAIN; ta, tb = b, min(b+TEST, len(full4)); best = None
        for n in GN:
            for am in GA:
                for rr in GR:
                    m = bt(a, b, key, n, am, rr, 0.01, 10000).metrics
                    if m["n_trades"] >= 15 and (best is None or m["profit_factor"] > best[0]):
                        best = (m["profit_factor"], n, am, rr)
        if best:
            _, n, am, rr = best; r = bt(ta, tb, key, n, am, rr, risk, eq)
            for _, x in r.trades.iterrows(): et.append(x["exit_time"]); ev.append(x["equity"])
            if len(r.trades): eq = r.trades["equity"].iloc[-1]; tt.append(r.trades)
        start += TEST
    if not tt: return None
    allt = pd.concat(tt)
    eqs = pd.Series(ev, index=pd.DatetimeIndex(et)); eqs = eqs[~eqs.index.duplicated(keep="last")]
    daily = eqs.resample("1D").last().ffill(); dd = (daily/daily.cummax()-1).min()
    yrs = (eqs.index[-1]-eqs.index[0]).days/365.25; cagr = (eqs.iloc[-1]/10000)**(1/yrs)-1
    mret = daily.resample("ME").last().pct_change().dropna()
    dret = daily.pct_change().dropna(); sharpe = np.sqrt(365)*dret.mean()/dret.std() if dret.std()>0 else 0
    pf = allt[allt.net>0].net.sum()/max(-allt[allt.net<=0].net.sum(), 1e-9)
    return dict(trades=len(allt), final=eqs.iloc[-1]/10000, cagr=cagr, avg_mo=mret.mean(),
                dd=dd, sharpe=sharpe, wr=(allt.net>0).mean(), pf=pf)

print("Walk-forward ADX25+DI breakout 4h, сесійний фільтр (risk 2%):\n")
print(f"{'сесія входу':24} {'угод':>5} {'final×':>7} {'CAGR%':>7} {'avg_mo%':>8} {'maxDD%':>7} {'Sharpe':>7} {'WR%':>5} {'PF':>5}")
for key in SESSIONS:
    r = wf(key)
    if r:
        print(f"{key:24} {r['trades']:5d} {r['final']:7.2f} {r['cagr']*100:7.1f} "
              f"{r['avg_mo']*100:8.2f} {r['dd']*100:7.1f} {r['sharpe']:7.2f} {r['wr']*100:5.1f} {r['pf']:5.2f}")

# масштабування ризику для найкращого сесійного варіанта
print("\nМасштабування ризику для 'skip US (без 12,16)':")
print(f"{'risk%':>6}{'CAGR%':>8}{'avg_mo%':>9}{'maxDD%':>8}{'final×':>8}")
for risk in [0.02, 0.03, 0.05, 0.07]:
    r = wf("skip US (без 12,16)", risk)
    print(f"{risk*100:6.0f}{r['cagr']*100:8.1f}{r['avg_mo']*100:9.2f}{r['dd']*100:8.1f}{r['final']:8.2f}")
