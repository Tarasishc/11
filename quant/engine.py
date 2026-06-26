"""Бектест-движок для price action стратегій на ф'ючерсах.

Принципи (усе налаштовується, дефолти консервативні):
  * Виконання без lookahead: сигнал рахується на закритті бара i,
    вхід — на ВІДКРИТТІ бара i+1.
  * Стоп/тейк за фіксованим RR. Дистанція стопа задається стратегією
    на сигнальному барі (ATR- або структурна).
  * Якщо бар торкається і стопа, і тейка — вважаємо що спрацював СТОП
    (песимістично).
  * Комісія taker, слипедж (закладений у ціну філа), фандинг як drag.
  * Fixed-fractional ризик: на угоду ризикуємо risk_pct від ПОТОЧНОГО
    капіталу (компаундинг). Розмір позиції з дистанції стопа.
  * Обмеження плеча max_leverage (надлишок -> зменшення позиції).
  * Одна позиція одночасно (без пірамідингу), опційний cooldown.
"""
from dataclasses import dataclass, field
import numpy as np
import pandas as pd


# --------------------------- ІНДИКАТОРИ ---------------------------------

def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    tr = true_range(df)
    # Wilder smoothing
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l = df["high"], df["low"]
    up = h.diff()
    dn = -l.diff()
    plus_dm = ((up > dn) & (up > 0)) * up
    minus_dm = ((dn > up) & (dn > 0)) * dn
    tr = true_range(df)
    atr_ = tr.ewm(alpha=1 / n, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr_
    minus_di = 100 * minus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr_
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0)
    dn = -d.clip(upper=0)
    rs = up.ewm(alpha=1 / n, adjust=False).mean() / dn.ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + rs)


def donchian_high(df: pd.DataFrame, n: int) -> pd.Series:
    return df["high"].rolling(n).max()


def donchian_low(df: pd.DataFrame, n: int) -> pd.Series:
    return df["low"].rolling(n).min()


# --------------------------- КОНФІГ -------------------------------------

@dataclass
class Config:
    fee: float = 0.0005          # taker 0.05% за сторону
    slip: float = 0.0003         # слипедж 0.03% (закладено в ціну філа)
    funding_per_8h: float = 0.0001   # 0.01% за 8 год (drag, обидві сторони)
    risk_pct: float = 0.01       # ризик на угоду від капіталу
    rr: float = 2.0              # reward/risk
    max_leverage: float = 20.0
    initial_equity: float = 10_000.0
    allow_long: bool = True
    allow_short: bool = True
    max_hold_bars: int = 0       # 0 = без часового стопа
    cooldown_bars: int = 0       # пауза після виходу
    bar_minutes: int = 15


@dataclass
class Result:
    trades: pd.DataFrame
    equity: pd.Series            # реалізований капітал на момент виходу
    daily_equity: pd.Series
    metrics: dict = field(default_factory=dict)


# --------------------------- СИМУЛЯЦІЯ ----------------------------------

