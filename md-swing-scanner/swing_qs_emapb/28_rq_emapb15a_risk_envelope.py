"""RQ-EMAPB-15A -- Structural Risk Envelope (critic-specified, 2026-10-07). Characterization only --
NOT a stop decision. Does the structural failure signal (entry -> +1% excursion -> retest box_high)
have a usable, executable, EARLIER price boundary that approximates it, without requiring the full
round-trip to confirm? Answering that requires first seeing whether failing trades and surviving/
winning trades are actually separable by adverse excursion depth -- if winners routinely experience
the same drawdown that failures do before confirming, no stop width recovers that distinction.

Four groups, same 3pm-entry population and 1% threshold as RQ-14a (frozen, not re-optimized):
  A.  Never reached +1% above entry at all.
  B1. Reached +1%, retested box_high on the SAME day as entry (D0).
  B2. Reached +1%, retested box_high on D1 (the next day).
  C.  Reached +1%, never retested box_high (survives to the end of the observation window).

For B1/B2 (confirmed failures): MAE before confirmation (worst price reached up to and including
the retest bar), MFE before confirmation, bars from entry to +1%, bars from +1% to retest, total
bars to failure.

For A/C (no confirmed failure in-window): MAE and MFE over the SAME observation window (entry
through end of D1 session), for the critical comparison critic specified -- do winners dip just as
deep as failures before working out, or is there a narrow region that actually separates them.

Usage: python3 swing_qs_emapb/28_rq_emapb15a_risk_envelope.py
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
UP_MOVE_THRESHOLD_PCT = 1.0  # frozen from RQ-14a


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
        d1_date = daily.Date.iloc[iD + 1]

        end_mask = h1.index[(h1.session_date > d1_date)]
        end_i = int(end_mask[0]) if len(end_mask) else len(h1)
        window = h1.iloc[entry_i:end_i].reset_index(drop=True)
        if window.empty:
            continue

        up_threshold_price = entry_price * (1 + UP_MOVE_THRESHOLD_PCT / 100)
        up_idx = window.index[window.High >= up_threshold_price]
        reached_up_move = len(up_idx) > 0

        out = dict(ticker=r.ticker, a_entry_date=r.a_entry_date, box_high=box_high,
                   entry_price=entry_price, reached_up_move=reached_up_move)

        if reached_up_move:
            up_i = int(up_idx[0])
            after_up = window.iloc[up_i + 1:]
            retest_idx = after_up.index[after_up.Low <= box_high]
            if len(retest_idx) > 0:
                retest_i = int(retest_idx[0])
                retest_session = window.session_date.iloc[retest_i]
                out["group"] = "B1" if retest_session == entry_day else "B2"
                pre_confirm = window.iloc[:retest_i + 1]
                out["mae_before_confirm_pct"] = (pre_confirm.Low.min() / entry_price - 1) * 100
                out["mfe_before_confirm_pct"] = (pre_confirm.High.max() / entry_price - 1) * 100
                out["bars_entry_to_up"] = up_i
                out["bars_up_to_retest"] = retest_i - up_i
                out["bars_entry_to_failure"] = retest_i
            else:
                out["group"] = "C"
                out["mae_window_pct"] = (window.Low.min() / entry_price - 1) * 100
                out["mfe_window_pct"] = (window.High.max() / entry_price - 1) * 100
        else:
            out["group"] = "A"
            out["mae_window_pct"] = (window.Low.min() / entry_price - 1) * 100
            out["mfe_window_pct"] = (window.High.max() / entry_price - 1) * 100

        rows.append(out)
        if (n + 1) % 5000 == 0:
            print(f"  ...{n + 1:,}/{len(pop_all):,}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb15a_risk_envelope.csv", index=False)
    already_run_pct = (df.entry_price / df.box_high - 1) * 100
    df = df[already_run_pct.abs() <= EXTENSION_OUTLIER_CUTOFF].copy()
    print(f"\nn={len(df):,} (after excluding corp-action artifacts)\n")

    print("=== Group sizes ===")
    print(df.group.value_counts())

    print("\n=== B1/B2 (confirmed failures): MAE/MFE before confirmation, timing ===")
    for g in ["B1", "B2"]:
        sub = df[df.group == g]
        print(f"\n--- {g} (n={len(sub):,}) ---")
        print(f"  MAE before confirm:  {sub.mae_before_confirm_pct.describe(percentiles=[.1,.25,.5,.75,.9]).round(2).to_dict()}")
        print(f"  MFE before confirm:  median={sub.mfe_before_confirm_pct.median():.2f}%")
        print(f"  bars entry->+1%:     median={sub.bars_entry_to_up.median():.1f}")
        print(f"  bars +1%->retest:    median={sub.bars_up_to_retest.median():.1f}")
        print(f"  bars entry->failure: median={sub.bars_entry_to_failure.median():.1f}")

    print("\n=== A/C (no confirmed failure): MAE/MFE over the SAME window, for comparison ===")
    for g in ["A", "C"]:
        sub = df[df.group == g]
        print(f"\n--- {g} (n={len(sub):,}) ---")
        print(f"  MAE over window: {sub.mae_window_pct.describe(percentiles=[.1,.25,.5,.75,.9]).round(2).to_dict()}")
        print(f"  MFE over window: median={sub.mfe_window_pct.median():.2f}%")

    print("\n=== THE CRITICAL COMPARISON: does a narrow adverse-excursion band separate failures from survivors? ===")
    fail_mae = pd.concat([df[df.group == "B1"].mae_before_confirm_pct, df[df.group == "B2"].mae_before_confirm_pct])
    survive_mae = df[df.group == "C"].mae_window_pct
    print(f"Failures (B1+B2) MAE-before-confirm: {fail_mae.describe(percentiles=[.1,.25,.5,.75,.9]).round(2).to_dict()}")
    print(f"Survivors (C) MAE-over-window:       {survive_mae.describe(percentiles=[.1,.25,.5,.75,.9]).round(2).to_dict()}")
    for thresh in [-1, -1.5, -2, -2.5, -3, -4, -5]:
        pct_fail_breach = (fail_mae <= thresh).mean() * 100
        pct_survive_breach = (survive_mae <= thresh).mean() * 100
        print(f"  stop at {thresh:+.1f}%: catches {pct_fail_breach:5.1f}% of failures, "
              f"would ALSO stop out {pct_survive_breach:5.1f}% of survivors")


if __name__ == "__main__":
    main()
