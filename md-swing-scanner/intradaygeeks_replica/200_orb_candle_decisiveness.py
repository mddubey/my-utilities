"""Does the opening candle's COLOUR make sense as the direction rule? (user, 2026-10-12, after the official-open fix flipped 8%).
DESCRIPTIVE on the corrected data (orb_sip.csv = official open). In-play trades split by how DECISIVE the 09:15 candle was:
body / range < 0.25 (near-doji: colour ~ coin toss) / 0.25-0.5 / >= 0.5 (strong), and by body as a multiple of daily ATR.
Paper rules, 10% ATR stop, hold to 15:15; shorts + longs; orders from 09:20 and from 09:30. Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from orb_common import read5_official
A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
S = A[(A.rv >= 1) & (A["rank"] <= 20) & A.traded].copy(); rows = []
for t, g in S.groupby("ticker"):
    m = read5_official(t)
    for ix, r in g.iterrows():
        f = m.loc[pd.Timestamp(r.date) + pd.Timedelta("9h15min")]
        rng = f.High - f.Low; body = abs(f.Close - f.Open)
        rows.append(dict(ix=ix, bodyp=body / rng if rng > 0 else 0, body_atr=body / f.Open * 100 / r.atr))
X = S.join(pd.DataFrame(rows).set_index("ix"))
def row(lab, g):
    if len(g) == 0: return f"| {lab} | 0 |"
    k = g.r1k10mid; byd = g.groupby("date").r1k10mid.sum().sort_values(ascending=False)
    return f"| {lab} | {len(g)} | {(g.o10mid == 'stop').mean()*100:.0f}% | {(g.R10mid > 0).mean()*100:.0f}% | {g.R10mid.mean():+.2f} | {k.mean():+.0f} | {k[~g.date.isin(byd.head(10).index)].mean():+.0f} | {k[g.date <= '2026-08-14'].mean():+.0f} / {k[g.date >= '2026-08-17'].mean():+.0f} |"
for sd, sn in ((-1, "SHORTS"), (1, "LONGS")):
    for st in ("09:20", "09:30"):
        G = X[(X.side == sd) & (X.et >= st)]
        print(f"\n## {sn}, orders from {st}\n| 09:15 candle | trades | stopped | win % | avg R | Rs @1k net | w/o top-10 days | half 1 / half 2 |\n|---|---|---|---|---|---|---|---|")
        print(row("ALL", G))
        for lab, msk in (("near-doji: body < 25% of range", G.bodyp < 0.25), ("body 25-50%", (G.bodyp >= 0.25) & (G.bodyp < 0.5)), ("strong: body >= 50%", G.bodyp >= 0.5),
                         ("body < 0.2x ATR", G.body_atr < 0.2), ("body 0.2-0.5x ATR", (G.body_atr >= 0.2) & (G.body_atr < 0.5)), ("body >= 0.5x ATR", G.body_atr >= 0.5)):
            print(row(lab, G[msk]))
