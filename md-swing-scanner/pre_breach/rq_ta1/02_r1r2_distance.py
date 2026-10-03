"""RQ-TA Family C -- is the trigger closer to overhead R1/R2 resistance in STALL/FAIL
vs BLAST breaches? Not tested in RQ-PB-2's original confluence sweep (pp/s1/ema8/13/21/34
only -- R1/R2 were never included). Motivated directly by hand-reconstructing RBLBANK
2026-09-23 (01_reconstruct_cases.py): its DAILY R2 (438.37) was nowhere near where the
stock topped, but its WEEKLY R2 (429.20) landed almost exactly on the real intraday high
(429.50) -- so both pivot periods are tested here, not just daily.

Reuses pre_breach/rq_pb2/pivot_feats.pkl as-is (trigger, cls, r5, atr_abs already built
and verified there -- same T-1-known ATR basis as the BLAST/STALL/FAIL labels, so d_r1/d_r2
are on the same scale as the existing pp/s1/ema distances). No new population, no new
outcome definition -- purely adding two more trigger-distance features to the existing
confluence framework (rq_pb2/FINDINGS.md section E).
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PB = ROOT / "pre_breach"
sys.path.insert(0, str(ROOT))

from backtest import load  # noqa: E402
from pivots import weekly_pivots  # noqa: E402

X = pd.read_pickle(PB / "rq_pb2" / "pivot_feats.pkl")[
    ["ticker", "date", "trigger", "cls", "r5", "r10", "atr_abs"]
]

out = []
for tk, g in X.groupby("ticker"):
    try:
        dd = load(tk)              # default pivot_fn=daily_pivots
        dw = load(tk, weekly_pivots)
    except Exception:
        continue
    F = pd.DataFrame({
        "r1_d": dd.r1, "r2_d": dd.r2,
        "r1_w": dw.r1, "r2_w": dw.r2,
    }).reindex(g.date)
    gg = g.set_index("date").join(F).reset_index()
    out.append(gg)
Y = pd.concat(out).reset_index(drop=True)

for lv in ["r1_d", "r2_d", "r1_w", "r2_w"]:
    Y[f"d_{lv}"] = (Y.trigger - Y[lv]) / Y.atr_abs


def st(g):
    return pd.Series({
        "n": len(g), "BLAST%": (g.cls == "BLAST").mean() * 100,
        "FAIL%": (g.cls == "FAIL").mean() * 100, "r5_mean": g.r5.mean(),
    })


pd.set_option("display.width", 200)
print("BASELINE (full pivot_feats.pkl population)")
print(st(Y).round(2).to_frame().T)

for lv in ["r1_d", "r2_d", "r1_w", "r2_w"]:
    c = f"d_{lv}"
    valid = Y[c].notna()
    b = pd.qcut(Y.loc[valid, c].rank(method="first"), 3, labels=["T1 near/above", "T2", "T3 far below"])
    t = Y.loc[valid].groupby(b).apply(st).round(2)
    t["range(ATR)"] = Y.loc[valid].groupby(b)[c].agg(lambda s: f"{s.min():.2f}..{s.max():.2f}")
    print(f"\n{c}  (trigger minus level, ATR; positive = trigger already above the level)")
    print(t)

# RBLBANK-motivated specific cut: is R2 (either period) within 1 ATR overhead of the trigger?
Y["r2d_near"] = (Y.d_r2_d >= -1.0) & (Y.d_r2_d < 0)
Y["r2w_near"] = (Y.d_r2_w >= -1.0) & (Y.d_r2_w < 0)
print("\nDaily R2 within 1 ATR overhead of trigger")
print(Y.groupby("r2d_near").apply(st).round(2))
print("\nWeekly R2 within 1 ATR overhead of trigger")
print(Y.groupby("r2w_near").apply(st).round(2))

Y.to_pickle(Path(__file__).resolve().parent / "r1r2_feats.pkl")