def backtest(df: pd.DataFrame, side: np.ndarray, stop_dist: np.ndarray,
             cfg: Config) -> Result:
    """side[i] in {+1,-1,0} — сигнал на закритті бара i.
    stop_dist[i] — дистанція стопа в ціні (>0), визначена на барі i.
    Вхід виконується на open[i+1]."""
    o = df["open"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    c = df["close"].to_numpy()
    idx = df.index
    n = len(df)

    equity = cfg.initial_equity
    eq_times, eq_vals = [idx[0]], [equity]
    trades = []

    i = 0
    while i < n - 1:
        s = side[i]
        sd = stop_dist[i]
        if s == 0 or not np.isfinite(sd) or sd <= 0:
            i += 1
            continue
        if s > 0 and not cfg.allow_long:
            i += 1; continue
        if s < 0 and not cfg.allow_short:
            i += 1; continue

        # вхід на наступному барі
        entry_bar = i + 1
        raw_entry = o[entry_bar]
        # слипедж у несприятливий бік
        entry = raw_entry * (1 + cfg.slip) if s > 0 else raw_entry * (1 - cfg.slip)
        stop = entry - s * sd
        target = entry + s * cfg.rr * sd

        # розмір позиції
        risk_amt = cfg.risk_pct * equity
        qty = risk_amt / sd
        notional = qty * entry
        if notional > cfg.max_leverage * equity:
            qty = cfg.max_leverage * equity / entry
            notional = qty * entry

        # форвард-скан виходу
        exit_price = None
        exit_bar = None
        reason = None
        j = entry_bar
        while j < n:
            hj, lj = h[j], l[j]
            if s > 0:
                hit_stop = lj <= stop
                hit_tgt = hj >= target
            else:
                hit_stop = hj >= stop
                hit_tgt = lj <= target
            if hit_stop and hit_tgt:
                # песимістично: стоп першим
                exit_price = stop * (1 - cfg.slip) if s > 0 else stop * (1 + cfg.slip)
                reason = "stop(both)"
                exit_bar = j; break
            if hit_stop:
                exit_price = stop * (1 - cfg.slip) if s > 0 else stop * (1 + cfg.slip)
                reason = "stop"; exit_bar = j; break
            if hit_tgt:
                exit_price = target   # ліміт — без слипеджу
                reason = "target"; exit_bar = j; break
            if cfg.max_hold_bars and (j - entry_bar) >= cfg.max_hold_bars:
                px = c[j]
                exit_price = px * (1 - cfg.slip) if s > 0 else px * (1 + cfg.slip)
                reason = "time"; exit_bar = j; break
            j += 1
        if exit_price is None:  # дотягнули до кінця даних
            px = c[n - 1]
            exit_price = px * (1 - cfg.slip) if s > 0 else px * (1 + cfg.slip)
            reason = "eod"; exit_bar = n - 1

        gross = s * qty * (exit_price - entry)
        notional_exit = qty * exit_price
        fees = cfg.fee * (notional + notional_exit)
        hours = (exit_bar - entry_bar) * cfg.bar_minutes / 60.0
        funding = cfg.funding_per_8h * notional * (hours / 8.0)
        net = gross - fees - funding
        equity += net

        r_mult = net / risk_amt if risk_amt > 0 else 0.0
        trades.append({
            "entry_time": idx[entry_bar], "exit_time": idx[exit_bar],
            "side": "L" if s > 0 else "S", "entry": entry, "exit": exit_price,
            "stop": stop, "target": target, "qty": qty, "notional": notional,
            "bars_held": exit_bar - entry_bar, "reason": reason,
            "net": net, "r_mult": r_mult, "equity": equity,
        })
        eq_times.append(idx[exit_bar]); eq_vals.append(equity)

        # наступний пошук після виходу + cooldown
        i = exit_bar + 1 + cfg.cooldown_bars

    trades_df = pd.DataFrame(trades)
    equity_s = pd.Series(eq_vals, index=pd.DatetimeIndex(eq_times))
    equity_s = equity_s[~equity_s.index.duplicated(keep="last")]

    # денний капітал для DD/Sharpe
    if len(equity_s) > 1:
        daily = equity_s.resample("1D").last().ffill()
        daily.iloc[0] = cfg.initial_equity if np.isnan(daily.iloc[0]) else daily.iloc[0]
        daily = daily.ffill()
    else:
        daily = equity_s

    metrics = compute_metrics(trades_df, daily, equity_s, cfg, df)
    return Result(trades_df, equity_s, daily, metrics)


def compute_metrics(trades: pd.DataFrame, daily: pd.Series, equity_s: pd.Series,
                    cfg: Config, df: pd.DataFrame) -> dict:
    m = {}
    n = len(trades)
    m["n_trades"] = n
    if n == 0:
        m.update(dict(total_return=0, cagr=0, max_dd=0, sharpe=0, sortino=0,
                      win_rate=0, profit_factor=0, expectancy_R=0,
                      avg_monthly=0, final_equity=cfg.initial_equity))
        return m

    final = equity_s.iloc[-1]
    m["final_equity"] = final
    m["total_return"] = final / cfg.initial_equity - 1

    days = (df.index[-1] - df.index[0]).days
    years = max(days / 365.25, 1e-9)
    m["years"] = round(years, 2)
    m["cagr"] = (final / cfg.initial_equity) ** (1 / years) - 1

    # max drawdown по денному капіталу
    roll_max = daily.cummax()
    dd = daily / roll_max - 1
    m["max_dd"] = dd.min()

    # Sharpe / Sortino з денних дохідностей
    dret = daily.pct_change().dropna()
    if dret.std() > 0:
        m["sharpe"] = np.sqrt(365) * dret.mean() / dret.std()
    else:
        m["sharpe"] = 0.0
    downside = dret[dret < 0]
    if len(downside) > 0 and downside.std() > 0:
        m["sortino"] = np.sqrt(365) * dret.mean() / downside.std()
    else:
        m["sortino"] = 0.0

    wins = trades[trades["net"] > 0]["net"]
    losses = trades[trades["net"] <= 0]["net"]
    m["win_rate"] = len(wins) / n
    gross_win = wins.sum()
    gross_loss = -losses.sum()
    m["profit_factor"] = gross_win / gross_loss if gross_loss > 0 else np.inf
    m["expectancy_R"] = trades["r_mult"].mean()
    m["avg_win_R"] = (wins / (cfg.risk_pct * cfg.initial_equity)).mean() if len(wins) else 0
    m["avg_bars"] = trades["bars_held"].mean()

    # середня місячна дохідність (за денним капіталом)
    mret = daily.resample("ME").last().pct_change().dropna()
    m["avg_monthly"] = mret.mean()
    m["monthly_win_rate"] = (mret > 0).mean()
    m["n_months"] = len(mret)
    m["pct_long"] = (trades["side"] == "L").mean()
    m["target_rate"] = (trades["reason"].str.startswith("target")).mean()
    return m


def fmt_metrics(m: dict) -> str:
    def pct(x):
        return f"{x*100:.1f}%" if isinstance(x, (int, float)) and np.isfinite(x) else str(x)
    return (
        f"trades={m['n_trades']} | tot={pct(m['total_return'])} | CAGR={pct(m['cagr'])} | "
        f"avg_mo={pct(m['avg_monthly'])} | maxDD={pct(m['max_dd'])} | "
        f"Sharpe={m['sharpe']:.2f} | Sortino={m['sortino']:.2f} | "
        f"WR={pct(m['win_rate'])} | PF={m['profit_factor']:.2f} | "
        f"E[R]={m['expectancy_R']:.3f} | %L={pct(m.get('pct_long',0))}"
    )
