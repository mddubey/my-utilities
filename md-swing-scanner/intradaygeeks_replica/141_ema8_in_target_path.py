"""Is the daily (or 1H) 8-EMA sitting inside the target path? (user, 2026-10-10, from the 5-stop chart read: 3 of 5 had the live
daily 8-EMA 0.16-0.68% below the entry). Spec fixed before running. Trades: revised frame (137) full stack, 10:15 candle, ATR >= 2%.
Live daily 8-EMA = 2/9 x entry + 7/9 x yesterday's daily EMA8; 1H EMA8 = as of the previous completed hour. Distance = (entry -
level) / entry, buckets: level ABOVE the entry | 0-0.5% below | 0.5-1% below (inside the 1% target path) | > 1% below (path clear).
Target / stall / stop with avg Rs, Rs @1L and @1k risk, by year. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "137_rerun_under_1pct_frame.py").read().split('LAY = {')[0])
src137 = open(Path(__file__).resolve().parent / "137_rerun_under_1pct_frame.py").read()
exec("def row" + src137.split("\ndef row")[1].split("\n\n\nH = ")[0])
Z = B[(B.hour == "10:15") & (B.atrp >= 2.0) & B.red & (B.n200 == True) & (B.s8 > B.s34) & (B.gap > -0.25) & (B.gap <= 0.5)].copy()
Z["d8_live"] = 2 / 9 * Z.entry + 7 / 9 * Z.s8
H = "| level position | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
LB = ["ABOVE the entry", "0-0.5% below", "0.5-1% below (in target path)", "> 1% below (path clear)"]
for nm, col in (("LIVE DAILY 8-EMA", "d8_live"), ("1H EMA8", "ema8")):
    dist = (Z.entry - Z[col]) / Z.entry * 100
    b = pd.cut(dist, [-100, 0, 0.5, 1, 100], labels=LB)
    print(f"\n## {nm} vs the entry ({len(Z)} trades)\n" + H); print(row("ALL", Z))
    for lab in LB: print(row(lab, Z[b == lab]))
