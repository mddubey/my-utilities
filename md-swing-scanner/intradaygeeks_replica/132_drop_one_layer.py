"""Drop one layer at a time (user, 2026-10-09). Spec fixed before running. Frozen frame (8j), current layers: red | Nifty close >
200-day SMA | stock daily 8>34 | gap -0.25..+0.5%. FULL = all four; then each removed in turn. A layer earns its place if removing
it lowers Rs/trade (both units) and is not offset by a large gain in setups. Both candles and by candle. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "130_rebaseline_frozen_frame.py").read().split("\nH = ")[0])
L4 = {"red": lambda d: d.red, "Nifty > 200d": lambda d: d.n200 == True, "stock daily 8>34": lambda d: d.s8 > d.s34,
      "gap -0.25..+0.5": lambda d: (d.gap > -0.25) & (d.gap <= 0.5)}


def keep(d, skip=None):
    m = d.red == d.red
    for k, f in L4.items():
        if k != skip: m &= f(d)
    return d[m]


H = "| version | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | Rs/trade @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
for HR in ("both", "09:15", "10:15"):
    X = B if HR == "both" else B[B.hour == HR]
    print(f"\n## candle {HR}\n" + H); print(row("FULL (all 4 layers)", keep(X)))
    for k in L4: print(row(f"without {k}", keep(X, k)))
