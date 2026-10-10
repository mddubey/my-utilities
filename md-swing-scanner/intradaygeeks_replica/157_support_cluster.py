"""Do failures line up with a CLUSTER of supports below the entry? (user, 2026-10-10: 'don't skip every 8-EMA trade; check if it
correlates with 1H EMA8, pivots, S1, S2, previous day low'). Spec fixed before running. v1 trades (10:15, red, full stack, Rs100
floor, cut dojis removed), branches A + B together, E1. Levels: live daily 8-EMA, 1H EMA8 (prev completed hour), yesterday's classic
pivots PP / S1 / S2, previous day's low. Zones below the entry: 'right under' 0-0.3%; 'in the path' 0.3-1%. (1) per level: share in
each zone among TARGETS vs STOPS vs all; (2) outcome by the NUMBER of levels right under (0 / 1 / 2+) and in the path. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "156_on_top_of_daily8.py").read().split("\nH = ")[0])
pv = {}
for t, g in B.groupby("ticker"):
    d = load(t)
    for ix, r in g.iterrows():
        p = d[d.index < pd.Timestamp(r.date)].iloc[-1]; PP = (p.High + p.Low + p.Close) / 3
        pv[ix] = dict(PP=PP, S1=2 * PP - p.High, S2=PP - (p.High - p.Low), PDL=p.Low)
PV = pd.DataFrame(pv).T
B = B.join(PV); B["D8"] = 2 / 9 * B.entry + 7 / 9 * B.s8; B["H8"] = B.ema8
LV = {"daily 8-EMA (live)": "D8", "1H EMA8": "H8", "daily PP": "PP", "daily S1": "S1", "daily S2": "S2", "previous day low": "PDL"}
X = X0[(X0.ex == "E1 1% / stop <= 0.5%") & (((X0.ov >= -0.5) & (X0.ov < 0)) | ((X0.ov >= 0) & (X0.atrp >= 3)))].copy()
for nm, c in LV.items():
    gap = (B.loc[X.ix, "entry"].values - B.loc[X.ix, c].values) / B.loc[X.ix, "entry"].values * 100
    X[c + "_under"] = (gap >= 0) & (gap < 0.3); X[c + "_path"] = (gap >= 0.3) & (gap < 1.0)
print(f"v1 trades (A + B, E1): {len(X)} | targets {(X.o=='target').sum()}, stops {(X.o=='stop').sum()}, stalls {(X.o=='stall').sum()}\n")
print("| level | RIGHT UNDER (0-0.3%): targets / stops / all | IN THE PATH (0.3-1%): targets / stops / all |\n|---|---|---|")
for nm, c in LV.items():
    f = lambda o, z: X[X.o == o][c + z].mean() * 100
    print(f"| {nm} | {f('target','_under'):.0f}% / {f('stop','_under'):.0f}% / {X[c+'_under'].mean()*100:.0f}% | {f('target','_path'):.0f}% / {f('stop','_path'):.0f}% / {X[c+'_path'].mean()*100:.0f}% |")
X["n_under"] = X[[c + "_under" for c in LV.values()]].sum(axis=1); X["n_path"] = X[[c + "_path" for c in LV.values()]].sum(axis=1)
H = "| group | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
print("\n## by number of levels stacked RIGHT UNDER the entry (0-0.3%)\n" + H)
for lab, m in (("0 levels", X.n_under == 0), ("1 level", X.n_under == 1), ("2+ levels", X.n_under >= 2)): print(row(lab, X[m]))
print("\n## by number of levels IN THE PATH (0.3-1%)\n" + H)
for lab, m in (("0 levels", X.n_path == 0), ("1 level", X.n_path == 1), ("2 levels", X.n_path == 2), ("3+ levels", X.n_path >= 3)): print(row(lab, X[m]))
print("\n## the one level that separates: 1H EMA8 right under the entry\n" + H)
print(row("1H EMA8 right under (0-0.3% below entry)", X[X.H8_under])); print(row("1H EMA8 not right under", X[~X.H8_under]))
