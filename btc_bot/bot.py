"""
Торговий бот для Binance Futures (Testnet за замовчуванням).
Запуск: python bot.py

Архітектура:
  - кожна стратегія зі strategies.ACTIVE_STRATEGIES працює незалежно
  - стан позицій зберігається у STATE_FILE (переживає рестарт)
  - діє ТІЛЬКИ по закритій свічці (без зазирання в майбутнє, як у бектесті)

ПОПЕРЕДЖЕННЯ: спершу ганяй на Testnet (USE_TESTNET=True). Реальні гроші — лише
після forward-тесту й перевірки, що результати в межах ~половини бектесту.
"""
import json
import time
import logging
import traceback
from datetime import datetime, timezone

import ccxt
import pandas as pd

import config
from strategies import ACTIVE_STRATEGIES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(config.LOG_FILE), logging.StreamHandler()],
)
log = logging.getLogger("bot")

TF_MS = {"15m": 900_000, "30m": 1_800_000, "1h": 3_600_000,
         "2h": 7_200_000, "4h": 14_400_000, "1d": 86_400_000}


def make_exchange():
    ex = ccxt.binanceusdm({
        "apiKey": config.API_KEY,
        "secret": config.API_SECRET,
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
    })
    if config.USE_TESTNET:
        ex.set_sandbox_mode(True)
    return ex


def load_state():
    try:
        with open(config.STATE_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"positions": {}, "last_candle_ts": {}}


def save_state(state):
    with open(config.STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def get_equity(ex):
    if config.EQUITY_OVERRIDE is not None:
        return float(config.EQUITY_OVERRIDE)
    bal = ex.fetch_balance()
    return float(bal["USDT"]["total"])


def fetch_df(ex, timeframe, limit):
    ohlcv = ex.fetch_ohlcv(config.SYMBOL, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "vol"])
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df


def position_size(equity, risk_pct, entry, stop):
    """Кількість BTC так, щоб втрата на стопі = risk_pct * equity."""
    risk_per_unit = abs(entry - stop)
    if risk_per_unit <= 0:
        return 0.0
    risk_usd = equity * risk_pct
    qty = risk_usd / risk_per_unit
    return qty


def open_position(ex, strat, signal, equity, state):
    df = fetch_df(ex, strat.timeframe, 3)
    entry = float(df["close"].iloc[-1])
    side = signal["side"]
    stop = entry * (1 - signal["stop_pct"]) if side == "long" else entry * (1 + signal["stop_pct"])
    risk_pct = config.RISK_PER_TRADE[strat.name]
    qty = round(position_size(equity, risk_pct, entry, stop), 3)
    if qty <= 0:
        log.warning(f"[{strat.name}] qty=0, пропускаю")
        return
    log.info(f"[{strat.name}] ВХІД {side} qty={qty} @~{entry:.1f} stop={stop:.1f} risk={risk_pct*100:.1f}%")
    if not config.DRY_RUN:
        order_side = "buy" if side == "long" else "sell"
        ex.create_order(config.SYMBOL, "market", order_side, qty)
    state["positions"][strat.name] = {
        "side": side, "entry_price": entry, "stop_price": stop,
        "qty": qty, "bars_held": 0, "opened_at": datetime.now(timezone.utc).isoformat(),
    }


def close_position(ex, strat, state):
    pos = state["positions"].get(strat.name)
    if not pos:
        return
    log.info(f"[{strat.name}] ВИХІД {pos['side']} qty={pos['qty']}")
    if not config.DRY_RUN:
        close_side = "sell" if pos["side"] == "long" else "buy"
        ex.create_order(config.SYMBOL, "market", close_side, pos["qty"], params={"reduceOnly": True})
    del state["positions"][strat.name]


def process_strategy(ex, strat, state):
    """Викликається раз на закриту свічку відповідного таймфрейму."""
    df = fetch_df(ex, strat.timeframe, strat.warmup + 5)
    pos = state["positions"].get(strat.name)

    if pos:
        pos["bars_held"] += 1
        if strat.should_exit(df, pos):
            close_position(ex, strat, state)
    else:
        signal = strat.should_enter(df)
        if signal:
            equity = get_equity(ex)
            open_position(ex, strat, signal, equity, state)
    save_state(state)


def candle_closed(ex, strat, state):
    """True, якщо з'явилась нова закрита свічка для цього таймфрейму."""
    df = fetch_df(ex, strat.timeframe, 2)
    # остання повністю закрита свічка — це передостанній рядок (останній ще формується)
    last_closed_ts = int(df["ts"].iloc[-2])
    prev = state["last_candle_ts"].get(strat.name)
    if prev != last_closed_ts:
        state["last_candle_ts"][strat.name] = last_closed_ts
        return True
    return False


def main():
    ex = make_exchange()
    if config.USE_TESTNET:
        try:
            ex.set_leverage(config.LEVERAGE, config.SYMBOL)
        except Exception as e:
            log.warning(f"set_leverage: {e}")
    state = load_state()
    log.info(f"Старт. Testnet={config.USE_TESTNET} DryRun={config.DRY_RUN} "
             f"Стратегії={[s.name for s in ACTIVE_STRATEGIES]}")

    while True:
        try:
            for strat in ACTIVE_STRATEGIES:
                if candle_closed(ex, strat, state):
                    log.info(f"[{strat.name}] нова свічка {strat.timeframe} — перевірка")
                    process_strategy(ex, strat, state)
            save_state(state)
        except ccxt.NetworkError as e:
            log.warning(f"network: {e}")
        except Exception:
            log.error(traceback.format_exc())
        time.sleep(config.POLL_SECONDS)


if __name__ == "__main__":
    main()
