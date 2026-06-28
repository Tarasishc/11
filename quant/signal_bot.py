"""
Сигнальний бот для KC-breakout стратегії (БЕЗ автоторгівлі — лише алерти в Telegram).
Рахує сигнали на ЗАКРИТТІ 4h-бара і шле повідомлення; заходиш РУКАМИ.

Запуск у СЕБЕ (не в цьому середовищі — тут немає доступу до бірж/Telegram):
    pip install ccxt requests pandas numpy
    # 1) Створи бота в Telegram через @BotFather -> отримай TOKEN
    # 2) Дізнайся свій CHAT_ID: напиши боту, потім відкрий
    #    https://api.telegram.org/bot<TOKEN>/getUpdates -> поле "chat":{"id":...}
    # 3) Впиши TOKEN/CHAT_ID нижче і запусти:
    python signal_bot.py            # робочий режим (цикл, чекає 4h-закриття)
    python signal_bot.py once       # одна перевірка зараз і вихід
    python signal_bot.py selftest   # перевірка логіки на локальних CSV (без мережі)

Стратегія (точно як у дослідженні, §18): 4h. LONG: close>верх Keltner & close>EMA200 & ADX>20.
SHORT: дзеркально. Стоп 2*ATR(14), тейк 4*ATR(14) (RR 1:2).
"""
import sys, json, time, os
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd

# ============================== КОНФІГ ==============================
TG_TOKEN   = "PUT_YOUR_BOT_TOKEN_HERE"
TG_CHAT_ID = "PUT_YOUR_CHAT_ID_HERE"
EXCHANGE   = "bybit"                       # або "binance"
SYMBOLS    = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]  # perp; для споту прибери :USDT
TIMEFRAME  = "4h"
ADX_MIN    = 20
KC_EMA, KC_ATR, KC_MULT = 20, 10, 2.0     # Keltner: EMA20 +/- 2*ATR10
TREND_EMA  = 200
ATR_STOP   = 14
STOP_MULT  = 2.0
RR         = 2.0
ACCOUNT    = 1000.0                        # розмір депозиту ($) для підказки розміру
RISK_PCT   = 0.02                          # ризик на угоду (2% — рекоменд., §15)
SESSION_FILTER = False                     # True = слати лише входи 00-12 UTC (опц., §10)
STATE_FILE = "signal_bot_state.json"
DRY_RUN    = False                         # True = друкувати замість надсилати
# ===================================================================


# ---------- індикатори (точно як engine.py) ----------
def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def _tr(df):
    pc = df["close"].shift(1)
    return pd.concat([df["high"]-df["low"], (df["high"]-pc).abs(), (df["low"]-pc).abs()], axis=1).max(axis=1)
def atr(df, n): return _tr(df).ewm(alpha=1/n, adjust=False).mean()
def adx(df, n=14):
    up = df["high"].diff(); dn = -df["low"].diff()
    plus_dm = ((up > dn) & (up > 0)) * up
    minus_dm = ((dn > up) & (dn > 0)) * dn
    a = _tr(df).ewm(alpha=1/n, adjust=False).mean()
    pdi = 100*plus_dm.ewm(alpha=1/n, adjust=False).mean()/a
    mdi = 100*minus_dm.ewm(alpha=1/n, adjust=False).mean()/a
    dx = 100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean()


def check_signal(df):
    """df = закриті 4h-бари (останній рядок = останній ЗАКРИТИЙ бар).
    Повертає dict сигналу або None."""
    if len(df) < TREND_EMA + 30:
        return None
    c = df["close"]
    mid = ema(c, KC_EMA); band = KC_MULT*atr(df, KC_ATR)
    upper, lower = mid+band, mid-band
    trend = ema(c, TREND_EMA)
    ax = adx(df, 14); a_stop = atr(df, ATR_STOP)
    i = -1  # останній закритий бар
    px = c.iloc[i]; ad = ax.iloc[i]; sd = a_stop.iloc[i]*STOP_MULT
    if not np.isfinite(ad) or ad < ADX_MIN or sd <= 0:
        return None
    def is_long(k): return c.iloc[k] > upper.iloc[k] and c.iloc[k] > trend.iloc[k] and ax.iloc[k] > ADX_MIN
    def is_short(k): return c.iloc[k] < lower.iloc[k] and c.iloc[k] < trend.iloc[k] and ax.iloc[k] > ADX_MIN
    side = None
    # лише СВІЖИЙ пробій (на попередньому барі сигналу цього боку не було) — не спамити, поки в позиції
    if is_long(-1) and not is_long(-2):
        side = "LONG"
    elif is_short(-1) and not is_short(-2):
        side = "SHORT"
    if side is None:
        return None
    if SESSION_FILTER:
        # година ВХОДУ = година наступного бара = година_цього_бара+4
        entry_hour = (df.index[i].hour + 4) % 24
        if entry_hour not in (0, 4, 8):
            return None
    if side == "LONG":
        stop = px - sd; target = px + RR*sd
    else:
        stop = px + sd; target = px - RR*sd
    qty = (ACCOUNT*RISK_PCT)/sd
    return dict(side=side, bar_time=df.index[i], price=px, stop=stop, target=target,
                adx=ad, atr=a_stop.iloc[i], stop_dist=sd, qty=qty, notional=qty*px)


