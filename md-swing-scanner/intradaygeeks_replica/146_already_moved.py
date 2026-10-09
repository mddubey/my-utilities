"""Already moved before we enter? (user, 2026-10-10: 'DLF -- the first candles did most of the move'). Spec fixed before running.
Trades: revised frame (137) full stack, 10:15 candle, 1% target, candle-high stop <= 0.5%, ATR >= 2%. (1) Day's OPEN vs the 1H EMA34
at the signal: below | 0-0.5% above | 0.5-1% above | > 1% above. (2) Already moved = (day's high so far - entry) / entry, in ATR units
(share of a normal day's range already spent falling): < 0.25 | 0.25-0.5 | 0.5-0.75 | > 0.75. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "137_rerun_under_1pct_frame.py").read().split('LAY = {')[0])
src137 = open(Path(__file__).resolve().parent / "137_rerun_under_1pct_frame.py").read()
exec("def row" + src137.split("\ndef row")[1].split("\n\n\nH = ")[0])
Z = B[(B.hour == "10:15") & (B.atrp >= 2.0) & B.red & (B.n200 == True) & (B.s8 > B.s34) & (B.gap > -0.25) & (B.gap <= 0.5)].copy()
dh, do = {}, {}
for t, g in Z.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    for ix, r in g.iterrows():
        d0 = h[(h.index.normalize() == pd.Timestamp(r.date)) & (h.index <= pd.Timestamp(f"{r.date} 10:15"))]
        dh[ix] = d0.High.max(); do[ix] = d0.Open.iloc[0]
Z["dayhigh"] = pd.Series(dh); Z["dayopen"] = pd.Series(do)
Z["open_vs_e34"] = (Z.dayopen / Z.ema34 - 1) * 100
Z["moved"] = (Z.dayhigh - Z.entry) / Z.entry * 100 / Z.atrp
H = "| bucket | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
print(f"## (1) day's OPEN vs 1H EMA34 ({len(Z)} trades)\n" + H)
for lab, lo, hi in (("opened BELOW", -99, 0), ("0-0.5% above", 0, 0.5), ("0.5-1% above", 0.5, 1), ("> 1% above", 1, 99)):
    print(row(lab, Z[(Z.open_vs_e34 > lo) & (Z.open_vs_e34 <= hi)]))
print(f"\n## (2) ALREADY MOVED: fall from the day's high to our entry, as a share of the daily ATR (median {Z.moved.median():.2f})\n" + H)
for lab, lo, hi in (("< 0.25 of a day's range", -1, 0.25), ("0.25-0.5", 0.25, 0.5), ("0.5-0.75", 0.5, 0.75), ("> 0.75 (most of a day spent)", 0.75, 99)):
    print(row(lab, Z[(Z.moved > lo) & (Z.moved <= hi)]))
