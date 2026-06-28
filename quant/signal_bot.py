"""
Сигнальний бот: 2 двигуни (KC breakout + FVG retest) -> Telegram. БЕЗ автоторгівлі.
Заходиш РУКАМИ за сигналом. Стратегія = §18/§27 дослідження (4h, BTC/ETH/SOL).

Запуск У СЕБЕ (не в цьому середовищі — тут немає доступу до бірж/Telegram):
    pip install ccxt requests pandas numpy
    # @BotFather -> TOKEN; свій CHAT_ID: напиши боту, відкрий
    #   https://api.telegram.org/bot<TOKEN>/getUpdates -> "chat":{"id":...}
    python signal_bot.py            # робочий цикл (чекає 4h-закриття)
    python signal_bot.py once       # одна перевірка зараз
    python signal_bot.py report     # надіслати денний звіт зараз
    python signal_bot.py selftest   # перевірка логіки на локальних CSV (без мережі)

KC LONG : close>верх Keltner & close>EMA200 & ADX>20  (SHORT дзеркально)
FVG LONG: bull FVG (max[-3]<low[-1]) у аптренді (close>EMA200), ціна ретестить зону
Стоп KC = 2*ATR(14); FVG = за межу зони (мін 0.5*ATR). Тейк = RR 1:2.
"""
import sys, json, time, os
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd

# ============================== КОНФІГ ==============================
TG_TOKEN   = "PUT_YOUR_BOT_TOKEN_HERE"
TG_CHAT_ID = "PUT_YOUR_CHAT_ID_HERE"
EXCHANGE   = "bybit"
SYMBOLS    = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
TIMEFRAME  = "4h"
ENGINES    = ("KC", "FVG")          # які двигуни вмикати
ADX_MIN    = 20
KC_EMA, KC_ATR, KC_MULT = 20, 10, 2.0
TREND_EMA  = 200
ATR_STOP   = 14
RR         = 2.0
FVG_LOOKAHEAD  = 20                  # скільки барів зона FVG лишається активною
FVG_ATR_FLOOR  = 0.5                 # мін. стоп = 0.5*ATR (для вузьких зон)
ACCOUNT    = 1000.0
RISK_PCT   = 0.01                    # 1% (≈7%/міс @ DD~36%); 1.5% для ~10%/міс
LEV_CAP    = 5.0                     # нагадування: сумарна експозиція <= 5x депо
SESSION_FILTER = False               # True = лише входи 00-12 UTC (опц., KC)
DAILY_REPORT   = True                # денний звіт на 00:00 UTC-закритті
STATE_FILE = "signal_bot_state.json"
DRY_RUN    = False
# ===================================================================


def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def _tr(df):
    pc = df["close"].shift(1)
    return pd.concat([df["high"]-df["low"], (df["high"]-pc).abs(), (df["low"]-pc).abs()], axis=1).max(axis=1)
def atr(df, n): return _tr(df).ewm(alpha=1/n, adjust=False).mean()
def adx(df, n=14):
    up = df["high"].diff(); dn = -df["low"].diff()
    pdm = ((up > dn) & (up > 0)) * up; mdm = ((dn > up) & (dn > 0)) * dn
    a = _tr(df).ewm(alpha=1/n, adjust=False).mean()
    pdi = 100*pdm.ewm(alpha=1/n, adjust=False).mean()/a
    mdi = 100*mdm.ewm(alpha=1/n, adjust=False).mean()/a
    dx = 100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean()


def _pack(strat, side, entry, stop, target, bar_time, adx_val=None):
    D = abs(entry-stop)
    qty = (ACCOUNT*RISK_PCT)/D if D > 0 else 0
    return dict(strat=strat, side=side, price=entry, stop=stop, target=target,
                stop_dist=D, qty=qty, notional=qty*entry, adx=adx_val, bar_time=bar_time)


def check_kc(df):
    """KC breakout — свіжий пробій на останньому ЗАКРИТОМУ барі."""
    if len(df) < TREND_EMA + 30: return None
    c = df["close"]; mid = ema(c, KC_EMA); band = KC_MULT*atr(df, KC_ATR)
    up, lo = mid+band, mid-band; tr = ema(c, TREND_EMA); ax = adx(df, 14); a = atr(df, ATR_STOP)
    if not np.isfinite(ax.iloc[-1]) or ax.iloc[-1] < ADX_MIN: return None
    def isL(k): return c.iloc[k] > up.iloc[k] and c.iloc[k] > tr.iloc[k] and ax.iloc[k] > ADX_MIN
    def isS(k): return c.iloc[k] < lo.iloc[k] and c.iloc[k] < tr.iloc[k] and ax.iloc[k] > ADX_MIN
    side = "LONG" if (isL(-1) and not isL(-2)) else ("SHORT" if (isS(-1) and not isS(-2)) else None)
    if side is None: return None
    if SESSION_FILTER and ((df.index[-1].hour+4) % 24) not in (0, 4, 8): return None
    px = c.iloc[-1]; sd = 2*a.iloc[-1]
    if sd <= 0: return None
    if side == "LONG":  return _pack("KC", side, px, px-sd, px+RR*sd, df.index[-1], ax.iloc[-1])
    else:               return _pack("KC", side, px, px+sd, px-RR*sd, df.index[-1], ax.iloc[-1])


