"""ДІАГНОСТИКА ДАНИХ: чому на демо майже нема сигналів?
Порівнює ЩІЛЬНІСТЬ сетапів на TESTNET (що бачить бот) з очікуванням бектесту.
ЗАПУСК НА VPS (з кореня репо, з ключами):
  set -a && . ./bot.env && set +a && venv/bin/python quant/diag_data.py

Що показує по кожній монеті:
  • скільки барів реально віддає testnet, діапазон дат, чи СВІЖІ дані, чи є ДІРИ;
  • скільки KC-пробоїв і FVG-зон за доступний період і В ПЕРЕРАХУНКУ НА МІСЯЦЬ;
  • РЕАЛЬНІ входи live-логіки на цих же даних (одна поз/монету, KC-перехоплення).
Порівняння: бектест мейннету = ~8.6 входів/міс (ETH+SOL). Якщо testnet дає
різко менше — причина «тиші» в ДАНИХ демо, а не в стратегії."""
import sys, time
import pandas as pd, numpy as np
import importlib.util, os
spec = importlib.util.spec_from_file_location("tb", os.path.join(os.path.dirname(__file__), "trade_bot.py"))
tb = importlib.util.module_from_spec(spec); spec.loader.exec_module(tb)

def fetch_all(ex, sym, days=400):
    """Тягне 4h історію з пагінацією (скільки testnet узагалі має)."""
    since = ex.milliseconds() - days*24*3600*1000
    rows = []
    while True:
        for attempt in range(4):
            try:
                b = ex.fetch_ohlcv(tb.M(sym), "4h", since=since, limit=1500); break
            except Exception as e:
                print("  retry:", str(e)[:80]); time.sleep(2*(attempt+1))
        else:
            break
        if not b: break
        rows += b
        if b[-1][0] == since or len(b) < 2: break
        since = b[-1][0] + 1
        if len(rows) > 20000: break
    uniq = sorted({r[0]: r for r in rows}.values())
    d = pd.DataFrame(uniq, columns=["ts","open","high","low","close","vol"])
    d["dt"] = pd.to_datetime(d["ts"], unit="ms", utc=True)
    return d.iloc[:-1].reset_index(drop=True)      # дроп незакритого

def live_backtest(d, engines=("KC","FVG")):
    """1-в-1 з машиною станів бота (одна поз/монету, KC-перехоплення)."""
    n = len(d)
    if n < tb.EMA_TREND + 10: return pd.DataFrame(columns=["t","eng","R"])
    c = d["close"]; h = d["high"]; l = d["low"]
    mid = tb.ema(c, tb.KC_EMA); band = tb.KC_MULT*tb.atr(d, tb.KC_ATR); up = mid+band; lo = mid-band
    trend = tb.ema(c, tb.EMA_TREND); ax = tb.adx(d, tb.ADX_LEN); a14 = tb.atr(d, tb.STOP_ATR)
    up,lo,trend,ax,a14 = [x.to_numpy() for x in (up,lo,trend,ax,a14)]
    c = c.to_numpy(); h = h.to_numpy(); l = l.to_numpy(); dt = d["dt"]
    def kc(k, side):
        if side > 0: return c[k] > up[k] and c[k] > trend[k] and ax[k] >= tb.ADX_MIN
        return c[k] < lo[k] and c[k] < trend[k] and ax[k] >= tb.ADX_MIN
    pos = None; tr = []
    for i in range(tb.EMA_TREND+5, n):
        if pos and pos["st"] == "in_pos":
            if pos["side"] == "long": hs = l[i] <= pos["stop"]; ht = h[i] >= pos["tgt"] and i > pos["nt"]
            else: hs = h[i] >= pos["stop"]; ht = l[i] <= pos["tgt"] and i > pos["nt"]
            if hs: tr.append((dt[i], pos["eng"], -1.0)); pos = None
            elif ht: tr.append((dt[i], pos["eng"], tb.RR)); pos = None
        elif pos and pos["st"] == "watch":
            pos["w"] += 1
            t = l[i] <= pos["entry"] if pos["side"] == "long" else h[i] >= pos["entry"]
            if t: pos = None
            elif pos["w"] >= tb.FVG_WAIT:
                D = max(abs(pos["entry"]-pos["zb"]), tb.FVG_FLOOR*a14[i]); s = 1 if pos["side"] == "long" else -1
                pos.update(stop=pos["entry"]-s*D, tgt=pos["entry"]+s*tb.RR*D, st="pending")
        elif pos and pos["st"] == "pending":
            pos["w"] += 1
            if pos["w"] >= tb.FVG_EXPIRY: pos = None
            else:
                t = l[i] <= pos["entry"] if pos["side"] == "long" else h[i] >= pos["entry"]
                if t:
                    okc = (c[i] > trend[i]) if pos["side"] == "long" else (c[i] < trend[i])
                    if okc and np.isfinite(ax[i]) and ax[i] >= tb.ADX_MIN:
                        pos["st"] = "in_pos"; pos["nt"] = i
                        hs = l[i] <= pos["stop"] if pos["side"] == "long" else h[i] >= pos["stop"]
                        if hs: tr.append((dt[i], pos["eng"], -1.0)); pos = None
                    else: pos = None
        if pos and pos["st"] in ("watch", "pending"):
            D = tb.KC_STOP_X*a14[i]
            for side, sd in [("long", 1), ("short", -1)]:
                if "KC" in engines and kc(i, sd) and not kc(i-1, sd):
                    pos = dict(st="in_pos", side=side, eng="KC", entry=c[i],
                               stop=c[i]-sd*D, tgt=c[i]+sd*tb.RR*D, nt=i); break
        if pos: continue
        D = tb.KC_STOP_X*a14[i]; np_ = None
        if "KC" in engines:
            if kc(i, 1) and not kc(i-1, 1): np_ = dict(st="in_pos", side="long", eng="KC", entry=c[i], stop=c[i]-D, tgt=c[i]+tb.RR*D, nt=i)
            elif kc(i, -1) and not kc(i-1, -1): np_ = dict(st="in_pos", side="short", eng="KC", entry=c[i], stop=c[i]+D, tgt=c[i]-tb.RR*D, nt=i)
        if np_ is None and "FVG" in engines and np.isfinite(a14[i]):
            if h[i-2] < l[i] and c[i] > trend[i]:
                np_ = dict(st="watch", side="long", eng="FVG", entry=(l[i]+h[i-2])/2, zb=h[i-2], w=0)
            elif l[i-2] > h[i] and c[i] < trend[i]:
                np_ = dict(st="watch", side="short", eng="FVG", entry=(h[i]+l[i-2])/2, zb=l[i-2], w=0)
        pos = np_
    return pd.DataFrame(tr, columns=["t", "eng", "R"])

