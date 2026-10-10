"""Fine sweep: where the live daily 8-EMA sits vs the entry, 0.1% buckets from -0.5 (8-EMA ABOVE the entry) to +1.5 (8-EMA BELOW the
entry, past the 1% target) (user, 2026-10-10). Spec fixed before running. v1 trades A + B, E1 and E2. gap = (entry - live daily
8-EMA) / entry x 100: positive = the line is below us (support), negative = above us. Cells are small: also a 3-bucket rolling
average. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "157_support_cluster.py").read().split('print(f"v1 trades')[0])
edges = [round(x, 1) for x in np.arange(-0.5, 1.51, 0.1)]
for en in EX:
    Y = X0[(X0.ex == en) & (((X0.ov >= -0.5) & (X0.ov < 0)) | ((X0.ov >= 0) & (X0.atrp >= 3)))].copy()
    bb = B.loc[Y.ix]; Y["gap"] = ((bb.entry - bb.D8) / bb.entry * 100).values
    print(f"\n## {en} ({len(Y)} trades; {(Y.gap < -0.5).sum()} with the 8-EMA > 0.5% above, {(Y.gap >= 1.5).sum()} with it > 1.5% below)")
    print("| daily 8-EMA vs entry | trades | target / stall / stop % | Rs/trade @1L | 3-bucket rolling Rs/trade |\n|---|---|---|---|---|")
    vals = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        g = Y[(Y.gap >= lo) & (Y.gap < hi)]; vals.append(g)
    for k, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
        g = vals[k]; roll = pd.concat(vals[max(0, k - 1):k + 2])
        lab = f"{'above' if hi <= 0 else 'below'} {abs(lo):.1f}-{abs(hi):.1f}%" if hi <= 0 or lo >= 0 else f"{lo:+.1f} to {hi:+.1f}%"
        o = g.o
        print(f"| {lab} | {len(g)} | " + (f"{(o=='target').mean()*100:.0f} / {(o=='stall').mean()*100:.0f} / {(o=='stop').mean()*100:.0f}" if len(g) else "") +
              f" | {g.rs1L.mean():+.0f} | {roll.rs1L.mean():+.0f} (n {len(roll)}) |" if len(g) else f"| {lab} | 0 | | | |")
