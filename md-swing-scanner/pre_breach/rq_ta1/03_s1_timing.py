"""RQ-TA Stage 2 / RQ-PB-2 open item G.1 -- order the touch-day S1 break against the
trigger touch itself, using 5-minute bars. rq_pb2/03_support_features.py's
SAME_low_above_s1 only looks at the FULL DAY's Low vs S1 (a daily-bar check) -- it
cannot say whether the break happened before or after the touch. This does, using the
same 5-min cache as 01/02 in rq_pb2 and the 2026-06-10..09-29 coverage window.

S1 is prior-day-known (pivots.daily_pivots shifts H/L/C internally -- no lookahead).
Population: panel.csv's touched & not-gap-through rows in the 5-min window, joined to
pivot_feats.pkl's cls/r5 for outcome (same BLAST/STALL/FAIL definition throughout this
project's RQ-PB-2 line).
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PB = ROOT / "pre_breach"
sys.path.insert(0, str(ROOT))

from backtest import load  # noqa: E402
from data.paths import INTRADAY_5M_DIR  # noqa: E402

WINDOW_LO, WINDOW_HI = pd.Timestamp("2026-06-10"), pd.Timestamp("2026-09-29")


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
        try:
            d = load(tk)
        except Exception:
            continue
        by_day = {k: gg.reset_index(drop=True) for k, gg in bars.groupby("day")}
        for r in g.itertuples():
            day = by_day.get(r.date)
            if day is None or len(day) < 10 or day.iloc[0].High is None:
                continue
            if r.date not in d.index:
                continue
            s1 = d.loc[r.date].s1  # already T-1-known (daily_pivots shifts internally)
            trig = r.trigger
            touch_idx = day.index[day.High >= trig]
            s1_idx = day.index[day.Low <= s1]
            if len(touch_idx) == 0:
                continue  # 5-min cache didn't register the touch (gap/data gap) -- skip, don't guess
            t_i = int(touch_idx[0])
            if len(s1_idx) == 0:
                order = "never"
            else:
                s_i = int(s1_idx[0])
                order = "before" if s_i < t_i else ("same_bar" if s_i == t_i else "after")
            rows.append(dict(ticker=tk, date=r.date, touch_i=t_i, s1_order=order))

    R = pd.DataFrame(rows).merge(outcomes, on=["ticker", "date"], how="left")
    R.to_csv(Path(__file__).resolve().parent / "s1_timing.csv", index=False)

    print(f"n={len(R)}  sessions={R.date.nunique()}  tickers={R.ticker.nunique()}")
    print("\nS1-break timing distribution")
    print(R.s1_order.value_counts())
    print("\nOutcome by S1-break timing (relative to the touch)")

    def st(g):
        return pd.Series({
            "n": len(g), "BLAST%": (g.cls == "BLAST").mean() * 100,
            "FAIL%": (g.cls == "FAIL").mean() * 100, "r5_mean": g.r5.mean(),
        })

    print(R.groupby("s1_order", observed=True).apply(st, include_groups=False).round(2))


if __name__ == "__main__":
    main()
