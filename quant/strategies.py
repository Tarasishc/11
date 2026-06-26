"""Стратегії price action. Кожна повертає (side, stop_dist):
  side[i] in {+1,-1,0} — сигнал на закритті бара i (вхід на open[i+1]).
  stop_dist[i] — дистанція стопа в ціні, визначена на барі i.

Усі правила однозначні й читаються з графіка."""
import numpy as np
import pandas as pd
import engine as E


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    o = df["open"].resample(rule, label="left", closed="left").first()
    h = df["high"].resample(rule, label="left", closed="left").max()
    l = df["low"].resample(rule, label="left", closed="left").min()
    c = df["close"].resample(rule, label="left", closed="left").last()
    v = df["vol"].resample(rule, label="left", closed="left").sum()
    out = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "vol": v})
    return out.dropna(subset=["open", "high", "low", "close"])


# ---------------- H1: Trend pullback до EMA (with-trend) -----------------
def h1_trend_pullback(d, ema_fast=50, ema_slow=200, ema_pull=20,
                      atr_n=14, atr_mult=1.5, allow_long=True, allow_short=True):
    c, o = d["close"], d["open"]
    ef = E.ema(c, ema_fast)
    es = E.ema(c, ema_slow)
    ep = E.ema(c, ema_pull)
    a = E.atr(d, atr_n)
    up = ef > es           # висхідний тренд
    dn = ef < es           # низхідний тренд
    bull_bar = c > o
    bear_bar = c < o
    prev_c = c.shift(1)

    # Шорт: тренд вниз; попередній бар закрився ВИЩЕ EMA20 (відкат вгору);
    # поточний бар-ведмідь закрився НИЖЧЕ EMA20 (відбиття).
    short = dn & (prev_c > ep.shift(1)) & (c < ep) & bear_bar
    # Лонг: дзеркально.
    long = up & (prev_c < ep.shift(1)) & (c > ep) & bull_bar

    side = np.zeros(len(d))
    if allow_long:
        side[long.to_numpy()] = 1
    if allow_short:
        side[short.to_numpy()] = -1
    stop_dist = (a * atr_mult).to_numpy()
    return side, stop_dist


# ---------------- H2: Donchian breakout + тренд-фільтр -------------------
def h2_breakout_trend(d, n=50, ema_trend=200, atr_n=14, atr_mult=2.0,
                      allow_long=True, allow_short=True):
    c = d["close"]
    dh = E.donchian_high(d, n).shift(1)
    dl = E.donchian_low(d, n).shift(1)
    et = E.ema(c, ema_trend)
    a = E.atr(d, atr_n)
    long = (c > dh) & (c > et)
    short = (c < dl) & (c < et)
    side = np.zeros(len(d))
    if allow_long:
        side[long.to_numpy()] = 1
    if allow_short:
        side[short.to_numpy()] = -1
    stop_dist = (a * atr_mult).to_numpy()
    return side, stop_dist


# ---------------- H3: Failed breakout (range reversal) ------------------
def h3_failed_breakout(d, n=30, atr_n=14, atr_mult=1.5, adx_n=14, adx_max=0,
                       allow_long=True, allow_short=True):
    c, h, l = d["close"], d["high"], d["low"]
    rh = E.donchian_high(d, n).shift(1)   # межа діапазону (без поточного бара)
    rl = E.donchian_low(d, n).shift(1)
    a = E.atr(d, atr_n)
    # Прокол вгору, але закриття назад усередину -> бичача пастка -> SHORT
    short = (h > rh) & (c < rh)
    # Прокол вниз, але закриття назад усередину -> ведмежа пастка -> LONG
    long = (l < rl) & (c > rl)
    if adx_max > 0:
        ax = E.adx(d, adx_n)
        rng = ax < adx_max
        short = short & rng
        long = long & rng
    side = np.zeros(len(d))
    if allow_long:
        side[long.to_numpy()] = 1
    if allow_short:
        side[short.to_numpy()] = -1
    stop_dist = (a * atr_mult).to_numpy()
    return side, stop_dist


# ---------------- H4: Bollinger mean-reversion (range) ------------------
def h4_bb_meanrev(d, n=20, k=2.0, atr_n=14, atr_mult=1.5, adx_n=14, adx_max=20,
                  allow_long=True, allow_short=True):
    c = d["close"]
    ma = E.sma(c, n)
    sd = c.rolling(n).std()
    upper = ma + k * sd
    lower = ma - k * sd
    a = E.atr(d, atr_n)
    ax = E.adx(d, adx_n)
    rng = ax < adx_max
    short = (c > upper) & rng
    long = (c < lower) & rng
    side = np.zeros(len(d))
    if allow_long:
        side[long.to_numpy()] = 1
    if allow_short:
        side[short.to_numpy()] = -1
    stop_dist = (a * atr_mult).to_numpy()
    return side, stop_dist


STRATS = {
    "H1_trend_pullback": h1_trend_pullback,
    "H2_breakout_trend": h2_breakout_trend,
    "H3_failed_breakout": h3_failed_breakout,
    "H4_bb_meanrev": h4_bb_meanrev,
}
