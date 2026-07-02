"""Завантаження 15m OHLCV для ETH/SOL/BNB (Binance USDT-M ф'ючерси) — для 15m-істини.
ЗАПУСК НА VPS (з кореня репо):  venv/bin/python quant/data/fetch_15m_all.py
Період: від першого бара відповідного *_4h.csv до тепер (щоб span збігався 1:1).
Якщо файл уже є і великий — пропускає (можна перезапускати безпечно)."""
import ccxt, csv, os, time

EX = ccxt.binance({"options": {"defaultType": "future"}, "enableRateLimit": True})
JOBS = [("ETH/USDT", "quant/data/eth_4h.csv", "quant/data/eth_15m.csv"),
        ("SOL/USDT", "quant/data/sol_4h.csv", "quant/data/sol_15m.csv"),
        ("BNB/USDT", "quant/data/bnb_4h.csv", "quant/data/bnb_15m.csv")]

for sym, src4h, out in JOBS:
    if os.path.exists(out) and sum(1 for _ in open(out)) > 1000:
        print(f"{out}: вже є, пропускаю"); continue
    with open(src4h) as f:
        f.readline(); since = int(f.readline().split(",")[0])
    now = EX.milliseconds(); rows = []; nreq = 0
    print(f"{sym} 15m від {EX.iso8601(since)} ...")
    while since < now:
        for attempt in range(5):
            try:
                batch = EX.fetch_ohlcv(sym, "15m", since=since, limit=1500); break
            except Exception as e:
                print("  retry:", e); time.sleep(3*(attempt+1))
        else:
            raise SystemExit("не вдалось після 5 спроб")
        if not batch: break
        rows += batch; nreq += 1
        last = batch[-1][0]
        if last == since: break
        since = last + 1
        if nreq % 25 == 0: print(f"  {len(rows):7d} барів, останній {EX.iso8601(last)}")
    uniq = sorted({r[0]: r for r in rows}.values())
    with open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["ts", "open", "high", "low", "close", "vol"]); w.writerows(uniq)
    print(f"  Готово: {len(uniq)} барів -> {out}")
print("ВСЕ. Тепер:  venv/bin/python quant/78_truth_all_coins.py")
