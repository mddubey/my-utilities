"""Skip when the first candle has already 'eaten' the day? (user, 2026-10-12 09:2x, live: SHADOWFAX's 09:15 candle = 1.8x its ATR).
Declared before running: first-candle RANGE (high - low, official open) as a multiple of daily ATR%; rule = skip if > 1.0x, nearby
cut-offs 0.75x and 1.5x shown (Rule #19). Bands < 0.5 / 0.5-0.75 / 0.75-1 / 1-1.5 / > 1.5. 175's in-play trades on the official open,
paper rules (10% ATR stop, hold to 15:15), shorts + longs, orders from 09:20 and from 09:30. PASS = kept beats baseline on Rs @1k net
in both halves AND w/o the top-10 days. Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from orb_common import read5_official
A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
S = A[(A.rv >= 1) & (A["rank"] <= 20) & A.traded].copy(); rr = {}
for t, g in S.groupby("ticker"):
    m = read5_official(t)
    for ix, r in g.iterrows():
        f = m.loc[pd.Timestamp(r.date) + pd.Timedelta("9h15min")]; rr[ix] = (f.High - f.Low) / f.Open * 100 / r.atr
S["rng"] = pd.Series(rr)


def st(g):
    k = g.r1k10mid; byd = g.groupby("date").r1k10mid.sum().sort_values(ascending=False)
    return k.mean(), k[~g.date.isin(byd.head(10).index)].mean(), k[g.date <= "2026-08-14"].mean(), k[g.date >= "2026-08-17"].mean()


def row(lab, g, base=None):
    if len(g) == 0: return f"| {lab} | 0 |"
    a = st(g); ok = "" if base is None else ("PASS" if (a[1] > base[1] and a[2] > base[2] and a[3] > base[3]) else "no")
    return f"| {lab} | {len(g)} | {(g.o10mid == 'stop').mean()*100:.0f}% | {(g.R10mid > 0).mean()*100:.0f}% | {g.R10mid.mean():+.2f} | {a[0]:+.0f} | {a[1]:+.0f} | {a[2]:+.0f} / {a[3]:+.0f} | {(g.R10mid >= 5).sum()} | {ok} |"


for sd, sn in ((-1, "SHORTS"), (1, "LONGS")):
    for stt in ("09:20", "09:30"):
        G = S[(S.side == sd) & (S.et >= stt)]; b = st(G)
        print(f"\n## {sn}, orders from {stt} (first-candle range median {G.rng.median():.2f}x ATR)\n| group | trades | stopped | win % | avg R | Rs @1k net | w/o top-10 days | half 1 / half 2 | +5R trades | vs baseline |\n|---|---|---|---|---|---|---|---|---|---|")
        print(row("BASELINE", G))
        for c in (0.75, 1.0, 1.5):
            print(row(f"KEPT: first candle <= {c}x ATR", G[G.rng <= c], b)); print(row(f"removed: > {c}x ATR", G[G.rng > c]))
        for lab, lo, hi in (("band < 0.5x", 0, 0.5), ("band 0.5-0.75x", 0.5, 0.75), ("band 0.75-1x", 0.75, 1.0), ("band 1-1.5x", 1.0, 1.5), ("band > 1.5x", 1.5, 99)):
            print(row(lab, G[(G.rng > lo) & (G.rng <= hi)]))
