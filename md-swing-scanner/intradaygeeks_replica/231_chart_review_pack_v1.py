"""WEEKEND CHART REVIEW PACK for v1 (user, 2026-10-17: 'we are very mechanical and time bound ... always taking things at close of
candle'; the user reviews charts on TradingView, I prepare the pack). Population = script 164's v1 trades (all v1 rules and skips,
E1 = 1% target / stop = candle high <= 0.5%, 3-year 1H set), both regimes. Random sample, fixed seed, picked before looking:
  Nifty ABOVE its 200-day (= real v1): 3 targets + 3 stops;  Nifty BELOW (the bear phase we are in): 3 targets + 3 stops.
Writes chart_review_v1_pack.csv (setups WITHOUT outcomes -- for a blind look with TradingView bar replay to 11:15) and
chart_review_v1_answers.csv (outcomes + blank columns for the user's read). Prints both."""
import sys, os, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.argv = ["x"]
__file__ = os.path.join(HERE, "164_v1_without_nifty200.py")
src = open(__file__).read().split("\nH = ")[0]
with contextlib.redirect_stdout(io.StringIO()): exec(src)
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(HERE))
from data.paths import INTRADAY_60M_DIR

E = V[V.ex.str.startswith("E1")].copy()
for c in ("ticker", "entry", "high", "low", "gap", "atrp", "ema8"): E[c] = E.ix.map(B[c])
pick = []
for nv in (True, False):
    for o in ("target", "stop"):
        x = E[(E.n200 == nv) & (E.o == o)]
        pick.append(x.sample(3, random_state=17))
P = pd.concat(pick).sample(frac=1, random_state=3).reset_index(drop=True)   # shuffled so the order gives nothing away


def path(t, day, entry, stop):
    h = pd.read_csv(INTRADAY_60M_DIR / f"{t}.csv", index_col=0)
    h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    g = h[h.index.normalize() == pd.Timestamp(day)]
    tg = entry * 0.99; after = g[g.index.strftime("%H:%M") >= "11:15"]
    for ts, b in after.iterrows():
        if b.High >= stop: return f"stop {ts:%H:%M} hour", g
        if b.Low <= tg: return f"target {ts:%H:%M} hour", g
    return "stall (out at close)", g


rows = []
for i, r in P.iterrows():
    stop = r.high; ex, g = path(r.ticker, r.date, r.entry, stop)
    c = g[g.index.strftime("%H:%M") == "10:15"]
    o = c.Open.iloc[0] if len(c) else np.nan
    rows.append(dict(n=i + 1, date=pd.Timestamp(r.date).strftime("%Y-%m-%d"), ticker=r.ticker, nifty_vs_200d="above" if r.n200 else "below",
                     candle="10:15-11:15 (1H)", c_open=round(o, 2), c_high=round(r.high, 2), c_low=round(r.low, 2), c_close=round(r.entry, 2),
                     ema34_1h=round(r.ema34, 2), ema8_1h=round(r.ema8, 2), entry_1115=round(r.entry, 2), stop=round(stop, 2),
                     stop_pct=round((stop / r.entry - 1) * 100, 2), target_1pct=round(r.entry * 0.99, 2), gap_pct=round(r.gap, 2), atr_pct=round(r.atrp, 2),
                     outcome=r.o, exit=ex, day_low_after=round(g[g.index.strftime("%H:%M") >= "11:15"].Low.min(), 2),
                     day_high_after=round(g[g.index.strftime("%H:%M") >= "11:15"].High.max(), 2)))
A = pd.DataFrame(rows)
blind = ["n", "date", "ticker", "nifty_vs_200d", "candle", "c_open", "c_high", "c_low", "c_close", "ema34_1h", "ema8_1h", "entry_1115", "stop", "stop_pct", "target_1pct", "gap_pct", "atr_pct"]
A[blind].to_csv(os.path.join(HERE, "chart_review_v1_pack.csv"), index=False)
for c in ("would_take (Y/N)", "your_entry", "your_stop", "your_exit", "what_you_see"): A[c] = ""
A.to_csv(os.path.join(HERE, "chart_review_v1_answers.csv"), index=False)
pd.set_option("display.width", 250)
print("BLIND PACK (no outcomes):"); print(A[blind].to_string(index=False))
print("\nOUTCOMES (reveal after your read):"); print(A[["n", "date", "ticker", "outcome", "exit", "day_low_after", "day_high_after"]].to_string(index=False))
