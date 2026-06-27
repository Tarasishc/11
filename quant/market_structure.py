"""Структура ринку + фрактали Вільямса (механічно, без lookahead).

Фрактал (вікно k): up-фрактал на барі j = high[j] строго вище за highs k барів ліворуч
і k барів праворуч. Стає ВІДОМИМ лише на барі j+k (потрібні k майбутніх барів).
down-фрактал — дзеркально по low.

На кожному барі i тримаємо: останній і попередній ПІДТВЕРДЖЕНІ swing high/low.
  trend_up = HH & HL (cur_SH>prev_SH і cur_SL>prev_SL)
  trend_dn = LH & LL
  break_up = close > cur_SH  (пробій останнього swing high)
  break_dn = close < cur_SL
Сигнали:
  continuation long = break_up & trend_up      (BOS у тренді)
  continuation short= break_dn & trend_dn
  reversal long     = break_up & trend_dn       (CHoCH — зміна характеру)
  reversal short    = break_dn & trend_up
Стоп: структурний (до протилежного swing), з ATR-обмеженням, або чистий ATR.
"""
import numpy as np
import pandas as pd
import engine as E


def fractals(df: pd.DataFrame, k: int = 2):
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    n = len(df)
    up = np.zeros(n, bool)
    dn = np.zeros(n, bool)
    for j in range(k, n - k):
        hj = h[j]
        if hj == max(h[j - k:j + k + 1]) and hj > h[j - 1] and hj > h[j + 1]:
            up[j] = True
        lj = l[j]
        if lj == min(l[j - k:j + k + 1]) and lj < l[j - 1] and lj < l[j + 1]:
            dn[j] = True
    return up, dn


def compute_structure(df: pd.DataFrame, k: int = 2):
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    n = len(df)
    up, dn = fractals(df, k)
    cur_SH = np.full(n, np.nan); prev_SH = np.full(n, np.nan)
    cur_SL = np.full(n, np.nan); prev_SL = np.full(n, np.nan)
    # ціна фрактала стає доступною на j+k
    avail_SH = {}; avail_SL = {}
    for j in range(n):
        if up[j] and j + k < n:
            avail_SH[j + k] = h[j]
        if dn[j] and j + k < n:
            avail_SL[j + k] = l[j]
    lastSH = prevSH = np.nan
    lastSL = prevSL = np.nan
    for i in range(n):
        if i in avail_SH:
            prevSH = lastSH; lastSH = avail_SH[i]
        if i in avail_SL:
            prevSL = lastSL; lastSL = avail_SL[i]
        cur_SH[i] = lastSH; prev_SH[i] = prevSH
        cur_SL[i] = lastSL; prev_SL[i] = prevSL
    return dict(cur_SH=cur_SH, prev_SH=prev_SH, cur_SL=cur_SL, prev_SL=prev_SL)


def ms_signals(df, k=2, mode="cont", stop_mode="struct", atr_mult=2.0,
               stop_cap_atr=4.0, stop_floor_atr=0.5, rr=2.0,
               allow_long=True, allow_short=True, struct=None, atr_arr=None):
    s = struct if struct is not None else compute_structure(df, k)
    c = df["close"].to_numpy()
    a = atr_arr if atr_arr is not None else E.atr(df, 14).to_numpy()
    cur_SH, prev_SH = s["cur_SH"], s["prev_SH"]
    cur_SL, prev_SL = s["cur_SL"], s["prev_SL"]

    trend_up = (cur_SH > prev_SH) & (cur_SL > prev_SL)
    trend_dn = (cur_SH < prev_SH) & (cur_SL < prev_SL)
    break_up = c > cur_SH
    break_dn = c < cur_SL

    if mode == "cont":
        long = break_up & trend_up
        short = break_dn & trend_dn
    elif mode == "rev":
        long = break_up & trend_dn
        short = break_dn & trend_up
    else:  # both — чистий swing-breakout
        long = break_up
        short = break_dn

    n = len(df)
    side = np.zeros(n)
    if allow_long:
        side[np.nan_to_num(long, nan=0).astype(bool)] = 1
    if allow_short:
        side[np.nan_to_num(short, nan=0).astype(bool)] = -1

    # дистанція стопа
    if stop_mode == "atr":
        stop_dist = a * atr_mult
    else:  # структурний з ATR-обмеженням
        sd = np.full(n, np.nan)
        long_mask = side > 0
        short_mask = side < 0
        sd[long_mask] = c[long_mask] - cur_SL[long_mask]   # стоп під swing low
        sd[short_mask] = cur_SH[short_mask] - c[short_mask]  # стоп над swing high
        cap = a * stop_cap_atr
        floor = a * stop_floor_atr
        sd = np.where(np.isfinite(sd), sd, np.nan)
        sd = np.clip(sd, floor, cap)
        stop_dist = sd
    # прибрати недопустимі
    bad = ~np.isfinite(stop_dist) | (stop_dist <= 0)
    side[bad] = 0
    return side, stop_dist
