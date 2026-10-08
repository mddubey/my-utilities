"""RQ-EMAPB-14a -- post-entry round-trip-to-box_high invalidation test (user-specified, 2026-10-06).

User's structural invalidation hypothesis, path-dependent (not a static level check): after a
realistic 3pm entry, if price first moves up at least 1% from entry (confirming some initial
strength), and THEN comes back down and re-touches box_high, that round-trip back to the breakout
level is the failure signal -- not "started below box_high" (a pre-entry state, already handled by
the extension-bucket finding), but "moved up, then gave it all back down to the level it broke
from."

Three-way comparison, same 3pm-entry population as RQ-EMAPB-3PM-01 (all extension buckets, this is
a POST-entry rule so it doesn't matter where entry sat relative to box_high):
  A. Never reached +1% above entry at all (weak immediately, no "up moment" to round-trip from)
  B. Reached +1% above entry, THEN came back down and touched box_high again (the proposed failure)
  C. Reached +1% above entry, and did NOT come back down to box_high (held the gain)

If B is a real, meaningfully worse outcome than C, this validates the round-trip idea as a usable
structural invalidation signal.

Usage: python3 swing_qs_emapb/27_rq_emapb14_roundtrip_invalidation.py
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
UP_MOVE_THRESHOLD_PCT = 1.0  # user-specified: at least 1% above entry counts as "an up moment"


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
        pm3 = h1.index[(h1.session_date == entry_day) & (h1.bar_time == ENTRY_BAR_TIME)]
        if len(pm3) == 0:
            continue
        entry_i = int(pm3[0])
        entry_price = h1.Close.iloc[entry_i]

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
        window = h1.iloc[entry_i:end_i].reset_index(drop=True)
        if window.empty:
            continue

        up_threshold_price = entry_price * (1 + UP_MOVE_THRESHOLD_PCT / 100)
        up_idx = window.index[window.High >= up_threshold_price]
        reached_up_move = len(up_idx) > 0
        retested_box_high = False
        if reached_up_move:
            after_up = window.iloc[int(up_idx[0]) + 1:]
            retested_box_high = bool((after_up.Low <= box_high).any()) if not after_up.empty else False

        rows.append(dict(
            ticker=r.ticker, a_entry_date=r.a_entry_date, box_high=box_high, entry_price=entry_price,
            reached_up_move=reached_up_move, retested_box_high=retested_box_high,
            d1_close_ret=(d1_close / entry_price - 1) * 100,
        ))
        if (n + 1) % 5000 == 0:
            print(f"  ...{n + 1:,}/{len(pop_all):,}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb14_roundtrip_invalidation.csv", index=False)
    already_run_pct = (df.entry_price / df.box_high - 1) * 100
    df = df[already_run_pct.abs() <= EXTENSION_OUTLIER_CUTOFF].copy()
    print(f"\nn={len(df):,} (after excluding corp-action artifacts)\n")

    def grp(label, mask):
        g = df[mask]
        print(f"  {label:48} n={len(g):6,} ({len(g)/len(df)*100:4.1f}%)  "
              f"D1close={g.d1_close_ret.median():+.2f}% / {(g.d1_close_ret>0).mean()*100:.1f}% pos")

    print(f"=== Three-way split: up-move (>= {UP_MOVE_THRESHOLD_PCT}%) then round-trip to box_high ===")
    grp("A. Never reached +1% up-move", ~df.reached_up_move)
    grp("B. Reached +1%, THEN round-tripped back to box_high", df.reached_up_move & df.retested_box_high)
    grp("C. Reached +1%, did NOT round-trip back", df.reached_up_move & ~df.retested_box_high)

    sub = df[df.reached_up_move]
    rng = np.random.RandomState(2026)
    y = (sub.d1_close_ret > 0).astype(int).values
    grp_bool = sub.retested_box_high.values
    obs = y[grp_bool].mean() - y[~grp_bool].mean()
    N = 2000
    diffs = np.empty(N)
    for i in range(N):
        perm = rng.permutation(grp_bool)
        diffs[i] = y[perm].mean() - y[~perm].mean()
    p = (np.abs(diffs) >= abs(obs)).mean()
    print(f"\n  randomization (B vs C, D1-close win rate): observed={obs*100:+.2f}pp  "
          f"null p95={np.percentile(np.abs(diffs),95)*100:.2f}pp  p={p:.4f}")


if __name__ == "__main__":
    main()
