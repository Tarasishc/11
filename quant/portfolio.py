"""Багатоінструментний портфельний движок (готовий під BTC+ETH+SOL+MNT).

Логіка: для кожного інструмента застосовуємо валідовану стратегію (4h Donchian80 +
ADX25+DI + сесія 00-12 UTC) при фіксованому ризику, беремо денні дохідності,
складаємо рівноваговий портфель. Диверсифікація підіймає Sharpe -> більша дохідність
при тій самій просадці. Далі risk-sweep під ціль 10%/міс @ 50-60% DD.

Використання:
  from portfolio import run_portfolio
  run_portfolio({"BTC":"quant/data/btc_15m.csv", "ETH":"quant/data/eth_4h.csv", ...})
"""
import numpy as np
import pandas as pd
import lib_data as L
import strategies as ST
import engine as E
import market_structure as MS


def _adx_di(d, n=14):
    h, l = d["high"], d["low"]; up = h.diff(); dn = -l.diff()
    pdm = ((up > dn) & (up > 0)) * up; mdm = ((dn > up) & (dn > 0)) * dn
    tr = E.true_range(d); a = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi = 100 * pdm.ewm(alpha=1/n, adjust=False).mean() / a
    mdi = 100 * mdm.ewm(alpha=1/n, adjust=False).mean() / a
    adx = (100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)).ewm(alpha=1/n, adjust=False).mean()
    return adx, pdi, mdi


def to_4h(df):
    """Зресемплити до 4h, якщо дані дрібніші; інакше лишити як є."""
    step = L.expected_step(df)
    if step <= pd.Timedelta(hours=1):
        return ST.resample(df, "4h"), 240
    if step <= pd.Timedelta(hours=4):
        return df, 240
    # денні чи грубіші
    return df, int(step.total_seconds() / 60)


def signals(d, kind="donchian", bmin=240):
    adx, pdi, mdi = _adx_di(d, 14)
    if kind == "donchian":
        dh = E.donchian_high(d, 80).shift(1); dl = E.donchian_low(d, 80).shift(1)
        up = (adx > 25) & (pdi > mdi); dn = (adx > 25) & (mdi > pdi)
        long = (d["close"] > dh) & up; short = (d["close"] < dl) & dn
        side = np.zeros(len(d)); side[long.to_numpy()] = 1; side[short.to_numpy()] = -1
        sd = (E.atr(d, 14) * 2.0).to_numpy()
    else:  # bos
        side, sd = MS.ms_signals(d, k=3, mode="cont", stop_mode="atr", atr_mult=2.0, rr=3.0)
        keep_l = ((adx > 25) & (pdi > mdi)).to_numpy(); keep_s = ((adx > 25) & (mdi > pdi)).to_numpy()
        side[(side > 0) & ~keep_l] = 0; side[(side < 0) & ~keep_s] = 0
    # сесійний фільтр лише для внутрішньоденних ТФ
    if bmin <= 240:
        hn = np.roll(d.index.hour.to_numpy(), -1)
        side[~np.isin(hn, [0, 4, 8])] = 0
    return side, sd


def instrument_daily_returns(df, kind="donchian", risk=0.01, rr=3.0):
    d, bmin = to_4h(df)
    side, sd = signals(d, kind, bmin)
    res = E.backtest(d, side, sd, E.Config(rr=rr, risk_pct=risk, bar_minutes=bmin))
    daily = res.equity.resample("1D").last().ffill()
    return daily.pct_change().fillna(0), res.metrics


def _stats(r, idx):
    eq = (1 + r).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    yrs = max((idx[-1] - idx[0]).days / 365.25, 1e-9)
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    sh = np.sqrt(365) * r.mean() / r.std() if r.std() > 0 else 0
    mo = eq.resample("ME").last().pct_change().dropna().mean()
    return dict(cagr=cagr, dd=dd, sharpe=sh, avg_mo=mo, final=eq.iloc[-1])


def run_portfolio(paths: dict, kind="donchian", rr=3.0):
    rets = {}; metr = {}
    for name, p in paths.items():
        df = L.load_any(p)
        r, m = instrument_daily_returns(df, kind=kind, rr=rr)
        rets[name] = r; metr[name] = m
        print(f"  {name:5} соло: {E.fmt_metrics(m)}")
    R = pd.DataFrame(rets).fillna(0)
    R = R.loc[R.index >= max(s.dropna().index[0] for s in rets.values())]
    idx = R.index
    print(f"\n  Спільний період: {idx[0].date()} → {idx[-1].date()}  ({len(idx)} днів)")
    print("\n  Кореляція денних дохідностей стратегії:")
    print(R.corr().round(2).to_string())

    port = R.mean(axis=1)  # рівновага
    print("\n  Соло vs портфель (ризик 1%):")
    for name in list(R.columns) + ["ПОРТФЕЛЬ"]:
        r = port if name == "ПОРТФЕЛЬ" else R[name]
        s = _stats(r, idx)
        print(f"    {name:9}: Sharpe={s['sharpe']:.2f}  CAGR={s['cagr']*100:5.1f}%  "
              f"avg_mo={s['avg_mo']*100:.2f}%  maxDD={s['dd']*100:.0f}%")

    # реальний компаундинг-sweep: масштабуємо денні дохідності (=плече) і міряємо фактичні DD/avg_mo
    print("\n  Risk-sweep портфеля (РЕАЛЬНИЙ компаундинг, масштаб денних дохідностей):")
    print(f"  {'scale×':>7}{'avg_mo%':>9}{'CAGR%':>8}{'maxDD%':>8}{'final×':>8}")
    for sc in [2, 4, 6, 8, 10, 12, 15]:
        r = port * sc
        eq = (1 + r).cumprod()
        dd = (eq / eq.cummax() - 1).min()
        mo = eq.resample("ME").last().pct_change().dropna().mean()
        yrs = max((idx[-1] - idx[0]).days / 365.25, 1e-9)
        cagr = eq.iloc[-1] ** (1 / yrs) - 1
        tag = "  <= ~10%/міс ціль" if mo >= 0.10 else ("  <= в межах 50-60% DD" if 0.50 <= abs(dd) <= 0.62 else "")
        print(f"  {sc:7d}{mo*100:9.2f}{cagr*100:8.1f}{dd*100:8.1f}{eq.iloc[-1]:8.2f}{tag}")
    return R, port


if __name__ == "__main__":
    import glob, os
    # автопошук файлів у quant/data
    found = {}
    for sym in ["btc", "eth", "sol", "mnt"]:
        cands = sorted(glob.glob(f"quant/data/*{sym}*.csv"))
        # надати перевагу 4h/15m
        cands = [c for c in cands if "month" not in c.lower()]
        if cands:
            found[sym.upper()] = cands[0]
    print("Знайдені файли:", found)
    if len(found) >= 2:
        run_portfolio(found)
    else:
        print("Замало інструментів. Завантаж SOL/ETH/MNT у quant/data/ і перезапусти.")
