"""
Стратегії. Кожна стратегія — окремий "стрім" з власним станом.
Логіка ТОЧНО відповідає бектесту (config D).

Базовий клас визначає інтерфейс. ConnorsLong30m — перший реалізований компонент.
Щоб додати новий стрім — успадкуй Strategy і реалізуй should_enter / should_exit.
"""
import numpy as np
import pandas as pd


def rsi(close: np.ndarray, period: int) -> np.ndarray:
    """RSI з EMA-згладжуванням (Wilder), як у бектесті."""
    d = pd.Series(close).diff()
    up = d.clip(lower=0)
    dn = -d.clip(upper=0)
    rs = up.ewm(alpha=1 / period, adjust=False).mean() / dn.ewm(alpha=1 / period, adjust=False).mean()
    return (100 - 100 / (1 + rs)).to_numpy()


class Strategy:
    name = "base"
    timeframe = "30m"
    # скільки свічок історії потрібно для розрахунку індикаторів
    warmup = 250

    def should_enter(self, df: pd.DataFrame):
        """
        df — DataFrame з колонками open/high/low/close, остання РЯДОК = щойно закрита свічка.
        Повертає dict {"side": "long"/"short", "stop_pct": float} або None.
        """
        raise NotImplementedError

    def should_exit(self, df: pd.DataFrame, position: dict) -> bool:
        """position — dict з entry_price, side, bars_held, stop_price. Повертає True якщо закривати."""
        raise NotImplementedError


class ConnorsLong30m(Strategy):
    """
    Connors RSI(2) long, 30m (компонент конфігурації D):
      ВХІД:  close > SMA(200) і RSI(2) < 15
      СТОП:  -2% від ціни входу
      ВИХІД: RSI(2) > 70, або стоп, або 24 бари (12 год)
    Бектест: winrate ~71%, ~10 угод/тиж.
    """
    name = "connors_long_30m"
    timeframe = "30m"
    warmup = 250

    TREND = 200
    RSI_LO = 15
    RSI_EXIT = 70
    STOP_PCT = 0.02
    MAX_BARS = 24

    def should_enter(self, df: pd.DataFrame):
        close = df["close"].to_numpy()
        sma = pd.Series(close).rolling(self.TREND).mean().to_numpy()
        rv = rsi(close, 2)
        if np.isnan(sma[-1]):
            return None
        if close[-1] > sma[-1] and rv[-1] < self.RSI_LO:
            return {"side": "long", "stop_pct": self.STOP_PCT}
        return None

    def should_exit(self, df: pd.DataFrame, position: dict) -> bool:
        close = df["close"].to_numpy()
        low = df["low"].to_numpy()
        rv = rsi(close, 2)
        # стоп
        if low[-1] <= position["stop_price"]:
            return True
        # повернення RSI до середини
        if rv[-1] > self.RSI_EXIT:
            return True
        # таймаут
        if position["bars_held"] >= self.MAX_BARS:
            return True
        return False


# Реєстр активних стратегій. Додавай сюди нові компоненти конфігурації D.
ACTIVE_STRATEGIES = [
    ConnorsLong30m(),
]
