"""Nifty FOLLOW-THROUGH as a gate for v1 (user, 2026-10-11, after 178; spec fixed before running). FT(L) = mean over the previous L Nifty
days (up to yesterday) of |close - open| / (high - low). Main cut FT(10) >= 0.50 (round number; note it sits next to 178's upper tercile
0.504). Gates on v1-without-the-Nifty-filter (= 164), E1 and E2, 2024-01..2026-09: G0 none | G1 Nifty > 200d (v1) | G2 FT only |
G3 200d AND FT | G4 200d OR FT. Robustness: G2 / G4 over L 5/10/20 x cut 0.45/0.50/0.55 (all 9 shown). Bear phase 2026-03..09: share
of days ON, trades added, Rs, by month. Practicality: flips, longest ON / OFF runs. Pass: G4 only if the added bear trades are positive
in both exits, most of the grid agrees, 2024/2025 not hurt; G2 only if >= the 200-day in every year. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
HERE = Path(__file__).resolve().parent
exec(open(HERE / "164_v1_without_nifty200.py").read().split('\nH = "')[0])
import numpy as np, pandas as pd
from data.paths import DAILY_DIR

N = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index()
br = (N.Close - N.Open).abs() / (N.High - N.Low).replace(0, np.nan)
FT = {L: br.rolling(L).mean().shift(1) for L in (5, 10, 20)}
n200 = (N.Close > N.Close.rolling(200).mean()).shift(1)
dt = pd.to_datetime(V.date)
for L in (5, 10, 20): V[f"ft{L}"] = [FT[L].get(x, np.nan) for x in dt]


def r(lab, g):
    if len(g) == 0: return f"| {lab} | 0 |"
    o = g.o; y = " / ".join(f"{g[g.yr == k].rs1L.mean():+.0f} ({(g.yr == k).sum()})" if (g.yr == k).any() else "-" for k in ("2024", "2025", "2026"))
    return (f"| {lab} | {len(g)} | {(o=='target').mean()*100:.0f} / {(o=='stall').mean()*100:.0f} / {(o=='stop').mean()*100:.0f} | "
            f"{g.rs1L.mean():+.0f} | {g.rs1k.mean():+.0f} | {y} |")


def runs(on):
    on = on.astype(int); grp = (on != on.shift()).cumsum(); lens = on.groupby(grp).agg(["first", "size"])
    return int((on != on.shift()).sum() - 1), int(lens[lens["first"] == 1]["size"].max()), int(lens[lens["first"] == 0]["size"].max())


days = N["2024-01-01":"2026-09-30"].index; bear = N["2026-03-01":"2026-09-30"].index
HD = "| gate | trades | target / stall / stop % | Rs/trade @1L | @1k risk | 2024 / 2025 / 2026 (trades) |\n|---|---|---|---|---|---|"
for en in EX:
    X = V[V.ex == en]; ft = X.ft10 >= 0.5
    print(f"\n## {en}\n{HD}")
    for lab, m in (("G0 no gate", X.ft10 == X.ft10), ("G1 Nifty > 200d (v1)", X.n200 == True), ("G2 FT(10) >= 0.50 only", ft),
                   ("G3 200d AND FT", (X.n200 == True) & ft), ("G4 200d OR FT", (X.n200 == True) | ft),
                   ("  G4's ADDED trades (below 200d, FT on)", (X.n200 == False) & ft), ("  below 200d, FT off", (X.n200 == False) & ~ft)):
        print(r(lab, X[m]))
    Z = X[(X.n200 == False) & (X.date >= "2026-03-01")]
    print(f"\nbear phase 2026-03..09, below-200 trades {len(Z)}: FT on {Z[Z.ft10 >= 0.5].pipe(lambda g: f'{len(g)} trades {g.rs1L.mean():+.0f}')} | FT off {Z[Z.ft10 < 0.5].pipe(lambda g: f'{len(g)} trades {g.rs1L.mean():+.0f}')}")
    print("| month | FT-on trades | Rs @1L | FT-off trades | Rs @1L |\n|---|---|---|---|---|")
    for mth, g in Z.groupby(Z.date.str[:7]):
        a, b = g[g.ft10 >= 0.5], g[g.ft10 < 0.5]
        print(f"| {mth} | {len(a)} | {a.rs1L.mean():+.0f} | {len(b)} | {b.rs1L.mean():+.0f} |" if len(a) else f"| {mth} | 0 | - | {len(b)} | {b.rs1L.mean():+.0f} |")
    print(f"\n### robustness grid, {en} (Rs/trade @1L; trades)\n| lookback | cut | G2 FT only | G2 2024 / 2025 / 2026 | G4 200d OR FT | G4 added (below 200d) | added 2026-03..09 |\n|---|---|---|---|---|---|---|")
    for L in (5, 10, 20):
        for c in (0.45, 0.5, 0.55):
            f = X[f"ft{L}"] >= c; g2 = X[f]; g4 = X[(X.n200 == True) | f]; ad = X[(X.n200 == False) & f]; ab = ad[ad.date >= "2026-03-01"]
            yy = " / ".join(f"{g2[g2.yr == k].rs1L.mean():+.0f}" for k in ("2024", "2025", "2026"))
            print(f"| {L} | {c:.2f} | {g2.rs1L.mean():+.0f} ({len(g2)}) | {yy} | {g4.rs1L.mean():+.0f} ({len(g4)}) | {ad.rs1L.mean():+.0f} ({len(ad)}) | {ab.rs1L.mean():+.0f} ({len(ab)}) |")
print("\n## practicality (FT(10) >= 0.50, all trading days)\n| | days ON | ON in 2026-03..09 | flips | longest ON run | longest OFF run |\n|---|---|---|---|---|---|")
for lab, s in (("FT(10) >= 0.50", (FT[10] >= 0.5)), ("Nifty > 200d", n200.astype(bool)), ("200d OR FT", n200.astype(bool) | (FT[10] >= 0.5))):
    s = s.reindex(days).fillna(False); fl, on, off = runs(s)
    print(f"| {lab} | {s.mean()*100:.0f}% | {s.reindex(bear).mean()*100:.0f}% | {fl} | {on} days | {off} days |")
