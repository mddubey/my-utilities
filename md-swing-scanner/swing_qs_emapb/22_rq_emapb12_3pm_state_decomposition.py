"""RQ-EMAPB-12 -- decomposing the shape of the 3pm state (critic-specified, 2026-10-06).

Follow-up to RQ-EMAPB-3PM-01, which found that stocks below box_high at 3pm outperform ones still
extended above it. Critic's pushback: that aggregate result conflates two different stories within
the "below box_high" group --

  Story 1 (healthy pullback): breaks out, runs up, retraces in an orderly way, still near box_high
    by 3pm -- a test of the broken level, not a failure.
  Story 2 (failed breakout): breaks out, then collapses straight through box_high, still falling
    into 3pm -- a real failure that just happens to share the same "below box_high" label.

This RQ does NOT introduce EMA8 (critic's explicit instruction -- keep this decomposition about the
shape of the box_high-relative path only) and does NOT sweep thresholds. It adds exactly the path
information needed to tell these two stories apart, using only information available by 3pm
(decision-time safe, same entry/population mechanics as 21_rq_emapb_3pm_entry.py):

  - morning_high: the best price reached intraday, from the entry day's open through the 14:15 bar.
  - retracement_from_high_pct: how much of that peak has been given back by the 3pm close.
  - day_low_so_far: the worst price reached intraday through 14:15.
  - is_at_session_low: whether the 3pm close IS (within 0.3%) the day's low so far -- "still
    falling into the close" -- vs meaningfully above it -- "has already bounced off a lower point,
    holding/recovering."

Usage: python3 swing_qs_emapb/22_rq_emapb12_3pm_state_decomposition.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_1H_DATE = pd.Timestamp("2023-10-23")
ENTRY_BAR_TIME = "14:15"
EXTENSION_OUTLIER_CUTOFF = 50
SESSION_LOW_EPS = 0.3  # within 0.3% of the day's low-so-far counts as "still at the low"


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


def randomization_test(y, group_bool, n=2000, seed=2026):
    rng = np.random.RandomState(seed)
    obs = y[group_bool].mean() - y[~group_bool].mean()
    diffs = np.empty(n)
    for i in range(n):
        perm = rng.permutation(group_bool)
        diffs[i] = y[perm].mean() - y[~perm].mean()
    p = (np.abs(diffs) >= abs(obs)).mean()
    return obs, np.percentile(np.abs(diffs), 95), p


def main():
    pop = pd.read_csv(f"{HERE}/rq_emapb08_joint.csv")
    pop_all = pop[(pop.outcome == "consolidation_resumption") &
                  (pd.to_datetime(pop.a_entry_date) >= MIN_1H_DATE)].copy()
    print(f"Fully unfiltered resumption population with 1H coverage: {len(pop_all):,}")

    rows = []
    cache_d, cache_h = {}, {}
    for n, r in enumerate(pop_all.itertuples()):
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

        day_bars = h1[(h1.session_date == entry_day) & (h1.bar_time <= ENTRY_BAR_TIME)]
        if day_bars.empty:
            continue
        pm3 = day_bars.index[day_bars.bar_time == ENTRY_BAR_TIME]
        if len(pm3) == 0:
            continue
        entry_i = int(pm3[0])
        entry_price = h1.Close.iloc[entry_i]
        morning_high = day_bars.High.max()
        day_low_so_far = day_bars.Low.min()

        dm = daily.index[daily.Date == entry_day]
        if len(dm) == 0:
            continue
        iD = int(dm[0])
        if iD + 1 >= len(daily):
            continue
        d1_close = daily.Close.iloc[iD + 1]
        d1_date = daily.Date.iloc[iD + 1]

        end_mask = h1.index[(h1.session_date > d1_date)]
        end_i = int(end_mask[0]) if len(end_mask) else len(h1)
        window = h1.iloc[entry_i:end_i]
        peak_price = window.High.max() if not window.empty else entry_price

        rows.append(dict(
            ticker=r.ticker, a_entry_date=r.a_entry_date, box_high=box_high, entry_price=entry_price,
            morning_high=morning_high, day_low_so_far=day_low_so_far,
            d1_close_ret=(d1_close / entry_price - 1) * 100,
            peak_ret=(peak_price / entry_price - 1) * 100,
        ))
        if (n + 1) % 5000 == 0:
            print(f"  ...{n + 1:,}/{len(pop_all):,}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb12_3pm_state.csv", index=False)
    print(f"\nn processed: {len(df):,}\n")

    df["already_run_pct"] = (df.entry_price / df.box_high - 1) * 100
    before = len(df)
    df = df[df.already_run_pct.abs() <= EXTENSION_OUTLIER_CUTOFF].copy()
    print(f"Excluded {before - len(df)} corporate-action artifacts. n={len(df):,} remain.\n")

    df["retracement_from_high_pct"] = (df.entry_price / df.morning_high - 1) * 100
    df["dist_from_session_low_pct"] = (df.entry_price / df.day_low_so_far - 1) * 100
    df["is_at_session_low"] = df.dist_from_session_low_pct <= SESSION_LOW_EPS
    df["d1_close_pos"] = (df.d1_close_ret > 0).astype(int)
    below = df[df.already_run_pct < 0].copy()
    print(f"Below-box_high-at-3pm population: n={len(below):,}\n")

    print("=== Critic's key test: within the below-box_high group, still falling vs. already bounced ===")
    for label, mask in [("Still at/near session low (still falling into 3pm)", below.is_at_session_low),
                         ("Already bounced off a lower low (recovering/holding)", ~below.is_at_session_low)]:
        g = below[mask]
        print(f"  {label:52} n={len(g):5,} ({len(g)/len(below)*100:4.1f}%)  "
              f"D1close={g.d1_close_ret.median():+.2f}% / {(g.d1_close_ret>0).mean()*100:.1f}% pos  "
              f"peak={g.peak_ret.median():+.2f}%")

    obs, p95, p = randomization_test(below.d1_close_pos.values, below.is_at_session_low.values)
    print(f"\n  randomization: observed={obs*100:+.2f}pp  null p95={p95*100:.2f}pp  p={p:.4f}")

    print("\n=== Secondary: retracement-from-morning-high terciles, within below-box_high group ===")
    below["retr_tercile"] = pd.qcut(below.retracement_from_high_pct, 3, labels=["deepest give-back", "mid", "shallowest give-back"])
    for t in ["deepest give-back", "mid", "shallowest give-back"]:
        g = below[below.retr_tercile == t]
        print(f"  {t:24} n={len(g):5,}  D1close={g.d1_close_ret.median():+.2f}% / {(g.d1_close_ret>0).mean()*100:.1f}% pos")

    print("\n=== Does 'is_at_session_low' matter the SAME way even for stocks still ABOVE box_high? (falsification check) ===")
    above = df[df.already_run_pct >= 0].copy()
    for label, mask in [("Still at/near session low", above.is_at_session_low),
                         ("Already bounced off a lower low", ~above.is_at_session_low)]:
        g = above[mask]
        print(f"  {label:32} n={len(g):6,} ({len(g)/len(above)*100:4.1f}%)  "
              f"D1close={g.d1_close_ret.median():+.2f}% / {(g.d1_close_ret>0).mean()*100:.1f}% pos")
    obs2, p95_2, p2 = randomization_test(above.d1_close_pos.values, above.is_at_session_low.values)
    print(f"\n  randomization (above-box_high group): observed={obs2*100:+.2f}pp  null p95={p95_2*100:.2f}pp  p={p2:.4f}")


if __name__ == "__main__":
    main()
