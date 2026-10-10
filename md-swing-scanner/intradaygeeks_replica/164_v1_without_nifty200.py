"""Current v1 WITHOUT the Nifty > 200-day filter (user, 2026-10-10: 'Nifty has been below its 200-day since 2026-02-26 -- 7 months
with no trades'). Spec fixed before running. v1 rules otherwise unchanged: liquid, Rs100 floor, ATR >= 2, stock daily 8>34, gap
-0.25..+0.5, 10:15 candle red, branch A (opened 0-0.5% below the 1H EMA34) or B (opened above, ATR >= 3%), no doji cut by the line,
daily 8-EMA at least 0.25% away from the 1H EMA34. E1 and E2. Split by Nifty above / below its 200-day SMA (yesterday), by year,
and 2026-03..2026-09 by month. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
src = open(Path(__file__).resolve().parent / "148_clean_shape_0915.py").read()
src = src.replace("(B.n200 == True) & ", "")
exec(src.split("\ndef row(")[0])
exec("def row(" + src.split("\ndef row(")[1].split("\n\n\nH = ")[0])
B["ov"] = (B.dayopen / B.ema34 - 1) * 100; B["bodyp"] = (B.open - B.entry) / (B.high - B["low"]).replace(0, float("nan"))
B["dd"] = abs(B.ema34 - (2 / 9 * B.entry + 7 / 9 * B.s8)) / B.entry * 100
for c in ("ov", "bodyp", "dd", "price_ok", "atrp", "open", "ema34", "n200"): R[c] = R.ix.map(B[c])
V = R[(R.hour == "10:15") & R.red & (R.price_ok == True) & (((R.ov >= -0.5) & (R.ov < 0)) | ((R.ov >= 0) & (R.atrp >= 3)))
      & ~((R.bodyp < 0.25) & (R.open >= R.ema34)) & (R.dd >= 0.25)].copy()
H = "| group | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
for en in EX:
    X = V[V.ex == en]
    print(f"\n## {en}\n" + H)
    print(row("v1 WITHOUT the Nifty filter (all days)", X)); print(row("Nifty ABOVE its 200-day (= current v1)", X[X.n200 == True])); print(row("Nifty BELOW its 200-day", X[X.n200 == False]))
    Z = X[(X.n200 == False) & (X.date >= "2026-03-01")]
    print(row("  of which 2026-03..2026-09 (the current bear phase)", Z))
    print("| month (Nifty below 200d, 2026) | trades | Rs/trade @1L |\n|---|---|---|")
    for m, g in Z.groupby(Z.date.str[:7]): print(f"| {m} | {len(g)} | {g.rs1L.mean():+.0f} |")
