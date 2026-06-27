"""Спроба наблизитись до 10%/міс: стеля при 60% DD, діагностика 'звідки 10%',
портфель BTC+ETH (диверсифікація)."""
import numpy as np
import pandas as pd
import lib_data as L
import lib_split as SP
import strategies as ST
import engine as E

pd.set_option("display.width", 200)

btc15 = L.load_btc_15m()
full4 = ST.resample(btc15, "4h")
is15, oos15 = SP.split(btc15)
is4 = ST.resample(is15, "4h"); oos4 = ST.resample(oos15, "4h")

def adx_di(d, n=14):
    h, l = d["high"], d["low"]; up = h.diff(); dn = -l.diff()
    pdm = ((up>dn)&(up>0))*up; mdm = ((dn>up)&(dn>0))*dn
    tr = E.true_range(d); a = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi = 100*pdm.ewm(alpha=1/n, adjust=False).mean()/a; mdi = 100*mdm.ewm(alpha=1/n, adjust=False).mean()/a
    adx = (100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).ewm(alpha=1/n, adjust=False).mean()
    return adx, pdi, mdi

def btc_signals(d, sess=True):
    adx, pdi, mdi = adx_di(d, 14)
    dh = E.donchian_high(d, 80).shift(1); dl = E.donchian_low(d, 80).shift(1)
    up = (adx>25)&(pdi>mdi); dn = (adx>25)&(mdi>pdi)
    long = (d["close"]>dh)&up; short = (d["close"]<dl)&dn
    side = np.zeros(len(d)); side[long.to_numpy()]=1; side[short.to_numpy()]=-1
    if sess:
        hn = np.roll(d.index.hour.to_numpy(), -1)
        side[~np.isin(hn,[0,4,8])] = 0
    return side, (E.atr(d,14)*2.0).to_numpy()

# ===== 1) Точна стеля при 60% DD (OOS, найкращий стек) =====
print("===== 1) BTC стек (Donchian+ADX+сесія) OOS — стеля під 50/60% DD =====")
print(f"{'risk%':>6}{'avg_mo%':>9}{'CAGR%':>8}{'maxDD%':>8}{'final×':>8}")
side_o, sd_o = btc_signals(oos4)
for risk in [0.03,0.05,0.06,0.07,0.08,0.10]:
    m = E.backtest(oos4, side_o, sd_o, E.Config(rr=3.0, risk_pct=risk, bar_minutes=240)).metrics
    print(f"{risk*100:6.0f}{m['avg_monthly']*100:9.2f}{m['cagr']*100:8.1f}{m['max_dd']*100:8.1f}{m['final_equity']/10000:8.2f}")

# ===== 2) Діагностика: звідки береться '10%/міс' =====
print("\n===== 2) Діагностика '10%/міс': in-sample / без комісій / високий ризик =====")
side_i, sd_i = btc_signals(is4)
scenarios = [
    ("OOS, з комісіями, risk 5%",  oos4, dict(fee=0.0005,slip=0.0003,funding_per_8h=0.0001), 0.05),
    ("IS,  з комісіями, risk 5%",  is4,  dict(fee=0.0005,slip=0.0003,funding_per_8h=0.0001), 0.05),
    ("IS,  БЕЗ комісій,  risk 5%",  is4,  dict(fee=0,slip=0,funding_per_8h=0), 0.05),
    ("IS,  БЕЗ комісій,  risk 10%", is4,  dict(fee=0,slip=0,funding_per_8h=0), 0.10),
    ("IS,  БЕЗ комісій,  risk 20%", is4,  dict(fee=0,slip=0,funding_per_8h=0), 0.20),
]
for name, d, costs, risk in scenarios:
    side, sd = btc_signals(d)
    m = E.backtest(d, side, sd, E.Config(rr=3.0, risk_pct=risk, bar_minutes=240, **costs)).metrics
    flag = "  <-- '10%/міс' з'являється тут (фейк: in-sample+без комісій+екстрим-ризик)" if m['avg_monthly']>=0.10 else ""
    print(f"  {name:30}: avg_mo={m['avg_monthly']*100:6.2f}%  maxDD={m['max_dd']*100:6.0f}%  "
          f"final×={m['final_equity']/10000:6.2f}  Sharpe={m['sharpe']:.2f}{flag}")

# ===== 3) Портфель BTC(4h) + ETH(1d) — диверсифікація =====
print("\n===== 3) Диверсифікація: портфель BTC(4h) + ETH(1d) =====")
def daily_returns(equity_s, idx_full):
    d = equity_s.resample("1D").last().ffill().reindex(idx_full).ffill()
    return d.pct_change().fillna(0)

# BTC на повному 4h
side_b, sd_b = btc_signals(full4)
res_b = E.backtest(full4, side_b, sd_b, E.Config(rr=3.0, risk_pct=0.01, bar_minutes=240))
# ETH daily, після діри (post 2018-11)
eth = L.load_eth_1d(); eth = eth[eth.index >= "2018-11-15"]
adx, pdi, mdi = adx_di(eth, 14)
dh = E.donchian_high(eth, 20).shift(1); dl = E.donchian_low(eth, 20).shift(1)
up = (adx>25)&(pdi>mdi); dn = (adx>25)&(mdi>pdi)
long = (eth["close"]>dh)&up; short = (eth["close"]<dl)&dn
side_e = np.zeros(len(eth)); side_e[long.to_numpy()]=1; side_e[short.to_numpy()]=-1
res_e = E.backtest(eth, side_e, (E.atr(eth,14)*2.0).to_numpy(), E.Config(rr=3.0, risk_pct=0.01, bar_minutes=1440))
print(f"  BTC соло: {E.fmt_metrics(res_b.metrics)}")
print(f"  ETH соло: {E.fmt_metrics(res_e.metrics)}")

# спільний денний індекс
idx = pd.date_range(max(res_b.daily_equity.index[0], res_e.daily_equity.index[0]),
                    min(res_b.daily_equity.index[-1], res_e.daily_equity.index[-1]), freq="D", tz="UTC")
rb = daily_returns(res_b.equity, idx); re = daily_returns(res_e.equity, idx)
corr = np.corrcoef(rb.values, re.values)[0,1]
print(f"  Кореляція денних дохідностей BTC vs ETH: {corr:.2f}")
# портфель 50/50 (ризик масштабуємо так, щоб порівняти Sharpe)
def stats(r):
    eq = (1+r).cumprod(); dd = (eq/eq.cummax()-1).min()
    yrs = (idx[-1]-idx[0]).days/365.25; cagr = eq.iloc[-1]**(1/yrs)-1
    sh = np.sqrt(365)*r.mean()/r.std() if r.std()>0 else 0
    mo = eq.resample("ME").last().pct_change().dropna().mean()
    return cagr, dd, sh, mo
for name, r in [("BTC", rb), ("ETH", re), ("50/50 портфель", 0.5*rb+0.5*re)]:
    cagr, dd, sh, mo = stats(r)
    print(f"  {name:16}: Sharpe={sh:.2f}  CAGR={cagr*100:5.1f}%  avg_mo={mo*100:.2f}%  maxDD={dd*100:.0f}%  (risk 1%)")

# масштаб портфеля під 60% DD
port = 0.5*rb+0.5*re
_,dd1,_,mo1 = stats(port)
scale = 0.60/abs(dd1)
print(f"\n  Якщо лінійно масштабувати портфель під 60% DD: ~{mo1*scale*100:.1f}%/міс (груба оцінка)")
print("  (BTC/ETH сильно корельовані -> вигода від диверсифікації мала; для Sharpe>2 треба 10-20 СЛАБО корельованих інструментів)")
