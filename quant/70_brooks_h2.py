"""H2/L2 за Елом Бруксом — механізація + чесний тест (IS -> OOS, 4 монети, 4h).

Механізація (за описом користувача):
  * Тренд: ціна над EMA20 (лонг) / під (шорт). Варіант: узгодження з EMA200.
  * Відкат: перший бар з нижчим хаєм (лонг) починає відлік.
  * H1 = перший бар, чий хай > хай попереднього (перша спроба вгору).
  * Після H1 нова хвиля вниз -> H2 = другий такий бар. Це сигнал.
  * Вхід: СТОП-ордер за екстремумом сигнального бара (тригер за <=2 барів, інакше скасовано).
  * Стоп: за лоу відкату (обидві хвилі), флор 0.5*ATR. RR фіксований.
Фільтри з тексту (тестуються ОКРЕМО і разом):
  touch  - відкат сягнув EMA20 («магніт», без нього = виснаження)
  strong - сильний сигнальний бар: тіло>=50% діапазону, закриття у верхній третині, у бік входу
  cAbove - закриття сигн. бара вище хаю попереднього (лонг)
  adx    - контекст сильного тренду: ADX>=20 (не флет)
  trap   - «пастка»: друга хвиля оновила лоу першої (виб'є слабких)
ДИСЦИПЛІНА: варіант обирається ЛИШЕ за IS; OOS — суддя. Реалістичні витрати."""
import numpy as np, pandas as pd
import lib_data as L, strategies as ST, engine as E

BASE = {"BTC": ST.resample(L.load_btc_15m(), "4h"), "ETH": L.load_any("quant/data/eth_4h.csv"),
        "SOL": L.load_any("quant/data/sol_4h.csv"), "BNB": L.load_any("quant/data/bnb_4h.csv")}
FEE, ES, SS = 0.0005, 0.0005, 0.0010
LA_ENTRY, PB_MAX = 2, 15

def naive(t): ts = pd.Timestamp(t); return ts.tz_localize(None) if ts.tzinfo else ts
def adxv(d):
    h, l = d["high"], d["low"]; up = h.diff(); dn = -l.diff()
    pdm = ((up > dn) & (up > 0))*up; mdm = ((dn > up) & (dn > 0))*dn
    tr = E.true_range(d); a = tr.ewm(alpha=1/14, adjust=False).mean()
    pdi = 100*pdm.ewm(alpha=1/14, adjust=False).mean()/a; mdi = 100*mdm.ewm(alpha=1/14, adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)).ewm(alpha=1/14, adjust=False).mean().to_numpy()

def signals(d, cfg):
    o, h, l, c = [d[x].to_numpy() for x in ["open", "high", "low", "close"]]
    e20 = E.ema(d["close"], 20).to_numpy(); e200 = E.ema(d["close"], 200).to_numpy()
    a14 = E.atr(d, 14).to_numpy(); ax = adxv(d); n = len(c); out = []
    for side in (1, -1):
        in_pb = False; count = 0; up_prev = False; pb_ext = leg1_ext = None; pb_bars = 0
        for i in range(210, n-3):
            if cfg.get("trend200"):
                tok = (c[i] > e200[i] and e20[i] > e200[i]) if side > 0 else (c[i] < e200[i] and e20[i] < e200[i])
            else:
                tok = c[i] > e20[i] if side > 0 else c[i] < e20[i]
            if not tok:
                in_pb = False; count = 0; up_prev = False; continue
            hh = (h[i] > h[i-1]) if side > 0 else (l[i] < l[i-1])       # спроба у бік тренду
            lh = (h[i] < h[i-1]) if side > 0 else (l[i] > l[i-1])       # контр-хвиля
            if not in_pb:
                if lh:
                    in_pb = True; count = 0; up_prev = False; pb_bars = 0
                    pb_ext = l[i] if side > 0 else h[i]
                continue
            pb_bars += 1
            if pb_bars > PB_MAX:                                        # затягнувся -> це вже флет
                in_pb = False; count = 0; continue
            pb_ext = min(pb_ext, l[i]) if side > 0 else max(pb_ext, h[i])
            if hh and not up_prev:
                count += 1
                if count == 1:
                    leg1_ext = pb_ext
                elif count == 2:                                        # H2/L2 сигнальний бар
                    ok = np.isfinite(a14[i])
                    if cfg.get("touch"):
                        ok = ok and ((pb_ext <= e20[i]) if side > 0 else (pb_ext >= e20[i]))
                    if cfg.get("strong"):
                        rng = h[i]-l[i]; body = abs(c[i]-o[i])
                        ok = ok and rng > 0 and body >= 0.5*rng and \
                             (((c[i]-l[i])/rng >= 0.6 and c[i] > o[i]) if side > 0
                              else ((h[i]-c[i])/rng >= 0.6 and c[i] < o[i]))
                    if cfg.get("cAbove"):
                        ok = ok and ((c[i] > h[i-1]) if side > 0 else (c[i] < l[i-1]))
                    if cfg.get("adx"):
                        ok = ok and np.isfinite(ax[i]) and ax[i] >= cfg["adx"]
                    if cfg.get("trap"):
                        ok = ok and ((pb_ext < leg1_ext) if side > 0 else (pb_ext > leg1_ext))
                    if ok:
                        entry = h[i] if side > 0 else l[i]              # стоп-вхід за екстремумом сигн. бара
                        sl = min(pb_ext, l[i]) if side > 0 else max(pb_ext, h[i])
                        D = max((entry - sl) if side > 0 else (sl - entry), 0.5*a14[i])
                        out.append((i, side, entry, D))
                    in_pb = False; count = 0                            # одна спроба на відкат
            up_prev = hh
    out.sort(key=lambda x: x[0])
    return out

