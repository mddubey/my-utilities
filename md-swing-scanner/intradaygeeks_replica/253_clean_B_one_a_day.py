"""ONE A DAY FROM THE WIDE-STOP CLEAN REJECTIONS (user, 2026-10-18: 'if I have not entered by 11:15, only the big clean rejections -- maximise the one trade').
Chat only. Group B (250: 10:15 red candle at the 1H 34, lower wick < 10%, upper wick >= 0.3% of price, stop = candle high > 0.5%; ATR >= 3%, >= Rs100, daily 8
not in path; 11:15 entry). Levers fixed before running: target 1% / 1.5% / 2% / 1x the stop / none (out after 5 hourly bars or the day's last bar);
filter all vs big pierce (> 0.59% above the line = 250's median); pick highest ATR / biggest pierce / smallest stop. Report per Rs1k risk (+ @1L), years, DD, streak."""
import sys, os, io, contextlib, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, os.path.dirname(HERE))
import numpy as np, pandas as pd
from data.paths import INTRADAY_60M_DIR
sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()): G = runpy.run_path("244_stop_above_earlier_wick.py")
B = G["G"]["B"]; cache = G["cache"]
b = B[(B.hour == "10:15") & B.red & (B.price_ok == True) & (B.atrp >= 3) & (B.high >= B.ema34) & (B.entry < B.ema34)].copy()
b = b[~((b.s8 < b.entry) & (b.s8 > b.entry * 0.99))]
rg = b.high - b["low"]; lw = (np.minimum(b.open, b.entry) - b["low"]) / rg; uwp = (b.high - np.maximum(b.open, b.entry)) / b.entry * 100
b = b[(lw < 0.10) & (uwp >= 0.3) & ((b.high / b.entry - 1) * 100 > 0.5)].copy()
b["stop_pct"] = (b.high / b.entry - 1) * 100; b["pierce"] = (b.high / b.ema34 - 1) * 100
def run(r, tgt):
    h = cache.get(r.ticker)
    if h is None:
        h = pd.read_csv(INTRADAY_60M_DIR / f"{r.ticker}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None); h = h[~h.index.duplicated()].sort_index(); cache[r.ticker] = h
    H, L, C, T = h.High.values, h.Low.values, h.Close.values, h.index; day = T.normalize(); i = h.index.get_loc(pd.Timestamp(f"{str(r.date)[:10]} 10:15"))
    tg = r.entry * (1 - tgt / 100) if tgt else -1; px, o = None, "stall"
    for j in range(i + 1, len(C)):
        if day[j] != day[i]: px = C[j - 1]; break
        if H[j] >= r.high: px, o = r.high, "stop"; break
        if tgt and L[j] <= tg: px, o = tg, "target"; break
        if j - i >= 5 or j + 1 >= len(C) or day[j + 1] != day[i]: px = C[j]; break
    ret = (r.entry - px) / r.entry * 100; return ret * 1000 - 85, (ret - 0.085) / r.stop_pct * 1000, o
TG = {"1%": lambda r: 1.0, "1.5%": lambda r: 1.5, "2%": lambda r: 2.0, "1x the stop": lambda r: r.stop_pct, "no target": lambda r: None}
for k, f in TG.items():
    res = [run(r, f(r)) for _, r in b.iterrows()]; b[f"{k}|1L"] = [x[0] for x in res]; b[f"{k}|1k"] = [x[1] for x in res]; b[f"{k}|o"] = [x[2] for x in res]
b["yr"] = b.date.astype(str).str[:4]; b["d"] = b.date.astype(str).str[:10]; MED = 0.59
def plan(S, key, asc, k):
    o = S.sort_values(["d", key], ascending=[True, asc]).drop_duplicates("d"); r = o[f"{k}|1k"]; eq = r.cumsum(); s = (r < 0).astype(int).astype(str).str.cat(); w = o[f"{k}|o"]
    return (f"{len(o)} | {(w=='target').mean()*100:.0f} / {(w=='stall').mean()*100:.0f} / {(w=='stop').mean()*100:.0f}% | {o[f'{k}|1L'].mean():+.0f} | {r.mean():+.0f} | "
            + " / ".join(f"{r[o.yr == y].mean():+.0f}" for y in ("2024", "2025", "2026")) + f" | {eq.iloc[-1]:+,.0f} / {(eq-eq.cummax()).min():,.0f} | {max(len(x) for x in s.split('0'))} |")
print(f"{len(b)} wide-stop clean rejections on {b.d.nunique()} days; big pierce (> {MED}%): {(b.pierce > MED).sum()} on {b[b.pierce > MED].d.nunique()} days")
print("| filter | pick | target | trades | target / stall / stop | @1L | @1k risk | @1k 2024 / 2025 / 2026 | @1k total / max DD | worst streak |\n|---|---|---|---|---|---|---|---|---|---|")
for fl, S in (("all", b), ("big pierce > 0.59%", b[b.pierce > MED])):
    for pk, key, asc in (("highest ATR", "atrp", False), ("biggest pierce", "pierce", False), ("smallest stop", "stop_pct", True)):
        for k in TG: print(f"| {fl} | {pk} | {k} | " + plan(S, key, asc, k))
