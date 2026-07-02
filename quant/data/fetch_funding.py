"""Історія funding rate (Binance USDT-M perp) для BTC/ETH/SOL/BNB.
ЗАПУСК НА VPS (з кореня репо):  venv/bin/python quant/data/fetch_funding.py
Зберігає quant/data/{coin}_funding.csv (ts,rate). Швидко: ~7-10 запитів/монету."""
import ccxt, csv, os, time

EX = ccxt.binance({"options": {"defaultType": "future"}, "enableRateLimit": True})
JOBS = [("BTC/USDT", "quant/data/btc_funding.csv"), ("ETH/USDT", "quant/data/eth_funding.csv"),
        ("SOL/USDT", "quant/data/sol_funding.csv"), ("BNB/USDT", "quant/data/bnb_funding.csv")]

for sym, out in JOBS:
    if os.path.exists(out) and sum(1 for _ in open(out)) > 500:
        print(f"{out}: вже є, пропускаю"); continue
    since = EX.parse8601("2019-09-01T00:00:00Z"); rows = []
    print(f"{sym} funding ...")
    while True:
        for attempt in range(5):
            try:
                batch = EX.fetch_funding_rate_history(sym, since=since, limit=1000); break
            except Exception as e:
                print("  retry:", e); time.sleep(3*(attempt+1))
        else:
            raise SystemExit("не вдалось після 5 спроб")
        if not batch: break
        rows += [(b["timestamp"], b["fundingRate"]) for b in batch]
        last = batch[-1]["timestamp"]
        if last == since or len(batch) < 100: break
        since = last + 1
    uniq = sorted({t: (t, r) for t, r in rows}.values())
    with open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["ts", "rate"]); w.writerows(uniq)
    print(f"  Готово: {len(uniq)} записів -> {out}")
print("ВСЕ. Тепер:  venv/bin/python quant/85_funding_test.py")
