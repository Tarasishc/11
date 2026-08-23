"""
АВТОМАТИЧНИЙ ТОРГОВИЙ БОТ — стратегія KC+FVG (Binance USDⓈ-M), з щоденним звітом у Telegram.

ПРАВИЛА (конфіг за 15m-істиною, скрипти 73-79):
  • Монети/двигуни: ETH, SOL = KC+FVG  (BTC слабший, BNB без еджу — прибрані)
  • ТФ 4h, дії ЛИШЕ на закритих барах (non-repaint)
  • Одна позиція на монету (бо два шорти на біржі зливаються)
  • KC: пробій каналу Кельтнера в бік EMA200 + ADX≥20 -> вхід МАРКЕТОМ
  • FVG-ПАКЕТ (mid50+wait>2+ADX20): 3-барний імбаланс у бік EMA200 ->
    лімітка на 50% ЗОНИ; озброюється лише з 3-го бару після формування
    (ретест у перші 2 бари = сетап згорів); філ приймається лише при
    тренді і ADX≥20 (лімітка знімається, поки умови погані)
  • Стоп = STOP-MARKET (гарантований вихід), Тейк = LIMIT (мейкер), RR 1:2
  • Розмір від РИЗИКУ: qty = equity*RISK_PCT / |entry-stop|   (плече саме виходить безпечним)

БЕЗПЕКА (за замовчуванням НІЧОГО реального не робить):
  • DRY_RUN=1  -> паперова торгівля (ніяких реальних ордерів)
  • TESTNET=1  -> якщо вимкнеш DRY_RUN, торгує на Binance Demo Trading (testnet
                 ф'ючерсів). Реальні ордери на демо-балансі + сигнали в TG.
  • Kill-switch: денний збиток > MAX_DAILY_LOSS -> зупинка + алерт
  • Реальні гроші тільки коли DRY_RUN=0 і TESTNET=0 і явно задані ключі.

РЕЖИМИ:
  python trade_bot.py run       # основний цикл (перевіряє закриття 4h-барів)
  python trade_bot.py once      # один прохід
  python trade_bot.py report    # надіслати щоденний звіт зараз
  python trade_bot.py balance   # діагностика: показати баланс і куди йдуть запити
  python trade_bot.py close SOL/USDT   # закрити позицію+ордери по монеті (або: close all)
  python trade_bot.py protect ETH/USDT 1686 1853   # почепити стоп/тейк на живу позицію
  python trade_bot.py preflight # перевірка контракту з біржею (після кожного git pull!)
  python trade_bot.py scan      # ЧОМУ мало сигналів: жива картина ADX/EMA/detect/слот по монетах
  python trade_bot.py selftest  # офлайн-перевірка логіки на локальних CSV (без біржі)

ЗМІННІ ОТОЧЕННЯ:
  BINANCE_KEY, BINANCE_SECRET, TG_TOKEN, TG_CHAT_ID
  BOT_DRY_RUN(=1), BOT_TESTNET(=1), BOT_RISK(=0.01), BOT_MAX_DAILY_LOSS(=0.10)
"""
import os, sys, json, time, math, datetime as dt
import numpy as np, pandas as pd
try:
    import ccxt
except Exception:
    ccxt = None
try:
    import urllib.request, urllib.parse
except Exception:
    pass

def _utcnow():                                   # naive UTC (без DeprecationWarning від utcnow)
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

def _load_dotenv():
    """Автозавантаження bot.env (рядки KEY=VAL) у os.environ, якщо змінної ще нема.
    Щоб ручні запуски (scan/journal/preflight) бачили ключі БЕЗ 'source bot.env'
    (веб-консоль VPS калічить таку команду). Змінні від systemd мають пріоритет."""
    here = os.path.dirname(os.path.abspath(__file__))
    for path in ("bot.env", os.path.join(here, "bot.env"), os.path.join(here, "..", "bot.env")):
        if not os.path.exists(path): continue
        try:
            for line in open(path):
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line: continue
                k, v = line.split("=", 1); k = k.strip(); v = v.strip().strip('"').strip("'")
                if k and k not in os.environ: os.environ[k] = v
        except Exception as e:
            print("bot.env не прочитано:", e)
        break
_load_dotenv()

# ----------------------------- КОНФІГ ---------------------------------------
DRY_RUN     = os.getenv("BOT_DRY_RUN", "1") == "1"
TESTNET     = os.getenv("BOT_TESTNET", "1") == "1"
API_KEY     = os.getenv("BINANCE_KEY", "")
API_SECRET  = os.getenv("BINANCE_SECRET", "")
TG_TOKEN    = os.getenv("TG_TOKEN", "")
TG_CHAT     = os.getenv("TG_CHAT_ID", "")
RISK_PCT    = float(os.getenv("BOT_RISK", "0.01"))
MAX_DAILY_LOSS = float(os.getenv("BOT_MAX_DAILY_LOSS", "0.10"))
# реалізм для ПАПЕРУ (щоб не брехав): комісія/сторону, слип входу, ДОДАТКОВИЙ слип стопа
FEE_RATE   = float(os.getenv("BOT_FEE", "0.0004"))
ENTRY_SLIP = float(os.getenv("BOT_ENTRY_SLIP", "0.0004"))
STOP_SLIP  = float(os.getenv("BOT_STOP_SLIP", "0.0010"))
START_EQUITY = float(os.getenv("BOT_PAPER_EQUITY", "1000"))   # стартовий депозит для DRY_RUN
TF          = "4h"
RR          = 2.0
LEV_CAP     = 5.0
REPORT_HOUR_UTC = int(os.getenv("BOT_REPORT_HOUR", "8"))      # година UTC для звіту
NOTIFY_TRADES = os.getenv("BOT_NOTIFY_TRADES", "1") == "1"    # 1=слати кожну угоду (вхід/вихід)
SIGNALS_ONLY  = os.getenv("BOT_SIGNALS_ONLY", "0") == "1"     # 1=ЛИШЕ 📥вхід/✅❌вихід (ручна торгівля)
STATE_FILE  = os.getenv("BOT_STATE", "bot_state.json")

# монета -> які двигуни; ccxt-символ Binance USDM
# (15m-істина: BTC найслабший з трійки, BNB без еджу -> торгуємо ETH+SOL)
COINS = {
    "ETH/USDT": ["KC", "FVG"],
    "SOL/USDT": ["KC", "FVG"],
}
FVG_WAIT = 2                          # анти-миттєвий-ретест: перші 2 бари = згорів
# параметри індикаторів (1-в-1 з бектестом)
EMA_TREND, KC_EMA, KC_ATR, KC_MULT = 200, 20, 10, 2.0
ADX_LEN, ADX_MIN, STOP_ATR, KC_STOP_X = 14, 20, 14, 2.0
FVG_FLOOR, FVG_EXPIRY = 0.5, 20      # стоп-флор у ATR; скільки барів чекати ретест

# ----------------------------- ІНДИКАТОРИ (Wilder) --------------------------
def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def _rma(s, n): return s.ewm(alpha=1/n, adjust=False).mean()
def atr(df, n):
    h, l, c = df["high"], df["low"], df["close"]; pc = c.shift()
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return _rma(tr, n)
def adx(df, n=14):
    h, l = df["high"], df["low"]; up = h.diff(); dn = -l.diff()
    pdm = ((up > dn) & (up > 0)) * up; mdm = ((dn > up) & (dn > 0)) * dn
    a = atr(df, n)
    pdi = 100 * _rma(pdm, n) / a; mdi = 100 * _rma(mdm, n) / a
    return (100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)).pipe(_rma, n)

