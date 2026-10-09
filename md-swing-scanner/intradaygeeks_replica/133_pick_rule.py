"""Pick rule: one trade a day (user, 2026-10-09). Spec fixed before running. Frozen frame (8j) + current layers (red, Nifty >
200d, stock daily 8>34, gap -0.25..+0.5). Time order respected: 09:15-candle setups are known at 10:15, 10:15-candle setups at
11:15. Plans: (A) first alarm with a setup (09:15 candle, else 10:15); (B) 10:15 candle only. Pick within the alarm by:
closest to the EMA34 (smallest dist) | highest ATR | strongest stock uptrend (daily 8/34 gap) | tightest stop | RANDOM (expected
value = average over 500 draws). Report trades, T/S/S split with avg Rs, Rs/trade @1L and @1k risk, by year, max drawdown and
longest losing streak (@1L). Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
exec(open(Path(__file__).resolve().parent / "130_rebaseline_frozen_frame.py").read().split("\nH = ")[0])
Z = B[B.red & (B.n200 == True) & (B.s8 > B.s34) & (B.gap > -0.25) & (B.gap <= 0.5)].copy()
Z["trend"] = Z.s8 / Z.s34 - 1
PICKS = (("closest to EMA34", "dist", True), ("highest ATR", "atrp", False), ("strongest stock uptrend", "trend", False),
         ("tightest stop", "stop", True))


def plan(X, mode):
    if mode == "A":
        first = X.groupby("date").hour.transform("min"); return X[X.hour == first]
    return X[X.hour == "10:15"]


def stats(lab, g):
    g = g.sort_values(["date", "hour"]); x = g.rs1L.values; eq = np.cumsum(x); dd = (eq - np.maximum.accumulate(eq)).min()
    s = (x <= 0).astype(int); best = cur = 0
    for v in s: cur = cur + 1 if v else 0; best = max(best, cur)
    parts = []
    for o in ("target", "stall", "stop"):
        k = g[g.o == o]; parts.append(f"{len(k)/len(g)*100:.0f}% ({k.rs1L.mean():+,.0f})")
    y = " / ".join(f"{g[g.yr == k].rs1L.mean():+.0f}" for k in ("2024", "2025", "2026"))
    return f"| {lab} | {len(g)} | " + " | ".join(parts) + f" | {g.rs1L.mean():+.0f} | {g.rs1k.mean():+.0f} | {g.rs1L.sum():+,.0f} | {y} | {dd:,.0f} | {best} |"


H = "| pick | trades | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | total @1L | @1L 2024 / 2025 / 2026 | max DD | longest losing streak |\n|---|---|---|---|---|---|---|---|---|---|---|"
rng = np.random.default_rng(3)
for mode, title in (("A", "PLAN A: first alarm with a setup (09:15 candle at 10:15, else 10:15 candle at 11:15)"), ("B", "PLAN B: 10:15 candle only (decided at 11:15)")):
    X = plan(Z, mode)
    print(f"\n## {title} -- {X.date.nunique()} days with a trade, {len(X)} candidate setups (avg {len(X)/X.date.nunique():.1f} per day)\n" + H)
    for nm, col, asc in PICKS:
        print(stats(nm, X.sort_values(col, ascending=asc).groupby("date").head(1)))
    r1L = [X.groupby("date").sample(1, random_state=int(rng.integers(1e9))).rs1L.mean() for _ in range(500)]
    r1k = [X.groupby("date").sample(1, random_state=int(rng.integers(1e9))).rs1k.mean() for _ in range(200)]
    print(f"| RANDOM (500 draws): Rs/trade @1L mean {np.mean(r1L):+.0f} (5th {np.percentile(r1L,5):+.0f} / 95th {np.percentile(r1L,95):+.0f}), @1k {np.mean(r1k):+.0f} | | | | | | | | | | |")
