"""Завантаження OHLCV у форматі ts,open,high,low,close,vol (як інші монети проєкту).

ЗАПУСК ЛОКАЛЬНО (в агенті біржа заблокована):
  python3 -m venv venv
  source venv/bin/activate            # Windows: venv\Scripts\activate
  pip install ccxt
  python fetch_ohlcv.py

Результат: bnb_4h.csv  ->  поклади у quant/data/ і завантаж у чат.
Для іншої монети — зміни SYMBOL та OUT нижче (напр. "XRP/USDT" -> "xrp_4h.csv")."""
import ccxt, csv, time

EX     = ccxt.binance({"options": {"defaultType": "future"}})  # Binance USDT-M ф'ючерси
SYMBOL = "BNB/USDT"      # що качаємо
TF     = "4h"            # таймфрейм стратегії
OUT    = "bnb_4h.csv"    # ім'я файлу (нижній регістр, як sol_4h.csv)
SINCE  = "2020-01-01T00:00:00Z"   # від цієї дати (раніше лістингу — візьме від наявного)

since = EX.parse8601(SINCE)
now   = EX.milliseconds()
rows  = []
while since < now:
    batch = EX.fetch_ohlcv(SYMBOL, TF, since=since, limit=1000)
    if not batch:
        break
    rows += batch
    last = batch[-1][0]
    if last == since:          # часовий курсор не зрушив — виходимо
        break
    since = last + 1
    print(f"  {len(rows):6d} барів, останній {EX.iso8601(last)}")
    time.sleep(EX.rateLimit / 1000)

# дедуп за timestamp + сортування за часом
uniq = {r[0]: r for r in rows}
data = sorted(uniq.values())

with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ts", "open", "high", "low", "close", "vol"])
    w.writerows(data)
print(f"Готово: {len(data)} барів -> {OUT}  ({EX.iso8601(data[0][0])} .. {EX.iso8601(data[-1][0])})")