# ----------------------------- СИГНАЛИ (на ОСТАННЬОМУ ЗАКРИТОМУ барі) --------
def detect(df, engines):
    """df = лише ЗАКРИТІ бари. Повертає список кандидатів на вхід для цього бару."""
    c = df["close"]; i = len(df) - 1
    if i < EMA_TREND + 5: return []
    mid = ema(c, KC_EMA); band = KC_MULT * atr(df, KC_ATR)
    up, lo = mid + band, mid - band
    trend = ema(c, EMA_TREND); ax = adx(df, ADX_LEN); a14 = atr(df, STOP_ATR)
    out = []
    px = lambda s, k: s.iloc[k]
    axv = float(px(ax, i)) if np.isfinite(px(ax, i)) else None   # ADX на сигнальному барі (форвард-лог)
    # --- KC: свіжий пробій у бік тренду + ADX ---
    if "KC" in engines and np.isfinite(px(ax, i)):
        def kc_state(k, side):
            if side > 0: return px(c, k) > px(up, k) and px(c, k) > px(trend, k) and px(ax, k) >= ADX_MIN
            return px(c, k) < px(lo, k) and px(c, k) < px(trend, k) and px(ax, k) >= ADX_MIN
        D = KC_STOP_X * px(a14, i); entry = px(c, i)   # вхід ≈ ціна закриття (далі маркет на відкритті)
        if kc_state(i, +1) and not kc_state(i - 1, +1):
            out.append(dict(engine="KC", side="long", typ="market",
                            entry=entry, stop=entry - D, target=entry + RR * D, adx=axv))
        if kc_state(i, -1) and not kc_state(i - 1, -1):
            out.append(dict(engine="KC", side="short", typ="market",
                            entry=entry, stop=entry + D, target=entry - RR * D, adx=axv))
    # --- FVG-пакет: новий 3-барний імбаланс у бік тренду -> ОЗБРОЄННЯ (watch) ---
    #     Лімітка на 50% зони; стоп/тейк/розмір рахуються при озброєнні (через 2 бари).
    if "FVG" in engines and np.isfinite(px(a14, i)):
        if px(df["high"], i - 2) < px(df["low"], i) and px(c, i) > px(trend, i):
            zt, zb = px(df["low"], i), px(df["high"], i - 2)
            out.append(dict(engine="FVG", side="long", typ="arm",
                            entry=(zt + zb) / 2, zb=zb, adx=axv))
        if px(df["low"], i - 2) > px(df["high"], i) and px(c, i) < px(trend, i):
            zt, zb = px(df["high"], i), px(df["low"], i - 2)
            out.append(dict(engine="FVG", side="short", typ="arm",
                            entry=(zt + zb) / 2, zb=zb, adx=axv))
    return out

def fvg_conditions_ok(df, side):
    """Умови філа FVG на останньому ЗАКРИТОМУ барі: тренд EMA200 + ADX>=20 (як у KC)."""
    c = df["close"]; i = len(df) - 1
    tr = ema(c, EMA_TREND).iloc[i]; ax = adx(df, ADX_LEN).iloc[i]
    tok = c.iloc[i] > tr if side == "long" else c.iloc[i] < tr
    return bool(tok and np.isfinite(ax) and ax >= ADX_MIN)

# ----------------------------- TELEGRAM -------------------------------------
def tg(msg):
    print("[TG]", msg.replace("\n", " | ")[:300])
    if not (TG_TOKEN and TG_CHAT): return
    for cid in str(TG_CHAT).split(","):          # кілька чатів через кому (особистий, група, канал)
        cid = cid.strip()
        if not cid: continue
        try:
            data = urllib.parse.urlencode({"chat_id": cid, "text": msg,
                                           "parse_mode": "HTML"}).encode()
            urllib.request.urlopen(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                                   data=data, timeout=15)
        except Exception as e:
            print(f"  TG помилка ({cid}):", e)

def note(msg):
    """Проміжні/службові повідомлення (зона, озброєння, згоріло, захист) —
    глушаться в режимі SIGNALS_ONLY, щоб лишались ЛИШЕ вхід/вихід."""
    if not SIGNALS_ONLY: tg(msg)

# ----------------------------- СТАН -----------------------------------------
def load_state():
    if os.path.exists(STATE_FILE):
        st = json.load(open(STATE_FILE))
        # міграція: старі FVG-слоти (лімітка на краю зони, без 'zb') несумісні з пакетом ->
        # знімаємо; їхні ордери на біржі прибере reconcile (список _stale). Відкритих позицій не чіпаємо.
        stale = []
        for sym in list(st.get("pos", {}).keys()):
            p = st["pos"][sym]
            old_fvg = p.get("engine") == "FVG" and p.get("status") in ("watch", "pending") and "zb" not in p
            not_traded = sym not in COINS         # монета з минулої епохи (BNB, BTC) -> прибрати слот
            if old_fvg or not_traded:
                st["pos"].pop(sym); stale.append(sym)
        if stale: st["_stale"] = sorted(set(st.get("_stale", []) + stale))
        return st
    return {"equity": START_EQUITY, "day": "", "day_start_equity": START_EQUITY,
            "halted": False, "pos": {}, "last_bar": {}, "trades": []}
def save_state(s): json.dump(s, open(STATE_FILE, "w"), indent=1, default=str)

# ----------------------------- БІРЖА ----------------------------------------
def make_exchange():
    if ccxt is None: raise RuntimeError("немає ccxt: pip install ccxt")
    # У DRY (папір) ключі не потрібні — і НЕ шлемо їх, щоб на мейннеті публічні дані
    # (klines) тягнулись чисто: інакше ccxt додає X-MBX-APIKEY і мейннет відхиляє
    # testnet-ключ навіть на публічних викликах (-2008). Папір по реальному ринку.
    key = "" if DRY_RUN else API_KEY
    sec = "" if DRY_RUN else API_SECRET
    ex = ccxt.binanceusdm({"apiKey": key, "secret": sec, "enableRateLimit": True})
    if TESTNET:
        # Binance Demo Trading (ф'ючерсний testnet). set_sandbox_mode наводить
        # URL на testnet.binancefuture.com. Новий ccxt ДОДАТКОВО блокує ф'ючерсне
        # демо в sign() (raise NotSupported), доки не ввімкнути офіційний прапорець
        # disableFuturesSandboxWarning — це «кнопка згоди»: демо працює нормально.
        try:
            ex.set_sandbox_mode(True)
        except Exception:                                    # старі/інші версії ccxt
            ex.urls["api"] = ex.deep_extend(ex.urls["api"], ex.urls["test"])
        ex.options["disableFuturesSandboxWarning"] = True
    return ex

def fetch_closed(ex, symbol, limit=320):
    o = ex.fetch_ohlcv(M(symbol), TF, limit=limit)
    df = pd.DataFrame(o, columns=["ts", "open", "high", "low", "close", "vol"])
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df.iloc[:-1].reset_index(drop=True)        # ДРОП незакритого бара

def equity_now(ex, st):
    if DRY_RUN: return st["equity"]
    try: return float(ex.fetch_balance()["USDT"]["total"])
    except Exception as e:
        print("equity_now: fetch_balance не вдалось ->", repr(e))  # у журнал, не мовчки
        return st["equity"]

# ----------------------------- РОЗМІР ПОЗИЦІЇ -------------------------------
def position_qty(equity, entry, stop):
    risk_usd = equity * RISK_PCT
    dist = abs(entry - stop)
    if dist <= 0: return 0.0
    qty = risk_usd / dist
    if entry * qty > equity * LEV_CAP:           # ліміт плеча
        qty = equity * LEV_CAP / entry
    return qty

# ----------------------------- ПРОДАКШН-ХЕЛПЕРИ -----------------------------
# запасні мінімуми (USDT нотіонал, base qty) — якщо немає доступу до load_markets
MIN_FALLBACK = {
    "BTC/USDT": dict(min_cost=50, min_amt=0.001),
    "ETH/USDT": dict(min_cost=20, min_amt=0.001),
    "SOL/USDT": dict(min_cost=5,  min_amt=0.01),
    "BNB/USDT": dict(min_cost=5,  min_amt=0.001),
}
_MARKETS_OK = False
SYM_MAP = {}                                     # 'ETH/USDT' -> реальний ccxt-символ ('ETH/USDT:USDT')
_ALL_MARKETS = set()                             # усі символи ринків (для лінивої резолюції БУДЬ-ЯКОЇ монети)

def _norm(s):
    """нормалізація символу перпа: 'ETH/USDT:USDT' -> 'ETH/USDT' (для порівнянь)."""
    return (s or "").split(":")[0]

def M(symbol):
    """символ для API-викликів ccxt (нові версії кличуть перпи 'X/USDT:USDT').
    Резолвить БУДЬ-ЯКУ монету (не лише зі списку) -> старі слоти не мапляться на голий символ."""
    if symbol in SYM_MAP: return SYM_MAP[symbol]
    if ":" not in symbol and (symbol + ":USDT") in _ALL_MARKETS:
        SYM_MAP[symbol] = symbol + ":USDT"; return SYM_MAP[symbol]
    return symbol

def with_retry(fn, *a, tries=4, **k):
    for i in range(tries):
        try:
            return fn(*a, **k)
        except Exception:
            if i == tries - 1: raise
            time.sleep(2 ** i)

def load_markets_safe(ex):
    global _MARKETS_OK, _ALL_MARKETS
    try:
        ex.load_markets(); _MARKETS_OK = True
        _ALL_MARKETS = set(ex.markets)
        for s in COINS:                          # резолв реальних символів перпів
            for cand in (s, s + ":USDT"):
                if cand in ex.markets: SYM_MAP[s] = cand; break
        print("  символи:", SYM_MAP or "як є")
    except Exception as e:
        print("  load_markets не вдалось (офлайн?) — запасні мінімуми:", e)

