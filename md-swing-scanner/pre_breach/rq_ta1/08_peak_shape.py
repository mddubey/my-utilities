"""RQ-TA baseline funnel, follow-up -- for the "ran further, then faded" majority
(79.7% of STALL+FAIL, per the FINDINGS.md baseline funnel section): how long did it push
and how far did it get, before fading? Scans the FULL rest of the session after the
touch bar (not the 15-min/3-bar window 06_post_touch_participation.py used, which was
too short to capture RBLBANK's real ~65-minute push to its day peak).

Same population as 03/04/05/06 (touched & non-gap-through, 2026-06-10..09-29, 5-min
cache). Purely descriptive -- no new predictive claim, no threshold, just
characterizing the shape of the majority failure mode found in the baseline funnel.
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
        ["ticker", "date", "cls", "r5", "atr_abs"]
    ].drop_duplicates(["ticker", "date"])
    panel = panel.merge(outcomes[["ticker", "date", "atr_abs"]], on=["ticker", "date"], how="inner")

    rows = []
    for tk, g in panel.groupby("ticker"):
        bars = load_5m(tk)
        if bars is None:
            continue
        by_day = {k: gg.reset_index(drop=True) for k, gg in bars.groupby("day")}
        for r in g.itertuples():
            day = by_day.get(r.date)
            if day is None or len(day) < 10 or not r.atr_abs:
                continue
            touch_idx = day.index[day.High >= r.trigger]
            if len(touch_idx) == 0:
                continue
            t_i = int(touch_idx[0])
            rest = day.iloc[t_i:]  # touch bar through end of day -- the REAL rest of the session
            peak_pos = rest.High.values.argmax()
            peak_bar = rest.index[peak_pos]
            peak_high = rest.High.iloc[peak_pos]
            rows.append(dict(
                ticker=tk, date=r.date,
                peak_time_min=5 * (peak_bar - t_i),
                peak_atr=(peak_high - r.trigger) / r.atr_abs,
                peak_pct=(peak_high / r.trigger - 1) * 100,
            ))

    R = pd.DataFrame(rows).merge(outcomes[["ticker", "date", "cls", "r5"]], on=["ticker", "date"], how="left")
    R.to_csv(Path(__file__).resolve().parent / "peak_shape.csv", index=False)

    print(f"n={len(R)}")
    print("\nSanity check -- RBLBANK 2026-09-23 (expect ~65 min, ~+0.28 ATR, ~+0.70%, matching the hand reconstruction)")
    print(R[(R.ticker == "RBLBANK") & (R.date == "2026-09-23")].to_string(index=False))

    def pct(s):
        return s.quantile([0.25, 0.5, 0.75, 0.9]).rename({0.25: "P25", 0.5: "median", 0.75: "P75", 0.9: "P90"})

    for label, sub in [
        ("ALL touches", R),
        ("BLAST only", R[R.cls == "BLAST"]),
        ("STALL only", R[R.cls == "STALL"]),
        ("FAIL only", R[R.cls == "FAIL"]),
        ("non-BLAST (STALL+FAIL) -- the 'ran further, then faded' majority", R[R.cls.isin(["STALL", "FAIL"])]),
    ]:
        print(f"\n--- {label} (n={len(sub)}) ---")
        print("peak_time_min:"); print(pct(sub.peak_time_min).round(1))
        print("peak_atr:     "); print(pct(sub.peak_atr).round(3))
        print("peak_pct:     "); print(pct(sub.peak_pct).round(3))


if __name__ == "__main__":
    main()
