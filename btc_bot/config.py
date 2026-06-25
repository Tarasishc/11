"""
Конфігурація бота. Заповни ключі Binance Testnet нижче.
Як отримати ключі: https://testnet.binancefuture.com/ -> API Key
"""
import os

# --- Binance Testnet (паперова торгівля; реальні гроші НЕ потрібні) ---
API_KEY = os.getenv("BINANCE_API_KEY", "ВСТАВ_СЮДИ_TESTNET_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET", "ВСТАВ_СЮДИ_TESTNET_SECRET")
USE_TESTNET = True            # True = testnet (безпечно). False = реальний рахунок.

SYMBOL = "BTC/USDT"
LEVERAGE = 3                  # плече на ф'ючерсах (для розміру позиції)

# --- Ризик-менеджмент ---
EQUITY_OVERRIDE = None        # None = брати баланс з біржі; або фіксоване число для тесту
# ризик на угоду у % від депозиту (як у бектесті конфігурації D)
RISK_PER_TRADE = {
    "connors_long_30m": 0.012,    # 1.2%
    # сюди додаси решту стрімів пізніше:
    # "connors_short_30m": 0.010,
    # "trend_vbt_4h_40":   0.008,
}

# --- Технічні ---
POLL_SECONDS = 20             # як часто перевіряти, чи закрилась свічка
STATE_FILE = "bot_state.json"
LOG_FILE = "bot.log"
DRY_RUN = False               # True = лише логувати сигнали, ордери НЕ слати
