"""Часова сезонність BTC + розбивка стратегії за часом/сесіями (дисципліна IS->OOS).
Усе з таймстемпів (UTC), без зовнішніх даних.
Сесії (UTC): Азія 00-07, Європа 07-13, US 13-21 (+оверлеп EU/US 13-16)."""
import numpy as np
import pandas as pd
import lib_data as L
import lib_split as SP
import strategies as ST
import engine as E

pd.set_option("display.width", 200)
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

btc15 = L.load_btc_15m()
is15, oos15 = SP.split(btc15)

# ---------- A. Описова сезонність BTC (15m) ----------
def seasonality(d, tag):
    r = d["close"].pct_change()
    vol = r.abs()
    print(f"\n--- {tag}: середній |рух| за бар (волатильність), % ---")
    by_h = vol.groupby(d.index.hour).mean() * 100
    print("за годиною UTC:")
    print(by_h.round(3).to_string())
    by_d = vol.groupby(d.index.dayofweek).mean() * 100
    by_d.index = [DOW[i] for i in by_d.index]
    print("за днем тижня:")
    print(by_d.round(3).to_string())
    print(f"  будні |рух| сер={vol[d.index.dayofweek<5].mean()*100:.3f}%  "
          f"вихідні={vol[d.index.dayofweek>=5].mean()*100:.3f}%  "
          f"(вихідні/будні={vol[d.index.dayofweek>=5].mean()/vol[d.index.dayofweek<5].mean():.2f})")

seasonality(is15, "IS (2017-2022)")
seasonality(oos15, "OOS (2022-2026)")

# ---------- B. Розбивка ADX-breakout 4h за часом входу ----------
def adx_di(d, n=14):
    h, l = d["high"], d["low"]; up = h.diff(); dn = -l.diff()
    pdm = ((up > dn) & (up > 0)) * up; mdm = ((dn > up) & (dn > 0)) * dn
    tr = E.true_range(d); a = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi = 100*pdm.ewm(alpha=1/n, adjust=False).mean()/a
    mdi = 100*mdm.ewm(alpha=1/n, adjust=False).mean()/a
    adx = (100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)).ewm(alpha=1/n, adjust=False).mean()
    return adx, pdi, mdi

def make_trades(d15):
    d = ST.resample(d15, "4h")
    adx, pdi, mdi = adx_di(d, 14)
    dh = E.donchian_high(d, 80).shift(1); dl = E.donchian_low(d, 80).shift(1)
    a = E.atr(d, 14)
    up = (adx > 25) & (pdi > mdi); dn = (adx > 25) & (mdi > pdi)
    long = (d["close"] > dh) & up; short = (d["close"] < dl) & dn
    side = np.zeros(len(d)); side[long.to_numpy()] = 1; side[short.to_numpy()] = -1
    res = E.backtest(d, side, (a*2.0).to_numpy(), E.Config(rr=3.0, risk_pct=0.01, bar_minutes=240))
    t = res.trades.copy()
    t["et"] = pd.to_datetime(t["entry_time"])
    t["hour"] = t["et"].dt.hour
    t["dow"] = t["et"].dt.dayofweek
    return t

def bucket(t, col, names=None):
    g = t.groupby(col)["r_mult"].agg(["count", "mean", "sum"])
    g["winrate"] = t.groupby(col).apply(lambda x: (x.net > 0).mean(), include_groups=False)
    if names:
        g.index = [names[i] for i in g.index]
    return g.round(3)

tis = make_trades(is15)
toos = make_trades(oos15)

print("\n\n========== ADX-breakout 4h: розбивка за ДНЕМ ТИЖНЯ входу ==========")
print(">> IN-SAMPLE:")
print(bucket(tis, "dow", DOW).to_string())
print(">> OUT-OF-SAMPLE:")
print(bucket(toos, "dow", DOW).to_string())

print("\n========== ADX-breakout 4h: розбивка за ГОДИНОЮ входу (UTC) ==========")
print(">> IN-SAMPLE:")
print(bucket(tis, "hour").to_string())
print(">> OUT-OF-SAMPLE:")
print(bucket(toos, "hour").to_string())

# сесії
def sess(h):
    if h < 7: return "Asia(00-07)"
    if h < 13: return "Europe(07-13)"
    return "US(13-21+)"
for t, tag in [(tis, "IS"), (toos, "OOS")]:
    t["session"] = t["hour"].map(sess)
print("\n========== За СЕСІЯМИ ==========")
print(">> IS:");  print(bucket(tis, "session").to_string())
print(">> OOS:"); print(bucket(toos, "session").to_string())

# вихідні vs будні (зведено)
print("\n========== Вихідні vs будні (вхід) ==========")
for t, tag in [(tis, "IS"), (toos, "OOS")]:
    we = t[t.dow >= 5]; wd = t[t.dow < 5]
    print(f">> {tag}: будні n={len(wd)} sumR={wd.r_mult.sum():+.1f} E[R]={wd.r_mult.mean():+.3f} | "
          f"вихідні n={len(we)} sumR={we.r_mult.sum():+.1f} E[R]={we.r_mult.mean():+.3f}")
