"""Тест стратегії на АКЦІЯХ/ІНДЕКСАХ (untuned, ті самі правила KC+FVG, 1D).
ts у файлах зламаний -> використовуємо ПОРЯДОК барів; IS/OOS 60/40 за позицією.
Це чесний крос-асет тест узагальнення."""
import importlib.util, builtins, numpy as np, pandas as pd
_p = builtins.print; builtins.print = lambda *a, **k: None
spec = importlib.util.spec_from_file_location("c60", "quant/60_stop_width.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print = _p
setups, taken = m.setups, m.taken

U = "/root/.claude/uploads/1a1f9a43-9b33-5f10-987c-59946e91120c"
FILES = {"QQQ(Nasdaq)": "qqq", "AAPL": "aapl", "TSLA": "tsla", "NVDA": "nvda", "MSFT": "msft"}
import glob
def load(tag):
    path = glob.glob(f"{U}/*-{tag}_1d.csv")[0]
    raw = pd.read_csv(path)
    n = len(raw)
    idx = pd.date_range("1990-01-01", periods=n, freq="B")   # синтетичні дати (порядок зберігається)
    return pd.DataFrame({"open": raw["open"].values, "high": raw["high"].values,
                         "low": raw["low"].values, "close": raw["close"].values}, index=idx)

print("Крос-асет тест (KC+FVG, 1D, untuned). IS/OOS 60/40 за порядком барів.\n")
print(f"{'інструмент':14s} | {'n':>4} {'IS exp':>7} {'OOS exp':>8} {'OOS WR':>7} {'OOS sumR':>9}")
print("-"*58)
agg_is, agg_oos = [], []
for name, tag in FILES.items():
    d = load(tag); n = len(d); cut = d.index[int(n*0.6)]
    rows = []
    for ts, si, raw, D, extype, exlvl in taken(d, "KF", 2.0, 0.5):
        r = si*(exlvl-raw)/D - 2*0.0005*(raw/D)
        rows.append((ts, r))
    T = pd.DataFrame(rows, columns=["t", "r"])
    iss = T[T["t"] < cut]["r"].values; oos = T[T["t"] >= cut]["r"].values
    agg_is += list(iss); agg_oos += list(oos)
    ie = iss.mean() if len(iss) else 0; oe = oos.mean() if len(oos) else 0
    wr = (oos > 0).mean()*100 if len(oos) else 0
    print(f"{name:14s} | {len(T):4d} {ie:+7.3f} {oe:+8.3f} {wr:6.0f}% {oos.sum():+8.0f}")
ai, ao = np.array(agg_is), np.array(agg_oos)
print("-"*58)
print(f"{'РАЗОМ':14s} | {len(ai)+len(ao):4d} {ai.mean():+7.3f} {ao.mean():+8.3f} {(ao>0).mean()*100:6.0f}% {ao.sum():+8.0f}")
print(f"\nКрипта (1D) OOS була +0.20R. Якщо акції теж у плюсі OOS -> едж УНІВЕРСАЛЬНИЙ.")
print("Якщо мінус -> едж крипто-специфічний (теж важливо знати).")