# ---------- Telegram ----------
def send_tg(text):
    if DRY_RUN or TG_TOKEN.startswith("PUT_"):
        print("[DRY/НЕ НАЛАШТОВАНО] " + text.replace("\n", " | ")); return
    import requests
    for _ in range(3):
        try:
            r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                              data={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=15)
            if r.status_code == 200: return
        except Exception as e:
            print("TG error:", e); time.sleep(3)


def fmt(sym, s):
    emoji = "🟢" if s["side"] == "LONG" else "🔴"
    return (f"{emoji} <b>{s['side']} {sym}</b>  (4h)\n"
            f"Сигнал-бар: {s['bar_time']:%Y-%m-%d %H:%M} UTC\n"
            f"Вхід (≈ринок зараз): <b>{s['price']:.4f}</b>\n"
            f"Стоп: <b>{s['stop']:.4f}</b>  (2·ATR={s['stop_dist']:.4f})\n"
            f"Тейк: <b>{s['target']:.4f}</b>  (RR 1:{RR:.0f})\n"
            f"ADX={s['adx']:.0f}\n"
            f"Розмір під {RISK_PCT*100:.0f}% ризику (депо ${ACCOUNT:.0f}): "
            f"{s['qty']:.4f} (ноціонал ≈${s['notional']:.0f})\n"
            f"➡️ Заходь marketable-limit; одразу постав OCO (стоп+тейк).")


# ---------- стан (де-дублікація) ----------
def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {}
def save_state(st): json.dump(st, open(STATE_FILE, "w"))


# ---------- дані (ccxt) ----------
def fetch(ex, sym):
    o = ex.fetch_ohlcv(sym, TIMEFRAME, limit=TREND_EMA+60)
    df = pd.DataFrame(o, columns=["ts", "open", "high", "low", "close", "vol"])
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.set_index("dt")
    # відкинути НЕЗАКРИТИЙ останній бар
    tf_ms = ex.parse_timeframe(TIMEFRAME)*1000
    now_ms = ex.milliseconds()
    if df["ts"].iloc[-1] + tf_ms > now_ms:
        df = df.iloc[:-1]
    return df[["open", "high", "low", "close", "vol"]]


def run_once(ex, st):
    for sym in SYMBOLS:
        try:
            df = fetch(ex, sym)
            sig = check_signal(df)
            if sig:
                key = sym
                bar_id = sig["bar_time"].isoformat()
                if st.get(key) == bar_id:
                    continue   # вже алертили цей бар
                send_tg(fmt(sym, sig))
                st[key] = bar_id
            print(f"{datetime.now(timezone.utc):%H:%M} {sym}: {'СИГНАЛ '+sig['side'] if sig else 'нема'}")
        except Exception as e:
            print(f"{sym} помилка: {e}")
    save_state(st)


def next_4h_wakeup():
    now = datetime.now(timezone.utc)
    h = (now.hour // 4 + 1)*4
    nxt = now.replace(minute=1, second=30, microsecond=0, hour=0) + timedelta(hours=h)
    return (nxt - now).total_seconds()


def selftest():
    """Перевірка логіки на локальних CSV (без мережі): скільки сигналів в історії."""
    import glob
    print("SELF-TEST на локальних CSV (логіка сигналів):")
    for sym, path in [("BTC", "quant/data/btc_15m.csv"), ("ETH", "quant/data/eth_4h.csv"),
                      ("SOL", "quant/data/sol_4h.csv")]:
        if not os.path.exists(path): continue
        raw = pd.read_csv(path)
        raw.columns = [x.strip().lower() for x in raw.columns]
        tcol = "ts" if "ts" in raw.columns else "time"
        if tcol == "ts":
            raw["dt"] = pd.to_datetime(raw["ts"], unit="ms", utc=True)
        else:
            raw["dt"] = pd.to_datetime(raw["time"].astype(str).str.strip('"'), utc=True)
        df = raw.set_index("dt")[["open", "high", "low", "close"]].astype(float)
        if (df.index[1]-df.index[0]) < pd.Timedelta(hours=4):
            df = df.resample("4h").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()
        # векторно: свіжі пробої (сигнал зараз, але не на попередньому барі)
        c = df["close"]; mid = ema(c, KC_EMA); band = KC_MULT*atr(df, KC_ATR)
        tr = ema(c, TREND_EMA); ax = adx(df, 14)
        L = (c > mid+band) & (c > tr) & (ax > ADX_MIN)
        S = (c < mid-band) & (c < tr) & (ax > ADX_MIN)
        freshL = L & ~L.shift(1, fill_value=False); freshS = S & ~S.shift(1, fill_value=False)
        last = df.index[(freshL | freshS)][-1] if (freshL | freshS).any() else None
        print(f"  {sym}: свіжих LONG={int(freshL.sum())} SHORT={int(freshS.sum())} | останній: {last}")
    print("OK — логіка працює (свіжі пробої ~ к-сть угод у бектесті).")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "loop"
    if mode == "selftest":
        selftest(); sys.exit()
    import ccxt
    ex = getattr(ccxt, EXCHANGE)({"enableRateLimit": True})
    st = load_state()
    if mode == "once":
        run_once(ex, st); sys.exit()
    send_tg("✅ Сигнальний бот запущено. Стежу за " + ", ".join(SYMBOLS) + f" ({TIMEFRAME}).")
    while True:
        run_once(ex, st)
        slp = max(next_4h_wakeup(), 60)
        print(f"Сплю {slp/60:.0f} хв до наступного 4h-закриття...")
        time.sleep(slp)
