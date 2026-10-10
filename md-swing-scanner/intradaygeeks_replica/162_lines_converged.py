"""Converged lines = chop? (user, 2026-10-10 theory, backed by practitioner ribbon literature: tangled / converged averages = range,
pullback entries get run over). Spec fixed before running. v1 trades A + B, E1 and E2. (1) Distance between the 1H EMA34 and the live
daily 8-EMA at entry, as % of price (absolute): < 0.25 | 0.25-0.5 | 0.5-1 | > 1. (2) The 1H 'ribbon': distance between the 1H EMA8 and
the 1H EMA34 (absolute): < 0.25 | 0.25-0.5 | 0.5-1 | > 1. (3) both converged (< 0.5 each) vs not. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "157_support_cluster.py").read().split('print(f"v1 trades')[0])
H = "| group | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
BK = ((0, 0.25, "< 0.25% apart (converged)"), (0.25, 0.5, "0.25-0.5% apart"), (0.5, 1, "0.5-1% apart"), (1, 99, "> 1% apart"))
for en in EX:
    Y = X0[(X0.ex == en) & (((X0.ov >= -0.5) & (X0.ov < 0)) | ((X0.ov >= 0) & (X0.atrp >= 3)))].copy()
    bb = B.loc[Y.ix]
    Y["d34_d8"] = (abs(bb.ema34 - bb.D8) / bb.entry * 100).values; Y["rib"] = (abs(bb.ema34 - bb.H8) / bb.entry * 100).values
    print(f"\n## {en} ({len(Y)} trades)\n### (1) 1H EMA34 vs live daily 8-EMA\n" + H)
    for lo, hi, lab in BK: print(row(lab, Y[(Y.d34_d8 >= lo) & (Y.d34_d8 < hi)]))
    print("### (2) 1H ribbon: 1H EMA8 vs 1H EMA34\n" + H)
    for lo, hi, lab in BK: print(row(lab, Y[(Y.rib >= lo) & (Y.rib < hi)]))
    both = (Y.d34_d8 < 0.5) & (Y.rib < 0.5)
    print("### (3) both converged\n" + H); print(row("all lines within 0.5% (knot)", Y[both])); print(row("not a knot", Y[~both]))
