"""RQ-EMAPB-09 proper -- First-hour mechanics of the daily-box resumption (critic-specified,
2026-10-06, following RQ-09A's timing finding: 53.2% of resumptions occur in the first 1H bar,
55.5% of those genuinely intrabar).

Guardrail (critic's, explicit): Close > box_high is NOT assumed to be the right execution event
just because 09A used it to localize timing. This RQ investigates what actually happens around
that moment, descriptively, before any trigger is proposed.

1H observation begins once the daily box is CONFIRMED (box_span_end, i.e. consolidation_start +
3 days) -- the daily setup is fully complete at that point, so starting the 1H clock there is
granularity-consistent (not redefining anything daily, just watching forward).

For the CLV>=0.80, valid-daily-box population, describes:
  - opening position relative to box_high (gap above / inside the box / below) at the bar that
    eventually crosses
  - whether crossing happens via a gap or intrabar move (reuses 09A's classification)
  - what happens in the 3 bars AFTER the cross: does price hold above box_high, or dip back below
    (whipsaw/rejection)
  - MFE/MAE in the hours after the cross, compared between first-hour crossers and later-hour
    crossers

No trigger proposed. No threshold optimization.

Usage: python3 swing_qs_emapb/18_rq_emapb09_first_hour_mechanics.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_1H_DATE = pd.Timestamp("2023-10-23")
BOX_CONFIRM_DAYS = 3  # same constant as 13_rq_emapb07_lifecycle.py, not re-tuned
POST_CROSS_BUCKETS = [1, 2, 3, 7, 14]
POST_CROSS_LABELS = ["1H", "2H", "3H", "~Day+1 end", "~Day+2 end"]


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
    pop = pop[(pop.outcome == "consolidation_resumption") & (pop.clv >= 0.80) &
              (pd.to_datetime(pop.a_entry_date) >= MIN_1H_DATE)].copy()
    print(f"CLV>=0.80, valid daily box, 1H coverage: {len(pop):,}")

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
        peak_i = int(pm[0])
        consolidation_start_i = peak_i + int(r.consolidation_start_days)
        box_span_end = consolidation_start_i + BOX_CONFIRM_DAYS
        if box_span_end >= len(daily):
            continue
        obs_start_date = daily.Date.iloc[box_span_end]
        box_high = r.box_high

        # --- find observation start in 1H data: first bar of the session the box is confirmed ---
        osm = h1.index[h1.session_date >= obs_start_date]
        if len(osm) == 0:
            continue
        obs_start_i = int(osm[0])
        window = h1.iloc[obs_start_i:obs_start_i + 200].reset_index(drop=True)
        if window.empty:
            continue

        # --- find the cross bar: first bar where Close > box_high ---
        cross_idx = window.index[window.Close > box_high]
        if len(cross_idx) == 0:
            continue
        cross_i = int(cross_idx[0])
        cross_bar = window.iloc[cross_i]

        # bar number from observation start (1-indexed) -- NOT session-relative like 09A, this is
        # "how many hours of watching since the box was confirmed", the more decision-relevant frame
        bar_num = cross_i + 1
        is_gap_above = bool(cross_bar.Open > box_high)
        is_inside_at_open = bool(cross_bar.Open <= box_high)
        # intrabar path on the cross bar itself
        cross_bar_high_above_pct = (cross_bar.High / box_high - 1) * 100
        cross_bar_low_vs_box_pct = (cross_bar.Low / box_high - 1) * 100  # negative if it dipped below box_high intrabar

        # --- what happens in the 3 bars AFTER the cross: hold or get rejected back below box_high ---
        post_cross = window.iloc[cross_i + 1:cross_i + 4]
        held = bool((post_cross.Low > box_high).all()) if len(post_cross) else None
        rejected = bool((post_cross.Low <= box_high).any()) if len(post_cross) else None

        # --- MFE/MAE from the first tradable point after the cross (next bar's Open) ---
        entry_i = cross_i + 1
        out = dict(bar_num_from_obs_start=bar_num, is_gap_above=is_gap_above,
                    is_inside_at_open=is_inside_at_open,
                    cross_bar_high_above_pct=cross_bar_high_above_pct,
                    cross_bar_low_vs_box_pct=cross_bar_low_vs_box_pct,
                    held_3bars=held, rejected_3bars=rejected)
        if entry_i < len(window):
            entry_price = window.Open.iloc[entry_i]
            for bars, label in zip(POST_CROSS_BUCKETS, POST_CROSS_LABELS):
                sub = window.iloc[entry_i:entry_i + bars]
                if sub.empty:
                    continue
                out[f"mfe_{label}"] = (sub.High.max() / entry_price - 1) * 100
                out[f"mae_{label}"] = (sub.Low.min() / entry_price - 1) * 100

        out.update(ticker=r.ticker, a_entry_date=r.a_entry_date)
        rows.append(out)
        if (n + 1) % 2000 == 0:
            print(f"  ...{n+1}/{len(pop):,}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb09_first_hour.csv", index=False)
    print(f"\nn processed: {len(df):,}\n")

    df["first_hour"] = df.bar_num_from_obs_start == 1

    print("=== Opening position at the cross bar ===")
    print(f"gap above box_high: {df.is_gap_above.mean()*100:.1f}%")
    print(f"inside the box at open (then crossed intrabar): {df.is_inside_at_open.mean()*100:.1f}%")

    print("\n=== Hold vs reject in the 3 bars after the cross ===")
    held_known = df.dropna(subset=["held_3bars"])
    print(f"n={len(held_known):,}")
    print(f"held (never dipped back below box_high): {held_known.held_3bars.mean()*100:.1f}%")
    print(f"rejected (dipped back below at least once): {held_known.rejected_3bars.mean()*100:.1f}%")

    print("\n=== First-hour crossers vs later-hour crossers: hold rate ===")
    for grp, g in held_known.groupby(df.loc[held_known.index, "first_hour"]):
        label = "first-hour cross" if grp else "later-hour cross"
        print(f"  {label:20} n={len(g):5,}  held={g.held_3bars.mean()*100:5.1f}%  "
              f"rejected={g.rejected_3bars.mean()*100:5.1f}%")

    print("\n=== First-hour crossers vs later-hour crossers: post-cross MFE/MAE ===")
    for grp, g in df.groupby("first_hour"):
        label = "first-hour cross" if grp else "later-hour cross"
        print(f"\n--- {label} (n={len(g):,}) ---")
        for label2 in POST_CROSS_LABELS:
            mfe = g[f"mfe_{label2}"].dropna()
            mae = g[f"mae_{label2}"].dropna()
            if len(mfe) == 0:
                continue
            print(f"  {label2:14} median MFE={mfe.median():+.2f}%  median MAE={mae.median():+.2f}%")

    print(f"\nWritten: {HERE}/rq_emapb09_first_hour.csv")


if __name__ == "__main__":
    main()
