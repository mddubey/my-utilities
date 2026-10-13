"""ORB first candle, measured the way the user READS the chart (2026-10-13, user on 213's examples: 'RITES has a lower wick like SHADOWFAX';
'CANFINHOME is a 2% move, you call it small?'; 'ZENSARTECH / NELCO: very small lower wick'). 213's 'sellers won' = close in the bottom THIRD
lumped RITES (close position 0.30) with ZENSARTECH (0.03); 'small' was relative to ATR, not the candle's own %. Spec fixed before running:
  Population / trade: 213's file (in-play ORB, 10% ATR stop, 1.5% / 2% targets, Rs @1k net), shorts and longs (mirrored).
  CLOSED AT THE EXTREME (main) = close position <= 0.10 (lower wick <= 10% of the range for a red candle); nearby 0.05 / 0.15 shown.
  Gradient for reading only: <= 0.05 | 0.05-0.10 | 0.10-0.20 | 0.20-0.33 | > 0.33.
  Candle size in the candle's OWN %: < 1.5% | 1.5-3% | 3-5% | >= 5%, next to 201's x-ATR buckets.
  Pass for 'closed at the extreme' = better than the rest in both targets, w/o the top-10 days and both halves."""
import sys
sys.path.insert(0, ".."); sys.path.insert(0, ".")
import pandas as pd, numpy as np
from orb_common import read5_official
X = pd.read_csv("orb_first_candle_shape.csv"); A = pd.read_csv("orb_sip.csv")[["ticker", "date", "side", "atr"]].rename(columns={"ticker": "t"})
X = X.merge(A, on=["t", "date", "side"]); assert len(X) == 1177
rp = {}
for t, g in X.groupby("t"):
    m = read5_official(t)
    for i, r in g.iterrows():
        f = m[m.index.normalize() == pd.Timestamp(r.date)].iloc[0]; rp[i] = (f.High - f.Low) / f.Open * 100
X["rng"] = pd.Series(rp); X["rng_atr"] = X.rng / X.atr
print("HAND CHECK (close position):", X[X.t.isin(["RITES", "CANFINHOME", "ZENSARTECH", "NELCO"]) & X.date.isin(["2026-07-02", "2026-07-08", "2026-07-06", "2026-08-18"]) & (X.side == -1)][["t", "date", "pos", "rng", "rng_atr"]].round(2).to_string(index=False))


def line(lab, x):
    o = [lab, str(len(x))]
    for c in ("x1.5", "x2.0"):
        v = x[c]; top = x.groupby("date")[c].sum().sort_values(ascending=False).head(10).index
        o.append(f"{(v > 0).mean()*100:.0f}% / {v.mean():+.0f} ({v[~x.date.isin(top)].mean():+.0f}) / {v[x.date <= '2026-08-14'].mean():+.0f} | {v[x.date >= '2026-08-17'].mean():+.0f}")
    return "| " + " | ".join(o) + " |"


H = "| group | trades | 1.5%: win / Rs (w/o top-10) / half 1 \\| half 2 | 2%: win / Rs (w/o top-10) / half 1 \\| half 2 |\n|---|---|---|---|"
for sd, sn in ((-1, "SHORTS"), (1, "LONGS (mirrored: close at the HIGH)")):
    G = X[X.side == sd]
    print(f"\n## {sn}: {len(G)}\n\nClose position (0 = closed exactly at the low for a red candle)\n{H}")
    print(line("BASELINE", G))
    for cut in (0.05, 0.10, 0.15):
        print(line(f"closed at the extreme, pos <= {cut:.2f}", G[G.pos <= cut])); print(line(f"  the rest, pos > {cut:.2f}", G[G.pos > cut]))
    for lo, hi in ((-0.01, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 1 / 3), (1 / 3, 1.01)):
        print(line(f"gradient {max(lo,0):.2f}-{min(hi,1):.2f}", G[(G.pos > lo) & (G.pos <= hi)]))
    print(f"\nCandle size in its own % vs in ATR\n{H}")
    for lo, hi in ((0, 1.5), (1.5, 3), (3, 5), (5, 99)): print(line(f"candle {lo}-{hi}%", G[(G.rng >= lo) & (G.rng < hi)]))
    for lo, hi in ((0, .75), (.75, 1), (1, 1.5), (1.5, 99)): print(line(f"candle {lo}-{hi}x ATR", G[(G.rng_atr >= lo) & (G.rng_atr < hi)]))
    print(f"\nClose at the extreme INSIDE each size group (own %)\n{H}")
    for lo, hi in ((0, 1.5), (1.5, 3), (3, 99)):
        S = G[(G.rng >= lo) & (G.rng < hi)]
        print(line(f"{lo}-{hi}%: pos <= 0.10", S[S.pos <= 0.10])); print(line(f"{lo}-{hi}%: pos > 0.10", S[S.pos > 0.10]))
