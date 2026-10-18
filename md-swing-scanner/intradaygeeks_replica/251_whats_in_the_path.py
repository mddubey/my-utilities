"""WHAT SITS BETWEEN THE ENTRY AND THE 1% TARGET? (user, 2026-10-18). Descriptive, chat only. For each support level known at 11:15, is it inside the path
(target < level < entry)? Levels: yesterday's close, yesterday's low, the day's low before 11:15, daily PP, daily S1, weekly PP, weekly S1, daily 34,
the 1H EMA8 (when below the entry). (The daily 8 is already excluded from both groups.) Groups: A = the scan's trades (245's X, 728, stop <= 0.5%);
B = the big clean rejections (250's X rebuilt, 1,127, stop > 0.5%). Per level: share of trades with it in the path, target / stall / stop and net @1k
with vs without; plus 'nothing in the path'."""
import sys, os, io, contextlib, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, os.path.dirname(HERE))
import numpy as np, pandas as pd
from data.paths import DAILY_DIR, INTRADAY_60M_DIR
sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()): G = runpy.run_path("244_stop_above_earlier_wick.py")
B = G["G"]["B"]; walk = G["walk"]; cache = G["cache"]
# group A: 245's population (rebuild via 245)
with contextlib.redirect_stdout(io.StringIO()): G5 = runpy.run_path("245_hourly34_stats.py")
XA = G5["X"]; NA = G5["G"]["N"].reset_index(drop=True)
A = pd.DataFrame({"ix": NA.loc[XA.index, "ix"].values, "o": XA.o.values, "rs1k": XA.rs1k.values, "rs1L": XA.rs1L.values})
# group B
b = B[(B.hour == "10:15") & B.red & (B.price_ok == True) & (B.atrp >= 3) & (B.high >= B.ema34) & (B.entry < B.ema34)].copy()
b = b[~((b.s8 < b.entry) & (b.s8 > b.entry * 0.99))]
rg = b.high - b["low"]; lw = (np.minimum(b.open, b.entry) - b["low"]) / rg; uwp = (b.high - np.maximum(b.open, b.entry)) / b.entry * 100
b = b[(lw < 0.10) & (uwp >= 0.3) & ((b.high / b.entry - 1) * 100 > 0.5)]
res = [walk(r, r.high) for _, r in b.iterrows()]
Bg = pd.DataFrame({"ix": b.index.values, "o": [x["o"] for x in res], "rs1k": [x["rs1k"] for x in res], "rs1L": [x["rs1L"] for x in res]})
dcache = {}
def levels(ix):
    r = B.loc[ix]; t = r.ticker; D = pd.Timestamp(str(r.date)[:10])
    if t not in dcache:
        d = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).sort_index(); dcache[t] = d[~d.index.duplicated()].dropna(subset=["Close"])
    d = dcache[t]; p = d[d.index < D]; y = p.iloc[-1]; pp = (y.High + y.Low + y.Close) / 3
    w = p.resample("W-FRI").agg({"High": "max", "Low": "min", "Close": "last"}).dropna(); w = w[w.index < D - pd.Timedelta(days=D.weekday())]; wy = w.iloc[-1]; wpp = (wy.High + wy.Low + wy.Close) / 3
    if t not in cache:
        h = pd.read_csv(INTRADAY_60M_DIR / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None); cache[t] = h[~h.index.duplicated()].sort_index()
    h = cache[t]; pre = h[(h.index.normalize() == D) & (h.index < D + pd.Timedelta("11h15min"))]
    L = {"yesterday's close": y.Close, "yesterday's low": y.Low, "day's low before 11:15": pre.Low.min() if len(pre) else np.nan, "daily PP": pp, "daily S1": 2 * pp - y.High,
         "weekly PP": wpp, "weekly S1": 2 * wpp - wy.High, "daily 34": p.Close.ewm(span=34, adjust=False).mean().iloc[-1], "1H EMA8": r.ema8}
    e = r.entry; return {k: bool(v == v and e * 0.99 < v < e) for k, v in L.items()}
for lab, Gp in (("A: the scan's trades (stop <= 0.5%)", A), ("B: big clean rejections (stop > 0.5%)", Bg)):
    P = pd.DataFrame([levels(ix) for ix in Gp.ix]); Z = pd.concat([Gp.reset_index(drop=True), P], axis=1)
    def s(x): return f"{len(x)} | {(x.o=='target').mean()*100:.0f} / {(x.o=='stall').mean()*100:.0f} / {(x.o=='stop').mean()*100:.0f}% | {x.rs1k.mean():+.0f}"
    print(f"\n### {lab} -- all {s(Z)}\n| level inside the 1% path | in path: n / target-stall-stop / net @1k | not in path: n / target-stall-stop / net @1k |\n|---|---|---|")
    for k in P.columns: print(f"| {k} | {s(Z[Z[k]])} | {s(Z[~Z[k]])} |")
    anyl = P.any(axis=1); cnt = P.sum(axis=1)
    print(f"| ANY of these | {s(Z[anyl])} | {s(Z[~anyl])} |")
    for c in (0, 1, 2, 3): print(f"| exactly {c} level(s) in the path{' (3 = 3 or more)' if c == 3 else ''} | {s(Z[(cnt == c) if c < 3 else (cnt >= 3)])} | |")
