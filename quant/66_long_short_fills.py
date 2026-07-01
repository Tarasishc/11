"""Окремі підрахунки на РОБОЧІЙ конфігурації (KC+FVG, база 2.0x/0.5, 4h):
  1) яких сетапів більше — ЛОНГИ чи ШОРТИ (KC / FVG-зони / реально взяті угоди)
  2) скільки FVG-ЛІМІТОК не взяло (ретесту зони не було у вікні 20 барів)
Детекція 1:1 з движком 60_stop_width -> ті самі числа, що в усіх тестах.
Повна історія (структурне питання про частоту сетапів, не про прибуток)."""
import numpy as np, pandas as pd, importlib.util, builtins
import lib_data as L, strategies as ST, engine as E

# reuse taken() з базового движка, щоб «взяті угоди» точно збігались з бектестом
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c60", "quant/60_stop_width.py")
m60 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m60); builtins.print = _p

BASE = {"BTC": ST.resample(L.load_btc_15m(), "4h"), "ETH": L.load_any("quant/data/eth_4h.csv"),
        "SOL": L.load_any("quant/data/sol_4h.csv"), "BNB": L.load_any("quant/data/bnb_4h.csv")}
ENG = {"BTC": "KF", "ETH": "KF", "SOL": "KF", "BNB": "F"}
LA = 20  # вікно очікування ретесту (як у движку: range(k+1, min(k+1+LA, n)))

def adxv(d):
    h, l = d["high"], d["low"]; up = h.diff(); dn = -l.diff()
    pdm = ((up > dn) & (up > 0))*up; mdm = ((dn > up) & (dn > 0))*dn
    tr = E.true_range(d); a = tr.ewm(alpha=1/14, adjust=False).mean()
    pdi = 100*pdm.ewm(alpha=1/14, adjust=False).mean()/a; mdi = 100*mdm.ewm(alpha=1/14, adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)).ewm(alpha=1/14, adjust=False).mean().to_numpy()

def kc_setups(d):
    """KC = маркет-входи (беруться завжди). -> list(side)."""
    cl = d["close"]; atr = E.atr(d, 14).to_numpy(); n = len(cl); out = []
    mid = E.ema(cl, 20); band = 2*E.atr(d, 10)
    up = ((cl > mid+band) & (cl > E.ema(cl, 200))).to_numpy()
    dn = ((cl < mid-band) & (cl < E.ema(cl, 200))).to_numpy(); ax = adxv(d)
    for i in range(1, n-1):
        if not np.isfinite(atr[i]) or ax[i] < 20: continue
        for si, sig in ((1, up), (-1, dn)):
            if sig[i] and not sig[i-1]: out.append(si)
    return out

def fvg_zones(d):
    """FVG = лімітки. -> list(side, filled?) ; filled=False -> лімітка НЕ взяла (ретесту не було)."""
    h, l, c = [d[x].to_numpy() for x in ["high", "low", "close"]]
    em = E.ema(d["close"], 200).to_numpy(); n = len(c); out = []
    for k in range(2, n-1):
        if h[k-2] < l[k] and c[k] > em[k]:                       # бичача FVG -> лімітка на зону
            zt = l[k]; filled = any(l[j] <= zt and c[j] > em[j] for j in range(k+1, min(k+1+LA, n)))
            out.append((1, filled))
        if l[k-2] > h[k] and c[k] < em[k]:                       # ведмежа FVG
            zt = h[k]; filled = any(h[j] >= zt and c[j] < em[j] for j in range(k+1, min(k+1+LA, n)))
            out.append((-1, filled))
    return out

print("РОБОЧА КОНФІГ (BTC/ETH/SOL=KC+FVG, BNB=FVG), 4h, повна історія\n")
hdr = f"{'мон':4s}| {'KC L':>5} {'KC S':>5} | {'FVGзон':>6} {'зонL':>5} {'зонS':>5} | {'взято':>5} {'НЕвзял':>6} {'%взл':>5} | {'угоди':>5} {'уг.L':>5} {'уг.S':>5}"
print(hdr); print("-"*len(hdr))

