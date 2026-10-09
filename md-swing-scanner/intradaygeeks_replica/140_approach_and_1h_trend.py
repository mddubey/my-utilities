"""Approach direction + 1H trend on the current full stack (user, 2026-10-09 late, after the failing-chart audit: 3 of 5 stops were
the price FALLING onto the EMA34 in a 1H uptrend). Spec fixed before running. Trades: revised frame (137) full stack, 10:15 candle,
ATR >= 2%. Splits: (a) 1H trend: 1H EMA8 < EMA34 (as of the previous completed hour) vs >=; (b) approach: the 09:15 candle CLOSED
below the 1H EMA34 (rallied INTO it) vs above (fell ONTO it); (c) 2 x 2. Rs at Rs1 lakh and Rs1k risk, net, by year. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "137_rerun_under_1pct_frame.py").read().split('LAY = {')[0])
src137 = open(Path(__file__).resolve().parent / "137_rerun_under_1pct_frame.py").read()
exec("def row" + src137.split("\ndef row")[1].split("\n\n\nH = ")[0])
Z = B[(B.hour == "10:15") & (B.atrp >= 2.0) & B.red & (B.n200 == True) & (B.s8 > B.s34) & (B.gap > -0.25) & (B.gap <= 0.5)].copy()
pc = []
for t, g in Z.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    e34 = h.Close.ewm(span=34, adjust=False).mean()
    for ix, r in g.iterrows():
        k = pd.Timestamp(f"{r.date} 09:15")
        if k in h.index: pc.append((ix, h.at[k, "Close"] < e34.shift(1).get(k)))   # 09:15 close vs the EMA34 the 09:15 candle was judged against
Z["into"] = pd.Series(dict(pc)); Z = Z[Z.into.notna()]
print(f"trades {len(Z)} (full stack 10:15)\n")
H = "| group | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
Z["h1down"] = Z.ema8 < Z.ema34   # 1H trend flag from 115 (the 'trend' column is overwritten in 137 with the daily 8/34 gap)
print("## (a) 1H trend\n" + H); print(row("ALL", Z))
print(row("1H EMA8 < EMA34 (1H downtrend)", Z[Z.h1down])); print(row("1H EMA8 >= EMA34 (1H uptrend)", Z[~Z.h1down]))
print("\n## (b) approach (09:15 close vs 1H EMA34)\n" + H)
print(row("rallied INTO it (09:15 closed below)", Z[Z.into == True])); print(row("fell ONTO it (09:15 closed above)", Z[Z.into == False]))
print("\n## (c) 2 x 2\n" + H)
for a, an in ((True, "1H down"), (False, "1H up")):
    for b, bn in ((True, "rallied into"), (False, "fell onto")):
        print(row(f"{an} + {bn}", Z[(Z.h1down == a) & (Z.into == b)]))
