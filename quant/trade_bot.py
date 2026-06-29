"""
АВТОМАТИЧНИЙ ТОРГОВИЙ БОТ — стратегія KC+FVG (Binance USDⓈ-M), з щоденним звітом у Telegram.

ПРАВИЛА (точно як у дослідженні):
  • Монети/двигуни: BTC,ETH,SOL = KC+FVG ; BNB = тільки FVG
  • ТФ 4h, дії ЛИШЕ на закритих барах (non-repaint)
  • Одна позиція на монету (бо два шорти на біржі зливаються)
  • KC: пробій каналу Кельтнера в бік EMA200 + ADX≥20 -> вхід МАРКЕТОМ
  • FVG: 3-барний імбаланс у бік EMA200 -> ЛІМІТКА на краю зони (мейкер), чекає ретест
  • Стоп = STOP-MARKET (гарантований вихід), Тейк = LIMIT (мейкер), RR 1:2
  • Розмір від РИЗИКУ: qty = equity*RISK_PCT / |entry-stop|   (плече саме виходить безпечним)

БЕЗПЕКА (за замовчуванням НІЧОГО реального не робить):
  • DRY_RUN=1  -> паперова торгівля (ніяких реальних ордерів)
  • TESTNET=1  -> якщо вимкнеш DRY_RUN, торгує на ТЕСТ-мережі Binance
  • Kill-switch: денний збиток > MAX_DAILY_LOSS -> зупинка + алерт
  • Реальні гроші тільки коли DRY_RUN=0 і TESTNET=0 і явно задані ключі.

РЕЖИМИ:
  python trade_bot.py run       # основний цикл (перевіряє закриття 4h-барів)
  python trade_bot.py once      # один прохід
  python trade_bot.py report    # надіслати щоденний звіт зараз
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

# ----------------------------- КОНФІГ ---------------------------------------
DRY_RUN     = os.getenv("BOT_DRY_RUN", "1") == "1"
TESTNET     = os.getenv("BOT_TESTNET", "1") == "1"
API_KEY     = os.getenv("BINANCE_KEY", "")
API_SECRET  = os.getenv("BINANCE_SECRET", "")
TG_TOKEN    = os.getenv("TG_TOKEN", "")
TG_CHAT     = os.getenv("TG_CHAT_ID", "")
RISK_PCT    = float(os.getenv("BOT_RISK", "0.01"))
MAX_DAILY_LOSS = float(os.getenv("BOT_MAX_DAILY_LOSS", "0.10"))
START_EQUITY = float(os.getenv("BOT_PAPER_EQUITY", "1000"))   # стартовий депозит для DRY_RUN
TF          = "4h"
RR          = 2.0
LEV_CAP     = 5.0
REPORT_HOUR_UTC = int(os.getenv("BOT_REPORT_HOUR", "8"))      # година UTC для звіту
NOTIFY_TRADES = os.getenv("BOT_NOTIFY_TRADES", "1") == "1"    # 1=слати кожну угоду (вхід/вихід)
STATE_FILE  = os.getenv("BOT_STATE", "bot_state.json")

# монета -> які двигуни; ccxt-символ Binance USDM
COINS = {
    "BTC/USDT": ["KC", "FVG"],
    "ETH/USDT": ["KC", "FVG"],
    "SOL/USDT": ["KC", "FVG"],
    "BNB/USDT": ["FVG"],          # на BNB KC слабкий -> лишаємо тільки FVG
}
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
    # --- KC: свіжий пробій у бік тренду + ADX ---
    if "KC" in engines and np.isfinite(px(ax, i)):
        def kc_state(k, side):
            if side > 0: return px(c, k) > px(up, k) and px(c, k) > px(trend, k) and px(ax, k) >= ADX_MIN
            return px(c, k) < px(lo, k) and px(c, k) < px(trend, k) and px(ax, k) >= ADX_MIN
        D = KC_STOP_X * px(a14, i); entry = px(c, i)   # вхід ≈ ціна закриття (далі маркет на відкритті)
        if kc_state(i, +1) and not kc_state(i - 1, +1):
            out.append(dict(engine="KC", side="long", typ="market",
                            entry=entry, stop=entry - D, target=entry + RR * D))
        if kc_state(i, -1) and not kc_state(i - 1, -1):
            out.append(dict(engine="KC", side="short", typ="market",
                            entry=entry, stop=entry + D, target=entry - RR * D))
    # --- FVG: новий 3-барний імбаланс у бік тренду -> лімітка на краю зони ---
    if "FVG" in engines and np.isfinite(px(a14, i)):
        if px(df["high"], i - 2) < px(df["low"], i) and px(c, i) > px(trend, i):
            zt, zb = px(df["low"], i), px(df["high"], i - 2)
            D = max(zt - zb, FVG_FLOOR * px(a14, i))
            out.append(dict(engine="FVG", side="long", typ="limit",
                            entry=zt, stop=zt - D, target=zt + RR * D))
        if px(df["low"], i - 2) > px(df["high"], i) and px(c, i) < px(trend, i):
            zt, zb = px(df["high"], i), px(df["low"], i - 2)
            D = max(zb - zt, FVG_FLOOR * px(a14, i))
            out.append(dict(engine="FVG", side="short", typ="limit",
                            entry=zt, stop=zt + D, target=zt - RR * D))
    return out

# ----------------------------- TELEGRAM -------------------------------------
def tg(msg):
    print("[TG]", msg.replace("\n", " | ")[:300])
    if not (TG_TOKEN and TG_CHAT): return
    try:
        data = urllib.parse.urlencode({"chat_id": TG_CHAT, "text": msg,
                                       "parse_mode": "HTML"}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                               data=data, timeout=15)
    except Exception as e:
        print("  TG помилка:", e)

# ----------------------------- СТАН -----------------------------------------
def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {"equity": START_EQUITY, "day": "", "day_start_equity": START_EQUITY,
            "halted": False, "pos": {}, "last_bar": {}, "trades": []}
def save_state(s): json.dump(s, open(STATE_FILE, "w"), indent=1, default=str)

# ----------------------------- БІРЖА ----------------------------------------
def make_exchange():
    if ccxt is None: raise RuntimeError("немає ccxt: pip install ccxt")
    ex = ccxt.binanceusdm({"apiKey": API_KEY, "secret": API_SECRET,
                           "enableRateLimit": True})
    if TESTNET: ex.set_sandbox_mode(True)
    return ex

def fetch_closed(ex, symbol, limit=320):
    o = ex.fetch_ohlcv(symbol, TF, limit=limit)
    df = pd.DataFrame(o, columns=["ts", "open", "high", "low", "close", "vol"])
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df.iloc[:-1].reset_index(drop=True)        # ДРОП незакритого бара

def equity_now(ex, st):
    if DRY_RUN: return st["equity"]
    try: return float(ex.fetch_balance()["USDT"]["total"])
    except Exception: return st["equity"]

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

def with_retry(fn, *a, tries=4, **k):
    for i in range(tries):
        try:
            return fn(*a, **k)
        except Exception:
            if i == tries - 1: raise
            time.sleep(2 ** i)

def load_markets_safe(ex):
    global _MARKETS_OK
    try:
        ex.load_markets(); _MARKETS_OK = True
    except Exception as e:
        print("  load_markets не вдалось (офлайн?) — запасні мінімуми:", e)

def limits_for(ex, symbol):
    if _MARKETS_OK:
        try:
            lim = ex.market(symbol).get("limits", {})
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
        qty = float(ex.amount_to_precision(symbol, qty)) if _MARKETS_OK else round(qty, 6)
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
            sym = p.get("symbol")
            if abs(amt) > 0 and sym in COINS and sym not in st["pos"]:
                st["pos"][sym] = dict(status="live", side="long" if amt > 0 else "short",
                                      engine="?", entry=float(p.get("entryPrice") or 0),
                                      stop=None, target=None, qty=abs(amt))
        tg(f"♻️ Reconcile: відкритих позицій на біржі {sum(1 for s in COINS if s in st['pos'])}")
    except Exception as e:
        print("reconcile помилка:", e)

# ----------------------------- ВИКОНАННЯ (live) -----------------------------
def place_live(ex, symbol, cand, qty):
    side = "buy" if cand["side"] == "long" else "sell"
    opp = "sell" if cand["side"] == "long" else "buy"
    try: ex.set_margin_mode("isolated", symbol)
    except Exception: pass
    try: ex.set_leverage(int(LEV_CAP), symbol)
    except Exception: pass
    q = float(ex.amount_to_precision(symbol, qty))
    if cand["typ"] == "market":
        ex.create_order(symbol, "market", side, q)
    else:  # FVG: пост-онлі лімітка на краю зони
        p = float(ex.price_to_precision(symbol, cand["entry"]))
        ex.create_order(symbol, "limit", side, q, p, {"timeInForce": "GTX"})
    # захисні ордери (reduceOnly): стоп = STOP_MARKET, тейк = LIMIT(мейкер)
    sp = float(ex.price_to_precision(symbol, cand["stop"]))
    tp = float(ex.price_to_precision(symbol, cand["target"]))
    ex.create_order(symbol, "STOP_MARKET", opp, q, None,
                    {"stopPrice": sp, "reduceOnly": True})
    ex.create_order(symbol, "limit", opp, q, tp, {"reduceOnly": True})

# ----------------------------- DRY-RUN симуляція фолу -----------------------
def dry_fill_and_manage(st, symbol, bar):
    """Паперова логіка: перевіряємо філ лімітки, спрацювання стопа/тейка по барі."""
    p = st["pos"].get(symbol)
    if not p: return
    hi, lo = bar["high"], bar["low"]; closed = None
    if p["status"] == "pending":              # лімітка FVG чекає фолу
        hit = lo <= p["entry"] if p["side"] == "long" else hi >= p["entry"]
        if hit:
            p["status"] = "in_pos"
            if NOTIFY_TRADES:
                tg(f"📥 Лімітка зайшла {symbol} {p['side'].upper()} @ {p['entry']:.4f} "
                   f"(стоп {p['stop']:.4f} / тейк {p['target']:.4f})")
        elif bar["i"] >= p["expiry_i"]:       # не зайшло -> скасувати
            st["pos"].pop(symbol)
            if NOTIFY_TRADES:
                tg(f"🚫 Лімітку скасовано {symbol} — не зайшло за {FVG_EXPIRY} барів")
            return
    if p.get("status") == "in_pos":
        if p["side"] == "long":
            if lo <= p["stop"]: closed = ("stop", p["stop"])
            elif hi >= p["target"]: closed = ("target", p["target"])
        else:
            if hi >= p["stop"]: closed = ("stop", p["stop"])
            elif lo <= p["target"]: closed = ("target", p["target"])
    if closed:
        reason, px = closed
        r = (px - p["entry"]) / (p["entry"] - p["stop"]) if p["side"] == "long" \
            else (p["entry"] - px) / (p["stop"] - p["entry"])
        pnl = st["equity"] * RISK_PCT * r
        st["equity"] += pnl
        st["trades"].append(dict(t=str(bar["dt"]), sym=symbol, eng=p["engine"],
                                 side=p["side"], r=round(r, 2), pnl=round(pnl, 2),
                                 reason=reason))
        st["pos"].pop(symbol)
        if NOTIFY_TRADES:
            emo = "✅" if r > 0 else "❌"
            tg(f"{emo} <b>Закрито {symbol} {p['side'].upper()}</b> ({p['engine']}) — {reason}\n"
               f"R {r:+.2f} | PnL {pnl:+.2f} USDT | депозит {st['equity']:.2f}")

# ----------------------------- ОБРОБКА ОДНОГО БАРА ---------------------------
def handle_symbol(ex, st, symbol, df):
    bar = {"i": len(df) - 1, "dt": df["dt"].iloc[-1],
           "high": df["high"].iloc[-1], "low": df["low"].iloc[-1]}
    if DRY_RUN: dry_fill_and_manage(st, symbol, bar)     # спершу ведемо відкриті
    if symbol in st["pos"]:                               # одна позиція на монету
        return
    cands = detect(df, COINS[symbol])
    if not cands: return
    cand = cands[0]                                       # перший сигнал бере слот
    eq = equity_now(ex, st)
    qty = position_qty(eq, cand["entry"], cand["stop"])
    qty = valid_size(ex, symbol, qty, cand["entry"])      # мінімуми біржі: краще пропустити, ніж оверризик
    if not qty:
        print(f"  [skip] {symbol}: розмір нижчий за мінімум біржі — мало капіталу для цього стопа")
        return
    lev = cand["entry"] * qty / eq
    msg = (f"{'🟢' if cand['side']=='long' else '🔴'} <b>{cand['engine']} "
           f"{cand['side'].upper()}</b> {symbol}\n"
           f"вхід({cand['typ']}) {cand['entry']:.4f} | стоп {cand['stop']:.4f} | "
           f"тейк {cand['target']:.4f}\nрозмір {qty:.4f} (плече ~{lev:.1f}x, ризик {RISK_PCT*100:.1f}%)")
    if DRY_RUN:
        st["pos"][symbol] = dict(status=("pending" if cand["typ"] == "limit" else "in_pos"),
                                 engine=cand["engine"], side=cand["side"],
                                 entry=cand["entry"], stop=cand["stop"], target=cand["target"],
                                 qty=qty, expiry_i=bar["i"] + FVG_EXPIRY)
        if NOTIFY_TRADES:
            tag = "⏳ Виставлено лімітку " if cand["typ"] == "limit" else "📥 Вхід "
            tg("[DRY] " + tag + "\n" + msg)
    else:
        try:
            place_live(ex, symbol, cand, qty)
            st["pos"][symbol] = dict(status="live", engine=cand["engine"], side=cand["side"],
                                     entry=cand["entry"], stop=cand["stop"], target=cand["target"], qty=qty)
            if NOTIFY_TRADES: tg("✅ " + msg)
        except Exception as e:
            tg(f"⚠️ помилка ордера {symbol}: {e}")

# ----------------------------- KILL-SWITCH + ЗВІТ ---------------------------
def check_day_and_killswitch(st, eq):
    today = dt.datetime.utcnow().strftime("%Y-%m-%d")
    if st["day"] != today:
        st["day"] = today; st["day_start_equity"] = eq; st["halted"] = False
    dd = (eq - st["day_start_equity"]) / st["day_start_equity"] if st["day_start_equity"] else 0
    if dd <= -MAX_DAILY_LOSS and not st["halted"]:
        st["halted"] = True
        tg(f"🛑 KILL-SWITCH: денний збиток {dd*100:.1f}% > ліміту {MAX_DAILY_LOSS*100:.0f}%. "
           f"Нові входи зупинено до завтра.")
    return st["halted"]

def daily_report(st, eq):
    since = dt.datetime.utcnow() - dt.timedelta(hours=24)
    rec = [t for t in st["trades"] if pd.Timestamp(t["t"]).to_pydatetime().replace(tzinfo=None) >= since]
    nr = len(rec); wins = sum(1 for t in rec if t["r"] > 0)
    sumR = sum(t["r"] for t in rec); pnl = sum(t["pnl"] for t in rec)
    openp = "; ".join(f"{k.split('/')[0]} {v['side']}({v['engine']})" for k, v in st["pos"].items()) or "немає"
    wr = f"{wins/nr*100:.0f}%" if nr else "—"
    lines = [f"📊 <b>Денний звіт</b> {dt.datetime.utcnow():%Y-%m-%d %H:%M}Z",
             f"Депозит: <b>{eq:.2f}</b> USDT  ({'DRY' if DRY_RUN else ('TESTNET' if TESTNET else 'LIVE')})",
             f"За 24г: угод {nr}, WR {wr}, сума {sumR:+.2f}R, PnL {pnl:+.2f} USDT",
             f"Відкриті: {openp}",
             f"Всього угод у журналі: {len(st['trades'])}",
             f"Бенчмарк: очікування ≈ +0.2R/угода (якщо за 30+ угод нижче 0 — стоп)"]
    if st.get("halted"): lines.append("🛑 СЬОГОДНІ ЗУПИНЕНО (kill-switch)")
    tg("\n".join(lines))

# ----------------------------- ЦИКЛ -----------------------------------------
def run_once(ex, st, force_report=False):
    eq = equity_now(ex, st)
    halted = check_day_and_killswitch(st, eq)
    for symbol in COINS:
        try:
            df = with_retry(fetch_closed, ex, symbol)
        except Exception as e:
            print(f"  fetch {symbol}: {e}"); continue
        last = str(df["dt"].iloc[-1])
        if st["last_bar"].get(symbol) == last and not force_report:
            # бар не новий — лише ведемо відкриті паперові позиції
            if DRY_RUN:
                handle_symbol_manage_only(st, symbol, df)
            continue
        st["last_bar"][symbol] = last
        if halted:                       # стоп-вхід, але відкриті ведемо
            if DRY_RUN: handle_symbol_manage_only(st, symbol, df)
            continue
        handle_symbol(ex, st, symbol, df)
    save_state(st)

def handle_symbol_manage_only(st, symbol, df):
    bar = {"i": len(df) - 1, "dt": df["dt"].iloc[-1],
           "high": df["high"].iloc[-1], "low": df["low"].iloc[-1]}
    dry_fill_and_manage(st, symbol, bar)

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
    ex = make_exchange()
    load_markets_safe(ex)
    reconcile(ex, st)
    if mode == "once":
        run_once(ex, st); daily_report(st, equity_now(ex, st)); return
    if mode == "report":
        daily_report(st, equity_now(ex, st)); return
    # mode == run: цикл
    tg(f"🤖 Бот запущено ({banner})")
    last_report_day = ""
    while True:
        try:
            run_once(ex, st)
            now = dt.datetime.utcnow()
            if now.hour == REPORT_HOUR_UTC and now.strftime("%Y-%m-%d") != last_report_day:
                daily_report(st, equity_now(ex, st)); last_report_day = now.strftime("%Y-%m-%d")
        except Exception as e:
            print("loop помилка:", e)
        time.sleep(60)

# ----------------------------- ОФЛАЙН SELF-TEST -----------------------------
def selftest():
    """Прогін стратегії бота на локальних CSV (без біржі) — перевірка правильності логіки."""
    print("\n=== SELF-TEST (офлайн, локальні дані) ===")
    files = {"BTC/USDT": "quant/data/btc_15m.csv", "ETH/USDT": "quant/data/eth_4h.csv",
             "SOL/USDT": "quant/data/sol_4h.csv", "BNB/USDT": "quant/data/bnb_4h.csv"}
    st = {"equity": START_EQUITY, "trades": [], "pos": {}}
    for symbol, path in files.items():
        if not os.path.exists(path):
            print(f"  {symbol}: немає {path}, пропуск"); continue
        raw = pd.read_csv(path)
        # BTC файл 15m -> ресемпл у 4h
        raw["dt"] = pd.to_datetime(raw["ts"], unit="ms", utc=True)
        d = raw.set_index("dt")
        if "btc_15m" in path:
            d = d.resample("4h").agg({"open": "first", "high": "max", "low": "min",
                                      "close": "last"}).dropna()
        d = d.reset_index()
        eng = COINS[symbol]; pos = None; trades = []
        # подієвий прогін бар-за-баром
        for i in range(EMA_TREND + 5, len(d)):
            sub = d.iloc[:i + 1]
            bar = d.iloc[i]
            if pos:  # ведемо відкриту
                if pos["status"] == "pending":
                    hit = bar["low"] <= pos["entry"] if pos["side"] == "long" else bar["high"] >= pos["entry"]
                    if hit: pos["status"] = "in_pos"
                    elif i >= pos["expiry_i"]: pos = None
                if pos and pos["status"] == "in_pos":
                    if pos["side"] == "long":
                        ex_ = pos["stop"] if bar["low"] <= pos["stop"] else (pos["target"] if bar["high"] >= pos["target"] else None)
                    else:
                        ex_ = pos["stop"] if bar["high"] >= pos["stop"] else (pos["target"] if bar["low"] <= pos["target"] else None)
                    if ex_ is not None:
                        r = (ex_ - pos["entry"]) / (pos["entry"] - pos["stop"]) if pos["side"] == "long" \
                            else (pos["entry"] - ex_) / (pos["stop"] - pos["entry"])
                        trades.append(r); pos = None
            if pos: continue
            cands = detect(sub, eng)
            if cands:
                c = cands[0]
                pos = dict(status=("pending" if c["typ"] == "limit" else "in_pos"),
                           side=c["side"], entry=c["entry"], stop=c["stop"],
                           target=c["target"], expiry_i=i + FVG_EXPIRY)
        r = np.array(trades)
        if len(r):
            print(f"  {symbol:9s}: угод={len(r):4d} exp={r.mean():+.3f}R WR={(r>0).mean()*100:.0f}%")
        else:
            print(f"  {symbol:9s}: 0 угод")
    print("Очікувано: exp у плюсі (~+0.1..+0.3R) -> логіка бота збігається з бектестом.")

if __name__ == "__main__":
    main()
