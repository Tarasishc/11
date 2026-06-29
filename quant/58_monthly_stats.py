"""Місячна статистика РОБОЧОЇ конфігурації бота: найгірший місяць, серія мінусів,
найкращі місяці. 4 монети одна-на-монету, BNB лише FVG, risk 1%."""
import importlib.util, builtins, numpy as np, pandas as pd
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c44", "quant/44_one_per_coin.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print = _p
import lib_data as L
BASE3 = m.BASE; naive = m.naive; one_per_coin = m.one_per_coin; fvg_tr = m.fvg_tr
bnb = L.load_any("quant/data/bnb_4h.csv")
RISK = 0.01

rows = []
for c in ["BTC", "ETH", "SOL"]:
    rows += one_per_coin(BASE3[c])                       # KC+FVG одна-на-монету
rows += [(naive(ts), r) for _, _, ts, r in fvg_tr(bnb)]  # BNB лише FVG
T = pd.DataFrame(rows, columns=["t", "r"]).sort_values("t").reset_index(drop=True)

eq = np.cumprod(1 + RISK * T["r"].values)
s = pd.Series(eq, index=pd.DatetimeIndex(T["t"]))
me = s.resample("ME").last().dropna()
mret = me.pct_change().dropna()
mret = pd.concat([pd.Series([me.iloc[0] - 1], index=[me.index[0]]), mret]) * 100  # у %

print(f"Період: {T['t'].min().date()} .. {T['t'].max().date()} | місяців: {len(mret)} | risk {RISK*100:.0f}%/угода\n")
print(f"Плюсових місяців: {(mret>0).mean()*100:.0f}%  | середній місяць: {mret.mean():+.2f}%  медіана: {mret.median():+.2f}%\n")

print("НАЙГІРШІ 5 місяців:")
for d, v in mret.sort_values().head(5).items():
    print(f"  {d:%Y-%m}: {v:+.2f}%")

print("\nНАЙКРАЩІ 5 місяців:")
for d, v in mret.sort_values(ascending=False).head(5).items():
    print(f"  {d:%Y-%m}: {v:+.2f}%")

# найдовша серія мінусових місяців
cur = best = 0; cur_start = best_start = best_end = None
for d, v in mret.items():
    if v < 0:
        if cur == 0: cur_start = d
        cur += 1
        if cur > best: best, best_start, best_end = cur, cur_start, d
    else:
        cur = 0
print(f"\nНайдовша серія МІНУСОВИХ місяців: {best} поспіль ({best_start:%Y-%m} .. {best_end:%Y-%m})")
# сумарна просадка за цю серію
streak = mret[(mret.index >= best_start) & (mret.index <= best_end)]
print(f"  сумарно за серію: {(np.prod(1+streak/100)-1)*100:+.1f}%")

# найдовша серія плюсів
cur = best = 0
for v in mret:
    cur = cur+1 if v > 0 else 0
    best = max(best, cur)
print(f"Найдовша серія ПЛЮСОВИХ місяців: {best} поспіль")

# річний підсумок
T["yr"] = pd.to_datetime(T["t"]).dt.year
print("\nЗа роками (R сумарно):")
for yr, g in T.groupby("yr"):
    print(f"  {yr}: {g['r'].sum():+5.0f}R  ({len(g)} угод)")
print("\n(Бектест. Лайв буде нижчий; це орієнтир, до чого готуватись.)")