def limits_for(ex, symbol):
    if _MARKETS_OK:
        try:
            lim = ex.market(M(symbol)).get("limits", {})
            mc = (lim.get("cost", {}) or {}).get("min")
            ma = (lim.get("amount", {}) or {}).get("min")
            if mc or ma:
                return mc or MIN_FALLBACK[symbol]["min_cost"], ma or MIN_FALLBACK[symbol]["min_amt"]
        except Exception:
            pass
    f = MIN_FALLBACK.get(symbol, dict(min_cost=5, min_amt=0))
    return f["min_cost"], f["min_amt"]

def valid_size(ex, symbol, qty, price):
    """Округлення + перевірка мінімумів біржі. None -> угоду ПРОПУСКАЄМО (НЕ оверризик!)."""
    min_cost, min_amt = limits_for(ex, symbol)
    try:
        qty = float(ex.amount_to_precision(M(symbol), qty)) if _MARKETS_OK else round(qty, 6)
    except Exception:
        qty = round(qty, 6)
    if qty < (min_amt or 0): return None
    if price * qty < (min_cost or 0): return None
    return qty

def reconcile(ex, st):
    """Старт у live: синхронізуємо стан із реальними відкритими позиціями."""
    if DRY_RUN: return
    try:
        for p in with_retry(ex.fetch_positions) or []:
            amt = float(p.get("contracts") or (p.get("info", {}) or {}).get("positionAmt") or 0)
            sym = _norm(p.get("symbol"))                 # 'ETH/USDT:USDT' -> 'ETH/USDT'
            if abs(amt) > 0 and sym in COINS and sym not in st["pos"]:
                st["pos"][sym] = dict(status="live", side="long" if amt > 0 else "short",
                                      engine="?", entry=float(p.get("entryPrice") or 0),
                                      stop=None, target=None, qty=abs(amt))
        for sym in COINS:                            # прибрати ОРФАНИ: ордери по монеті без відстеж. позиції
            if sym not in st["pos"]:
                cancel_symbol_orders(ex, sym)
        for sym in st.pop("_stale", []):             # монети з минулих епох: зняти ордери І закрити позицію
            if sym in st["pos"]: continue
            cancel_symbol_orders(ex, sym)
            signed = live_pos_signed(ex, sym)
            if signed != 0:
                try:
                    side = "sell" if signed > 0 else "buy"
                    q = float(ex.amount_to_precision(M(sym), abs(signed)))
                    ex.create_order(M(sym), "market", side, q, None, {"reduceOnly": True})
                    note(f"🧹 Прибрано залишок минулої епохи: {sym} закрито ({q}), ордери знято")
                except Exception as e:
                    print("stale close", sym, e)
        note(f"♻️ Reconcile: відкритих позицій на біржі {sum(1 for s in COINS if s in st['pos'])}")
    except Exception as e:
        print("reconcile помилка:", e)

# ----------------------------- ВИКОНАННЯ (live) -----------------------------
def place_protective(ex, symbol, side, qty, stop, target, have=None):
    """reduceOnly-захист: стоп (STOP_MARKET) + тейк (LIMIT). Ставить ЛИШЕ відсутні ноги
    (have = вже наявні ids). Кликати коли позиція існує — інакше Binance -2022."""
    have = have or {}
    opp = "sell" if side == "long" else "buy"
    ms = M(symbol)
    q = float(ex.amount_to_precision(ms, qty))
    ids = {}
    if not have.get("stop"):
        sp = float(ex.price_to_precision(ms, stop))
        ids["stop"] = ex.create_order(ms, "STOP_MARKET", opp, q, None,
                                      {"stopPrice": sp, "reduceOnly": True}).get("id")
    if not have.get("tp"):
        tp = float(ex.price_to_precision(ms, target))
        ids["tp"] = ex.create_order(ms, "limit", opp, q, tp, {"reduceOnly": True}).get("id")
    return ids

def place_live(ex, symbol, cand, qty):
    side = "buy" if cand["side"] == "long" else "sell"
    ms = M(symbol)
    try: ex.set_margin_mode("isolated", ms)
    except Exception: pass
    try: ex.set_leverage(int(LEV_CAP), ms)
    except Exception: pass
    q = float(ex.amount_to_precision(ms, qty)); ids = {}
    if cand["typ"] == "market":                          # KC: позиція з'являється ОДРАЗУ
        ids["entry"] = ex.create_order(ms, "market", side, q).get("id")
        try:                                             # захист одразу; недоставлене доставить poll_live
            ids.update(place_protective(ex, symbol, cand["side"], q, cand["stop"], cand["target"], have=ids))
        except Exception as e:
            print("protective(market) відкладено до poll_live:", e)
    else:                                                # FVG: пост-онлі лімітка, позиції ЩЕ НЕМА
        p = float(ex.price_to_precision(ms, cand["entry"]))
        ids["entry"] = ex.create_order(ms, "limit", side, q, p, {"timeInForce": "GTX"}).get("id")
        # reduceOnly без позиції -> -2022, тож стоп/тейк ставить poll_live КОЛИ лімітка зайде
    return ids

# ---- опитування реальних позицій (testnet/live): філи, закриття, скасування ----
def live_pos_amt(ex, symbol):
    """|позиція| по монеті. None = НЕ ВДАЛОСЬ дізнатись (не плутати з 0!)."""
    try:
        try: rows = with_retry(ex.fetch_positions, [M(symbol)])
        except Exception: rows = with_retry(ex.fetch_positions)      # fallback: всі позиції
        for pos in rows or []:
            if _norm(pos.get("symbol")) == symbol:
                return abs(float(pos.get("contracts") or (pos.get("info", {}) or {}).get("positionAmt") or 0))
        return 0.0
    except Exception as e:
        print("pos", symbol, e)
        return None

def open_order_ids(ex, symbol):
    """множина id відкритих ордерів по монеті. None = не вдалось дізнатись."""
    try:
        return {o["id"] for o in with_retry(ex.fetch_open_orders, M(symbol))}
    except Exception as e:
        print("orders", symbol, e)
        return None

def cancel_symbol_orders(ex, symbol):
    ids = open_order_ids(ex, symbol)
    for oid in ids or []:
        try: ex.cancel_order(oid, M(symbol))
        except Exception: pass

def ensure_protective(ex, symbol, p, amt):
    """Захист позиції за ФАКТИЧНИМ станом біржі (не за збереженими id):
    reduceOnly STOP_MARKET = нога стопа, reduceOnly LIMIT = нога тейка.
    Наявні ноги приймаємо, ДУБЛІКАТИ знімаємо, відсутнє ставимо. TG — раз на позицію."""
    if p.get("stop") is None or p.get("target") is None: return     # reconcile-позиція без рівнів
    try:
        orders = with_retry(ex.fetch_open_orders, M(symbol))
    except Exception as e:
        print("orders", symbol, e); return          # стан невідомий -> нічого не робимо (без спаму)
    def is_ro(o):
        v = o.get("reduceOnly")
        if v is None: v = (o.get("info", {}) or {}).get("reduceOnly")
        return v in (True, "true", "True")
    def has_trigger(o):
        """ccxt уніфікує STOP_MARKET у type='market' -> розпізнаємо ногу стопа за
        НАЯВНІСТЮ тригер-ціни, а не за назвою типу."""
        for v in (o.get("stopPrice"), o.get("triggerPrice"), (o.get("info", {}) or {}).get("stopPrice")):
            try:
                if v not in (None, "") and float(v) > 0: return True
            except (TypeError, ValueError):
                pass
        return False
    ro = [o for o in orders if is_ro(o)]
    stops = [o for o in ro if has_trigger(o)]
    tps = [o for o in ro if not has_trigger(o)]
    ids = p.setdefault("ids", {})
    # ЗАПОБІЖНИК: reduceOnly-ордерів явно забагато -> зносимо ВСІ і ставимо свіжу пару.
    # (обмежує наслідки будь-якого майбутнього сюрпризу в форматі відповіді біржі)
    if len(ro) > 4:
        print(f"protective {symbol}: {len(ro)} reduceOnly ордерів! зразок:",
              {k: (ro[0].get(k)) for k in ("id", "type", "stopPrice", "triggerPrice", "reduceOnly")},
              "info:", (ro[0].get("info", {}) or {}))
        for o in ro:
            try: ex.cancel_order(o["id"], M(symbol))
            except Exception: pass
        stops = []; tps = []; ids.pop("stop", None); ids.pop("tp", None)
        if not p.get("prot_purge_note"):
            note(f"🧯 {symbol}: знесено {len(ro)} дублікатів захисту, ставлю чисту пару стоп+тейк")
            p["prot_purge_note"] = True
    for extra in stops[1:] + tps[1:]:                # дублікати від старих циклів -> геть
        try: ex.cancel_order(extra["id"], M(symbol))
        except Exception: pass
    if stops: ids["stop"] = stops[0]["id"]
    if tps: ids["tp"] = tps[0]["id"]
    missing = {}
    if not stops: missing["stop"] = True
    if not tps: missing["tp"] = True
    if not missing:                                  # обидві ноги на місці -> повне відновлення
        for k in ("prot_tries", "prot_gaveup", "prot_warn"): p.pop(k, None)
        return
    if p.get("prot_tries", 0) >= 3:                  # 3 невдалі доставки -> стоп, не спамимо ордерами
        if not p.get("prot_gaveup"):
            note(f"‼️ {symbol}: захист не тримається після 3 спроб — постав руками стоп "
                 f"{p['stop']:.4f} / тейк {p['target']:.4f} і кинь скрін")
            p["prot_gaveup"] = True
        return
    try:
        p["prot_tries"] = p.get("prot_tries", 0) + 1
        have = {k: ids.get(k) for k in ("stop", "tp") if not missing.get(k)}
        prot = place_protective(ex, symbol, p["side"], amt, p["stop"], p["target"],
                                have={k: True for k in have})
        for k, v in (prot or {}).items(): ids[k] = v
        if prot and not p.get("prot_note") and NOTIFY_TRADES:
            legs = "+стоп" * ("stop" in prot) + "+тейк" * ("tp" in prot)
            note(f"🛡 Доставлено захист {symbol}: {legs}")
            p["prot_note"] = True                    # один раз на позицію, без спаму
    except Exception as e:
        print("protective", symbol, e)
        if not p.get("prot_warn"):
            note(f"⚠️ не вдалось поставити захист {symbol}: {e}")
            p["prot_warn"] = True

