"""RQ-TA Family D, lead-time sweep -- how far before the touch (if at all) does a
volume-based early-warning signal exist? Three pre-declared checkpoints, all using ONLY
bars strictly before (or, for the fixed checkpoint, not yet past) the touch -- no
lookahead into the touch bar itself or later:

  A. 5 min before the touch  (touch_i - 1 bar)
  B. 30 min before the touch (touch_i - 6 bars)
  C. a FIXED clock time, 30 min after the 09:15 open (09:45, bar index 6) -- answers a
     different practical question than A/B: "if I check at a fixed time of day, before
     I even know a touch is coming, does today's volume-so-far already flag risk?"
     Only valid for rows where the touch happens AFTER 09:45 (otherwise the touch has
     already occurred by the checkpoint, which is not a prediction anymore).

Feature: cumulative volume up to the checkpoint, normalized against that TICKER's own
historical median cumulative volume by the same time-of-day (prior 20 sessions,
strictly before today -- same construction as rq_pb2/01_approach_entry.py's "typ"
baseline and live_checkpoint.py's _clock_time_volume_fraction idea, reused rather than
reinvented). This is a genuine RVOL-at-a-point-in-time measure, not the touch bar's own
(post-hoc) volume.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PB = ROOT / "pre_breach"
sys.path.insert(0, str(ROOT))

from data.paths import INTRADAY_5M_DIR  # noqa: E402

WINDOW_LO, WINDOW_HI = pd.Timestamp("2026-06-10"), pd.Timestamp("2026-09-29")
FIXED_CHECKPOINT_BAR = 6  # bar index 6 = 09:45 (09:15 + 6*5min)


def load_5m(ticker):
    p = INTRADAY_5M_DIR / f"{ticker}.csv"
    if not p.exists():
        return None
    d = pd.read_csv(p)
    d["dt"] = pd.to_datetime(d.Datetime, utc=True).dt.tz_convert("Asia/Kolkata")
    d["day"] = d.dt.dt.normalize().dt.tz_localize(None)
    d["hm"] = d.dt.dt.strftime("%H:%M")
    return d


def build_typical_profile(bars):
    """Per-ticker median cumulative volume by time-of-day, prior 20 sessions, strictly
    before today -- exact same construction as rq_pb2/01_approach_entry.py."""
    bars = bars[(bars.hm >= "09:15") & (bars.hm <= "15:25")].copy()
    bars["cumv"] = bars.groupby("day").Volume.cumsum()
    piv = bars.pivot_table(index="day", columns="hm", values="cumv")
    typ = piv.rolling(20, min_periods=10).median().shift(1)
    return bars, typ


def main():
    panel = pd.read_csv(PB / "panel.csv", parse_dates=["date"])
    panel = panel[(panel.touched) & (~panel.gap_through) &
                  (panel.date >= WINDOW_LO) & (panel.date <= WINDOW_HI)]
    outcomes = pd.read_pickle(PB / "rq_pb2" / "pivot_feats.pkl")[
        ["ticker", "date", "cls", "r5"]
    ].drop_duplicates(["ticker", "date"])

    rows = []
    for tk, g in panel.groupby("ticker"):
        bars = load_5m(tk)
        if bars is None:
            continue
        bars, typ = build_typical_profile(bars)
        by_day = {k: gg.reset_index(drop=True) for k, gg in bars.groupby("day")}
        for r in g.itertuples():
            day = by_day.get(r.date)
            if day is None or len(day) < 10 or r.date not in typ.index:
                continue
            touch_idx = day.index[day.High >= r.trigger]
            if len(touch_idx) == 0:
                continue
            t_i = int(touch_idx[0])

            def ratio_at(bar_i):
                if bar_i < 0 or bar_i >= len(day):
                    return np.nan
                hm = day.hm.iloc[bar_i]
                tv = typ.loc[r.date].get(hm, np.nan)
                if not tv or tv <= 0 or pd.isna(tv):
                    return np.nan
                return day.cumv.iloc[bar_i] / tv

            rec = dict(ticker=tk, date=r.date, touch_i=t_i)
            rec["ratio_5before"] = ratio_at(t_i - 1) if t_i >= 1 else np.nan
            rec["ratio_30before"] = ratio_at(t_i - 6) if t_i >= 6 else np.nan
            rec["ratio_fixed0945"] = ratio_at(FIXED_CHECKPOINT_BAR) if t_i > FIXED_CHECKPOINT_BAR else np.nan
            rows.append(rec)

    R = pd.DataFrame(rows).merge(outcomes, on=["ticker", "date"], how="left")
    R.to_csv(Path(__file__).resolve().parent / "lead_time_sweep.csv", index=False)

    def st(g):
        return pd.Series({
            "n": len(g), "BLAST%": (g.cls == "BLAST").mean() * 100,
            "FAIL%": (g.cls == "FAIL").mean() * 100, "r5_mean": g.r5.mean(),
        })

    print(f"n total touches={len(R)}")
    for col, label in [
        ("ratio_5before", "A. 5 min BEFORE the touch"),
        ("ratio_30before", "B. 30 min BEFORE the touch"),
        ("ratio_fixed0945", "C. FIXED checkpoint 09:45 (only touches after 09:45)"),
    ]:
        valid = R[col].replace([np.inf, -np.inf], np.nan).notna()
        n_valid = valid.sum()
        print(f"\n{label} -- n={n_valid}")
        if n_valid < 30:
            print("  too few rows, skipping tercile split")
            continue
        b = pd.qcut(R.loc[valid, col].rank(method="first"), 3, labels=["T1 low", "T2", "T3 high"])
        t = R.loc[valid].groupby(b, observed=True).apply(st, include_groups=False).round(3)
        t["range"] = R.loc[valid].groupby(b, observed=True)[col].agg(lambda s: f"{s.min():.2f}..{s.max():.2f}")
        print(t)


if __name__ == "__main__":
    main()
