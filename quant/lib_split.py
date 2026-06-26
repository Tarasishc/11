"""Розділення IS/OOS. 60% найраніших барів -> in-sample, 40% -> out-of-sample.
OOS НЕ використовується до Кроку 6."""
import pandas as pd

IS_FRAC = 0.60


def split_idx(df: pd.DataFrame, frac: float = IS_FRAC):
    k = int(len(df) * frac)
    return k


def split(df: pd.DataFrame, frac: float = IS_FRAC):
    k = split_idx(df, frac)
    return df.iloc[:k].copy(), df.iloc[k:].copy()


def describe(df: pd.DataFrame, frac: float = IS_FRAC):
    k = split_idx(df, frac)
    is_df, oos_df = df.iloc[:k], df.iloc[k:]
    return {
        "split_bar": k,
        "is_period": (is_df.index[0], is_df.index[-1], len(is_df)),
        "oos_period": (oos_df.index[0], oos_df.index[-1], len(oos_df)),
    }