def live_pos_signed(ex, symbol):
    """Позиція зі знаком (+лонг/-шорт), 0 якщо нема."""
    try:
        try: rows = with_retry(ex.fetch_positions, [M(symbol)])
        except Exception: rows = with_retry(ex.fetch_positions)
        for pos in rows or []:
            if _norm(pos.get("symbol")) == symbol:
                raw = (pos.get("info", {}) or {}).get("positionAmt")
                if raw is not None: return float(raw)
                amt = abs(float(pos.get("contracts") or 0))
                return -amt if pos.get("side") == "short" else amt
    except Exception as e:
        print("pos_signed", symbol, e)
    return 0.0

def close_command(ex, st, target):
    """Ручне закриття через бота: скасувати ордери + закрити позицію маркетом (reduceOnly)."""
    syms = [target] if target != "all" else sorted(set(list(st["pos"].keys()) + list(COINS.keys())))
    for sym in syms:
        if DRY_RUN:
            if st["pos"].pop(sym, None): tg(f"🧹 [DRY] Слот {sym} очищено вручну")
            continue
        cancel_symbol_orders(ex, sym)
        amt = live_pos_signed(ex, sym)
        if amt != 0:
            side = "sell" if amt > 0 else "buy"
            q = float(ex.amount_to_precision(M(sym), abs(amt)))
            try:
                ex.create_order(M(sym), "market", side, q, None, {"reduceOnly": True})
                tg(f"🧹 Закрито вручну через бота: {sym} ({'LONG' if amt > 0 else 'SHORT'} {q})")
            except Exception as e:
                print("close", sym, e); tg(f"⚠️ не вдалось закрити {sym}: {e}"); continue
        p = st["pos"].pop(sym, None)
        if p and p.get("status") in ("in_pos", "live"):
            st["trades"].append(dict(t=str(_utcnow()), sym=sym, eng=p.get("engine", "?"),
                                     side=p.get("side"), r=0.0, pnl=0.0,
                                     reason="manual", adx=p.get("adx")))
    save_state(st)
    print("close: готово.", "Слоти:", list(st["pos"].keys()) or "порожньо")

ENTRIES_ENABLED = True                       # preflight може вимкнути НОВІ входи (відкриті ведемо)

def preflight(ex):
    """Перевірка контракту з біржею на старті live: все, що вже ламалось.
    Провал -> TG-алерт і блок НОВИХ входів (відкриті позиції ведемо далі)."""
    probs = []
    for s in COINS:
        if s not in SYM_MAP: probs.append(f"символ не зрезолвлено: {s}")
    try:
        for r_ in (ex.fetch_positions() or [])[:5]:
            sym = r_.get("symbol") or ""
            if sym and _norm(sym) not in COINS and ":" in sym and _norm(sym) == sym:
                probs.append(f"нормалізація символу не працює: {sym}")
    except Exception as e:
        probs.append(f"fetch_positions падає: {e}")
    for s in COINS:
        if open_order_ids(ex, s) is None:
            probs.append(f"fetch_open_orders падає: {s}")
        try:
            float(ex.amount_to_precision(M(s), 1.2345)); float(ex.price_to_precision(M(s), 123.456))
        except Exception as e:
            probs.append(f"precision {s}: {e}")
    try:
        float(ex.fetch_balance()["USDT"]["total"])
    except Exception as e:
        probs.append(f"fetch_balance: {e}")
    # РЕАЛЬНА перевірка ЗАПИСУ: чи може ключ ВЗАГАЛІ виставити ордер (не лише читати).
    # Раніше preflight перевіряв тільки читання -> ключ без права торгівлі проходив як OK,
    # а бот мовчки не міг відкрити жодної позиції (симптом: 1 угода за 2 міс, placed=False).
    # Ставимо крихітну лімітку ДАЛЕКО від ціни (не виконається) ТИМ САМИМ типом, що й FVG
    # (GTX post-only), і одразу знімаємо. Помилка тут = точна причина «не торгує».
    if not DRY_RUN:
        ts = next(iter(COINS))
        def _place_test():
            px = float(ex.fetch_ticker(M(ts))["last"])
            min_cost, min_amt = limits_for(ex, ts)
            tpx = float(ex.price_to_precision(M(ts), px * 0.5))          # -50% -> точно НЕ філ
            q = float(ex.amount_to_precision(M(ts), max((min_cost or 5) / tpx * 1.2, min_amt or 0)))
            return ex.create_order(M(ts), "limit", "buy", q, tpx, {"timeInForce": "GTX"}).get("id")
        oid = None
        try:
            oid = _place_test()
            print(f"preflight: тест-ордер OK — {ts} лімітка виставилась (запис працює)")
        except Exception as e:
            es = str(e)
            # -4061: акаунт у HEDGE MODE (двобічні позиції), а бот шле ордери без positionSide.
            # Стратегія працює в ONE-WAY -> пробуємо перемкнути і повторити ордер.
            if "-4061" in es or "position side" in es.lower():
                try:
                    ex.set_position_mode(False)                         # False = one-way
                    print("preflight: акаунт був у HEDGE MODE -> перемкнув у One-way, пробую знову")
                    oid = _place_test()
                    print("preflight: тест-ордер OK після переходу в One-way ✅")
                except Exception as e2:
                    probs.append(f"акаунт у HEDGE MODE і НЕ вдалось перемкнути в One-way ({e2}). "
                                 f"Закрий ВСІ позиції на демо і перемкни Position Mode → One-way вручну в Binance")
            else:
                probs.append(f"ТЕСТ-ОРДЕР ПРОВАЛЕНО ({ts}): {e}")
        finally:
            if oid:
                try: ex.cancel_order(oid, M(ts))
                except Exception as ec: print("preflight: тест-ордер не знявся (прибере reconcile):", ec)
    if probs:
        tg("⛔ <b>PREFLIGHT провалено</b> — нові входи ВИМКНЕНО до фіксу:\n" + "\n".join(f"• {p}" for p in probs))
        return False
    print("preflight: OK (читання + ЗАПИС ордера)")
    return True