def taken(d, cfg, rr=2.0):
    """тригер стоп-входу (<=LA_ENTRY барів) + послідовне виконання одна-позиція-за-раз."""
    h, l, c = [d[x].to_numpy() for x in ["high", "low", "close"]]; n = len(c); idx = d.index
    out = []; ou = -1
    for sb, side, entry, D in signals(d, cfg):
        if sb <= ou: continue
        eb = None
        for j in range(sb+1, min(sb+1+LA_ENTRY, n)):
            if (h[j] > entry) if side > 0 else (l[j] < entry): eb = j; break
        if eb is None: continue                                          # не тригернуло -> скасовано
        stop = entry - side*D; tgt = entry + side*rr*D; j = eb; ex = None
        while j < n:
            if (l[j] <= stop) if side > 0 else (h[j] >= stop): ex = ("stop", stop, j); break
            if (h[j] >= tgt) if side > 0 else (l[j] <= tgt): ex = ("tgt", tgt, j); break
            j += 1
        if ex is None: ex = ("eod", c[-1], n-1)
        en = entry*(1 + side*ES)
        exf = ex[1]*(1 - side*SS) if ex[0] == "stop" else ex[1]
        R = side*(exf-en)/D - 2*FEE*(en/D)
        out.append((naive(idx[eb]), side, R)); ou = ex[2]
    return out

def seg_rows(cfg, rr=2.0):
    rows = []
    for coin, d in BASE.items():
        cut = naive(d.index[int(len(d)*0.6)])
        for ts, side, R in taken(d, cfg, rr):
            rows.append(("OOS" if ts >= cut else "IS", ts, side, R))
    return pd.DataFrame(rows, columns=["seg", "ts", "side", "R"])

def brief(T, seg):
    s = T[T.seg == seg]
    if not len(s): return 0, float("nan"), float("nan")
    return len(s), s["R"].mean(), (s["R"] > 0).mean()*100

VARIANTS = [
    ("V0 база (тренд EMA20)",            {}),
    ("V1 +touch EMA20 (магніт)",         {"touch": 1}),
    ("V2 +сильний бар",                  {"strong": 1}),
    ("V3 +закр>hi попер. бара",          {"cAbove": 1}),
    ("V4 +ADX>=20 (не флет)",            {"adx": 20}),
    ("V5 +trap (L2 нижче L1)",           {"trap": 1}),
    ("V6 комбо touch+strong+ADX",        {"touch": 1, "strong": 1, "adx": 20}),
    ("V7 тренд EMA200-узгодж.+touch",    {"trend200": 1, "touch": 1}),
]
print("H2/L2 Брукса, 4 монети 4h, RR2, реалістичні витрати. Вибір варіанта — ЛИШЕ за IS.\n")
print(f"{'варіант':32s} | {'n IS':>5} {'exp IS':>7} {'WR':>4} | {'n OOS':>5} {'exp OOS':>8} {'WR':>4}")
print("-"*76)
res = {}
for name, cfg in VARIANTS:
    T = seg_rows(cfg); res[name] = (cfg, T)
    ni, ei, wi = brief(T, "IS"); no, eo, wo = brief(T, "OOS")
    print(f"{name:32s} | {ni:5d} {ei:+7.3f} {wi:3.0f}% | {no:5d} {eo:+8.3f} {wo:3.0f}%")

# вибір за IS (правило: найвищий IS exp при n_IS>=300)
cand = [(name, brief(T, "IS")[1]) for name, (cfg, T) in res.items() if brief(T, "IS")[0] >= 300]
best = max(cand, key=lambda x: x[1])[0]
cfg_best, T_best = res[best]
print(f"\nОБРАНО на IS: {best}")

# RR-стадія для обраного (теж лише за IS)
print(f"\nRR для обраного варіанта (вибір за IS):")
rr_res = {}
for rr in [1.0, 1.5, 2.0]:
    T = seg_rows(cfg_best, rr); rr_res[rr] = T
    ni, ei, wi = brief(T, "IS"); no, eo, wo = brief(T, "OOS")
    print(f"  RR {rr:.1f} | IS n={ni} exp={ei:+.3f} WR={wi:.0f}% | OOS n={no} exp={eo:+.3f} WR={wo:.0f}%")
best_rr = max(rr_res, key=lambda rr: rr_res[rr][rr_res[rr].seg == "IS"]["R"].mean())
print(f"ОБРАНО RR={best_rr}")

# фінальний вердикт обраної зв'язки на OOS + місячні
T = rr_res[best_rr]; O = T[T.seg == "OOS"].sort_values("ts")
r = O["R"].values; eq = np.cumprod(1 + 0.01*r)
me = pd.Series(eq, index=pd.DatetimeIndex(O["ts"])).resample("ME").last().dropna()
mr = me.pct_change().dropna(); mr = pd.concat([pd.Series([me.iloc[0]-1], index=[me.index[0]]), mr])*100
dd = ((eq/np.maximum.accumulate(eq))-1).min()*100
span = (O["ts"].max()-O["ts"].min()).days/30.44
print(f"\nФІНАЛ (OOS, risk 1%): n={len(r)} ({len(r)/span:.1f}/міс) exp={r.mean():+.3f}R WR={(r>0).mean()*100:.0f}% "
      f"| сер/міс {mr.mean():+.2f}% медіана {mr.median():+.2f}% +міс {(mr>0).mean()*100:.0f}% DD {dd:.0f}%")
print("Довідка: наша база KC+FVG OOS реалістично = exp +0.120R, +4.4%/міс, DD -31%")
