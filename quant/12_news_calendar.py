"""Повторювані події: FOMC (макро-новина) + детерміновані календарні (кінець місяця,
місячна експірація = остання п'ятниця). Усе ОПИСОВО, з дисципліною IS/OOS.
Caveat: біля рідкісних подій угод мало -> це не фільтр, а risk-контекст."""
import numpy as np
import pandas as pd
import lib_data as L
import lib_split as SP
import strategies as ST
import engine as E

# Дати рішень FOMC (другий день засідання, публічний розклад ФРС). 2017-2026.
FOMC = pd.to_datetime([
    "2017-02-01","2017-03-15","2017-05-03","2017-06-14","2017-07-26","2017-09-20","2017-11-01","2017-12-13",
    "2018-01-31","2018-03-21","2018-05-02","2018-06-13","2018-08-01","2018-09-26","2018-11-08","2018-12-19",
    "2019-01-30","2019-03-20","2019-05-01","2019-06-19","2019-07-31","2019-09-18","2019-10-30","2019-12-11",
    "2020-01-29","2020-03-03","2020-03-15","2020-04-29","2020-06-10","2020-07-29","2020-09-16","2020-11-05","2020-12-16",
    "2021-01-27","2021-03-17","2021-04-28","2021-06-16","2021-07-28","2021-09-22","2021-11-03","2021-12-15",
    "2022-01-26","2022-03-16","2022-05-04","2022-06-15","2022-07-27","2022-09-21","2022-11-02","2022-12-14",
    "2023-02-01","2023-03-22","2023-05-03","2023-06-14","2023-07-26","2023-09-20","2023-11-01","2023-12-13",
    "2024-01-31","2024-03-20","2024-05-01","2024-06-12","2024-07-31","2024-09-18","2024-11-07","2024-12-18",
    "2025-01-29","2025-03-19","2025-05-07","2025-06-18","2025-07-30","2025-09-17","2025-10-29","2025-12-10",
    "2026-01-28","2026-03-18","2026-04-29","2026-06-17",
], utc=True).normalize()

btc15 = L.load_btc_15m()
daily = btc15["close"].resample("1D").last()
dret = daily.pct_change().abs()           # денний |рух| (волатильність)
dret_signed = daily.pct_change()
split_day = pd.Timestamp(SP.split(btc15)[1].index[0]).normalize()

def event_vol(dates, label, win=1):
    """Порівняння |руху| у вікні ±win днів навколо подій з базовим рівнем, IS/OOS."""
    idx = dret.index.normalize()
    ev_mask = pd.Series(False, index=dret.index)
    for d in dates:
        ev_mask |= (idx >= d - pd.Timedelta(days=0)) & (idx <= d + pd.Timedelta(days=win))
    for tag, sl in [("IS", dret.index < split_day), ("OOS", dret.index >= split_day)]:
        ev = dret[ev_mask & sl].mean()
        base = dret[~ev_mask & sl].mean()
        n_ev = (ev_mask & sl).sum()
        print(f"  {label} [{tag}]: |рух| у дні події={ev*100:.2f}%  базовий={base*100:.2f}%  "
              f"ratio={ev/base:.2f}  (днів-подій={n_ev})")

print("===== FOMC: волатильність у день рішення та наступний день =====")
event_vol(FOMC, "FOMC ±1д", win=1)

print("\n===== Детерміновані календарні події (без зовнішніх даних) =====")
# turn-of-month: останні 2 + перші 2 календарні дні місяця
idx = dret.index
tom_mask = (idx.day <= 2) | (idx.day >= idx.days_in_month - 1)
# остання п'ятниця місяця (місячна експірація опціонів)
is_fri = idx.dayofweek == 5 - 1  # Friday=4
last_fri = []
for (y, m), grp in dret.groupby([idx.year, idx.month]):
    fr = grp.index[grp.index.dayofweek == 4]
    if len(fr): last_fri.append(fr.max())
last_fri = pd.DatetimeIndex(last_fri)
exp_mask = idx.isin(last_fri) | idx.isin(last_fri + pd.Timedelta(days=1))

for name, mask in [("turn-of-month (±2д межі місяця)", tom_mask),
                   ("місячна експірація (ост.п'ятниця ±1д)", exp_mask)]:
    for tag, sl in [("IS", idx < split_day), ("OOS", idx >= split_day)]:
        m = pd.Series(mask, index=idx)
        ev = dret[m & sl].mean(); base = dret[~m & sl].mean()
        print(f"  {name} [{tag}]: |рух|={ev*100:.2f}%  базовий={base*100:.2f}%  ratio={ev/base:.2f}")

# ===== Як стратегія поводилась у дні навколо FOMC (описово) =====
print("\n===== ADX-breakout 4h: угоди, що ВІДКРИТІ у вікні FOMC ±1д (описово) =====")
def adx_di(d, n=14):
    h, l = d["high"], d["low"]; up = h.diff(); dn = -l.diff()
    pdm = ((up>dn)&(up>0))*up; mdm = ((dn>up)&(dn>0))*dn
    tr = E.true_range(d); a = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi = 100*pdm.ewm(alpha=1/n, adjust=False).mean()/a; mdi = 100*mdm.ewm(alpha=1/n, adjust=False).mean()/a
    adx = (100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)).ewm(alpha=1/n, adjust=False).mean()
    return adx, pdi, mdi
d4 = ST.resample(btc15, "4h")
adx, pdi, mdi = adx_di(d4, 14)
dh = E.donchian_high(d4, 80).shift(1); dl = E.donchian_low(d4, 80).shift(1); a = E.atr(d4, 14)
up = (adx>25)&(pdi>mdi); dn = (adx>25)&(mdi>pdi)
side = np.zeros(len(d4)); side[((d4["close"]>dh)&up).to_numpy()] = 1; side[((d4["close"]<dl)&dn).to_numpy()] = -1
res = E.backtest(d4, side, (a*2.0).to_numpy(), E.Config(rr=3.0, risk_pct=0.01, bar_minutes=240))
t = res.trades.copy()
t["ed"] = pd.to_datetime(t["entry_time"]).dt.normalize()
t["xd"] = pd.to_datetime(t["exit_time"]).dt.normalize()
fomc_set = set(FOMC)
def overlaps_fomc(r):
    days = pd.date_range(r["ed"], r["xd"], freq="D")
    return any((dd in fomc_set) or (dd - pd.Timedelta(days=1) in fomc_set) for dd in days)
t["near_fomc"] = t.apply(overlaps_fomc, axis=1)
near = t[t.near_fomc]; far = t[~t.near_fomc]
print(f"  угод біля FOMC: n={len(near)}  E[R]={near.r_mult.mean():+.3f}  WR={(near.net>0).mean()*100:.0f}%  sumR={near.r_mult.sum():+.1f}")
print(f"  решта угод     : n={len(far)}  E[R]={far.r_mult.mean():+.3f}  WR={(far.net>0).mean()*100:.0f}%  sumR={far.r_mult.sum():+.1f}")
print("  (мала вибірка біля FOMC -> це не фільтр, а контекст ризику)")