def poll_live(ex, st):
    """Кожен цикл на testnet/live: філи лімовок і закриття позицій.
    АНТИФАНТОМ: закриття оголошується лише після 2 ПОСПІЛЬ читань amt==0 І якщо
    захисні ордери теж зникли (Binance сам знімає reduceOnly, коли позиція закрита)."""
    if DRY_RUN: return
    for symbol in list(st["pos"].keys()):
        p = st["pos"][symbol]
        amt = live_pos_amt(ex, symbol)
        if amt is None: continue                          # біржа не відповіла -> без висновків
        if p.get("status") == "pending":
            if amt > 0:                                   # лімітка виконалась -> позиція існує
                p["status"] = "in_pos"; p["zero_polls"] = 0
                ensure_protective(ex, symbol, p, amt)     # ТЕПЕР ставимо reduceOnly стоп/тейк
                if NOTIFY_TRADES:
                    tg(f"📥 Філ {symbol} {p['side'].upper()} @ ~{p.get('entry',0):.4f} "
                       f"(стоп {p.get('stop',0):.4f} / тейк {p.get('target',0):.4f})")
        elif p.get("status") in ("in_pos", "live"):
            if amt > 0:
                p["zero_polls"] = 0
                ensure_protective(ex, symbol, p, amt)     # доставити відсутні ноги захисту
                continue
            # amt == 0: або закрито, або збій читання -> перевіряємо і чекаємо підтвердження
            ids = p.get("ids", {})
            open_ids = open_order_ids(ex, symbol)
            prot = [ids[k] for k in ("stop", "tp") if ids.get(k)]
            if open_ids is not None and prot and any(i in open_ids for i in prot):
                p["zero_polls"] = 0; continue             # захист живий -> позиція існує (збій читання)
            p["zero_polls"] = p.get("zero_polls", 0) + 1
            if p["zero_polls"] < 2:
                continue                                  # перше нульове читання -> ще раз за хвилину
            # причина закриття — за СТАТУСОМ ордера (біржа сама знімає другу ногу, тому
            # «ордер зник» не означає «спрацював»; питаємо, чи був ВИКОНАНИЙ)
            def _filled(oid):
                try:
                    o = ex.fetch_order(oid, M(symbol))
                    return o.get("status") == "closed" or float(o.get("filled") or 0) > 0
                except Exception:
                    return None
            reason = "?"
            if ids.get("tp") and _filled(ids["tp"]): reason = "target"
            elif ids.get("stop") and _filled(ids["stop"]): reason = "stop"
            elif open_ids is not None:                    # запасна евристика, як раніше
                if ids.get("tp") and ids["tp"] not in open_ids: reason = "target"
                elif ids.get("stop") and ids["stop"] not in open_ids: reason = "stop"
            cancel_symbol_orders(ex, symbol)              # прибрати завислий протилежний ордер
            r = 2.0 if reason == "target" else (-1.0 if reason == "stop" else 0.0)
            st["trades"].append(dict(t=str(_utcnow()), sym=symbol, eng=p.get("engine", "?"),
                                     side=p.get("side"), r=r, pnl=0.0, reason=reason, adx=p.get("adx")))
            st["pos"].pop(symbol)
            if NOTIFY_TRADES:
                tg(f"{'✅' if r > 0 else '❌'} <b>Закрито {symbol} {str(p.get('side')).upper()}</b> "
                   f"({p.get('engine','?')}) — {reason} (~{r:+.1f}R)")

# ----------------------------- DRY-RUN симуляція фолу -----------------------
def paper_close(st, symbol, p, reason, px, bar_dt):
    """Паперове закриття з реалізмом (слип входу/стопа + комісії) і TG."""
    sgn = 1 if p["side"] == "long" else -1
    en, D = p["entry"], abs(p["entry"] - p["stop"])
    en_f = en * (1 + sgn * ENTRY_SLIP)                       # гірший філ входу
    ex_f = px * (1 - sgn * STOP_SLIP) if reason == "stop" else px  # стоп проскакує; тейк=лімітка
    r = sgn * (ex_f - en_f) / D - 2 * FEE_RATE * (en_f / D)   # + комісії обидві сторони
    pnl = st["equity"] * RISK_PCT * r
    st["equity"] += pnl
    st["trades"].append(dict(t=str(bar_dt), sym=symbol, eng=p["engine"],
                             side=p["side"], r=round(r, 2), pnl=round(pnl, 2),
                             reason=reason, adx=p.get("adx")))
    st["pos"].pop(symbol, None)
    if NOTIFY_TRADES:
        emo = "✅" if r > 0 else "❌"
        tg(f"{emo} <b>Закрито {symbol} {p['side'].upper()}</b> ({p['engine']}) — {reason}\n"
           f"R {r:+.2f} | PnL {pnl:+.2f} USDT | депозит {st['equity']:.2f}")

def dry_fill_and_manage(st, symbol, bar):
    """Паперове ведення ВІДКРИТОЇ позиції: стоп/тейк по закритому бару.
    На барі філа FVG тейк не зараховуємо (no_tgt_bar) — чесність 15m-істини."""
    p = st["pos"].get(symbol)
    if not p or p.get("status") != "in_pos": return
    hi, lo = bar["high"], bar["low"]; closed = None
    tgt_ok = str(bar["dt"]) != p.get("no_tgt_bar")
    if p["side"] == "long":
        if lo <= p["stop"]: closed = ("stop", p["stop"])
        elif tgt_ok and hi >= p["target"]: closed = ("target", p["target"])
    else:
        if hi >= p["stop"]: closed = ("stop", p["stop"])
        elif tgt_ok and lo <= p["target"]: closed = ("target", p["target"])
    if closed:
        paper_close(st, symbol, p, closed[0], closed[1], bar["dt"])

# ------------------------ FVG-ПАКЕТ: машина станів ---------------------------
def step_fvg_slot(ex, st, symbol, df):
    """На кожному НОВОМУ закритому барі веде FVG-слот: watch -> pending -> філ/смерть.
    watch: 2 бари після формування; ретест у цей час = сетап згорів.
    pending: лімітка на 50% зони; тримається на книзі лише коли тренд+ADX ок
    (інакше знімається — філ при поганих умовах = смерть сетапу в бектесті)."""
    p = st["pos"].get(symbol)
    if not p or p.get("engine") != "FVG" or p.get("status") not in ("watch", "pending"): return
    bar_h, bar_l = df["high"].iloc[-1], df["low"].iloc[-1]
    bar_dt = df["dt"].iloc[-1]
    p["bars_waited"] = p.get("bars_waited", 0) + 1
    touched = bar_l <= p["entry"] if p["side"] == "long" else bar_h >= p["entry"]
    if p["status"] == "watch":
        if touched:                                   # ретест зарано -> фільтр wait>2
            st["pos"].pop(symbol)
            if NOTIFY_TRADES: note(f"🚫 FVG {symbol}: ретест у перші {FVG_WAIT} бари — сетап згорів")
            return
        if p["bars_waited"] < FVG_WAIT:               # ще чекаємо чисті бари
            return
        # 2 чисті бари -> ОЗБРОЄННЯ (рахуємо рівні/розмір; touched тут завжди False)
        a = float(atr(df, STOP_ATR).iloc[-1])
        D = max(abs(p["entry"] - p["zb"]), FVG_FLOOR * a)
        sgn = 1 if p["side"] == "long" else -1
        p["stop"] = p["entry"] - sgn * D; p["target"] = p["entry"] + sgn * RR * D
        eq = equity_now(ex, st)
        qty = valid_size(ex, symbol, position_qty(eq, p["entry"], p["stop"]), p["entry"])
        if not qty:
            st["pos"].pop(symbol)
            print(f"  [skip] {symbol}: розмір нижчий за мінімум біржі"); return
        p["qty"] = qty; p["status"] = "pending"; p["placed"] = False
        if NOTIFY_TRADES:
            note(f"⏳ {symbol} {p['side'].upper()}: лімітка готова @ {p['entry']:.4f} — ЩЕ НЕ в позиції.\n"
                 f"Виставлю на біржу лише коли тренд+ADX за напрямом; заходжу ТІЛЬКИ на ретесті.\n"
                 f"Якщо зайде: стоп {p['stop']:.4f} / тейк {p['target']:.4f} (ризик {RISK_PCT*100:.1f}%).\n"
                 f"Реальний вхід підтвердить окреме «📥 Філ».")
        # НЕ повертаємось: далі (live) виставляємо лімітку ЦЬОГО ж бару, щоб вона стояла
        # на книзі вже наступного бару (fill з k+3, як у бектесті). У DRY нижче touched=False,
        # тож філ цього бару не станеться — філи з наступного бару.
    # --- pending ---
    if p["bars_waited"] >= FVG_EXPIRY:                # 20 барів від формування -> знято
        if not DRY_RUN and p.get("placed"): cancel_symbol_orders(ex, symbol)
        st["pos"].pop(symbol)
        if NOTIFY_TRADES: note(f"🚫 Лімітку знято {symbol} — не зайшло за {FVG_EXPIRY} барів")
        return
    cond = fvg_conditions_ok(df, p["side"])
    if DRY_RUN:
        if touched:
            if cond:
                p["status"] = "in_pos"; p["no_tgt_bar"] = str(bar_dt)
                if NOTIFY_TRADES:
                    tg(f"📥 Лімітка зайшла {symbol} {p['side'].upper()} @ {p['entry']:.4f} "
                       f"(стоп {p['stop']:.4f} / тейк {p['target']:.4f})")
                hit_stop = bar_l <= p["stop"] if p["side"] == "long" else bar_h >= p["stop"]
                if hit_stop:                          # той самий бар: лише СТОП (тейк — з наступного)
                    paper_close(st, symbol, p, "stop", p["stop"], bar_dt)
            else:
                st["pos"].pop(symbol)
                if NOTIFY_TRADES: note(f"🚫 FVG {symbol}: ретест без тренду/ADX≥20 — сетап згорів")
        return
    # live/demo: тримаємо ордер на книзі лише коли умови ок
    if cond and not p.get("placed"):
        try:
            ms = M(symbol)
            q = float(ex.amount_to_precision(ms, p["qty"]))
            side = "buy" if p["side"] == "long" else "sell"
            pr = float(ex.price_to_precision(ms, p["entry"]))
            oid = ex.create_order(ms, "limit", side, q, pr, {"timeInForce": "GTX"}).get("id")
            p.setdefault("ids", {})["entry"] = oid; p["placed"] = True
        except Exception as e:
            print("fvg place", symbol, e)
    elif not cond and p.get("placed"):
        cancel_symbol_orders(ex, symbol)
        p.setdefault("ids", {}).pop("entry", None); p["placed"] = False

