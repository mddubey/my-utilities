"""Target size vs what happened (user, 2026-10-09: 'are we aiming for unrealistic targets?'). Spec fixed before running.
Same trades as 134 (frozen frame + current layers, both candles; target = 0.5 x ATR). (1) By target size bucket (% of price):
1-1.25 | 1.25-1.5 | 1.5-2 | 2-2.5 | > 2.5: target / stall / stop %, out-of-time share, avg best move in %, Rs @1L. (2) How far the
trades actually go: share whose best price (before the exit) reached 0.5 / 0.75 / 1.0 / 1.25 / 1.5 / 2.0% below entry, by
target bucket. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "134_stall_anatomy.py").read().split("\ndef table(")[0])
A["tp"] = 0.5 * A.atrp; A["best_pct"] = A.mfe * A.tp
A["tb"] = pd.cut(A.tp, [1, 1.25, 1.5, 2, 2.5, 99], labels=["1-1.25%", "1.25-1.5%", "1.5-2%", "2-2.5%", "> 2.5%"], include_lowest=True)
print("| target size | trades | target % | stall % (out of time) | stop % | avg best move % | median best move % | Rs/trade @1L |\n|---|---|---|---|---|---|---|---|")
for b, g in A.groupby("tb", observed=True):
    print(f"| {b} | {len(g)} | {(g.o=='target').mean()*100:.0f} | {(g.o=='stall').mean()*100:.0f} ({(g.stype=='stall: out of time').mean()*100:.0f}) | {(g.o=='stop').mean()*100:.0f} | "
          f"{g.best_pct.mean():.2f} | {g.best_pct.median():.2f} | {g.rs.mean():+.0f} |")
print("\n## how far the trades actually went (share whose best price reached X% below entry before the exit)\n| target size | 0.5% | 0.75% | 1.0% | 1.25% | 1.5% | 2.0% |\n|---|---|---|---|---|---|---|")
for b, g in list(A.groupby("tb", observed=True)) + [("ALL", A)]:
    print(f"| {b} | " + " | ".join(f"{(g.best_pct >= x).mean()*100:.0f}%" for x in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)) + " |")
