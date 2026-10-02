"""Pre-breach detector -- SPEC section 7 (secondary): do the pre-open features separate the REAL
swing R of BC v2 touch trades? Canonical population via population_builder.build_population
(bc_v2_recipe, gate_clock="T-1", primed_engine exits). Pre-open features joined post hoc on
(ticker, entry_date) from panel.csv -- telemetry only, never used to gate (Gate Integrity).

Usage: python3 06_stock_side.py CHUNK NCHUNKS  -> bc_v2_chunk_{CHUNK}.csv
       python3 06_stock_side.py report
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent


def build(chunk, nchunks):
    import backtest
    from population_builder import build_population, bc_v2_recipe
    tickers = sorted(pd.read_csv(ROOT / "nifty500_universe.csv", header=None)[0])[chunk::nchunks]
    pop = build_population(tickers, backtest.load, bc_v2_recipe, gate_clock="T-1", verbose=True)
    pop.to_csv(OUT / f"bc_v2_chunk_{chunk}.csv", index=False)


def stack(r):
    w, l = r[r > 0], r[r <= 0]
    return (f"{len(r)} | {r.mean():+.3f} | {r.median():+.3f} | {(r>0).mean()*100:.1f} | {(r>=.25).mean()*100:.1f} | "
            f"{(r>=.5).mean()*100:.1f} | {(r>=1).mean()*100:.1f} | {w.mean()/abs(l.mean()):.2f}")


def report():
    import glob
    pop = pd.concat([pd.read_csv(f, parse_dates=["entry_date"]) for f in sorted(glob.glob(str(OUT / "bc_v2_chunk_*.csv")))])
    print(f"BC v2 canonical population n={len(pop)}, {pop.entry_date.min().date()}..{pop.entry_date.max().date()}")
    panel = pd.read_csv(OUT / "panel.csv", parse_dates=["date"])
    sc = pd.read_csv(OUT / "detector_scores.csv", parse_dates=["date"])
    j = pop.merge(panel, left_on=["ticker", "entry_date"], right_on=["ticker", "date"], how="left", validate="1:1")
    print(f"joined to panel: {j.date.notna().sum()} of {len(j)} (unmatched = entry days whose T-1 row is not in the panel)")
    j = j[j.date.notna()].copy()
    j = j.merge(sc, on=["ticker", "date"], how="left", validate="1:1")
    j["gap_through"] = j.gap_through.astype(bool)
    j["year"] = j.entry_date.dt.year
    j["score"] = np.where(j.gap_through, 1.0, j.score_dist)
    hdr = "| cohort | n | meanR | medR | win>0 | >=0.25R | >=0.5R | >=1R | payoff |\n|---|---|---|---|---|---|---|---|---|"
    for feat, lab in [("score", "pre-open fire score (distance-only logistic)"), ("gap_pct", "opening gap %"),
                      ("dist_open_atr", "open distance (ATR)")]:
        x = j.dropna(subset=[feat])
        hi = x[feat] >= x[feat].median()
        print(f"\n=== {lab}: split at median, real primed_engine R ===\n{hdr}")
        print(f"| BASELINE | {stack(x.r_multiple)} |")
        print(f"| {feat} >= median | {stack(x[hi].r_multiple)} |")
        print(f"| {feat} < median | {stack(x[~hi].r_multiple)} |")
        print("per-year meanR (>= median / < median): " + ", ".join(
            f"{yr}: {g[g[feat] >= x[feat].median()].r_multiple.mean():+.3f}/{g[g[feat] < x[feat].median()].r_multiple.mean():+.3f}"
            for yr, g in x.groupby("year")))
    gt = j[j.gap_through]
    print(f"\ngap-through-open entries vs intraday-touch entries:\n{hdr}")
    print(f"| gap-through | {stack(gt.r_multiple)} |")
    print(f"| intraday touch | {stack(j[~j.gap_through].r_multiple)} |")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report()
    else:
        build(int(sys.argv[1]), int(sys.argv[2]))