def main():
    ex = tb.make_exchange(); tb.load_markets_safe(ex)
    api = ex.urls.get("api", {}); url = api.get("fapiPublic") if isinstance(api, dict) else api
    print(f"Джерело даних: {'TESTNET (демо)' if tb.TESTNET else 'MAINNET'} -> {url}")
    print(f"Порівняння: бектест мейннету ETH+SOL = ~8.6 входів/міс (медіана 9, найгірше 2-міс вікно = 8).\n")
    for sym in tb.COINS:
        try:
            d = fetch_all(ex, sym)
        except Exception as e:
            print(f"{sym}: ПАДАЄ -> {e}\n"); continue
        if len(d) == 0: print(f"{sym}: 0 барів!\n"); continue
        span_days = (d["dt"].iloc[-1] - d["dt"].iloc[0]).days
        span_mo = max(span_days/30.44, 0.1)
        age_h = (pd.Timestamp.utcnow() - d["dt"].iloc[-1]).total_seconds()/3600
        # діри: скільки пропущених 4h-барів
        gaps = ((d["ts"].diff().dropna()/(4*3600*1000)).round() - 1).clip(lower=0)
        c = d["close"]
        mid = tb.ema(c, tb.KC_EMA); band = tb.KC_MULT*tb.atr(d, tb.KC_ATR); up = mid+band; lo = mid-band
        trend = tb.ema(c, tb.EMA_TREND); ax = tb.adx(d, tb.ADX_LEN); h = d["high"]; l = d["low"]
        kcL = (c > up) & (c > trend) & (ax >= tb.ADX_MIN); kcS = (c < lo) & (c < trend) & (ax >= tb.ADX_MIN)
        kcf = int((kcL & ~kcL.shift(1, fill_value=False)).sum() + (kcS & ~kcS.shift(1, fill_value=False)).sum())
        fvg = int(((h.shift(2) < l) & (c > trend)).sum() + ((l.shift(2) > h) & (c < trend)).sum())
        T = live_backtest(d)
        print(f"=== {sym} ===")
        print(f"  барів {len(d)} | {str(d['dt'].iloc[0])[:16]} .. {str(d['dt'].iloc[-1])[:16]} "
              f"(~{span_days}д = {span_mo:.1f} міс)")
        print(f"  свіжість: останній бар {age_h:.1f}г тому " + ("✅" if age_h < 8 else "⚠️ СТАРІ ДАНІ!"))
        print(f"  пропущених барів (діри): {int(gaps.sum())} " + ("✅" if gaps.sum() < 5 else "⚠️ ДІРЯВІ ДАНІ!"))
        print(f"  ADX>=20 на {int((ax >= tb.ADX_MIN).sum())}/{len(d)} барах ({(ax>=tb.ADX_MIN).mean()*100:.0f}%)")
        print(f"  СИРІ кандидати: KC-пробоїв {kcf} ({kcf/span_mo:.2f}/міс) | FVG-зон {fvg} ({fvg/span_mo:.2f}/міс)")
        print(f"  РЕАЛЬНИХ входів (live-логіка): {len(T)} ({len(T)/span_mo:.2f}/міс) "
              f"| KC {int((T.eng=='KC').sum())} | FVG {int((T.eng=='FVG').sum())}")
        print(f"     -> очікували ~4.3/міс на монету; тут {len(T)/span_mo:.2f}/міс "
              + ("✅ у нормі" if len(T)/span_mo >= 2 else "⛔ РІЗКО МЕНШЕ -> дані демо винні") + "\n")
    print("Висновок: якщо '/міс' на testnet різко нижче мейннету -> демо-дані не")
    print("відтворюють ринок, і 'тиша' — артефакт testnet, а не поломка/стратегія.")

if __name__ == "__main__":
    main()
