"""RQ-EMAPB-11A -- Candidate A Execution Mechanics: Gap vs First Pullback (critic-specified,
2026-10-06). Population: 1,002 A-pass first-hour crosses (gap above box_high at the open).

Pre-registered, per critic -- no variants, no threshold sweep:
  - Gap entry: opening price of the A-pass cross hour.
  - Pullback reference: 1H EMA8 (pre-existing convention, not invented post-hoc).
  - Pullback event: first of the NEXT 3 completed 1H bars whose Low touches/crosses EMA8 (no
    close-below-and-reclaim requirement -- touch only, to avoid imposing a confirmation
    philosophy that could discard legitimate pullbacks).
  - Pullback entry price: the EMA8 VALUE at that first qualifying touch (not the bar's own O/C).
  - Window: next 3 completed 1H bars after the cross/gap bar. Fixed, not chosen after results.

Three populations, NOT "immediate vs EMA" as a simple two-way comparison (critic's explicit
correction -- EMA-offered is a selected-after-the-fact subset):
  1. Immediate-open: all 1,002 A-pass cases.
  2. EMA-offered: A-pass cases that touch EMA8 within the next 3 bars.
  3. EMA-not-offered: A-pass cases that never touch EMA8 within the next 3 bars.

Primary quantities are actual price distances (gap_open - box_high, MFE from box_high, MFE from
gap_open, pullback-entry improvement vs gap-open), not "% of MFE consumed" (critic: path-dependent,
can mislead). "Opportunity consumed" reported only as a secondary descriptive stat.

No strategy promotion. No EMA variants (EMA8 only).

Usage: python3 swing_qs_emapb/20_rq_emapb11a_gap_vs_pullback.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
PULLBACK_WINDOW = 3  # next 3 completed 1H bars, pre-registered, not tuned
OUTCOME_BUCKETS = [1, 2, 3, 7, 14]
OUTCOME_LABELS = ["1H", "2H", "3H", "~Day+1 end", "~Day+2 end"]


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
    # decision-time-safe: the EMA8 level known BEFORE a bar starts (shift(1)) -- using the
    # same-bar EMA8 would use that bar's own close before it's known, a lookahead violation.
    d["ema8"] = d.Close.ewm(span=8, adjust=False).mean().shift(1)
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
    fh = pd.read_csv(f"{HERE}/rq_emapb09_first_hour.csv")
    fh = fh[fh.bar_num_from_obs_start == 1].copy()
    pop = pd.read_csv(f"{HERE}/rq_emapb08_joint.csv")
    fh = fh.merge(pop[["ticker", "a_entry_date", "box_high", "peak_date", "consolidation_start_days"]],
                  on=["ticker", "a_entry_date"], how="left")

    rows = []
    cache_d, cache_h = {}, {}
    for n, r in enumerate(fh.itertuples()):
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
        cross_i = int(osm[0])
        cross_bar = h1.iloc[cross_i]
        if cross_bar.Close <= box_high or cross_bar.Open <= box_high:
            continue  # A-pass only

        gap_open = cross_bar.Open
        end_i = min(cross_i + 1 + 200, len(h1))
        window = h1.iloc[cross_i:end_i].reset_index(drop=True)

        # --- pullback search: next PULLBACK_WINDOW completed bars after the cross bar ---
        pb_search = window.iloc[1:1 + PULLBACK_WINDOW]
        touch_idx = pb_search.index[pb_search.Low <= pb_search.ema8]
        offered = len(touch_idx) > 0
        pullback_entry, pullback_bars_taken = None, None
        if offered:
            ti = int(touch_idx[0])
            pullback_entry = window.ema8.iloc[ti]
            pullback_bars_taken = ti  # bars after the cross (1-indexed would be ti, since window[0]=cross)

        out = dict(ticker=r.ticker, a_entry_date=r.a_entry_date, box_high=box_high,
                   gap_open=gap_open, gap_above_box_pct=(gap_open / box_high - 1) * 100,
                   offered=offered, pullback_entry=pullback_entry,
                   pullback_bars_taken=pullback_bars_taken)
        if offered:
            out["pullback_improvement_pct"] = (gap_open / pullback_entry - 1) * 100  # positive = pullback entry was cheaper

        # MFE/MAE from gap_open and from box_high, at fixed horizons (window starts AT cross bar)
        for bars, label in zip(OUTCOME_BUCKETS, OUTCOME_LABELS):
            sub = window.iloc[0:bars + 1]  # include cross bar itself, since gap_open IS the cross bar's open
            if sub.empty:
                continue
            out[f"mfe_from_gap_{label}"] = (sub.High.max() / gap_open - 1) * 100
            out[f"mae_from_gap_{label}"] = (sub.Low.min() / gap_open - 1) * 100
            out[f"mfe_from_boxhigh_{label}"] = (sub.High.max() / box_high - 1) * 100
            if offered:
                post_pb = window.iloc[pullback_bars_taken:pullback_bars_taken + bars + 1]
                if not post_pb.empty:
                    out[f"mfe_from_pullback_{label}"] = (post_pb.High.max() / pullback_entry - 1) * 100
                    out[f"mae_from_pullback_{label}"] = (post_pb.Low.min() / pullback_entry - 1) * 100

        out["held_3bars"] = r.held_3bars
        rows.append(out)
        if (n + 1) % 300 == 0:
            print(f"  ...{n+1}/{len(fh):,}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb11a_gap_vs_pullback.csv", index=False)
    n_total = len(df)
    print(f"\nn (A-pass first-hour crosses processed): {n_total:,}\n")

    print("=== 1. Gap economics (immediate-open population, all A-pass) ===")
    print(f"median gap above box_high: {df.gap_above_box_pct.median():.2f}%")
    for label in OUTCOME_LABELS:
        mfe_g = df[f"mfe_from_gap_{label}"].dropna()
        mfe_b = df[f"mfe_from_boxhigh_{label}"].dropna()
        print(f"  {label:14} MFE from gap_open={mfe_g.median():+.2f}%   MFE from box_high={mfe_b.median():+.2f}%")

    print(f"\n=== 2. Pullback offer rate ===")
    print(f"EMA-offered (touches 1H EMA8 within {PULLBACK_WINDOW} bars): {df.offered.mean()*100:.1f}%")
    print(f"EMA-not-offered (runs without a pullback): {(~df.offered).mean()*100:.1f}%")
    offered_df = df[df.offered]
    print(f"median bars taken to reach pullback: {offered_df.pullback_bars_taken.median():.1f}")
    print(f"median entry improvement (pullback vs gap-open): {offered_df.pullback_improvement_pct.median():+.2f}%")

    print(f"\n=== 3. Three-population comparison ===")
    groups = {
        "Immediate-open (all A-pass)": df,
        "EMA-offered (touches EMA8 in 3 bars)": df[df.offered],
        "EMA-not-offered (never touches)": df[~df.offered],
    }
    for label, g in groups.items():
        print(f"\n--- {label} (n={len(g):,}, {len(g)/n_total*100:.1f}% of A-pass) ---")
        print(f"  held_3bars (box_high holds): {g.held_3bars.mean()*100:.1f}%")
        for lbl in OUTCOME_LABELS:
            if label.startswith("EMA-offered"):
                mfe = g[f"mfe_from_pullback_{lbl}"].dropna()
                mae = g[f"mae_from_pullback_{lbl}"].dropna()
                ref = "from pullback entry"
            else:
                mfe = g[f"mfe_from_gap_{lbl}"].dropna()
                mae = g[f"mae_from_gap_{lbl}"].dropna()
                ref = "from gap-open"
            if len(mfe) == 0:
                continue
            print(f"  {lbl:14} MFE {ref}={mfe.median():+.2f}%  MAE {ref}={mae.median():+.2f}%")

    print(f"\nWritten: {HERE}/rq_emapb11a_gap_vs_pullback.csv")


if __name__ == "__main__":
    main()
