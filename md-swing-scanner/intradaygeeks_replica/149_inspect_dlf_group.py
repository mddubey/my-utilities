"""Inspect the DLF-type group (user, 2026-10-10: '442 trades, 26% still hit target -- wide stops or something else?').
Spec fixed before running. Trades: 137 frame (10:15, 1% / stop <= 0.5%, full stack) that OPENED ABOVE the 1H EMA34 and fell > 0.25 of a
day's ATR from the day's high before entry. Compare TARGET vs STOP vs STALL trades on: stop %, stop / ATR, already-moved (ATR units),
open above EMA34 %, gap %, ATR %, price vs live daily 8-EMA, hour the trade ended; plus the same for the 'opened below + little moved'
group for contrast. Descriptive only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "147_new_slices_overlap.py").read().split('print(f"{len(Z)} trades')[0])
Z["nr"] = Z.stop / Z.atrp; Z["d8gap"] = (Z.entry - Z.d8_live) / Z.entry * 100
G = Z[~Z.A & ~Z.C]; K = Z[Z.A & Z.C]
cols = (("stop %", "stop"), ("stop / ATR", "nr"), ("already moved (x ATR)", "moved"), ("open vs 1H EMA34 %", "open_vs_e34"),
        ("gap %", "gap"), ("ATR %", "atrp"), ("price above daily 8-EMA %", "d8gap"), ("best move % before exit", "best"))
for nm, X in (("DLF type: opened ABOVE, fell a lot (n=%d)" % len(G), G), ("contrast: opened BELOW, rallied in (n=%d)" % len(K), K)):
    print(f"\n## {nm} -- medians by outcome\n| measure | TARGET | STALL | STOP |\n|---|---|---|---|")
    for lab, c in cols:
        print(f"| {lab} | " + " | ".join(f"{X[X.o == o][c].median():+.2f}" for o in ("target", "stall", "stop")) + " |")
    print(f"| trades | " + " | ".join(f"{(X.o == o).sum()}" for o in ("target", "stall", "stop")) + " |")
    print(f"| median hours to exit | " + " | ".join(f"{X[X.o == o].bh.median():.0f}" for o in ("target", "stall", "stop")) + " |")
