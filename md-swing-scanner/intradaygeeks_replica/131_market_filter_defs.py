"""Which market filter? (user, 2026-10-09: 'filters 1 and 2 look similar; what about 50 vs 200'). Spec fixed before running.
Frozen frame (8j), script 130's walked population with the non-market layers on (red, stock daily 8>34, gap -0.25..+0.5),
both candles and by candle. Market filters (all from yesterday's Nifty close): none | 8>34 | close > 200-day SMA | 50-day SMA >
200-day SMA (golden cross) | 8>34 AND close > 200d | 8>34 AND 50 > 200. Also: how often the definitions agree (share of days).
Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "130_rebaseline_frozen_frame.py").read().split("\nH = ")[0])
s50, s200 = nc.rolling(50).mean(), nc.rolling(200).mean()
B = B.join(pd.DataFrame({"g50": (s50 > s200).shift(1)}), on="d")
Z = B[B.red & (B.s8 > B.s34) & (B.gap > -0.25) & (B.gap <= 0.5)]
dd = pd.DataFrame({"n834": (nc.ewm(span=8, adjust=False).mean() > nc.ewm(span=34, adjust=False).mean()).shift(1),
                   "n200": (nc > s200).shift(1), "g50": (s50 > s200).shift(1)}).loc["2024-01-01":"2026-09-30"].dropna()
print(f"days 2024-01..2026-09: {len(dd)} | 8>34 {dd.n834.mean():.0%} | >200d {dd.n200.mean():.0%} | 50>200 {dd.g50.mean():.0%} | "
      f">200d vs 50>200 agree {(dd.n200 == dd.g50).mean():.0%} | 8>34 vs >200d agree {(dd.n834 == dd.n200).mean():.0%}")
F = (("no market filter", lambda d: d.red == d.red), ("8>34", lambda d: d.n834 == True), ("close > 200d", lambda d: d.n200 == True),
     ("50 > 200 (golden cross)", lambda d: d.g50 == True), ("8>34 AND close > 200d (current)", lambda d: (d.n834 == True) & (d.n200 == True)),
     ("8>34 AND 50 > 200", lambda d: (d.n834 == True) & (d.g50 == True)))
H = "| market filter | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | Rs/trade @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
for HR in ("both", "09:15", "10:15"):
    X = Z if HR == "both" else Z[Z.hour == HR]
    print(f"\n## candle {HR}\n" + H)
    for nm, f in F: print(row(nm, X[f(X)]))
