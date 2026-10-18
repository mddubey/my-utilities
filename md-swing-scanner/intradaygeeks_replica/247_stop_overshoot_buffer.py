"""'IT JUST TAKES MY SL AND COMES BACK' (user, 2026-10-18, AJANTPHARM / SHYAMMETL / KISSHT). Spec fixed before running. Trades: the hourly 34 rejection
one a day (245's O). Part 1 (descriptive): for the STOPPED trades, how far the day's high after entry went past the stop (<= 0.05 / 0.05-0.1 / 0.1-0.2 /
0.2-0.5 / > 0.5% of entry), and how many then reached the 1% target later that day, or closed below the entry. Part 2: stop = the scan's stop + a buffer
b = 0.05 / 0.10 / 0.20% of the entry, (i) uncapped, (ii) capped so the total stop never exceeds 0.5%. Same hourly exit engine (244's walk). Net Rs @1L and
@1k risk (sized to each stop), target / stall / stop, top-10 trades removed, years, one-a-day max drawdown @1k."""
import sys, os, io, contextlib, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, os.path.dirname(HERE))
import pandas as pd, numpy as np
from data.paths import INTRADAY_60M_DIR
sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()): G = runpy.run_path("245_hourly34_stats.py")
O = G["O"]; G2 = G["G"]; N = G2["N"].reset_index(drop=True); walk = G2["walk"]; cache = G2["cache"]
rows = []
for idx, o in O.iterrows():
    r = N.loc[idx]; base = r.entry * (1 + o.u_risk / 100)
    h = cache.get(r.ticker)
    if h is None:
        h = pd.read_csv(INTRADAY_60M_DIR / f"{r.ticker}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
        h = h[~h.index.duplicated()].sort_index(); cache[r.ticker] = h
    D = pd.Timestamp(str(r.date)[:10]); af = h[(h.index.normalize() == D) & (h.index >= D + pd.Timedelta("11h15min"))]
    rec = dict(date=o.date, yr=o.yr, o=o.o, base_risk=o.u_risk, over=(af.High.max() / base - 1) * 100, tgt_later=(af.Low.min() <= r.entry * 0.99),
               close_below=(af.Close.iloc[-1] < r.entry), base_rs1L=o.rs1L, base_rs1k=o.rs1k, base_o=o.o)
    for b in (0.05, 0.10, 0.20):
        for cap in (False, True):
            st = base + r.entry * b / 100
            if cap: st = min(st, r.entry * 1.005)
            w = walk(r, st); k = f"b{b}{'c' if cap else ''}"
            rec.update({f"{k}_rs1L": w["rs1L"], f"{k}_rs1k": w["rs1k"], f"{k}_o": w["o"], f"{k}_risk": w["risk"]})
    rows.append(rec)
X = pd.DataFrame(rows)
assert (X.base_rs1L.round(3) == O.rs1L.values.round(3)).all()
S = X[X.o == "stop"]
print(f"PART 1 -- {len(S)} stopped trades of {len(X)} (one a day)\n| high went past the stop by | stopped trades | share | then hit the 1% target later | closed below the entry |\n|---|---|---|---|---|")
for lo, hi in ((0, 0.05), (0.05, 0.1), (0.1, 0.2), (0.2, 0.5), (0.5, 99)):
    x = S[(S.over > lo) & (S.over <= hi)]
    print(f"| {lo}-{hi}% | {len(x)} | {len(x)/len(S)*100:.0f}% | {x.tgt_later.sum()} ({x.tgt_later.mean()*100:.0f}%) | {x.close_below.sum()} ({x.close_below.mean()*100:.0f}%) |")
def line(lab, p):
    rs1L, rs1k, ow = X[f"{p}_rs1L"], X[f"{p}_rs1k"], X[f"{p}_o"]
    rk = X[f"{p}_risk"] if f"{p}_risk" in X else X.base_risk
    eq = rs1k.cumsum(); t10 = rs1L.drop(rs1L.nlargest(10).index)
    return (f"| {lab} | {rk.median():.2f}% | {(ow=='target').mean()*100:.0f} / {(ow=='stall').mean()*100:.0f} / {(ow=='stop').mean()*100:.0f}% | {rs1L.mean():+.0f} | {rs1k.mean():+.0f} | {t10.mean():+.0f} | "
            + " / ".join(f"{rs1k[X.yr == y].mean():+.0f}" for y in ("2024", "2025", "2026")) + f" | {eq.iloc[-1]:+,.0f} / {(eq-eq.cummax()).min():,.0f} |")
print(f"\nPART 2 -- one a day, {len(X)} trades\n| stop | median stop | target / stall / stop | Rs @1L | Rs @1k risk | @1L w/o top-10 trades | @1k 2024 / 2025 / 2026 | @1k total / max DD |\n|---|---|---|---|---|---|---|---|")
print(line("scan's stop (now)", "base"))
for b in (0.05, 0.10, 0.20):
    print(line(f"+ {b}% buffer, uncapped", f"b{b}")); print(line(f"+ {b}% buffer, capped at 0.5% total", f"b{b}c"))