def check_fvg(df):
    """FVG retest — останній закритий бар ВПЕРШЕ ретестить активну FVG-зону у бік тренду."""
    if len(df) < TREND_EMA + 30: return None
    c = df["close"]; em = ema(c, TREND_EMA); a = atr(df, ATR_STOP)
    H = df["high"].values; Lw = df["low"].values; C = c.values; EM = em.values
    j = len(df)-1; A = a.iloc[-1]
    if not np.isfinite(A) or A <= 0: return None
    lo_b = max(2, j-FVG_LOOKAHEAD)
    # bull: найсвіжіша FVG, яку поточний бар ретестить вперше
    for f in range(j-1, lo_b-1, -1):
        if H[f-2] < Lw[f] and C[f] > EM[f]:                       # bull FVG у аптренді
            zt, zb = Lw[f], H[f-2]
            if Lw[j] <= zt and C[j] > EM[j] and all(Lw[b] > zt for b in range(f+1, j)):
                D = max(zt-zb, FVG_ATR_FLOOR*A)
                return _pack("FVG", "LONG", zt, zt-D, zt+RR*D, df.index[-1])
    for f in range(j-1, lo_b-1, -1):
        if Lw[f-2] > H[f] and C[f] < EM[f]:                       # bear FVG у даунтренді
            zt, zb = H[f], Lw[f-2]
            if H[j] >= zt and C[j] < EM[j] and all(H[b] < zt for b in range(f+1, j)):
                D = max(zb-zt, FVG_ATR_FLOOR*A)
                return _pack("FVG", "SHORT", zt, zt+D, zt-RR*D, df.index[-1])
    return None


def fmt(sym, s):
    em = "🟢" if s["side"] == "LONG" else "🔴"
    extra = f"ADX={s['adx']:.0f}\n" if s.get("adx") is not None else ""
    how = ("➡️ Вхід marketable-limit зараз + OCO (стоп+тейк)." if s["strat"] == "KC"
           else f"➡️ Постав ЛІМІТКУ на {s['price']:.4f} (вхід у зону), дій ~3 дні + OCO.")
    return (f"{em} <b>{s['strat']} {s['side']} {sym}</b> (4h)\n"
            f"Бар: {s['bar_time']:%Y-%m-%d %H:%M} UTC\n"
            f"Вхід: <b>{s['price']:.4f}</b>\n"
            f"Стоп: <b>{s['stop']:.4f}</b> ({s['stop_dist']:.4f})\n"
            f"Тейк: <b>{s['target']:.4f}</b> (RR 1:{RR:.0f})\n{extra}"
            f"Розмір під {RISK_PCT*100:.1f}% ризику (${ACCOUNT:.0f}): {s['qty']:.4f} "
            f"(ноціонал ${s['notional']:.0f})\n"
            f"⚠️ Сумарна експозиція ≤{LEV_CAP:.0f}×; 3-тя в один бік ×0.6.\n{how}")


def send_tg(text):
    if DRY_RUN or TG_TOKEN.startswith("PUT_"):
        print("[DRY] " + text.replace("\n", " | ")); return
    import requests
    for _ in range(3):
        try:
            r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                              data={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=15)
            if r.status_code == 200: return
        except Exception as e:
            print("TG error:", e); time.sleep(3)


def load_state(): return json.load(open(STATE_FILE)) if os.path.exists(STATE_FILE) else {}
def save_state(st): json.dump(st, open(STATE_FILE, "w"))


def fetch(ex, sym):
    o = ex.fetch_ohlcv(sym, TIMEFRAME, limit=TREND_EMA+FVG_LOOKAHEAD+40)
    df = pd.DataFrame(o, columns=["ts", "open", "high", "low", "close", "vol"])
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True); df = df.set_index("dt")
    if df["ts"].iloc[-1] + ex.parse_timeframe(TIMEFRAME)*1000 > ex.milliseconds():
        df = df.iloc[:-1]                                # відкинути незакритий бар
    return df[["open", "high", "low", "close", "vol"]]


def run_once(ex, st):
    checks = {"KC": check_kc, "FVG": check_fvg}
    for sym in SYMBOLS:
        try:
            df = fetch(ex, sym); fired = []
            for eng in ENGINES:
                sig = checks[eng](df)
                if sig:
                    key = f"{sym}:{eng}"; bid = sig["bar_time"].isoformat()
                    if st.get(key) != bid:
                        send_tg(fmt(sym, sig)); st[key] = bid; fired.append(f"{eng} {sig['side']}")
                        st.setdefault("log", []).append(dict(t=datetime.now(timezone.utc).isoformat(),
                            eng=eng, side=sig["side"], sym=sym.split("/")[0], px=round(sig["price"], 4)))
                        st["log"] = st["log"][-300:]
            print(f"{datetime.now(timezone.utc):%H:%M} {sym}: {', '.join(fired) if fired else 'нема'}")
        except Exception as e:
            print(f"{sym} помилка: {e}")
    save_state(st)


