"""RQ-EMAPB-04 -- Daily-session episode reconstruction + timescale distribution
(critic-specified, 2026-10-04, after the same-day peak bug in RQ-EMAPB-03).

Fixes the bug: `find_peak()` in 07_visual_audit_build.py walked forward on 1H bars, so
intraday continuation within A's own session got mislabeled as "the peak" -- all 30 sampled
episodes had peak_date == a_entry_date. This script redoes the SAME running-high walk on
DAILY bars instead, for the SAME population, with NO new filters and NO pre-chosen minimum
separation (critic explicitly rejected the 5/10/15-day grid as premature).

Purely descriptive: report the distribution of how long real post-A continuation actually
takes. No promotion, no filter, no strategy test.

Usage: python3 swing_qs_emapb/08_daily_episode_reconstruction.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DAILY_DIR = "data/daily"
WINDOW_DAYS = 50  # generous, pre-declared observation window past A; not tuned to results


def load_daily(ticker):
    f = os.path.join(DAILY_DIR, f"{ticker}.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f)
    if d.empty:
        return None
    d["Date"] = pd.to_datetime(d["Date"])
    d = d.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)
    return d


def reconstruct(d, ia):
    """Daily-session version of the same running-high walk used at 1H in RQ-EMAPB-03.
    Returns dict of descriptive fields, or None if window doesn't fit."""
    end = min(ia + 1 + WINDOW_DAYS, len(d))
    if end - ia < 5:
        return None

    running_high = d.High.iloc[ia]
    peak_i = ia
    for k in range(ia + 1, end):
        if d.High.iloc[k] > running_high:
            running_high = d.High.iloc[k]
            peak_i = k
        else:
            break
    else:
        # ran through the whole window still making new highs -- no pullback formed at all
        return dict(a_to_peak_days=peak_i - ia, peak_hit_window_end=True,
                     pullback_start_i=None, continuation_i=None, days_to_continuation=None,
                     pullback_min_low=None, pullback_depth_pct=None, window_truncated=True)

    pullback_start_i = peak_i + 1
    window_min_low = d.Low.iloc[pullback_start_i:end].min() if pullback_start_i < end else np.nan
    pullback_depth_pct = (window_min_low / running_high - 1) * 100 if pd.notna(window_min_low) else None

    continuation_i = None
    for k in range(pullback_start_i, end):
        if d.High.iloc[k] > running_high:
            continuation_i = k
            break

    return dict(
        a_to_peak_days=peak_i - ia,
        peak_hit_window_end=False,
        pullback_start_i=pullback_start_i,
        continuation_i=continuation_i,
        days_to_continuation=(continuation_i - peak_i) if continuation_i is not None else None,
        pullback_min_low=window_min_low,
        pullback_depth_pct=pullback_depth_pct,
        window_truncated=(continuation_i is None),
        peak_date=str(d.Date.iloc[peak_i].date()),
        peak_high=running_high,
        continuation_date=str(d.Date.iloc[continuation_i].date()) if continuation_i is not None else None,
    )


def bucket(days):
    if days is None or pd.isna(days):
        return "never (within 50d window)"
    if days <= 1:
        return "1d (immediate, no real pause)"
    if days <= 3:
        return "2-3d"
    if days <= 6:
        return "4-6d"
    if days <= 15:
        return "7-15d"
    return ">15d"


