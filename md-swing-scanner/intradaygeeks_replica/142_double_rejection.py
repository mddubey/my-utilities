"""Does a SECOND rejection at the daily 8-EMA add to the 1H EMA34 rejection? (user, 2026-10-10). Spec fixed before running.
Frame: revised (137) -- 10:15 candle, 1% target, candle-high stop <= 0.5%, liquid; common layers kept: ATR >= 2%, red, Nifty close >
200-day SMA, gap -0.25..+0.5%. Daily rejection = the day's high so far reached the LIVE daily 8-EMA AND the candle closed below it
(115's pierce_d8 and below_d8). Versions: A current stack (stock daily 8>34, no daily-8 condition) | B double rejection, any stock
trend | C double rejection + stock daily uptrend | D double rejection, stock daily DOWNtrend only. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "137_rerun_under_1pct_frame.py").read().split('LAY = {')[0])
src137 = open(Path(__file__).resolve().parent / "137_rerun_under_1pct_frame.py").read()
exec("def row" + src137.split("\ndef row")[1].split("\n\n\nH = ")[0])
C = B[(B.hour == "10:15") & (B.atrp >= 2.0) & B.red & (B.n200 == True) & (B.gap > -0.25) & (B.gap <= 0.5)]
up = C.s8 > C.s34; dr = C.pierce_d8 & C.below_d8
H = "| version | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
print(f"common pool (10:15, ATR>=2, red, Nifty>200d, gap zone, stop<=0.5%): {len(C)} setups\n\n" + H)
print(row("common pool, no stock-trend / daily-8 condition", C))
print(row("A. current stack (stock daily uptrend)", C[up]))
print(row("B. DOUBLE rejection, any stock trend", C[dr]))
print(row("C. double rejection + stock daily uptrend", C[dr & up]))
print(row("D. double rejection, stock daily DOWNtrend", C[dr & ~up]))
print(row("(contrast) no daily rejection, any trend", C[~dr]))
