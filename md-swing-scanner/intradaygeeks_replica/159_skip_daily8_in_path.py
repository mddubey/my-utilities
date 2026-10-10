"""Simplest daily-8 rule (user, 2026-10-10: 'just skip when the daily 8-EMA sits in the target path -- how much do we lose?'). Spec
fixed before running. v1 trades (10:15, red, full stack, Rs100 floor, cut dojis removed), branches A + B, exits E1 / E2. Rule: SKIP
when the live daily 8-EMA lies between the entry and the target (0% to target-distance below the entry; E1 target 1%, E2 its own
target). Report ALL / KEPT / REMOVED with setups, days, Rs per trade and TOTAL Rs @1L, by branch. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "157_support_cluster.py").read().split('print(f"v1 trades')[0])
H = "| group | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 | TOTAL @1L |\n|---|---|---|---|---|---|---|---|---|---|"
for en in EX:
    Y = X0[(X0.ex == en) & (((X0.ov >= -0.5) & (X0.ov < 0)) | ((X0.ov >= 0) & (X0.atrp >= 3)))].copy()
    bb = B.loc[Y.ix]; gap = (bb.entry - bb.D8) / bb.entry * 100
    tp = np.where(en.startswith("E1"), 1.0, np.maximum(1.0, 0.35 * bb.atrp))
    Y["inpath"] = ((gap >= 0) & (gap <= tp)).values
    Y["br"] = np.where(Y.ov < 0, "A", "B")
    print(f"\n## {en}\n" + H)
    for nm, Z in (("A + B", Y), ("branch A", Y[Y.br == "A"]), ("branch B", Y[Y.br == "B"])):
        for lab, m in (("ALL", Z.inpath | ~Z.inpath), ("KEPT (daily 8-EMA not in the path)", ~Z.inpath), ("REMOVED (daily 8-EMA in the path)", Z.inpath)):
            g = Z[m]; print(row(f"{nm}: {lab}", g) + f" {g.rs1L.sum():+,.0f} |")