# ----------------------------- ОБРОБКА ОДНОГО БАРА ---------------------------
def handle_symbol(ex, st, symbol, df):
    if not ENTRIES_ENABLED:                               # preflight провалено -> нових входів нема
        return
    p = st["pos"].get(symbol)
    if p and p.get("status") in ("in_pos", "live"):       # реальна позиція тримає слот
        return
    cands = detect(df, COINS[symbol])
    if not cands: return
    # KC-маркет перехоплює слот у НЕспрацьованої FVG-лімітки (як у бектесті:
    # позицію бере той, хто реально зайшов перший; лімітка ще не зайшла)
    if p:
        kc = next((c for c in cands if c["typ"] == "market"), None)
        if kc is None: return
        if not DRY_RUN and p.get("placed"): cancel_symbol_orders(ex, symbol)
        st["pos"].pop(symbol, None)
        cand = kc
        if NOTIFY_TRADES: note(f"↪️ KC перехоплює слот {symbol} (FVG-лімітку знято)")
    else:
        cand = cands[0]                                   # перший сигнал бере слот
    if cand["typ"] == "arm":                              # FVG-пакет: спершу фаза watch
        st["pos"][symbol] = dict(status="watch", engine="FVG", side=cand["side"],
                                 entry=cand["entry"], zb=cand["zb"],
                                 bars_waited=0, adx=cand.get("adx"))
        if NOTIFY_TRADES:
            axv = cand.get("adx")
            note(f"🕐 FVG {symbol} {cand['side'].upper()}: зона сформована, лімітка на 50% "
                 f"({cand['entry']:.4f}) озброїться через {FVG_WAIT} бари"
                 + (f" | ADX {axv:.1f}" if axv is not None else ""))
        return
    eq = equity_now(ex, st)
    qty = position_qty(eq, cand["entry"], cand["stop"])
    qty = valid_size(ex, symbol, qty, cand["entry"])      # мінімуми біржі: краще пропустити, ніж оверризик
    if not qty:
        print(f"  [skip] {symbol}: розмір нижчий за мінімум біржі — мало капіталу для цього стопа")
        return
    lev = cand["entry"] * qty / eq
    axv = cand.get("adx")
    adx_tag = ""
    if axv is not None:                                   # форвард-лог фільтра ADX≥20 на FVG
        weak = cand["engine"] == "FVG" and axv < ADX_MIN
        adx_tag = f"\nADX {axv:.1f}" + (" ⚠️ слабкий тренд (<20) — форвард-тест фільтра" if weak else " ✓")
    msg = (f"{'🟢' if cand['side']=='long' else '🔴'} <b>{cand['engine']} "
           f"{cand['side'].upper()}</b> {symbol}\n"
           f"вхід({cand['typ']}) {cand['entry']:.4f} | стоп {cand['stop']:.4f} | "
           f"тейк {cand['target']:.4f}\nрозмір {qty:.4f} (плече ~{lev:.1f}x, ризик {RISK_PCT*100:.1f}%)"
           + adx_tag)
    if DRY_RUN:
        st["pos"][symbol] = dict(status=("pending" if cand["typ"] == "limit" else "in_pos"),
                                 engine=cand["engine"], side=cand["side"],
                                 entry=cand["entry"], stop=cand["stop"], target=cand["target"],
                                 qty=qty, bars_waited=0, adx=axv)
        if NOTIFY_TRADES:
            tag = "⏳ Виставлено лімітку " if cand["typ"] == "limit" else "📥 Вхід "
            tg("[DRY] " + tag + "\n" + msg)
    else:
        try:
            ids = place_live(ex, symbol, cand, qty)
            st["pos"][symbol] = dict(status=("pending" if cand["typ"] == "limit" else "in_pos"),
                                     engine=cand["engine"], side=cand["side"], entry=cand["entry"],
                                     stop=cand["stop"], target=cand["target"], qty=qty,
                                     ids=ids, bars_waited=0, adx=axv)
            if NOTIFY_TRADES: tg("✅ " + msg)
        except Exception as e:
            cancel_symbol_orders(ex, symbol)         # прибрати завислий вхідний ордер, якщо вхід частково впав
            st["pos"].pop(symbol, None)
            note(f"⚠️ помилка ордера {symbol}: {e}")

# ----------------------------- KILL-SWITCH + ЗВІТ ---------------------------
def check_day_and_killswitch(st, eq):
    today = _utcnow().strftime("%Y-%m-%d")
    if st["day"] != today:
        st["day"] = today; st["day_start_equity"] = eq; st["halted"] = False
    dd = (eq - st["day_start_equity"]) / st["day_start_equity"] if st["day_start_equity"] else 0
    if abs(dd) > 0.5:                     # >50% за день неможливо при ризику 3% -> це ЗМІНА БАЗИСУ
        print(f"kill-switch: базис змінився ({st['day_start_equity']:.0f}->{eq:.0f}), ре-базис без стопу")
        st["day_start_equity"] = eq; st["halted"] = False   # (перемикання режиму/балансу) не стоп
        return False
    if dd <= -MAX_DAILY_LOSS and not st["halted"]:
        st["halted"] = True
        tg(f"🛑 KILL-SWITCH: денний збиток {dd*100:.1f}% > ліміту {MAX_DAILY_LOSS*100:.0f}%. "
           f"Нові входи зупинено до завтра.")
    return st["halted"]

def journal_dump(st):
    """Діагностика БЕЗ біржі (лише bot_state.json): що бот НАСПРАВДІ робив.
    Ключове: last_bar = свіжість даних, які БАЧИВ бот (чи не застряг на старих),
    слоти, і журнал угод по місяцях — щоб побачити, де зникають входи."""
    now = _utcnow()
    print("=== СТАН БОТА (bot_state.json) ===")
    print(f"equity={st.get('equity')} | day={st.get('day')} | halted={st.get('halted')}")
    print(f"\nОстанній ОБРОБЛЕНИЙ бар (що бачив бот -> чи свіжі дані):")
    for sym in COINS:
        lb = (st.get("last_bar") or {}).get(sym)
        if not lb: print(f"  {sym}: (нема)"); continue
        try:
            t = pd.Timestamp(lb).to_pydatetime().replace(tzinfo=None)
            age = (now - t).total_seconds() / 3600
            flag = "✅ свіжий" if age < 8 else f"⚠️ СТАРИЙ на {age:.0f}г — БОТ ЗАСТРЯГ НА СТАРИХ ДАНИХ!"
            print(f"  {sym}: {lb}  ({flag})")
        except Exception:
            print(f"  {sym}: {lb}")
    print(f"\nСлоти зараз:")
    for sym in COINS:
        p = (st.get("pos") or {}).get(sym)
        print(f"  {sym}: {p if p else 'вільний'}")
    tr = st.get("trades", [])
    print(f"\nУгод у журналі ВСЬОГО: {len(tr)}")
    if tr:
        df = pd.DataFrame(tr); df["t"] = pd.to_datetime(df["t"], errors="coerce")
        df["ym"] = df["t"].dt.strftime("%Y-%m")
        print("  по місяцях (реасони закриття):")
        for ym, g in df.groupby("ym"):
            rc = {k: int(v) for k, v in g["reason"].value_counts().items()} if "reason" in g else {}
            print(f"    {ym}: {len(g):3d} угод  {rc}")
        print("  останні 20 записів журналу:")
        for _, r in df.tail(20).iterrows():
            print(f"    {str(r['t'])[:16]}  {r.get('sym'):9s} {str(r.get('eng')):4s} "
                  f"{str(r.get('side')):5s} {str(r.get('reason')):8s} {float(r.get('r') or 0):+.1f}R")

