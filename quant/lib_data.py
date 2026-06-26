"""Завантаження та нормалізація OHLCV даних.

Три джерела з різними форматами:
  - btc_15m.csv : ts(ms epoch),open,high,low,close,vol   (роздільник ',')
  - btc_1m_month.csv / eth_1d.csv : time;open;high;low;close;Volume (роздільник ';',
    час у вигляді рядка, можливі лапки та BOM)

Усі функції повертають DataFrame з UTC-індексом 'dt' і колонками
['open','high','low','close','vol'] типу float, відсортований, без дублікатів.
"""
import pandas as pd
import numpy as np


def load_btc_15m(path: str = "quant/data/btc_15m.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df[["dt", "open", "high", "low", "close", "vol"]]
    df = df.set_index("dt").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    for c in ["open", "high", "low", "close", "vol"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _load_semicolon(path: str) -> pd.DataFrame:
    # BOM + лапки навколо дати; десятковий роздільник '.'
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.rename(columns={"volume": "vol"})
    df["dt"] = pd.to_datetime(df["time"].astype(str).str.strip('"'), utc=True)
    df = df[["dt", "open", "high", "low", "close", "vol"]]
    df = df.set_index("dt").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    for c in ["open", "high", "low", "close", "vol"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def load_btc_month(path: str = "quant/data/btc_1m_month.csv") -> pd.DataFrame:
    return _load_semicolon(path)


def load_eth_1d(path: str = "quant/data/eth_1d.csv") -> pd.DataFrame:
    return _load_semicolon(path)


def expected_step(df: pd.DataFrame) -> pd.Timedelta:
    """Медіанний крок між барами."""
    return df.index.to_series().diff().median()


def gap_report(df: pd.DataFrame) -> dict:
    """Аналіз пропусків відносно медіанного кроку."""
    step = expected_step(df)
    diffs = df.index.to_series().diff()
    n_bars = len(df)
    # ідеальна кількість барів за період
    span = df.index[-1] - df.index[0]
    ideal = int(span / step) + 1
    missing_bars = ideal - n_bars
    big_gaps = diffs[diffs > step * 1.5]
    return {
        "step": step,
        "n_bars": n_bars,
        "ideal_bars": ideal,
        "missing_bars": missing_bars,
        "coverage_pct": round(100 * n_bars / ideal, 2),
        "n_gaps": int((diffs > step * 1.5).sum()),
        "max_gap": diffs.max(),
        "top_gaps": big_gaps.sort_values(ascending=False).head(10),
    }


def ohlc_sanity(df: pd.DataFrame) -> dict:
    """Перевірка коректності OHLC."""
    hi = df["high"]
    lo = df["low"]
    op = df["open"]
    cl = df["close"]
    bad_hl = (hi < lo).sum()
    bad_h = ((hi < op) | (hi < cl)).sum()
    bad_l = ((lo > op) | (lo > cl)).sum()
    nonpos = ((df[["open", "high", "low", "close"]] <= 0).any(axis=1)).sum()
    nan_rows = df[["open", "high", "low", "close"]].isna().any(axis=1).sum()
    vol_nan = df["vol"].isna().sum()
    # екстремальні бар-до-бар стрибки (можливі помилки даних)
    ret = cl.pct_change().abs()
    extreme = (ret > 0.5).sum()  # >50% за один бар
    return {
        "rows": len(df),
        "high<low": int(bad_hl),
        "high<open|close": int(bad_h),
        "low>open|close": int(bad_l),
        "nonpositive_price": int(nonpos),
        "nan_ohlc_rows": int(nan_rows),
        "nan_vol": int(vol_nan),
        "extreme_bar_moves(>50%)": int(extreme),
        "max_abs_bar_return": round(float(ret.max()), 4),
    }
