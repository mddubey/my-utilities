"""Stop vs noise (user, 2026-10-10: 'ATR >= 2 with a 0.5% max stop -- worst of both worlds? the charts get wiped by noise').
Spec fixed before running. Trades: revised frame (137) full stack, 10:15 candle, 1% target, candle-high stop <= 0.5%, ATR >= 2%.
Noise ratio = stop % / daily ATR % (the stop as a share of the stock's normal daily move). Buckets: < 0.1 | 0.1-0.15 | 0.15-0.25 |
> 0.25. Also split inside ATR 2-3% and ATR >= 3%. Rs @1L and @1k risk, by year. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "137_rerun_under_1pct_frame.py").read().split('LAY = {')[0])
src137 = open(Path(__file__).resolve().parent / "137_rerun_under_1pct_frame.py").read()
exec("def row" + src137.split("\ndef row")[1].split("\n\n\nH = ")[0])
Z = B[(B.hour == "10:15") & (B.atrp >= 2.0) & B.red & (B.n200 == True) & (B.s8 > B.s34) & (B.gap > -0.25) & (B.gap <= 0.5)].copy()
Z["nr"] = Z.stop / Z.atrp
LB = ["< 0.10 (stop tiny vs daily move)", "0.10-0.15", "0.15-0.25", "> 0.25 (stop big vs daily move)"]
Z["nb"] = pd.cut(Z.nr, [0, 0.10, 0.15, 0.25, 9], labels=LB)
H = "| stop / ATR | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
for nm, X in (("ALL (ATR >= 2%)", Z), ("ATR 2-3%", Z[Z.atrp < 3]), ("ATR >= 3%", Z[Z.atrp >= 3])):
    print(f"\n## {nm}: {len(X)} trades, median stop {X.stop.median():.2f}%, median stop/ATR {X.nr.median():.2f}\n" + H)
    for lab in LB: print(row(lab, X[X.nb == lab]))