def coin_picture(ex, st):
    """Компактна жива картина по монетах для звіту: тренд / ADX / стан KC / слот.
    Щоб було видно, що бот ЖИВИЙ і ЧОМУ тихо (сильний тренд -> KC в каналі,
    FVG-лімітка висить без ретесту), а не «завис/зламався»."""
    out = []
    for symbol in COINS:
        try:
            df = fetch_closed(ex, symbol); c = df["close"]; i = len(df) - 1
            trend = ema(c, EMA_TREND).iloc[i]; ax = adx(df, ADX_LEN).iloc[i]
            mid = ema(c, KC_EMA).iloc[i]; b = KC_MULT * atr(df, KC_ATR).iloc[i]; price = c.iloc[i]
            tdir = "аптренд↑" if price > trend else "даунтренд↓"
            kc = "пробій↑" if price > mid + b else ("пробій↓" if price < mid - b else "в каналі")
            p = st["pos"].get(symbol)
            if not p: slot = "вільний"
            elif p.get("status") in ("in_pos", "live"): slot = f"У ПОЗИЦІЇ {str(p.get('side')).upper()}"
            elif p.get("status") == "pending":
                slot = f"{p.get('engine')} {p.get('side')} лімітка {p.get('bars_waited',0)}/{FVG_EXPIRY} (жду ретест)"
            elif p.get("status") == "watch":
                slot = f"{p.get('engine')} {p.get('side')} watch {p.get('bars_waited',0)}/{FVG_WAIT}"
            else: slot = str(p.get("status"))
            out.append(f"• {symbol.split('/')[0]}: {tdir} ADX {ax:.0f} | KC:{kc} | слот: {slot}")
        except Exception as e:
            out.append(f"• {symbol.split('/')[0]}: картина недоступна ({str(e)[:40]})")
    return out

def daily_report(ex, st, eq):
    since = _utcnow() - dt.timedelta(hours=24)
    rec = [t for t in st["trades"] if pd.Timestamp(t["t"]).to_pydatetime().replace(tzinfo=None) >= since]
    nr = len(rec); wins = sum(1 for t in rec if t["r"] > 0)
    sumR = sum(t["r"] for t in rec); pnl = sum(t["pnl"] for t in rec)
    openp = "; ".join(f"{k.split('/')[0]} {v['side']}({v['engine']})" for k, v in st["pos"].items()) or "немає"
    wr = f"{wins/nr*100:.0f}%" if nr else "—"
    lines = [f"📊 <b>Денний звіт</b> {_utcnow():%Y-%m-%d %H:%M}Z",
             f"Депозит: <b>{eq:.2f}</b> USDT  ({'DRY' if DRY_RUN else ('TESTNET' if TESTNET else 'LIVE')})",
             f"За 24г: угод {nr}, WR {wr}, сума {sumR:+.2f}R, PnL {pnl:+.2f} USDT",
             f"Відкриті: {openp}",
             f"Всього угод у журналі: {len(st['trades'])}",
             f"Бенчмарк: очікування ≈ +0.2R/угода (якщо за 30+ угод нижче 0 — стоп)"]
    if not DRY_RUN and not ENTRIES_ENABLED:              # гучне попередження: бот НЕ відкриває позицій
        lines.insert(1, "⛔ <b>УВАГА: НОВІ ВХОДИ ВИМКНЕНО</b> (preflight не пройдено) — "
                        "бот не відкриває позиції! Перевір зв'язок/ключі й перезапусти.")
    fvg = [t for t in st["trades"] if t.get("eng") == "FVG" and t.get("adx") is not None]
    if fvg:                                              # накопичувальний форвард-тест фільтра ADX
        lo = [t["r"] for t in fvg if t["adx"] < ADX_MIN]; hi = [t["r"] for t in fvg if t["adx"] >= ADX_MIN]
        av = lambda x: sum(x) / len(x) if x else 0.0
        lines.append(f"🔬 FVG форвард ADX: &lt;20 → {len(lo)}уг {av(lo):+.2f}R | ≥20 → {len(hi)}уг {av(hi):+.2f}R")
    lines.append("🔎 <b>Жива картина</b> (бот працює, ось стан ринку):")
    lines += coin_picture(ex, st)
    tg("\n".join(lines))

# ----------------------------- ЦИКЛ -----------------------------------------
def run_once(ex, st, force_report=False):
    if not DRY_RUN: poll_live(ex, st)          # testnet/live: детект філів/закриттів на біржі -> TG
    eq = equity_now(ex, st)
    halted = check_day_and_killswitch(st, eq)
    for symbol in COINS:
        try:
            df = with_retry(fetch_closed, ex, symbol)
        except Exception as e:
            print(f"  fetch {symbol}: {e}"); continue
        last = str(df["dt"].iloc[-1])
        if st["last_bar"].get(symbol) == last and not force_report:
            continue   # бар не новий -> НІЧОГО (управляємо лише на закритті НОВИХ барів,
                       # інакше фантомні філи проти бару формування)
        st["last_bar"][symbol] = last
        step_fvg_slot(ex, st, symbol, df)      # FVG-пакет: watch/pending -> філ/зняття
        if DRY_RUN:
            bar = {"dt": df["dt"].iloc[-1], "high": df["high"].iloc[-1], "low": df["low"].iloc[-1]}
            dry_fill_and_manage(st, symbol, bar)   # ведення відкритої позиції
        if halted:                       # стоп-вхід, але відкриті ведемо (вище)
            continue
        handle_symbol(ex, st, symbol, df)
    save_state(st)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    banner = f"режим={mode} DRY_RUN={DRY_RUN} TESTNET={TESTNET} risk={RISK_PCT*100:.1f}%"
    print("BOT:", banner)
    if not DRY_RUN and not TESTNET:
        print("‼️  УВАГА: РЕАЛЬНІ ГРОШІ. Запуск через 10с, Ctrl+C щоб скасувати.")
        if mode == "run": time.sleep(10)
    if mode == "selftest":
        return selftest()
    st = load_state()
    if mode == "journal":                        # діагностика зі стану, БЕЗ біржі/ключів
        return journal_dump(st)
    ex = make_exchange()
    load_markets_safe(ex)
    if mode == "balance":                    # діагностика підключення (демо/лайв)
        api = ex.urls.get("api", {})
        url = api.get("fapiPrivate") if isinstance(api, dict) else api
        print(f"режим ключів: {'DEMO/TESTNET' if TESTNET else 'LIVE'} | запити -> {url}")
        try:
            b = ex.fetch_balance()["USDT"]
            print(f"✅ Баланс USDT: total={b['total']} | free={b['free']}")
        except Exception as e:
            print("❌ fetch_balance:", repr(e))
        return
    if mode == "preflight":
        return print("PREFLIGHT:", "OK ✅" if preflight(ex) else "ПРОВАЛЕНО ⛔ (див. вище)")
    if mode == "close":
        return close_command(ex, st, sys.argv[2] if len(sys.argv) > 2 else "all")
    if mode == "protect":                    # protect SYMBOL STOP TARGET — почепити захист на живу позицію
        sym = sys.argv[2]; sp = float(sys.argv[3]); tp = float(sys.argv[4])
        signed = live_pos_signed(ex, sym); amt = abs(signed)
        if amt <= 0:
            print(f"{sym}: позиції на біржі нема"); return
        side = "long" if signed > 0 else "short"
        ok = (sp < tp) if side == "long" else (sp > tp)
        if not ok:
            print(f"помилка: для {side} стоп має бути {'нижче' if side=='long' else 'вище'} тейка"); return
        p = st["pos"].setdefault(sym, dict(engine="?", qty=amt))
        p.update(status="in_pos", side=side, stop=sp, target=tp, qty=amt, zero_polls=0)
        p.setdefault("entry", 0)
        ensure_protective(ex, sym, p, amt)
        save_state(st)
        print(f"{sym} {side} amt={amt}: стоп {sp} / тейк {tp} | ордери: {p.get('ids')}")
        return
    if mode == "limits":                     # мінімуми біржі -> який депозит треба, щоб угоди не пропускались
        print(f"Мінімальний депозит для авто-торгівлі (ризик {RISK_PCT*100:.0f}%, щоб угоди НЕ пропускались):\n")
        need_all = 0.0
        for s in COINS:
            mc, ma = limits_for(ex, s)
            try: px = float(ex.fetch_ticker(M(s))["last"])
            except Exception: px = 0.0
            wide = 0.08                       # широкий стоп (2×ATR буває ~8% ціни) — найгірший для сайзу
            eq_notional = mc * wide / RISK_PCT if mc else 0        # нотіонал >= min notional
            eq_qty = 5 * ma * px * wide / RISK_PCT if (ma and px) else 0   # qty >= 5 кроків (мале округлення)
            need = max(eq_notional, eq_qty)
            need_all = max(need_all, need)
            print(f"  {s}: ціна {px:.2f} | min notional {mc} USDT | min qty {ma}")
            print(f"      -> щоб угоди по {s.split('/')[0]} НЕ пропускались і ризик був точним: депозит ≥ ~${need:.0f}")
        print(f"\nОтже мінімально «нормально функціонувати» (обидві монети): ≈ ${need_all:.0f}")
        print(f"Рекомендація: взяти з запасом ×1.5-2 (просадки/варіативність) -> ~${need_all*1.7:.0f}")
        return
    if mode == "scan":                       # ЧОМУ мало сигналів: жива картина по кожній монеті
        print(f"ENTRIES_ENABLED буде обчислено в run; preflight зараз:", "OK" if preflight(ex) else "ПРОВАЛ")
        for symbol in COINS:
            try:
                df = with_retry(fetch_closed, ex, symbol)
            except Exception as e:
                print(f"\n{symbol}: fetch ПАДАЄ -> {e} (це БАГ: нема даних = нема сигналів)"); continue
            c = df["close"]; trend = ema(c, EMA_TREND); ax = adx(df, ADX_LEN)
            mid = ema(c, KC_EMA); band = KC_MULT * atr(df, KC_ATR)
            i = len(df) - 1
            cands = detect(df, COINS[symbol])
            print(f"\n{symbol}: барів {len(df)} | {str(df['dt'].iloc[0])[:16]} .. {str(df['dt'].iloc[-1])[:16]}")
            if len(df) < EMA_TREND + 5:
                print(f"  ⛔ БАРІВ ЗАМАЛО ({len(df)}<{EMA_TREND+5}) -> detect завжди порожній! (тонкі дані testnet?)")
            print(f"  close {c.iloc[-1]:.4f} | EMA200 {trend.iloc[-1]:.4f} -> ціна {'ВИЩЕ (лонг-зона)' if c.iloc[-1]>trend.iloc[-1] else 'НИЖЧЕ (шорт-зона)'}")
            axl = ax.tail(6).round(1).tolist()
            print(f"  ADX останні 6 барів: {axl} -> {'≥20 (тренд, можна)' if ax.iloc[-1]>=ADX_MIN else '<20 (ФЛЕТ -> KC блоковано)'}")
            print(f"  KC: верх {(mid+band).iloc[-1]:.4f} / низ {(mid-band).iloc[-1]:.4f} (close {'над верхом' if c.iloc[-1]>(mid+band).iloc[-1] else ('під низом' if c.iloc[-1]<(mid-band).iloc[-1] else 'усередині каналу — пробою нема')})")
            print(f"  detect() -> {len(cands)} кандидатів: {[(x['engine'], x['side'], x['typ']) for x in cands]}")
            p = st['pos'].get(symbol)
            if p:
                print(f"  СЛОТ ЗАЙНЯТО: {p.get('status')} {p.get('engine')} {p.get('side')} bars_waited={p.get('bars_waited')} (блокує нові до звільнення)")
            else:
                print(f"  слот вільний")
        return
    if mode == "positions":                  # діагностика: сирі позиції/ордери з біржі
        try:
            for pos in ex.fetch_positions() or []:
                amt = float(pos.get("contracts") or (pos.get("info", {}) or {}).get("positionAmt") or 0)
                if abs(amt) > 0:
                    print(f"POS {pos.get('symbol')} (норм: {_norm(pos.get('symbol'))}) amt={amt} "
                          f"entry={pos.get('entryPrice')}")
        except Exception as e:
            print("fetch_positions:", repr(e))
        for sym in COINS:
            print(f"ORDERS {sym}: {open_order_ids(ex, sym)}")
        print("Слоти бота:", {k: v.get('status') for k, v in st['pos'].items()} or "порожньо")
        return
    reconcile(ex, st)
    if mode == "once":
        run_once(ex, st); daily_report(ex, st, equity_now(ex, st)); return
    if mode == "report":
        daily_report(ex, st, equity_now(ex, st)); return
    # mode == run: цикл
    global ENTRIES_ENABLED
    if not DRY_RUN:
        ENTRIES_ENABLED = preflight(ex)          # контракт з біржею; провал -> без нових входів
    tg(f"🤖 Бот запущено ({banner})" + ("" if ENTRIES_ENABLED else " ⛔ входи вимкнено (preflight)"))
    last_report_day = ""
    last_preflight = time.time()                  # для авто-відновлення входів (див. нижче)
    while True:
        try:
            run_once(ex, st)
            now = _utcnow()
            # АВТО-ВІДНОВЛЕННЯ: якщо входи вимкнені preflight-ом (міг бути ТИМЧАСОВИЙ збій
            # на старті), періодично пробуємо ще раз і вмикаємо назад, коли зв'язок ок.
            # Тільки «вмикаємо» — щоб короткий мережевий збій під час роботи НЕ вимкнув
            # робочого бота (там усі виклики й так у try/except і просто пропускають угоду).
            if not DRY_RUN and not ENTRIES_ENABLED and time.time() - last_preflight >= 1800:
                last_preflight = time.time()
                load_markets_safe(ex)             # ринки/символи могли не завантажитись на старті
                if preflight(ex):
                    ENTRIES_ENABLED = True
                    tg("✅ Preflight пройдено — <b>входи знову увімкнено</b>.")
            if now.hour == REPORT_HOUR_UTC and now.strftime("%Y-%m-%d") != last_report_day:
                daily_report(ex, st, equity_now(ex, st)); last_report_day = now.strftime("%Y-%m-%d")
        except Exception as e:
            print("loop помилка:", e)
        time.sleep(60)

