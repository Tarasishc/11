"""Крок 1 — інспекція даних. Друкує звіт по всіх трьох джерелах."""
import pandas as pd
import lib_data as L

pd.set_option("display.width", 120)


def report(name, df):
    print("=" * 70)
    print(f"# {name}")
    print("=" * 70)
    print(f"Період : {df.index[0]}  →  {df.index[-1]}")
    print(f"Барів  : {len(df):,}")
    g = L.gap_report(df)
    print(f"Крок (медіана)     : {g['step']}")
    print(f"Покриття           : {g['coverage_pct']}%  "
          f"(є {g['n_bars']:,} з ~{g['ideal_bars']:,} ідеальних, пропуск ~{g['missing_bars']:,})")
    print(f"Пропусків (>1.5x)  : {g['n_gaps']}   макс. розрив: {g['max_gap']}")
    if g["n_gaps"] > 0:
        print("Найбільші розриви:")
        for ts, d in g["top_gaps"].items():
            print(f"   {ts}  розрив {d}")
    s = L.ohlc_sanity(df)
    print("OHLC-санітарність:")
    for k, v in s.items():
        print(f"   {k:28s}: {v}")
    # ціновий діапазон
    print(f"Ціна close: min={df['close'].min():.4f}  max={df['close'].max():.2f}")
    print()


btc15 = L.load_btc_15m()
report("BTC 15m (робочий датасет)", btc15)

# рік за роком — скільки барів і чи рівномірно
print("BTC 15m — барів по роках:")
print(btc15.groupby(btc15.index.year).size().to_string())
print()

ethd = L.load_eth_1d()
report("ETH 1D", ethd)

btcm = L.load_btc_month()
report("BTC 1M (місяць)", btcm)
