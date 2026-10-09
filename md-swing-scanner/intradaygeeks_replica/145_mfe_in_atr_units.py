"""Deriving the target fraction k (user, 2026-10-10: 'how do we derive 0.35?'). Theory (Brownian motion, reflection principle):
median of the one-way maximum over a fraction f of the day = 0.674 x sigma_day x sqrt(f); daily ATR ~ expected daily range =
sqrt(8/pi) x sigma_day ~ 1.60 x sigma_day. From the 10:15 candle close (11:15) to the 15:15 exit, f ~ 4 / 6.25 = 0.64 ->
median max excursion ~ 0.674 x sqrt(0.64) / 1.60 = 0.34 x ATR. Empirical check, spec fixed before running: current stack, 10:15
candle, ATR >= 2%; MFE = how far price went IN OUR FAVOUR (entry - lowest low) from 11:15 to 15:15, IGNORING the stop, in ATR units.
Report median and percentiles; share reaching k = 0.25 / 0.35 / 0.5; also the same for the AGAINST side (highest high - entry). Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
exec(open(Path(__file__).resolve().parent / "130_rebaseline_frozen_frame.py").read().split('B["tp"] = 0.5 * B.atrp')[0])
B = B[(B.hour == "10:15") & (B.atrp >= 2.0) & B.red & (B.n200 == True) & (B.s8 > B.s34) & (B.gap > -0.25) & (B.gap <= 0.5)].copy()
fav, adv = {}, {}
for t, g in B.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    for ix, r in g.iterrows():
        k = pd.Timestamp(f"{r.date} 10:15")
        if k not in h.index: continue
        rest = h[(h.index > k) & (h.index.normalize() == k.normalize())]
        if len(rest) == 0: continue
        fav[ix] = (r.entry - rest.Low.min()) / r.entry * 100 / r.atrp
        adv[ix] = (rest.High.max() - r.entry) / r.entry * 100 / r.atrp
B["fav"] = pd.Series(fav); B["adv"] = pd.Series(adv); B = B[B.fav.notna()]
print(f"{len(B)} setups. Theory: median one-way max over the rest of the day ~ 0.34 x ATR (if the daily ATR were pure intraday noise)\n")
print("| side | 25th pct | MEDIAN | 75th pct | share reaching 0.25 x ATR | 0.35 x ATR | 0.5 x ATR |\n|---|---|---|---|---|---|---|")
for nm, c in (("IN OUR FAVOUR (down)", "fav"), ("AGAINST US (up)", "adv")):
    x = B[c]; print(f"| {nm} | {x.quantile(.25):.2f} | {x.median():.2f} | {x.quantile(.75):.2f} | " + " | ".join(f"{(x >= k).mean()*100:.0f}%" for k in (0.25, 0.35, 0.5)) + " |")
print("\n| ATR band | setups | median favourable (x ATR) | median against (x ATR) |\n|---|---|---|---|")
for b, g in B.groupby(pd.cut(B.atrp, [2, 2.5, 3, 3.5, 99], labels=["2-2.5%", "2.5-3%", "3-3.5%", "> 3.5%"], include_lowest=True), observed=True):
    print(f"| {b} | {len(g)} | {g.fav.median():.2f} | {g.adv.median():.2f} |")
