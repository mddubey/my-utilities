"""1H EMA8 position on current v1 (user, 2026-10-10: the old live rule 'skip EMA8 0.4-0.6% below' was a proxy for clutter in the target
path; re-test it on v1, sweep from 0.5% above the entry to 1.5% below). Spec fixed before running. v1 = 10:15, red, full stack, Rs100
floor, cut dojis removed, CONVERGED LINES removed (daily 8-EMA within 0.25% of the 1H EMA34); branches A + B; E1 and E2.
gap = (entry - 1H EMA8) / entry x 100 (positive = EMA8 below us). (1) coarse declared buckets: EMA8 above the entry | 0-0.3 | 0.3-0.4 |
0.4-0.6 (old live rule) | 0.6-1.0 | > 1.0 below; each with the share of trades having PDL / S1 / S2 in the target path (0-1% below);
(2) fine 0.1% sweep -0.5..+1.5 with a 3-bucket rolling average. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "157_support_cluster.py").read().split('print(f"v1 trades')[0])
for en in EX:
    Y = X0[(X0.ex == en) & (((X0.ov >= -0.5) & (X0.ov < 0)) | ((X0.ov >= 0) & (X0.atrp >= 3)))].copy()
    bb = B.loc[Y.ix]
    Y = Y[(abs(bb.ema34 - bb.D8) / bb.entry * 100).values >= 0.25]; bb = B.loc[Y.ix]
    Y["g8"] = ((bb.entry - bb.H8) / bb.entry * 100).values
    for c in ("PDL", "S1", "S2"):
        gg = ((bb.entry - bb[c]) / bb.entry * 100).values; Y["p_" + c] = (gg > 0) & (gg <= 1.0)
    Y["clutter"] = Y[["p_PDL", "p_S1", "p_S2"]].any(axis=1)
    print(f"\n## {en} -- v1 incl. converged-lines rule: {len(Y)} trades")
    print("| 1H EMA8 vs entry | trades | target / stall / stop % | Rs/trade @1L | @1k risk | 2024 / 2025 | PDL / S1 / S2 in path | any clutter |\n|---|---|---|---|---|---|---|---|")
    for lab, lo, hi in (("EMA8 ABOVE the entry", -99, 0), ("0-0.3% below", 0, 0.3), ("0.3-0.4% below", 0.3, 0.4), ("0.4-0.6% below (old live rule)", 0.4, 0.6), ("0.6-1.0% below", 0.6, 1.0), ("> 1.0% below", 1.0, 99)):
        g = Y[(Y.g8 >= lo) & (Y.g8 < hi)]
        if len(g) < 10: print(f"| {lab} | {len(g)} | | | | | | |"); continue
        o = g.o; y = " / ".join(f"{g[g.yr == k].rs1L.mean():+.0f}" if (g.yr == k).sum() >= 10 else "-" for k in ("2024", "2025"))
        print(f"| {lab} | {len(g)} | {(o=='target').mean()*100:.0f} / {(o=='stall').mean()*100:.0f} / {(o=='stop').mean()*100:.0f} | {g.rs1L.mean():+.0f} | {g.rs1k.mean():+.0f} | {y} | "
              f"{g.p_PDL.mean()*100:.0f}% / {g.p_S1.mean()*100:.0f}% / {g.p_S2.mean()*100:.0f}% | {g.clutter.mean()*100:.0f}% |")
    edges = [round(x, 1) for x in np.arange(-0.5, 1.51, 0.1)]; vals = [Y[(Y.g8 >= lo) & (Y.g8 < hi)] for lo, hi in zip(edges[:-1], edges[1:])]
    print("\n| 1H EMA8 vs entry (0.1%) | trades | Rs/trade @1L | 3-bucket rolling |\n|---|---|---|---|")
    for k, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
        g = vals[k]; roll = pd.concat(vals[max(0, k - 1):k + 2])
        lab = f"above {abs(hi):.1f}-{abs(lo):.1f}%" if hi <= 0 else f"below {lo:.1f}-{hi:.1f}%"
        print(f"| {lab} | {len(g)} | {g.rs1L.mean():+.0f} | {roll.rs1L.mean():+.0f} (n {len(roll)}) |" if len(g) else f"| {lab} | 0 | | {roll.rs1L.mean():+.0f} (n {len(roll)}) |")
