"""v1 BELOW the Nifty 200-day, kept only when the entry is far below YESTERDAY'S HIGH (user, 2026-10-12; lead from 181, re-confirmed on
the official open; spec declared in chat before running). v1 rules otherwise unchanged (164 population, official day open). Rule:
entry <= yesterday's high x (1 - X%), X = 2.5 (main), 2 and 3 shown (not tuned). Both exits, both branches, by year, the 2026-03..09
bear phase alone, and the same rule applied ABOVE the 200-day (must not hurt v1 there). PASS = kept trades positive in BOTH exits AND
in the bear phase alone (both exits). Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import pandas as pd
HERE = Path(__file__).resolve().parent
__file__ = str(HERE / "164_v1_without_nifty200.py")
exec(open(HERE / "164_v1_without_nifty200.py").read().split('\nH = "')[0])
for c in ("entry", "prev_high"): V["_" + c] = V.ix.map(B[c])
V["dyh"] = (V._entry / V._prev_high - 1) * 100; V["br"] = ["A" if x < 0 else "B" for x in V.ov]


def r(lab, g):
    if len(g) == 0: return f"| {lab} | 0 |"
    o = g.o; y = " / ".join(f"{g[g.yr == k].rs1L.mean():+.0f} ({(g.yr == k).sum()})" if (g.yr == k).any() else "-" for k in ("2024", "2025", "2026"))
    z = g[(g.n200 == False) & (g.date >= "2026-03-01")]
    return f"| {lab} | {len(g)} | {(o=='target').mean()*100:.0f} / {(o=='stall').mean()*100:.0f} / {(o=='stop').mean()*100:.0f} | {g.rs1L.mean():+.0f} | {g.rs1k.mean():+.0f} | {y} | {z.rs1L.mean():+.0f} ({len(z)}) |"


HD = "| group | trades | target / stall / stop % | Rs/trade @1L | @1k risk | 2024 / 2025 / 2026 (n) | bear phase 2026-03..09 @1L (n) |\n|---|---|---|---|---|---|---|"
for en in EX:
    X = V[V.ex == en]
    for reg, rl in ((False, "Nifty BELOW 200d"), (True, "Nifty ABOVE 200d (check: must not hurt)")):
        G = X[X.n200 == reg]
        print(f"\n## {en} -- {rl}\n{HD}"); print(r("BASELINE", G))
        for x in (2.0, 2.5, 3.0):
            k = G[G.dyh <= -x]; print(r(f"KEPT: entry >= {x}% below yesterday's high", k)); print(r(f"removed: < {x}% below", G[G.dyh > -x]))
        k = G[G.dyh <= -2.5]
        for b in ("A", "B"): print(r(f"  kept (2.5%), branch {b}", k[k.br == b]))
