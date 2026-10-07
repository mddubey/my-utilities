"""RQ-EMAPB-13v2 -- full-denominator rerun of the frozen RQ-13 rule (critic-specified, 2026-10-06).

RQ-13's first pass measured precision/coverage only against episodes we already know eventually
resolve (outcome=='consolidation_resumption') -- a real live morning scan would also be watching
boxes that form and never break out at all (outcome=='consolidation_failure'), which were entirely
missing from that denominator. This rebuilds the SAME frozen rule (first-hour High within 1% of
box_high -- NOT re-optimized, per critic's explicit instruction) against the full population of
both outcomes, to get a live-comparable precision/coverage read.

Population-construction choice, stated explicitly (not the frozen 1% rule -- a necessary, separate
boundary to keep the window tractable and avoid the RQ-12 staleness problem): every episode's
"primed window" is capped at WINDOW_DAYS trading days after box confirmation (~the 95th-percentile
genuine resolution gap found in the RQ-12 scope-check). For resumption episodes, if the real
resolution happens beyond this cap, the episode contributes only target=0 rows within the window
(treated the same as "didn't resolve in time" for this test). For failure episodes, every day in
the window is target=0 (never resolves at all, per the existing outcome label).

Usage: python3 swing_qs_emapb/26_rq_emapb13v2_full_denominator.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_1H_DATE = pd.Timestamp("2023-10-23")
PROXIMITY_THRESHOLD_PCT = -1.0  # FROZEN from RQ-13 -- do not change
WINDOW_DAYS = 20  # population-construction cap, not the frozen rule


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


def process_episode(r, daily, h1, is_resumption, cache_cross):
    peak_date = pd.Timestamp(r.peak_date)
    pm = daily.index[daily.Date == peak_date]
    if len(pm) == 0 or pd.isna(r.consolidation_start_days):
        return []
    peak_i = int(pm[0]); consolidation_start_i = peak_i + int(r.consolidation_start_days)
    box_span_end_i = consolidation_start_i + 3
    window_end_i = box_span_end_i + WINDOW_DAYS
    if box_span_end_i >= len(daily) - 1:
        return []
    window_end_i = min(window_end_i, len(daily) - 1)
    box_high = r.box_high
    clv = r.clv

    resolution_i, resolved_bar1 = None, None
    if is_resumption:
        osm = h1.index[h1.session_date >= daily.Date.iloc[box_span_end_i + 1]]
        if len(osm):
            search = h1.iloc[osm[0]:osm[0] + 2000]
            ci = search.index[search.Close > box_high]
            if len(ci):
                resolution_bar_i = int(ci[0])
                resolution_session = h1.session_date.iloc[resolution_bar_i]
                bar_num = int((h1.iloc[:resolution_bar_i + 1].session_date == resolution_session).sum())
                res_dm = daily.index[daily.Date == resolution_session]
                if len(res_dm):
                    cand_resolution_i = int(res_dm[0])
                    if cand_resolution_i <= window_end_i:  # only counts if within the capped window
                        resolution_i = cand_resolution_i
                        resolved_bar1 = bar_num == 1

    out = []
    for di in range(box_span_end_i + 1, window_end_i + 1):
        day_date = daily.Date.iloc[di]
        is_resolution_day = (resolution_i is not None) and (di == resolution_i)
        if is_resolution_day and resolved_bar1:
            continue  # trivial already-caught case, excluded per RQ-13 design

        t1_close = daily.Close.iloc[di - 1]
        t1_dist_pct = (t1_close / box_high - 1) * 100
        box_age_days = di - 1 - box_span_end_i

        day_bars = h1[h1.session_date == day_date]
        bar1 = day_bars[day_bars.bar_time == "09:15"]
        if bar1.empty:
            continue
        o, h, l, c = bar1.Open.iloc[0], bar1.High.iloc[0], bar1.Low.iloc[0], bar1.Close.iloc[0]
        if c > box_high:
            continue

        target = 1 if is_resolution_day else 0
        out.append(dict(
            ticker=r.ticker, a_entry_date=r.a_entry_date, day_date=day_date, box_high=box_high,
            t1_dist_pct=t1_dist_pct, box_age_days=box_age_days, clv=clv,
            open_vs_box_pct=(o / box_high - 1) * 100, high_vs_box_pct=(h / box_high - 1) * 100,
            close_vs_box_pct=(c / box_high - 1) * 100, low_vs_box_pct=(l / box_high - 1) * 100,
            target=target, is_resumption_episode=is_resumption,
        ))
    return out


def main():
    pop = pd.read_csv(f"{HERE}/rq_emapb08_joint.csv")
    res = pop[(pop.outcome == "consolidation_resumption") & (pd.to_datetime(pop.a_entry_date) >= MIN_1H_DATE)].copy()
    fail = pop[(pop.outcome == "consolidation_failure") & (pd.to_datetime(pop.a_entry_date) >= MIN_1H_DATE)].copy()
    print(f"Resumption episodes: {len(res):,}  Failure episodes: {len(fail):,}  Total: {len(res)+len(fail):,}")

    rows = []
    cache_d, cache_h = {}, {}
    combined = [(r, True) for r in res.itertuples()] + [(r, False) for r in fail.itertuples()]
    for n, (r, is_resumption) in enumerate(combined):
        daily = cache_d.setdefault(r.ticker, load_daily(r.ticker))
        h1 = cache_h.setdefault(r.ticker, load_60m(r.ticker))
        if daily is None or h1 is None:
            continue
        rows.extend(process_episode(r, daily, h1, is_resumption, None))
        if (n + 1) % 5000 == 0:
            print(f"  ...{n + 1:,}/{len(combined):,}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb13v2_full_panel.csv", index=False)
    print(f"\nn primed-morning rows (full denominator): {len(df):,}  "
          f"(target=1: {df.target.sum():,}, {df.target.mean()*100:.3f}% of mornings)\n")

    df["flagged"] = df.high_vs_box_pct >= PROXIMITY_THRESHOLD_PCT
    n_pos = df.target.sum()
    n_flag = df.flagged.sum()
    n_tp = (df.flagged & (df.target == 1)).sum()
    n_fp = (df.flagged & (df.target == 0)).sum()

    print(f"=== Frozen rule: first-hour High within {abs(PROXIMITY_THRESHOLD_PCT)}% of box_high ===")
    print(f"Live base rate (all primed mornings, both outcomes): {df.target.mean()*100:.3f}%")
    print(f"Coverage (of all true same-day resolutions, % flagged): {n_tp/n_pos*100:.1f}%  ({n_tp:,} of {n_pos:,})")
    print(f"Precision (of flagged mornings, % that resolve): {n_tp/n_flag*100:.2f}%  ({n_tp:,} of {n_flag:,})")
    print(f"False-positive rate (of flagged mornings, % that do NOT resolve): {n_fp/n_flag*100:.2f}%  ({n_fp:,} of {n_flag:,})")
    print(f"Precision lift over live base rate: {n_tp/n_flag*100 - df.target.mean()*100:+.2f}pp")

    print(f"\n% of all primed mornings from resumption episodes: {df.is_resumption_episode.mean()*100:.1f}%")
    print(f"% of all primed mornings from failure episodes: {(~df.is_resumption_episode).mean()*100:.1f}%")


if __name__ == "__main__":
    main()