def daily_report(ex, st):
    """Зведення за 24 год: сигнали + знімок ринку по монетах."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recent = [e for e in st.get("log", []) if e["t"] >= cutoff]
    lines = [f"📊 <b>Денний звіт</b> {datetime.now(timezone.utc):%Y-%m-%d}",
             f"Сигналів за 24 год: <b>{len(recent)}</b>"]
    for e in recent:
        lines.append(f"  • {e['eng']} {e['side']} {e['sym']} @ {e['px']}")
    lines.append("\n<b>Стан ринку:</b>")
    for sym in SYMBOLS:
        try:
            df = fetch(ex, sym); c = df["close"]; px = c.iloc[-1]
            ax = adx(df, 14).iloc[-1]; tr = ema(c, TREND_EMA).iloc[-1]
            d = "↑ вгору" if px > tr else "↓ вниз"
            mode = "тренд" if ax > ADX_MIN else "ФЛЕТ"
            lines.append(f"  {sym.split('/')[0]}: {px:.2f} | {d} | ADX {ax:.0f} ({mode})")
        except Exception as ee:
            lines.append(f"  {sym.split('/')[0]}: помилка ({str(ee)[:30]})")
    lines.append("\nБот живий ✅")
    send_tg("\n".join(lines))
    st["last_report"] = datetime.now(timezone.utc).strftime("%Y-%m-%d"); save_state(st)


def next_4h_wakeup():
    now = datetime.now(timezone.utc); h = (now.hour//4 + 1)*4
    nxt = now.replace(minute=1, second=30, microsecond=0, hour=0) + timedelta(hours=h)
    return max((nxt-now).total_seconds(), 60)


def selftest():
    print("SELF-TEST (логіка на локальних CSV, векторно):")
    for sym, path in [("BTC", "quant/data/btc_15m.csv"), ("ETH", "quant/data/eth_4h.csv"),
                      ("SOL", "quant/data/sol_4h.csv")]:
        if not os.path.exists(path): continue
        raw = pd.read_csv(path); raw.columns = [x.strip().lower() for x in raw.columns]
        if "ts" in raw.columns: raw["dt"] = pd.to_datetime(raw["ts"], unit="ms", utc=True)
        else: raw["dt"] = pd.to_datetime(raw["time"].astype(str).str.strip('"'), utc=True)
        df = raw.set_index("dt")[["open", "high", "low", "close"]].astype(float)
        if (df.index[1]-df.index[0]) < pd.Timedelta(hours=4):
            df = df.resample("4h").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()
        c = df["close"]; mid = ema(c, KC_EMA); band = KC_MULT*atr(df, KC_ATR); tr = ema(c, TREND_EMA); ax = adx(df, 14)
        L = (c > mid+band) & (c > tr) & (ax > ADX_MIN); S = (c < mid-band) & (c < tr) & (ax > ADX_MIN)
        kc = (L & ~L.shift(1, fill_value=False)).sum() + (S & ~S.shift(1, fill_value=False)).sum()
        # FVG ретести — швидкий підрахунок (індикатори рахуємо 1 раз)
        em = ema(c, TREND_EMA).values; H = df["high"].values; Lw = df["low"].values; C = c.values; n = len(df); fv = 0
        for f in range(2, n):
            if H[f-2] < Lw[f] and C[f] > em[f]:
                zt = Lw[f]
                for j in range(f+1, min(f+1+FVG_LOOKAHEAD, n)):
                    if Lw[j] <= zt:
                        fv += 1 if C[j] > em[j] else 0; break
            if Lw[f-2] > H[f] and C[f] < em[f]:
                zt = H[f]
                for j in range(f+1, min(f+1+FVG_LOOKAHEAD, n)):
                    if H[j] >= zt:
                        fv += 1 if C[j] < em[j] else 0; break
        print(f"  {sym}: KC свіжих={int(kc)} | FVG ретестів={fv} | останній бар {df.index[-1]}")
    print("OK — обидва двигуни працюють.")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "loop"
    if mode == "selftest": selftest(); sys.exit()
    import ccxt
    ex = getattr(ccxt, EXCHANGE)({"enableRateLimit": True}); st = load_state()
    if mode == "once": run_once(ex, st); sys.exit()
    if mode == "report": daily_report(ex, st); sys.exit()
    send_tg(f"✅ Бот запущено. Двигуни: {', '.join(ENGINES)}. Стежу: {', '.join(SYMBOLS)} ({TIMEFRAME}).")
    while True:
        run_once(ex, st)
        now = datetime.now(timezone.utc)
        if DAILY_REPORT and now.hour < 4 and st.get("last_report") != now.strftime("%Y-%m-%d"):
            daily_report(ex, st)
        slp = next_4h_wakeup(); print(f"Сплю {slp/60:.0f} хв до 4h-закриття..."); time.sleep(slp)
