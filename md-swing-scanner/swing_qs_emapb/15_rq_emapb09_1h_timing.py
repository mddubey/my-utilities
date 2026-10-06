"""RQ-EMAPB-09 -- 1H path & timing after A, by CLV group (critic-specified, 2026-10-05).

1H observation starts at the first 1H bar of the session AFTER A closes (not after peak, not
after a confirmed box) -- captures the ~26.6% of episodes (immediate_continuation) that never
form a multi-day box at all, which is essential to answering "does the opportunity appear within
hours." Daily A/peak/box classifications are NOT redefined here -- they're reused exactly as
already computed in RQ-EMAPB-07/08; this script only describes the hourly path on top of them.

No new trading rule. "Meaningful upside" reported as raw MFE distribution + reclaim-the-known-
levels timing, not an invented threshold.

Usage: python3 swing_qs_emapb/15_rq_emapb09_1h_timing.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
DAILY_DIR = "data/daily"
MIN_1H_DATE = pd.Timestamp("2023-10-23")
TIME_BUCKETS = [1, 2, 3, 4, 7, 14, 20]  # 1H bars; ~7/day on NSE -> approx 1 day, 2 days, 3 days
BUCKET_LABELS = ["1H", "2H", "3H", "4H", "~Day+1 end", "~Day+2 end", "~Day+3 end"]


def load_daily(ticker):
    f = os.path.join(DAILY_DIR, f"{ticker}.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f)
    if d.empty:
        return None
    d["Date"] = pd.to_datetime(d["Date"])
    return d.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)


def load_60m(ticker):
    f = INTRADAY_60M_DIR / f"{ticker}.csv"
    if not f.exists():
        return None
    d = pd.read_csv(f, index_col=0)
    if d.empty:
        return None
    d.index = pd.to_datetime(d.index, utc=True).tz_convert("Asia/Kolkata")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    d = d.dropna(subset=["Close", "High", "Low", "Open"])
    d["session_date"] = d.index.normalize().tz_localize(None)
    return d.reset_index(drop=True)


def process_episode(r, daily, h1):
    a_date = pd.Timestamp(r.a_entry_date)
    a_idx_match = daily.index[daily.Date == a_date]
    if len(a_idx_match) == 0:
        return None
    a_i = int(a_idx_match[0])
    a_day_high = daily.High.iloc[a_i]
    a_day_low = daily.Low.iloc[a_i]
    a_day_close = daily.Close.iloc[a_i]
    peak_high = r.peak_high

    start_match = h1.index[h1.session_date > a_date]
    if len(start_match) == 0:
        return None
    start_i = int(start_match[0])

    # resolution window end: peak_date's row + resolution_days_from_peak (trading days), per the
    # already-known daily classification -- NOT redefined here.
    peak_date = pd.Timestamp(r.peak_date)
    peak_match = daily.index[daily.Date == peak_date]
    if len(peak_match) == 0 or pd.isna(r.resolution_days_from_peak):
        return None
    peak_i = int(peak_match[0])
    resolution_i = peak_i + int(r.resolution_days_from_peak)
    if resolution_i >= len(daily):
        return None
    resolution_date = daily.Date.iloc[resolution_i]

    # search window: from start_i through a few sessions past the known resolution date (buffer
    # for the exact crossing hour, which the daily Close check can only localize to the day)
    end_match = h1.index[h1.session_date > resolution_date]
    end_i = int(end_match[0]) + 14 if len(end_match) else len(h1)
    end_i = min(end_i, len(h1))
    if end_i - start_i < 1:
        return None

    window = h1.iloc[start_i:end_i].reset_index(drop=True)

    def ret_at(n):
        if len(window) <= n - 1:
            return None
        return (window.Close.iloc[n - 1] / a_day_close - 1) * 100

    out = dict(
        first_1h_return=ret_at(1), first_2h_return=ret_at(2), first_3h_return=ret_at(3),
    )

    # first-session (day A+1 only) MFE/MAE
    day1 = window[window.session_date == window.session_date.iloc[0]]
    out["first_session_mfe_pct"] = (day1.High.max() / a_day_close - 1) * 100
    out["first_session_mae_pct"] = (day1.Low.min() / a_day_close - 1) * 100

    # whether A-day Low is threatened within the window
    out["a_day_low_breached_1h"] = bool(window.Low.min() < a_day_low)

    # hours to reclaim A-day High (Close-based) and to new episode high (Close > peak_high)
    reclaim_idx = window.index[window.Close > a_day_high]
    out["hours_to_reclaim_a_day_high"] = int(reclaim_idx[0]) + 1 if len(reclaim_idx) else None
    newhigh_idx = window.index[window.Close > peak_high]
    out["hours_to_new_episode_high"] = int(newhigh_idx[0]) + 1 if len(newhigh_idx) else None

    # MFE/MAE at each pre-declared time bucket (bars-in, not optimized)
    for bars, label in zip(TIME_BUCKETS, BUCKET_LABELS):
        sub = window.iloc[:bars]
        if sub.empty:
            out[f"mfe_{label}"] = None
            out[f"mae_{label}"] = None
            out[f"reached_newhigh_{label}"] = False
            continue
        out[f"mfe_{label}"] = (sub.High.max() / a_day_close - 1) * 100
        out[f"mae_{label}"] = (sub.Low.min() / a_day_close - 1) * 100
        out[f"reached_newhigh_{label}"] = bool((sub.Close > peak_high).any())

    return out


def main():
    pop = pd.read_csv(f"{HERE}/rq_emapb08_joint.csv")
    pop = pop[pd.to_datetime(pop.a_entry_date) >= MIN_1H_DATE].copy()
    print(f"Episodes with 1H coverage (a_entry_date >= {MIN_1H_DATE.date()}): {len(pop):,} "
          f"of {len(pd.read_csv(f'{HERE}/rq_emapb08_joint.csv')):,} total")

    rows = []
    cache_daily, cache_60m = {}, {}
    for n, r in enumerate(pop.itertuples()):
        daily = cache_daily.setdefault(r.ticker, load_daily(r.ticker))
        h1 = cache_60m.setdefault(r.ticker, load_60m(r.ticker))
        if daily is None or h1 is None:
            continue
        res = process_episode(r, daily, h1)
        if res is None:
            continue
        res.update(ticker=r.ticker, a_entry_date=r.a_entry_date, clv_q=r.clv_q, result3=r.result3)
        rows.append(res)
        if (n + 1) % 5000 == 0:
            print(f"  ...{n+1}/{len(pop):,} episodes scanned, {len(rows):,} processed")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb09_1h_timing.csv", index=False)
    print(f"\nEpisodes processed: {len(df):,}")

    df["clv_group"] = df.clv_q.map({"Q1": "unfavorable", "Q2": "unfavorable", "Q3": "middle",
                                      "Q4": "favorable", "Q5": "favorable"})

    print("\n=== SPEED: median MFE and % reaching new-episode-high, by time bucket x CLV group ===")
    for grp in ["unfavorable", "middle", "favorable"]:
        sub = df[df.clv_group == grp]
        print(f"\n--- CLV {grp} (n={len(sub):,}) ---")
        for label in BUCKET_LABELS:
            mfe = sub[f"mfe_{label}"].dropna()
            reached = sub[f"reached_newhigh_{label}"]
            print(f"  {label:14} median MFE={mfe.median():+.2f}%  P75={mfe.quantile(.75):+.2f}%  "
                  f"% reached new high so far={reached.mean()*100:5.1f}%")

    print("\n=== Early response comparison, by CLV group ===")
    for grp in ["unfavorable", "middle", "favorable"]:
        sub = df[df.clv_group == grp]
        print(f"\n--- CLV {grp} (n={len(sub):,}) ---")
        print(f"  median first_1h_return={sub.first_1h_return.median():+.2f}%  "
              f"first_3h_return={sub.first_3h_return.median():+.2f}%")
        print(f"  median first_session_mfe={sub.first_session_mfe_pct.median():+.2f}%  "
              f"first_session_mae={sub.first_session_mae_pct.median():+.2f}%")
        print(f"  % A-day Low breached (1H-resolution check): {sub.a_day_low_breached_1h.mean()*100:.1f}%")
        hrh = sub.hours_to_reclaim_a_day_high.dropna()
        print(f"  % ever reclaiming A-day High: {sub.hours_to_reclaim_a_day_high.notna().mean()*100:.1f}%  "
              f"median hours (if reclaimed): {hrh.median():.1f}")
        hnh = sub.hours_to_new_episode_high.dropna()
        print(f"  % ever making new episode high: {sub.hours_to_new_episode_high.notna().mean()*100:.1f}%  "
              f"median hours (if made): {hnh.median():.1f}")

    print(f"\nWritten: {HERE}/rq_emapb09_1h_timing.csv")


if __name__ == "__main__":
    main()