def main():
    pop = pd.read_csv("swing_qs_bpc/rq_bpc05_a_volume_diagnostics.csv")
    pop = pop[(pop.entry_definition == 10) & (pop.vol_ratio >= 1.5) &
              (pop.a_entry_date >= "2023-10-23")]
    print(f"Population (unchanged from RQ-EMAPB-01/02/03): {len(pop):,} A's")

    rows = []
    cache = {}
    for r in pop.itertuples():
        d = cache.get(r.ticker)
        if d is None:
            d = load_daily(r.ticker)
            cache[r.ticker] = d
        if d is None:
            continue
        match = d.index[d.Date == pd.Timestamp(r.a_entry_date)]
        if len(match) == 0:
            continue
        ia = int(match[0])
        res = reconstruct(d, ia)
        if res is None:
            continue
        res.update(ticker=r.ticker, a_entry_date=r.a_entry_date, a_entry_price=r.a_entry_price)
        rows.append(res)

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb04_daily_episodes.csv", index=False)
    print(f"Episodes with valid window: {len(df):,}\n")

    # --- Sanity check: compare a few episodes against the OLD same-day-bug 30-sample ---
    old_meta = pd.read_csv(f"{HERE}/visual_audit/episode_metadata.csv")
    print("--- Hand-check vs old (buggy) same-day peak sample ---")
    for r in old_meta.head(5).itertuples():
        row = df[(df.ticker == r.ticker) & (df.a_entry_date == r.a_entry_date)]
        if row.empty:
            print(f"{r.ticker} {r.a_entry_date}: not in new reconstruction (window/data issue)")
            continue
        row = row.iloc[0]
        print(f"{r.ticker:12} A={r.a_entry_date}  OLD peak(1H,same-day)={r.peak_date}  "
              f"NEW peak(daily)={row.get('peak_date', 'hit window end')}  "
              f"a_to_peak_days={row.a_to_peak_days}  days_to_continuation={row.days_to_continuation}")

    # --- a_to_peak_days distribution (does the impulse itself extend past A's own day?) ---
    print("\n--- Distribution: A -> peak (does the impulse extend past A's own session?) ---")
    n = len(df)
    vc = df.a_to_peak_days.value_counts().sort_index()
    print(f"same day (0 extra days): {vc.get(0, 0):,} ({vc.get(0,0)/n*100:.1f}%)")
    print(f"1-2 extra days: {df.a_to_peak_days.between(1,2).sum():,} "
          f"({df.a_to_peak_days.between(1,2).sum()/n*100:.1f}%)")
    print(f"3-5 extra days: {df.a_to_peak_days.between(3,5).sum():,} "
          f"({df.a_to_peak_days.between(3,5).sum()/n*100:.1f}%)")
    print(f"6+ extra days: {(df.a_to_peak_days>=6).sum():,} ({(df.a_to_peak_days>=6).sum()/n*100:.1f}%)")
    print(f"never found a pullback within {WINDOW_DAYS}d window (still extending): "
          f"{df.peak_hit_window_end.sum():,} ({df.peak_hit_window_end.mean()*100:.1f}%)")

    # --- THE key diagnostic: peak -> continuation timescale ---
    print("\n--- Distribution: peak -> continuation (the actual 'pullback/base' duration) ---")
    scoped = df[~df.peak_hit_window_end]
    print(f"n (episodes that actually formed a peak+pullback within window) = {len(scoped):,}")
    scoped = scoped.copy()
    scoped["bucket"] = scoped.days_to_continuation.apply(bucket)
    order = ["1d (immediate, no real pause)", "2-3d", "4-6d", "7-15d", ">15d",
             "never (within 50d window)"]
    counts = scoped["bucket"].value_counts().reindex(order, fill_value=0)
    for b, c in counts.items():
        print(f"  {b:28}: {c:5,}  ({c/len(scoped)*100:5.1f}%)")

    # --- Pullback depth, descriptive only (no 50% gate per critic's instruction) ---
    print("\n--- Pullback depth (min Low during pullback, % below peak high) -- observational only ---")
    pd_s = scoped.pullback_depth_pct.dropna()
    print(f"median={pd_s.median():.2f}%  p25={pd_s.quantile(.25):.2f}%  p75={pd_s.quantile(.75):.2f}%")

    print(f"\nWritten: {HERE}/rq_emapb04_daily_episodes.csv")


if __name__ == "__main__":
    main()
