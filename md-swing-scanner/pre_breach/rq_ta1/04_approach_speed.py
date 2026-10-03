"""RQ-TA Stage 3 -- does an unusually FAST approach (session open -> trigger touch) have
a different immediate outcome than a slow one? Directly tests the brief's practical
question: are we entering after the fast move has already happened?

Cut pre-declared from logic, not from the data (Logic-first filters discipline): "touched
within the first 30 minutes of the session" (bars 0-5, 09:15-09:45) vs later -- a real,
round distinction (the opening-volatility window every intraday practitioner already
treats differently), not a median/tercile chosen after looking at outcomes. Tercile split
is also shown alongside so the shape is visible, not just the one binary cut.

Reuses the exact same population/loading machinery as 03_s1_timing.py (touched &
non-gap-through, 2026-06-10..09-29, 5-min cache) for consistency -- same rows, same
outcome join.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PB = ROOT / "pre_breach"
sys.path.insert(0, str(ROOT))

from data.paths import INTRADAY_5M_DIR  # noqa: E402

WINDOW_LO, WINDOW_HI = pd.Timestamp("2026-06-10"), pd.Timestamp("2026-09-29")
FAST_CUTOFF_MIN = 30  # pre-declared: first 30 minutes of the session


def load_5m(ticker):
    p = INTRADAY_5M_DIR / f"{ticker}.csv"
    if not p.exists():
        return None
    d = pd.read_csv(p)
    d["dt"] = pd.to_datetime(d.Datetime, utc=True).dt.tz_convert("Asia/Kolkata")
    d["day"] = d.dt.dt.normalize().dt.tz_localize(None)
    return d


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
        by_day = {k: gg.reset_index(drop=True) for k, gg in bars.groupby("day")}
        for r in g.itertuples():
            day = by_day.get(r.date)
            if day is None or len(day) < 10:
                continue
            touch_idx = day.index[day.High >= r.trigger]
            if len(touch_idx) == 0:
                continue
            t_i = int(touch_idx[0])
            rows.append(dict(ticker=tk, date=r.date, minutes_to_touch=5 * t_i,
                              open_to_trigger_pct=(r.trigger / day.Open.iloc[0] - 1) * 100))

    R = pd.DataFrame(rows).merge(outcomes, on=["ticker", "date"], how="left")
    R.to_csv(Path(__file__).resolve().parent / "approach_speed.csv", index=False)

    def st(g):
        return pd.Series({
            "n": len(g), "BLAST%": (g.cls == "BLAST").mean() * 100,
            "FAIL%": (g.cls == "FAIL").mean() * 100, "r5_mean": g.r5.mean(),
        })

    print(f"n={len(R)}  sessions={R.date.nunique()}")

    R["fast"] = R.minutes_to_touch < FAST_CUTOFF_MIN
    print(f"\nPre-declared cut: touched within first {FAST_CUTOFF_MIN} min vs later")
    print(R.groupby("fast", observed=True).apply(st, include_groups=False).round(3))

    print("\nTercile shape (minutes to touch)")
    b = pd.qcut(R.minutes_to_touch.rank(method="first"), 3, labels=["fastest", "mid", "slowest"])
    t = R.groupby(b, observed=True).apply(st, include_groups=False).round(3)
    t["range(min)"] = R.groupby(b, observed=True).minutes_to_touch.agg(lambda s: f"{s.min()}..{s.max()}")
    print(t)

    print("\nDecile shape (finer view)")
    b10 = pd.qcut(R.minutes_to_touch.rank(method="first"), 10, labels=False)
    t10 = R.groupby(b10, observed=True).apply(st, include_groups=False).round(3)
    t10["range(min)"] = R.groupby(b10, observed=True).minutes_to_touch.agg(lambda s: f"{s.min()}..{s.max()}")
    print(t10)


if __name__ == "__main__":
    main()
