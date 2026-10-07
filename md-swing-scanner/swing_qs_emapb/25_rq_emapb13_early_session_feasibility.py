"""RQ-EMAPB-13 -- Predictive Execution Feasibility: T-1 Priming -> Early-Day IOC (critic-specified,
2026-10-06). ONE bounded test, no new predictors, no threshold sweep, hard stop after this.

Data-resolution note: critic specified a 9:45-10:00 decision point (first 30-45 min). Our intraday
data is hourly (09:15-10:15, 10:15-11:15, ...), so there is no clean way to see "as of 9:45." The
closest honest approximation: the decision uses the COMPLETED 09:15 bar's OHLC, known once that bar
closes at 10:15 -- so the real decision clock here is ~10:15, not 9:45-10:00. Stated explicitly,
not hidden.

Non-circularity design (the critical methodological point): a predictor built from the 09:15 bar
cannot be evaluated against "did the 09:15 bar itself cross box_high" -- that's not a prediction,
that's the event itself, perfectly caught by any resting order with zero information needed. RQ-13
therefore asks a narrower, non-circular, genuinely predictive question: among PRIMED mornings that
have NOT yet closed above box_high by 10:15 (i.e., excluding the trivial already-caught first-bar
resolutions), does the 09:15 bar's shape (how close it got, its range/direction) + the T-1 known
state predict whether box_high resolves LATER THE SAME DAY (bar 2 onward) vs not today at all?

Population: the existing valid EMAPB resumption episodes (no new discovery machinery). For each
episode, every day from box_span_end+1 (the first live-primed morning) through the actual
resolution day (inclusive) is one row -- these are the "mornings you'd actually be watching."
Target = 1 only on the day that resolves AND only if the cross happens in bar 2+ (not bar 1,
already excluded from the eligible population). All earlier primed-but-not-resolving days are
target = 0.

Caveat stated per plan: negatives come only from the same resumption episodes' other primed days,
not from episodes that fail and never resolve (consolidation_failure) -- a faster first pass;
precision read here is likely somewhat optimistic vs a true live scan that also watches names that
never break out.

Pre-registered outputs (per critic): coverage, precision, IOC viability (MFE/return from the
decision point forward) for ONE simple rule: first-hour High gets within close range of box_high.

Usage: python3 swing_qs_emapb/25_rq_emapb13_early_session_feasibility.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_1H_DATE = pd.Timestamp("2023-10-23")
PROXIMITY_THRESHOLD_PCT = -1.0  # "approaches box_high": first-hour High within 1% of box_high


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
    print(f"Resumption episodes with 1H coverage: {len(pop):,}")

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
        box_span_end_i = consolidation_start_i + 3
        if box_span_end_i >= len(daily) - 1:
            continue
        box_high = r.box_high
        clv = r.clv

        # find the actual resolution day + whether it resolved in bar 1 (any-hour search, not
        # limited to 14:15 -- RQ-13 needs the true resolution day/bar, not the 3pm-constrained one)
        osm = h1.index[h1.session_date >= daily.Date.iloc[box_span_end_i + 1]]
        if len(osm) == 0:
            continue
        search = h1.iloc[osm[0]:osm[0] + 2000]
        ci = search.index[search.Close > box_high]
        if len(ci) == 0:
            continue
        resolution_bar_i = int(ci[0])
        resolution_session = h1.session_date.iloc[resolution_bar_i]
        bar_num_in_session = int((h1.iloc[:resolution_bar_i + 1].session_date == resolution_session).sum())
        resolved_bar1 = bar_num_in_session == 1

        res_dm = daily.index[daily.Date == resolution_session]
        if len(res_dm) == 0:
            continue
        resolution_i = int(res_dm[0])

        # enumerate every primed morning from box_span_end+1 through resolution_i (inclusive)
        for di in range(box_span_end_i + 1, resolution_i + 1):
            day_date = daily.Date.iloc[di]
            is_resolution_day = (di == resolution_i)
            if is_resolution_day and resolved_bar1:
                continue  # trivial already-caught case, excluded per non-circularity design

            t1_close = daily.Close.iloc[di - 1]
            t1_dist_pct = (t1_close / box_high - 1) * 100
            box_age_days = di - 1 - box_span_end_i

            day_bars = h1[h1.session_date == day_date]
            bar1 = day_bars[day_bars.bar_time == "09:15"]
            if bar1.empty:
                continue
            o, h, l, c = bar1.Open.iloc[0], bar1.High.iloc[0], bar1.Low.iloc[0], bar1.Close.iloc[0]
            if c > box_high:
                continue  # sanity: should already be excluded by resolved_bar1 check, but guard anyway

            target = 1 if is_resolution_day else 0  # resolution_day here is always bar2+ by construction

            rows.append(dict(
                ticker=r.ticker, a_entry_date=r.a_entry_date, day_date=day_date, box_high=box_high,
                t1_dist_pct=t1_dist_pct, box_age_days=box_age_days, clv=clv,
                open_vs_box_pct=(o / box_high - 1) * 100, high_vs_box_pct=(h / box_high - 1) * 100,
                close_vs_box_pct=(c / box_high - 1) * 100, low_vs_box_pct=(l / box_high - 1) * 100,
                target=target, resolution_session=resolution_session, resolution_bar_i=resolution_bar_i,
            ))
        if (n + 1) % 3000 == 0:
            print(f"  ...{n + 1:,}/{len(pop):,}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb13_early_session_panel.csv", index=False)
    print(f"\nn primed-morning rows: {len(df):,}  (target=1: {df.target.sum():,}, "
          f"{df.target.mean()*100:.2f}% of mornings)\n")

    # the one simple rule: first-hour High gets within PROXIMITY_THRESHOLD_PCT of box_high
    df["flagged"] = df.high_vs_box_pct >= PROXIMITY_THRESHOLD_PCT

    n_eligible_positives = df.target.sum()
    n_flagged = df.flagged.sum()
    n_flagged_and_positive = (df.flagged & (df.target == 1)).sum()

    print(f"=== Rule: first-hour High within {abs(PROXIMITY_THRESHOLD_PCT)}% of box_high ===")
    print(f"Coverage (of eligible later-today resolutions, % flagged by 10:15): "
          f"{n_flagged_and_positive / n_eligible_positives * 100:.1f}%  "
          f"({n_flagged_and_positive:,} of {n_eligible_positives:,})")
    print(f"Precision (of flagged mornings, % that actually resolve later today): "
          f"{n_flagged_and_positive / n_flagged * 100:.1f}%  ({n_flagged_and_positive:,} of {n_flagged:,})")
    print(f"Base rate (unconditional, % of all primed mornings that resolve later today): "
          f"{df.target.mean()*100:.2f}%")
    print(f"Precision lift over base rate: "
          f"{n_flagged_and_positive / n_flagged * 100 - df.target.mean()*100:+.2f}pp")


if __name__ == "__main__":
    main()
