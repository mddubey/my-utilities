"""RQ-TA1-C -- Intraday Candidate State / Stall-Likelihood Discovery.

Supersedes "touch-event stall discrimination" per the user's own correction: their real
workflow never knows WHEN a touch will happen, so every feature must be defined at a
FIXED CLOCK TIME from market open, using only information available by then -- never
relative to the touch (which is unknown at decision time). The eventual touch is used
ONLY to label the outcome afterward.

Pre-declared snapshots (critic's own list, not tuned): 09:20, 09:30, 09:45, 10:00,
10:30, 11:00, 12:00. A candidate is ELIGIBLE at a snapshot only if it has not touched
yet by that time -- once touched, it drops out of later snapshots. This is not a
filter, it is what "still approaching" means.

Feature families, first pass only (critic's own list; D and E's sector piece
deliberately deferred -- "families to investigate, not a giant feature stack"):
  A. Opening-state: gap_pct, dist_open_atr (both already in panel.csv, constant across
     snapshots -- known at the open), first-bar direction.
  B. Participation: cumulative volume so far / this ticker's own historical median
     cumulative volume at the same time-of-day (prior 20 sessions, strictly before
     today -- same `typ` baseline as 07_lead_time_sweep.py, reused not reinvented).
  C. Price progression: % of the open->trigger distance already covered, range-so-far
     in ATR, remaining distance to trigger in ATR.

No threshold optimization. Report existence/direction only.
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

# clock time -> bar index (09:15 = bar 0, each bar = 5 min)
SNAPSHOTS = {"09:20": 1, "09:30": 3, "09:45": 6, "10:00": 9, "10:30": 15, "11:00": 21, "12:00": 33}


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
    before today -- same construction as 07_lead_time_sweep.py / rq_pb2/01_approach_entry.py."""
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
        ["ticker", "date", "cls", "r5", "atr_abs"]
    ].drop_duplicates(["ticker", "date"])
    panel = panel.merge(outcomes[["ticker", "date", "atr_abs"]], on=["ticker", "date"], how="inner")

    rows = []
    for tk, g in panel.groupby("ticker"):
        bars = load_5m(tk)
        if bars is None:
            continue
        bars, typ = build_typical_profile(bars)
        by_day = {k: gg.reset_index(drop=True) for k, gg in bars.groupby("day")}
        for r in g.itertuples():
            day = by_day.get(r.date)
            if day is None or len(day) < 10 or r.date not in typ.index or not r.atr_abs:
                continue
            touch_idx = day.index[day.High >= r.trigger]
            if len(touch_idx) == 0:
                continue
            t_i = int(touch_idx[0])
            open0 = day.Open.iloc[0]
            first_dir_up = bool(day.Close.iloc[0] > day.Open.iloc[0])

            for snap_hm, snap_i in SNAPSHOTS.items():
                if t_i <= snap_i:
                    continue  # already touched by this snapshot -- not an "approaching" state anymore
                if snap_i >= len(day):
                    continue
                window = day.iloc[:snap_i + 1]
                close_now = window.Close.iloc[-1]

                tv = typ.loc[r.date].get(snap_hm, np.nan)
                cum_vol_ratio = (window.cumv.iloc[-1] / tv) if (tv and tv > 0 and not pd.isna(tv)) else np.nan

                denom = r.trigger - open0
                progress_pct = ((close_now - open0) / denom * 100) if denom else np.nan
                range_so_far_atr = (window.High.max() - window.Low.min()) / r.atr_abs
                dist_to_trigger_atr = (r.trigger - close_now) / r.atr_abs

                rows.append(dict(
                    ticker=tk, date=r.date, snapshot=snap_hm,
                    gap_pct=r.gap_pct, dist_open_atr=r.dist_open_atr, first_dir_up=first_dir_up,
                    cum_vol_ratio=cum_vol_ratio, progress_pct=progress_pct,
                    range_so_far_atr=range_so_far_atr, dist_to_trigger_atr=dist_to_trigger_atr,
                ))

    R = pd.DataFrame(rows).merge(outcomes[["ticker", "date", "cls", "r5"]], on=["ticker", "date"], how="left")
    R.to_csv(Path(__file__).resolve().parent / "candidate_state_snapshots.csv", index=False)

    def st(g):
        return pd.Series({
            "n": len(g), "BLAST%": (g.cls == "BLAST").mean() * 100,
            "FAIL%": (g.cls == "FAIL").mean() * 100, "r5_mean": g.r5.mean(),
        })

    print(f"n total rows (candidate x eligible snapshot) = {len(R)}")
    print("\nEligible n and baseline outcome distribution, by snapshot (does 'still approaching at time T' itself select for anything?)")
    print(R.groupby("snapshot", observed=True).apply(st, include_groups=False).round(3).reindex(SNAPSHOTS.keys()))

    for feat in ["cum_vol_ratio", "progress_pct", "range_so_far_atr", "dist_to_trigger_atr", "dist_open_atr", "gap_pct"]:
        print(f"\n=== {feat} ===")
        for snap_hm in SNAPSHOTS:
            sub = R[R.snapshot == snap_hm]
            valid = sub[feat].replace([np.inf, -np.inf], np.nan).notna()
            n_valid = valid.sum()
            if n_valid < 60:
                print(f"  {snap_hm}: n={n_valid}, too few, skipped")
                continue
            b = pd.qcut(sub.loc[valid, feat].rank(method="first"), 3, labels=["T1", "T2", "T3"])
            t = sub.loc[valid].groupby(b, observed=True).apply(st, include_groups=False).round(3)
            print(f"  {snap_hm} (n={n_valid}):")
            print("   ", t[["n", "BLAST%", "FAIL%", "r5_mean"]].to_string().replace("\n", "\n    "))

    print("\nfirst_dir_up (direction of the very first 5-min bar), by snapshot")
    for snap_hm in SNAPSHOTS:
        sub = R[R.snapshot == snap_hm]
        print(f"  {snap_hm}:")
        print("   ", sub.groupby("first_dir_up", observed=True).apply(st, include_groups=False).round(3).to_string().replace("\n", "\n    "))


if __name__ == "__main__":
    main()
