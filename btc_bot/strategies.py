"""
Стратегії конфігурації D. Кожна — окремий "стрім" з власним станом.
Логіка ТОЧНО відповідає бектесту.

Інтерфейс (base Strategy):
  should_enter(df) -> {"side": "long"/"short", "stop_price": float} | None
  should_exit(df, position) -> bool   (може оновлювати position["stop_price"] для трейлінгу)

Атрибути стратегії:
  name, timeframe, warmup
  sizing_mode: "risk" (розмір під стоп) | "notional" (частка номіналу, для календаря)
  notional_mult: множник номіналу для sizing_mode="notional"
"""
import numpy as np
import pandas as pd


def rsi(close, period):
    d = pd.Series(close).diff()
    up = d.clip(lower=0)
    dn = -d.clip(upper=0)
    rs = up.ewm(alpha=1 / period, adjust=False).mean() / dn.ewm(alpha=1 / period, adjust=False).mean()
    return (100 - 100 / (1 + rs)).to_numpy()


def atr(high, low, close, period=14):
    h, l, c = pd.Series(high), pd.Series(low), pd.Series(close)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean().to_numpy()


class Strategy:
    name = "base"
    timeframe = "30m"
    warmup = 250
    sizing_mode = "risk"
    notional_mult = 1.0

    def should_enter(self, df):
        raise NotImplementedError

    def should_exit(self, df, position):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 1) Connors RSI(2) mean-reversion (вихід по поверненню RSI). Високий вінрейт.
# ---------------------------------------------------------------------------
class ConnorsLong30m(Strategy):
    name = "connors_long_30m"; timeframe = "30m"; warmup = 250
    TREND = 200; RSI_LO = 15; RSI_EXIT = 70; STOP_PCT = 0.02; MAX_BARS = 24

    def should_enter(self, df):
        close = df["close"].to_numpy()
        sma = pd.Series(close).rolling(self.TREND).mean().to_numpy()
        rv = rsi(close, 2)
        if np.isnan(sma[-1]):
            return None
        if close[-1] > sma[-1] and rv[-1] < self.RSI_LO:
            return {"side": "long", "stop_price": close[-1] * (1 - self.STOP_PCT)}
        return None

    def should_exit(self, df, position):
        close = df["close"].to_numpy(); low = df["low"].to_numpy(); rv = rsi(close, 2)
        if low[-1] <= position["stop_price"]:
            return True
        if rv[-1] > self.RSI_EXIT:
            return True
        return position["bars_held"] >= self.MAX_BARS


class ConnorsShort30m(Strategy):
    name = "connors_short_30m"; timeframe = "30m"; warmup = 150
    TREND = 100; RSI_HI = 90; RSI_EXIT = 30; STOP_PCT = 0.02; MAX_BARS = 24

    def should_enter(self, df):
        close = df["close"].to_numpy()
        sma = pd.Series(close).rolling(self.TREND).mean().to_numpy()
        rv = rsi(close, 2)
        if np.isnan(sma[-1]):
            return None
        if close[-1] < sma[-1] and rv[-1] > self.RSI_HI:
            return {"side": "short", "stop_price": close[-1] * (1 + self.STOP_PCT)}
        return None

    def should_exit(self, df, position):
        close = df["close"].to_numpy(); high = df["high"].to_numpy(); rv = rsi(close, 2)
        if high[-1] >= position["stop_price"]:
            return True
        if rv[-1] < self.RSI_EXIT:
            return True
        return position["bars_held"] >= self.MAX_BARS


# ---------------------------------------------------------------------------
# 2) Trend: Donchian breakout + ATR trailing stop (даємо прибутку бігти)
# ---------------------------------------------------------------------------
class _VBTBase(Strategy):
    LB = 40; STOP_ATR = 2.0; TRAIL_ATR = 2.5; MAX_BARS = 60

    def should_enter(self, df):
        close = df["close"].to_numpy(); high = df["high"].to_numpy(); low = df["low"].to_numpy()
        # макс high за LB попередніх БАРІВ (без поточного) — без lookahead
        roll_hi = pd.Series(high).rolling(self.LB).max().shift(1).to_numpy()
        a = atr(high, low, close, 14)
        if np.isnan(roll_hi[-1]) or np.isnan(a[-1]):
            return None
        if close[-1] > roll_hi[-1]:
            return {"side": "long", "stop_price": close[-1] - a[-1] * self.STOP_ATR}
        return None

    def should_exit(self, df, position):
        close = df["close"].to_numpy(); low = df["low"].to_numpy()
        high = df["high"].to_numpy()
        a = atr(high, low, close, 14)
        # трейлінг по щойно закритій свічці
        new_stop = close[-1] - a[-1] * self.TRAIL_ATR
        if new_stop > position["stop_price"]:
            position["stop_price"] = new_stop
        if low[-1] <= position["stop_price"]:
            return True
        return position["bars_held"] >= self.MAX_BARS