TOT = dict(kcl=0, kcs=0, zl=0, zs=0, zf=0, zn=0, tl=0, ts=0)
for coin, d in BASE.items():
    kcl = kcs = 0
    if "K" in ENG[coin]:
        ks = kc_setups(d); kcl = sum(1 for s in ks if s > 0); kcs = sum(1 for s in ks if s < 0)
    zones = fvg_zones(d)
    zl = sum(1 for s, f in zones if s > 0); zs = sum(1 for s, f in zones if s < 0)
    zf = sum(1 for s, f in zones if f); zn = len(zones) - zf
    tk = m60.taken(d, ENG[coin], 2.0, 0.5)              # взяті угоди (одна-на-монету), як у бектесті
    tl = sum(1 for r in tk if r[1] > 0); ts = sum(1 for r in tk if r[1] < 0)
    fillpct = 100*zf/len(zones) if zones else 0
    print(f"{coin:4s}| {kcl:5d} {kcs:5d} | {len(zones):6d} {zl:5d} {zs:5d} | {zf:5d} {zn:6d} {fillpct:4.0f}% | {len(tk):5d} {tl:5d} {ts:5d}")
    TOT["kcl"] += kcl; TOT["kcs"] += kcs; TOT["zl"] += zl; TOT["zs"] += zs
    TOT["zf"] += zf; TOT["zn"] += zn; TOT["tl"] += tl; TOT["ts"] += ts

zt = TOT["zf"] + TOT["zn"]
print("-"*len(hdr))
print(f"{'РАЗ':4s}| {TOT['kcl']:5d} {TOT['kcs']:5d} | {zt:6d} {TOT['zl']:5d} {TOT['zs']:5d} | "
      f"{TOT['zf']:5d} {TOT['zn']:6d} {100*TOT['zf']/zt:4.0f}% | {TOT['tl']+TOT['ts']:5d} {TOT['tl']:5d} {TOT['ts']:5d}")

# зведення
all_setL = TOT["kcl"] + TOT["zl"]; all_setS = TOT["kcs"] + TOT["zs"]; all_set = all_setL + all_setS
tk_tot = TOT["tl"] + TOT["ts"]
print("\n1) ЛОНГИ vs ШОРТИ")
print(f"   всі сетапи (KC+FVGзони): лонг {all_setL} ({100*all_setL/all_set:.0f}%) / шорт {all_setS} ({100*all_setS/all_set:.0f}%)")
print(f"   реально взяті угоди:     лонг {TOT['tl']} ({100*TOT['tl']/tk_tot:.0f}%) / шорт {TOT['ts']} ({100*TOT['ts']/tk_tot:.0f}%)")
print("\n2) FVG-ЛІМІТКИ (не взяло = ретесту зони не було за 20 барів)")
print(f"   виставлено {zt} лімсетапів | взяло {TOT['zf']} ({100*TOT['zf']/zt:.0f}%) | "
      f"НЕ взяло {TOT['zn']} ({100*TOT['zn']/zt:.0f}%)")
elig = TOT["kcl"] + TOT["kcs"] + TOT["zf"]            # KC(маркет) + FVG що взяли лімітку
print("\n3) ПРАВИЛО ОДНА-НА-МОНЕТУ: скільки придатних сетапів пропущено (слот зайнятий)")
print(f"   придатних (KC + філовані FVG) {elig} | реально взято {tk_tot} | "
      f"пропущено {elig-tk_tot} ({100*(elig-tk_tot)/elig:.0f}%) — бо вже була відкрита позиція")
print("\n(KC = маркет, беруться завжди; «не взяло» в п.2 = лише FVG-лімітки без ретесту.\n"
      " Сигналів набагато більше, ніж слотів -> дефіциту входів немає, всі цифри прибутку\n"
      " рахувались саме на взятому підмножині. Історія 2017-26 бичача, але фільтр EMA200\n"
      " дає майже 50/50 -> у ведмежий ринок перекіс піде в шорти.)")
