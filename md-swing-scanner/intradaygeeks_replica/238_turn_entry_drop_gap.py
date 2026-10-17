"""DROP THE GAP ZONE from the turn-entry version (user, 2026-10-17, removing mechanical filters one at a time). Spec fixed before running.
233's events (turn 0.1% below the touch high, 0.5% stop, 1% target / 15:15). Kept: liquid, >= Rs100, uptrend, branch A (opened 0-0.5% below
the line) / B (opened above), daily 8 not in the path; ATR shown two ways: current (>= 2%, B needs >= 3%) and the simpler ATR >= 3% (237).
Gap (official open vs yesterday's close) buckets: <= -2 / -2..-1 / -1..-0.25 / -0.25..+0.5 (the current zone) / +0.5..+1 / +1..+2 / > +2.
Report net Rs per Rs1 lakh, target / stall / stop, top-10 days removed, months; kept vs removed vs baseline. (Script 121, 2026-10-09, 3-yr
1H, plain touch: gap down >= 1% lost -100..-133 every year; flat / small gap up best.)"""
import pandas as pd, numpy as np
from pathlib import Path
HERE = Path(__file__).resolve().parent; COST = 0.085
A = pd.read_csv(HERE / "v1_turn_entry.csv"); A = A[A.X == 0.001]
F = A[(A.liq >= 15) & (A.pc >= 100) & A.up & ~A.in_path & A.ov.notna()].copy()
F["branch"] = np.where((F.ov >= -0.5) & (F.ov < 0), "A", np.where(F.ov >= 0, "B", "-")); F = F[F.branch != "-"]
CUR = F[(F.atr >= 2) & ((F.branch == "A") | (F.atr >= 3))]; A3 = F[F.atr >= 3]
GB = [-99, -2, -1, -0.25, 0.5, 1, 2, 99]; GL = ["<= -2%", "-2..-1%", "-1..-0.25%", "-0.25..+0.5% (zone)", "+0.5..+1%", "+1..+2%", "> +2%"]
def cell(x):
    if not len(x): return "0 | | | |"
    w = x.fixed_why; t10 = x.groupby("date").fixed_ret.sum().nlargest(10).index
    mo = "/".join(f"{(g.fixed_ret.mean()-COST)*1000:+.0f}" for _, g in x.groupby(x.date.str[:7]))
    return f"{len(x)} | {(w=='target').mean()*100:.0f} / {(w=='stall').mean()*100:.0f} / {(w=='stop').mean()*100:.0f}% | {(x.fixed_ret.mean()-COST)*1000:+.0f} | {(x[~x.date.isin(t10)].fixed_ret.mean()-COST)*1000:+.0f} | {mo}"
H = "| group | n | target / stall / stop | net Rs @1L | top-10 days removed | months 06/07/08/09/10 |\n|---|---|---|---|---|---|"
for nm, X in (("current ATR rules", CUR), ("ATR >= 3% (simpler)", A3)):
    zone = X.gap.between(-0.25, 0.5, inclusive="right")
    print(f"\n### {nm}\n{H}")
    print(f"| BASELINE, any gap | {cell(X)} |"); print(f"| KEPT: gap zone -0.25..+0.5% | {cell(X[zone])} |"); print(f"| REMOVED: outside the zone | {cell(X[~zone])} |")
    b = pd.cut(X.gap, GB, labels=GL)
    for g in GL: print(f"| gap {g} | {cell(X[b == g])} |")
    print(f"| gap down < -0.25% (all) | {cell(X[X.gap <= -0.25])} |"); print(f"| gap up > +0.5% (all) | {cell(X[X.gap > 0.5])} |")
