"""RQ-EMAPB scope-check -- entry-day search-window staleness audit (2026-10-06).

Follow-up to hand-verifying RQ-EMAPB-12's (false-positive) above-box_high finding: two examples
(EMCURE, AKUMS) showed box_high sitting 40-50% below the entry price, implausible for a single
episode. Traced to the entry-day search window in 21_rq_emapb_3pm_entry.py (searches up to ~300
bars / ~50 trading days forward from box confirmation for a qualifying cross) -- in rare cases this
can find a cross long after the box confirmed, possibly an unrelated later rally mis-attributed to
a stale box rather than a genuine continuation of the same episode.

This script quantifies: (1) how long that gap typically is, overall and by extension bucket, and
(2) whether RQ-EMAPB-3PM-01's core finding (below-box_high beats extended at 3pm) survives once the
long-delayed ("stale") cases are excluded from the one bucket where staleness is concentrated
(5%+ above). Does NOT fix the search-window scope issue itself -- that remains open for any future
RQ built on this population.

Usage: python3 swing_qs_emapb/23_rq_emapb_scope_check.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd
from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_1H_DATE = pd.Timestamp("2023-10-23")
ENTRY_BAR_TIME = "14:15"
EXTENSION_OUTLIER_CUTOFF = 50
STALE_GAP_DAYS = 10


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
    d["bar_time"] = d.index.strftime("%H:%M")
    return d.reset_index(drop=True)


def load_daily(ticker):
    f = f"data/daily/{ticker}.csv"
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f)
    if d.empty:
        return None
    d["Date"] = pd.to_datetime(d.Date)
    return d.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)


def main():
    pop = pd.read_csv(f"{HERE}/rq_emapb08_joint.csv")
    pop = pop[(pop.outcome == "consolidation_resumption") &
              (pd.to_datetime(pop.a_entry_date) >= MIN_1H_DATE)].copy()

    rows = []
    cache_d, cache_h = {}, {}
    for n, r in enumerate(pop.itertuples()):
        daily = cache_d.setdefault(r.ticker, load_daily(r.ticker))
        h1 = cache_h.setdefault(r.ticker, load_60m(r.ticker))
        if daily is None or h1 is None:
            continue
        peak_date = pd.Timestamp(r.peak_date)
        pm = daily.index[daily.Date == peak_date]
        if len(pm) == 0 or pd.isna(r.consolidation_start_days):
            continue
        peak_i = int(pm[0]); consolidation_start_i = peak_i + int(r.consolidation_start_days)
        box_span_end = consolidation_start_i + 3
        if box_span_end >= len(daily):
            continue
        obs_start_date = daily.Date.iloc[box_span_end]
        box_high = r.box_high
        osm = h1.index[h1.session_date >= obs_start_date]
        if len(osm) == 0:
            continue
        search = h1.iloc[osm[0]:osm[0] + 300]
        search_upto3 = search[search.bar_time <= ENTRY_BAR_TIME]
        ci = search_upto3.index[search_upto3.Close > box_high]
        if len(ci) == 0:
            continue
        entry_day = h1.session_date.iloc[int(ci[0])]
        gap_days = (entry_day - obs_start_date).days

        pm3 = h1.index[(h1.session_date == entry_day) & (h1.bar_time == ENTRY_BAR_TIME)]
        if len(pm3) == 0:
            continue
        entry_i = int(pm3[0])
        entry_price = h1.Close.iloc[entry_i]
        already_run_pct = (entry_price / box_high - 1) * 100

        dm = daily.index[daily.Date == entry_day]
        if len(dm) == 0:
            continue
        iD = int(dm[0])
        if iD + 1 >= len(daily):
            continue
        d1_close = daily.Close.iloc[iD + 1]

        rows.append(dict(ticker=r.ticker, a_entry_date=r.a_entry_date, gap_days=gap_days,
                          already_run_pct=already_run_pct,
                          d1_close_ret=(d1_close / entry_price - 1) * 100))
        if (n + 1) % 5000 == 0:
            print(f"  ...{n + 1:,}/{len(pop):,}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb_scope_check.csv", index=False)
    print(f"\nn={len(df):,}")
    print(df.gap_days.describe(percentiles=[.5, .75, .9, .95, .99]).round(1))

    df2 = df[df.already_run_pct.abs() <= EXTENSION_OUTLIER_CUTOFF].copy()
    bins = [-100, 0, 1, 2, 3, 5, 100]
    labels = ["below", "0-1", "1-2", "2-3", "3-5", "5plus"]
    df2["bucket"] = pd.cut(df2.already_run_pct, bins=bins, labels=labels)

    print("\nmedian gap_days by extension bucket:")
    print(df2.groupby("bucket", observed=True).gap_days.median())
    print(f"\n% of each bucket with gap_days > {STALE_GAP_DAYS} (possibly stale/unrelated rally):")
    print(df2.groupby("bucket", observed=True).gap_days.apply(lambda s: (s > STALE_GAP_DAYS).mean() * 100).round(1))

    fiveplus = df2[df2.bucket == "5plus"]
    clean = fiveplus[fiveplus.gap_days <= STALE_GAP_DAYS]
    stale = fiveplus[fiveplus.gap_days > STALE_GAP_DAYS]
    print(f"\n=== 5%+ bucket, clean vs stale ===")
    print(f"Clean (gap<={STALE_GAP_DAYS}d): n={len(clean):,}  D1close median={clean.d1_close_ret.median():+.2f}%  "
          f"pct_pos={(clean.d1_close_ret > 0).mean() * 100:.1f}%")
    print(f"Stale (gap>{STALE_GAP_DAYS}d):  n={len(stale):,}  D1close median={stale.d1_close_ret.median():+.2f}%  "
          f"pct_pos={(stale.d1_close_ret > 0).mean() * 100:.1f}%")


if __name__ == "__main__":
    main()