# ----------------------------- ОФЛАЙН SELF-TEST -----------------------------
def selftest():
    """Прогін стратегії бота на локальних CSV (без біржі) — перевірка правильності логіки."""
    print("\n=== SELF-TEST (офлайн, локальні дані, FVG-пакет) ===")
    files = {"ETH/USDT": "quant/data/eth_4h.csv", "SOL/USDT": "quant/data/sol_4h.csv",
             "BTC/USDT*": "quant/data/btc_15m.csv"}    # BTC* — референс, не торгується
    for symbol, path in files.items():
        if not os.path.exists(path):
            print(f"  {symbol}: немає {path}, пропуск"); continue
        raw = pd.read_csv(path)
        raw["dt"] = pd.to_datetime(raw["ts"], unit="ms", utc=True)
        d = raw.set_index("dt")
        if "btc_15m" in path:
            d = d.resample("4h").agg({"open": "first", "high": "max", "low": "min",
                                      "close": "last"}).dropna()
        d = d.reset_index()
        eng = COINS.get(symbol, ["KC", "FVG"])
        pos = None; trades = []
        for i in range(EMA_TREND + 5, len(d)):
            sub = d.iloc[:i + 1]; bar = d.iloc[i]
            if pos and pos["status"] == "watch":
                pos["w"] += 1
                touched = bar["low"] <= pos["entry"] if pos["side"] == "long" else bar["high"] >= pos["entry"]
                if touched: pos = None                       # wait>2: ранній ретест = згорів
                elif pos["w"] >= FVG_WAIT:
                    a = float(atr(sub, STOP_ATR).iloc[-1])
                    D = max(abs(pos["entry"] - pos["zb"]), FVG_FLOOR * a)
                    sgn = 1 if pos["side"] == "long" else -1
                    pos.update(stop=pos["entry"] - sgn * D, target=pos["entry"] + sgn * RR * D,
                               status="pending")
            elif pos and pos["status"] == "pending":
                pos["w"] += 1
                if pos["w"] >= FVG_EXPIRY: pos = None
                else:
                    touched = bar["low"] <= pos["entry"] if pos["side"] == "long" else bar["high"] >= pos["entry"]
                    if touched:
                        if fvg_conditions_ok(sub, pos["side"]):
                            pos["status"] = "in_pos"; pos["nt"] = i     # тейк лише з наступного бара
                            hs = bar["low"] <= pos["stop"] if pos["side"] == "long" else bar["high"] >= pos["stop"]
                            if hs: trades.append(-1.0); pos = None
                        else:
                            pos = None                        # ретест без тренду/ADX = згорів
            elif pos and pos["status"] == "in_pos":
                if pos["side"] == "long":
                    hs = bar["low"] <= pos["stop"]; ht = bar["high"] >= pos["target"] and i > pos.get("nt", -1)
                else:
                    hs = bar["high"] >= pos["stop"]; ht = bar["low"] <= pos["target"] and i > pos.get("nt", -1)
                if hs: trades.append(-1.0); pos = None
                elif ht: trades.append(RR); pos = None
            if pos: continue
            cands = detect(sub, eng)
            if cands:
                c = cands[0]
                if c["typ"] == "arm":
                    pos = dict(status="watch", side=c["side"], entry=c["entry"], zb=c["zb"], w=0)
                else:
                    pos = dict(status="in_pos", side=c["side"], entry=c["entry"],
                               stop=c["stop"], target=c["target"], nt=-1)
        r = np.array(trades)
        if len(r):
            print(f"  {symbol:9s}: угод={len(r):4d} exp={r.mean():+.3f}R (брутто) WR={(r>0).mean()*100:.0f}%")
        else:
            print(f"  {symbol:9s}: 0 угод")
    print("Очікувано: exp брутто ~+0.2..+0.5R, менше угод ніж раніше (пакет фільтрує).")

if __name__ == "__main__":
    main()
