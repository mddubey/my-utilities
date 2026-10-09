"""How big is the 10:15 rejection candle? (user, 2026-10-10: 'if the rejection candle itself is huge I am shorting way below the
EMA34; volatile stocks chop'). Spec fixed before running. Trades: 10:15 candle, red, full stack (148's population), both exits.
Splits: (1) candle range (high - low) as a share of the daily ATR: < 0.15 | 0.15-0.25 | 0.25-0.35 | > 0.35; (2) how far BELOW the
1H EMA34 we short (close vs EMA34): 0-0.1 | 0.1-0.2 | 0.2-0.3 | > 0.3%; (3) ATR >= 3% x candle range. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "148_clean_shape_0915.py").read().split("\ndef row(")[0])
src = open(Path(__file__).resolve().parent / "148_clean_shape_0915.py").read()
exec("def row(" + src.split("\ndef row(")[1].split("\n\n\nH = ")[0])
B["rng"] = (B.high - B["low"]) / B.entry * 100 / B.atrp
for c in ("rng", "dist", "atrp"): R[c] = R.ix.map(B[c])
X0 = R[(R.hour == "10:15") & R.red]
H = "| split | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
for en in EX:
    X = X0[X0.ex == en]
    print(f"\n## {en} -- 10:15 red, full stack ({len(X)} trades; median candle range {X.rng.median():.2f} x ATR, median distance below EMA34 {X.dist.median():.2f}%)\n" + H)
    for lab, lo, hi in (("candle range < 0.15 x ATR", 0, 0.15), ("0.15-0.25 x ATR", 0.15, 0.25), ("0.25-0.35 x ATR", 0.25, 0.35), ("> 0.35 x ATR (big candle)", 0.35, 99)):
        print(row(lab, X[(X.rng > lo) & (X.rng <= hi)]))
    for lab, lo, hi in (("short 0-0.1% below EMA34", 0, 0.1), ("0.1-0.2% below", 0.1, 0.2), ("0.2-0.3% below", 0.2, 0.3), ("> 0.3% below", 0.3, 99)):
        print(row(lab, X[(X.dist > lo) & (X.dist <= hi)]))
    for a, an in ((True, "ATR >= 3%"), (False, "ATR 2-3%")):
        Y = X[(X.atrp >= 3) == a]
        for lab, lo, hi in (("small candle (< 0.2 x ATR)", 0, 0.2), ("big candle (>= 0.2 x ATR)", 0.2, 99)): print(row(f"{an}, {lab}", Y[(Y.rng > lo) & (Y.rng <= hi)]))
