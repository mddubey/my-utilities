"""Check 1 as declared (user, 2026-10-10 -- run it, user not yet convinced by the logic): skip when the price sits RIGHT ON TOP of
the live daily 8-EMA (support just under the entry). Spec fixed before running. v1 trades (10:15, red, full stack, Rs100 floor, cut
dojis removed), branches A and B, exits E1 / E2. d8gap = (entry - live daily 8-EMA) / entry, in % (positive = the line is below us).
Rules: skip 0 <= d8gap < 0.3%; neighbour: skip 0 <= d8gap < 0.5%. Report ALL / kept / removed, plus buckets. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "155_spike_above_stop.py").read().split("\nH = ")[0])
B["d8gap"] = (B.entry - (2 / 9 * B.entry + 7 / 9 * B.s8)) / B.entry * 100
X0["d8gap"] = X0.ix.map(B.d8gap)
H = "| group | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
for en in EX:
    for bn, bm in (("A", lambda d: (d.ov >= -0.5) & (d.ov < 0)), ("B", lambda d: (d.ov >= 0) & (d.atrp >= 3))):
        X = X0[X0.ex == en]; X = X[bm(X)]
        on3 = (X.d8gap >= 0) & (X.d8gap < 0.3); on5 = (X.d8gap >= 0) & (X.d8gap < 0.5)
        print(f"\n## {en} -- branch {bn}\n" + H); print(row("ALL", X))
        print(row("KEPT (skip 0-0.3% on top)", X[~on3])); print(row("REMOVED: price 0-0.3% above the daily 8-EMA", X[on3]))
        print(row("KEPT (skip 0-0.5%)", X[~on5])); print(row("REMOVED: price 0-0.5% above", X[on5]))
        for lab, lo, hi in (("bucket: price BELOW the daily 8-EMA", -99, 0), ("bucket: 0.5-1% above", 0.5, 1), ("bucket: > 1% above", 1, 99)):
            print(row(lab, X[(X.d8gap >= lo) & (X.d8gap < hi)]))
