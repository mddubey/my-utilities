"""RQ-TA Stage 1 -- reconstruct the two motivating cases (RBLBANK, COALINDIA) from raw
5-min bars + daily pivots, then a small, pre-declared (not cherry-picked) comparison set.

Trigger = high10_prior*1.005, same as production (signals.py). All daily levels (pp, r1,
r2, s1, atr14) are prior-day-known (backtest.load's daily_pivots, no lookahead).

Comparison-set rule, declared BEFORE looking at any outcome: from pivot_feats.pkl's
BLAST/STALL/FAIL classification (RQ-PB-2's own pre-declared r5 >= 1.5 / <= -1.0 ATR
thresholds), restricted to the 5-min-cache window and excluding the two motivating
dates themselves, draw 3 STALL and 3 BLAST tickers with a fixed seed (42). No filtering
on how well they match the hypothesis.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PB = ROOT / "pre_breach"
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backtest import load  # noqa: E402
from data.paths import INTRADAY_5M_DIR  # noqa: E402

MOTIVATING = [("RBLBANK", "2026-09-23"), ("COALINDIA", "2026-09-30")]


def load_5m(ticker):
    p = INTRADAY_5M_DIR / f"{ticker}.csv"
    if not p.exists():
        return None
    d = pd.read_csv(p)
    d["dt"] = pd.to_datetime(d.Datetime, utc=True).dt.tz_convert("Asia/Kolkata")
    d["day"] = d.dt.dt.normalize().dt.tz_localize(None)
    d["hm"] = d.dt.dt.strftime("%H:%M")
    return d


def reconstruct(ticker, date_str):
    date = pd.Timestamp(date_str)
    d = load(ticker)
    if date not in d.index:
        print(f"{ticker} {date_str}: not in daily cache"); return None
    row_idx = d.index.get_loc(date)
    cur, prior = d.iloc[row_idx], d.iloc[row_idx - 1]
    # high10_prior, pp, r1, r2, s1 are already T-1-known ON THE CURRENT ROW (signals.py
    # shifts them internally: high10_prior=High.shift(1).rolling(10).max(); daily_pivots()
    # builds pp/r1/r2/s1 from shift(1) H/L/C). Only atr14 is NOT pre-shifted -- use the
    # prior row for it, matching rq_pb2/03_support_features.py's own atr14.shift(1).
    trigger = cur.high10_prior * 1.005
    s1, r1, r2, pp, atr = cur.s1, cur.r1, cur.r2, cur.pp, prior.atr14

    bars5 = load_5m(ticker)
    if bars5 is None:
        print(f"{ticker} {date_str}: no 5-min cache"); return None
    day = bars5[bars5.day == date].reset_index(drop=True)
    if day.empty:
        print(f"{ticker} {date_str}: no 5-min bars for this date"); return None

    touch_idx = day.index[day.High >= trigger]
    s1_idx = day.index[day.Low <= s1]
    touch_i = int(touch_idx[0]) if len(touch_idx) else None
    s1_i = int(s1_idx[0]) if len(s1_idx) else None

    print(f"\n=== {ticker} {date_str} ===")
    print(f"prior-day pp={pp:.2f} r1={r1:.2f} r2={r2:.2f} s1={s1:.2f} atr14={atr:.2f}")
    print(f"trigger (high10_prior*1.005) = {trigger:.2f}  "
          f"[dist to r1={(r1-trigger)/atr:+.2f} ATR, to r2={(r2-trigger)/atr:+.2f} ATR]")
    if touch_i is not None:
        print(f"touch bar: {day.hm.iloc[touch_i]} (bar #{touch_i}, {5*touch_i} min after open)")
    else:
        print("never touched intraday (per 5-min High) -- check trigger/day alignment")
    if s1_i is not None:
        order = "BEFORE" if touch_i is not None and s1_i < touch_i else (
            "AFTER" if touch_i is not None else "no-touch-reference")
        print(f"S1 break bar: {day.hm.iloc[s1_i]} (bar #{s1_i}) -- {order} the touch")
    else:
        print("S1 never broken intraday")

    cols = ["hm", "Open", "High", "Low", "Close", "Volume"]
    window = day.iloc[max(0, (touch_i or 0) - 2): (touch_i or 0) + 8][cols] if touch_i is not None else day[cols].head(12)
    print(window.to_string(index=False))
    day.to_csv(OUT / f"recon_{ticker}_{date_str}.csv", index=False)
    return dict(ticker=ticker, date=date_str, trigger=trigger, pp=pp, r1=r1, r2=r2, s1=s1, atr=atr,
                touch_i=touch_i, s1_i=s1_i)


def comparison_set():
    X = pd.read_pickle(PB / "rq_pb2" / "pivot_feats.pkl")
    lo, hi = pd.Timestamp("2026-06-10"), pd.Timestamp("2026-09-29")
    X = X[(X.date >= lo) & (X.date <= hi)]
    exclude = {(t, pd.Timestamp(dt)) for t, dt in MOTIVATING}
    X = X[~X.apply(lambda r: (r.ticker, r.date) in exclude, axis=1)]
    have_5m = {p.stem for p in INTRADAY_5M_DIR.glob("*.csv")}
    X = X[X.ticker.isin(have_5m)].reset_index(drop=True)  # pivot_feats.pkl's index is NOT
    # unique across tickers (each group's reset_index(drop=True) restarts at 0 before concat) --
    # without this, .loc[idx] below returns every row sharing an index value, not 3 picks.
    rng = np.random.default_rng(42)
    picks = []
    for cls in ("STALL", "BLAST"):
        pool = X[X.cls == cls]
        idx = rng.choice(pool.index.values, size=min(3, len(pool)), replace=False)
        picks.append(pool.loc[idx])
    P = pd.concat(picks)
    print("\n=== pre-declared comparison set (seed=42, 3 STALL + 3 BLAST) ===")
    print(P[["ticker", "date", "trigger", "cls", "r5"]].to_string(index=False))
    return P


if __name__ == "__main__":
    for tk, dt in MOTIVATING:
        reconstruct(tk, dt)
    picks = comparison_set()
    for r in picks.itertuples():
        reconstruct(r.ticker, r.date.strftime("%Y-%m-%d"))