class VBT_4H_40(_VBTBase):
    name = "vbt_4h_40"; timeframe = "4h"; warmup = 80
    LB = 40; STOP_ATR = 2.0; TRAIL_ATR = 2.5; MAX_BARS = 60


class VBT_4H_50(_VBTBase):
    name = "vbt_4h_50"; timeframe = "4h"; warmup = 90
    LB = 50; STOP_ATR = 1.5; TRAIL_ATR = 3.0; MAX_BARS = 60


class VBT_1D_20(_VBTBase):
    name = "vbt_1d_20"; timeframe = "1d"; warmup = 60
    LB = 20; STOP_ATR = 1.0; TRAIL_ATR = 4.0; MAX_BARS = 30


# ---------------------------------------------------------------------------
# 3) Momentum continuation + ATR trailing stop
# ---------------------------------------------------------------------------
class _MomBase(Strategy):
    LB = 16; THRESH = 0.01; STOP_ATR = 2.0; TRAIL_ATR = 2.0; MAX_BARS = 50

    def should_enter(self, df):
        close = df["close"].to_numpy(); high = df["high"].to_numpy(); low = df["low"].to_numpy()
        a = atr(high, low, close, 14)
        if len(close) <= self.LB or np.isnan(a[-1]):
            return None
        ret = (close[-1] - close[-1 - self.LB]) / close[-1 - self.LB]
        if ret >= self.THRESH:
            return {"side": "long", "stop_price": close[-1] - a[-1] * self.STOP_ATR}
        return None

    def should_exit(self, df, position):
        close = df["close"].to_numpy(); low = df["low"].to_numpy(); high = df["high"].to_numpy()
        a = atr(high, low, close, 14)
        new_stop = close[-1] - a[-1] * self.TRAIL_ATR
        if new_stop > position["stop_price"]:
            position["stop_price"] = new_stop
        if low[-1] <= position["stop_price"]:
            return True
        return position["bars_held"] >= self.MAX_BARS


class Mom_2H_16(_MomBase):
    name = "mom_2h_16"; timeframe = "2h"; warmup = 50
    LB = 16; THRESH = 0.01; STOP_ATR = 2.0; TRAIL_ATR = 2.0; MAX_BARS = 50


class Mom_1H_8(_MomBase):
    name = "mom_1h_8"; timeframe = "1h"; warmup = 40
    LB = 8; THRESH = 0.008; STOP_ATR = 2.0; TRAIL_ATR = 2.5; MAX_BARS = 60


# ---------------------------------------------------------------------------
# 4) Ведмежий календар: шорт у даунтренді (close<EMA100), холд 1 день.
#    Нотіональний сайзинг (0.5x), вихід по часу. Захисний широкий стоп.
# ---------------------------------------------------------------------------
class BearCalendar1D(Strategy):
    name = "bear_calendar_1d"; timeframe = "1d"; warmup = 120
    sizing_mode = "notional"; notional_mult = 0.5
    EMA = 100; HOLD_BARS = 1; SAFETY_STOP_PCT = 0.15

    def should_enter(self, df):
        close = df["close"].to_numpy()
        ema = pd.Series(close).ewm(span=self.EMA, adjust=False).mean().to_numpy()
        if np.isnan(ema[-1]):
            return None
        if close[-1] < ema[-1]:
            return {"side": "short", "stop_price": close[-1] * (1 + self.SAFETY_STOP_PCT)}
        return None

    def should_exit(self, df, position):
        high = df["high"].to_numpy()
        if high[-1] >= position["stop_price"]:
            return True
        return position["bars_held"] >= self.HOLD_BARS


# Усі активні стріми конфігурації D.
ACTIVE_STRATEGIES = [
    ConnorsLong30m(),
    ConnorsShort30m(),
    VBT_4H_40(),
    VBT_4H_50(),
    VBT_1D_20(),
    Mom_2H_16(),
    Mom_1H_8(),
    BearCalendar1D(),
]
