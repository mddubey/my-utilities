"""Stage A — pre-breakout 1H structure audit (descriptive only, 2026-09-28).

Question: do the trades that turned into the desirable QS moves sit on a
recognisable 1H structure immediately before the breakout, while the daily chart
does not distinguish them? This script only DESCRIBES the 1H anatomy before each
breach and compares distributions across outcome groups. No thresholds, no
filter, no rule — Stage 0 guardrails and Rule #19/#21 apply.

Research Preflight:
1. Population: the 96 replay events in trajectory_replay/mvp_v1/events.csv, drawn
   before any trajectory was looked at; 89 have five fully complete prior 1H
   sessions (FINDINGS.md, 1H data-infrastructure note). The other 7 are reported
   as excluded, not silently dropped.
2. Entry clock: every feature uses only 1H bars whose CLOSE is at or before
   `entry_timestamp` (the first 5-min bar touching the trigger). The bar containing
   the breach is never used. Swing highs/lows use the k=1 symmetric confirmation on
   bars that are all already closed, so nothing after the breach is consulted.
3. Stop definition: outcomes are read from events.csv as already computed there
   (initial_stop_price inherited from that file); this script derives no new R.
4. Exit engine: none — outcomes are the fixed 6-session observation window the
   replay already produced (mfe_r, first_0.25R_min, D5_close_r).
5. Comparison unit: pre-entry structure descriptors vs post-entry trajectory
   groups, on the same events. Descriptive separation only.
"""
import os
import sys

sys.path.insert(0, "/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner")
os.chdir("/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner")

import warnings

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from resample_1h import load_1h

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS = "swing_qs/trajectory_replay/mvp_v1/events.csv"
TWO_AXES = "swing_qs/trajectory_replay/mvp_v1/two_axes_all_96.csv"
LOOKBACK_BARS = 30          # ~5 sessions of 1H bars
PRIOR_SESSIONS = 5


def closed_before(bars, ts):
    """1H bars whose close is at or before ts. Stub bars (15:15 on a 15:30 session)
    are 15 minutes long; every other bar is 60."""
    is_stub = bars.index.strftime("%H:%M") == "15:15"
    close_ts = bars.index + pd.to_timedelta(np.where(is_stub, 15, 60), unit="m")
    return bars[close_ts <= ts]


def pivots_k1(bars):
    """k=1 symmetric swing points: a bar whose High exceeds both neighbours is a
    swing high, whose Low undercuts both is a swing low. Last bar can't be one."""
    h, lo = bars.High.to_numpy(), bars.Low.to_numpy()
    sh = [i for i in range(1, len(bars) - 1) if h[i] > h[i - 1] and h[i] > h[i + 1]]
    sl = [i for i in range(1, len(bars) - 1) if lo[i] < lo[i - 1] and lo[i] < lo[i + 1]]
    return sh, sl


def monotone_run(values, higher):
    """Length of the run of consecutive higher (or lower) values ending at the last one."""
    run = 1 if values else 0
    for a, b in zip(values[-2::-1], values[::-1]):
        if (b > a) if higher else (b < a):
            run += 1
        else:
            break
    return run


def features(bars, trigger, entry_session):
    lb = bars.tail(LOOKBACK_BARS)
    rng_pct = ((lb.High - lb.Low) / lb.Close * 100)
    dclose = lb.Close.diff().abs().sum()
    sh, sl = pivots_k1(lb)
    sh_vals = lb.High.to_numpy()[sh].tolist()
    sl_vals = lb.Low.to_numpy()[sl].tolist()
    pivots_sorted = sorted([(i, "H") for i in sh] + [(i, "L") for i in sl])
    alternations = sum(1 for (_, a), (_, b) in zip(pivots_sorted, pivots_sorted[1:]) if a != b)
    prior_sessions = [s for s in sorted(bars.session.unique()) if s < entry_session][-PRIOR_SESSIONS:]
    per_session = bars[bars.session.isin(prior_sessions)].groupby("session").agg(
        High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"))
    sess_ranges = (per_session.High - per_session.Low) / per_session.Close * 100
    entry_day = bars[bars.session == entry_session]
    prev_close = bars[bars.session < entry_session].Close.iloc[-1]
    return dict(
        bars_in_lookback=len(lb),
        n_entry_day_bars_before_breach=len(entry_day),
        entry_day_open_gap_pct=(entry_day.Open.iloc[0] / prev_close - 1) * 100 if len(entry_day) else np.nan,
        range_contraction_6v24=rng_pct.tail(6).mean() / rng_pct.head(len(lb) - 6).mean(),
        range_contraction_12v18=rng_pct.tail(12).mean() / rng_pct.head(len(lb) - 12).mean(),
        last_session_range_vs_prior5=sess_ranges.iloc[-1] / sess_ranges.iloc[:-1].mean(),
        consolidation_width_pct_12=(lb.tail(12).High.max() - lb.tail(12).Low.min()) / trigger * 100,
        consolidation_width_pct_30=(lb.High.max() - lb.Low.min()) / trigger * 100,
        trigger_vs_lookback_high_pct=(trigger / lb.High.max() - 1) * 100,
        trigger_vs_last_swing_high_pct=(trigger / sh_vals[-1] - 1) * 100 if sh_vals else np.nan,
        trigger_vs_last_swing_low_pct=(trigger / sl_vals[-1] - 1) * 100 if sl_vals else np.nan,
        last_close_vs_trigger_pct=(lb.Close.iloc[-1] / trigger - 1) * 100,
        close_position_in_lookback_range=(lb.Close.iloc[-1] - lb.Low.min()) / (lb.High.max() - lb.Low.min()),
        n_swing_highs=len(sh), n_swing_lows=len(sl), n_alternations=alternations,
        higher_lows_run=monotone_run(sl_vals, higher=True),
        lower_highs_run=monotone_run(sh_vals, higher=False),
        efficiency_ratio_30=abs(lb.Close.iloc[-1] - lb.Close.iloc[0]) / dclose if dclose else np.nan,
        up_bar_fraction_30=(lb.Close > lb.Open).mean(),
        net_move_30_pct=(lb.Close.iloc[-1] / lb.Close.iloc[0] - 1) * 100,
    )


def cliffs_delta(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) == 0 or len(b) == 0:
        return np.nan
    gt = (a[:, None] > b[None, :]).sum()
    lt = (a[:, None] < b[None, :]).sum()
    return (gt - lt) / (len(a) * len(b))


def main():
    warnings.filterwarnings("ignore")
    ev = pd.read_csv(EVENTS, parse_dates=["entry_date", "entry_timestamp"])
    ev["entry_timestamp"] = ev.entry_timestamp.dt.tz_convert("Asia/Kolkata")
    ev = ev.merge(pd.read_csv(TWO_AXES)[["trade_id", "is_confirmed", "max_giveback_r"]], on="trade_id")
    ev["reached_025R_by_D5"] = ev["first_0.25R_min"].notna()
    # events.csv carries TECHM 2026-07-13 twice (two entry_definitions, one trade);
    # one pre-breakout structure per real breakout, so keep the first.
    ev = ev.drop_duplicates(subset=["ticker", "entry_date"], keep="first")

    rows, excluded = [], []
    for _, e in ev.iterrows():
        h = load_1h(e.ticker)
        entry_session = e.entry_date.date()
        prior = [s for s in sorted(h.session.unique()) if s < entry_session][-PRIOR_SESSIONS:]
        window = h[h.session.isin(prior + [entry_session])]
        if len(prior) < PRIOR_SESSIONS or not window[window.session.isin(prior)].complete.all():
            excluded.append(dict(trade_id=e.trade_id, ticker=e.ticker, entry_date=entry_session,
                                 reason="fewer than 5 complete prior 1H sessions"))
            continue
        bars = closed_before(window, e.entry_timestamp)
        f = features(bars, e.entry_price, entry_session)
        f.update(trade_id=e.trade_id, ticker=e.ticker, entry_date=entry_session,
                 breach_time=e.entry_timestamp.strftime("%H:%M"),
                 is_confirmed=bool(e.is_confirmed), reached_025R_by_D5=bool(e.reached_025R_by_D5),
                 mfe_r=e.mfe_r, D5_close_r=e.D5_close_r, max_giveback_r=e.max_giveback_r)
        rows.append(f)

    feat = pd.DataFrame(rows)
    feat.to_csv(f"{OUT_DIR}/pre_breakout_1h_features.csv", index=False)
    pd.DataFrame(excluded).to_csv(f"{OUT_DIR}/excluded.csv", index=False)

    feature_cols = [c for c in feat.columns if c not in (
        "trade_id", "ticker", "entry_date", "breach_time", "is_confirmed", "reached_025R_by_D5",
        "mfe_r", "D5_close_r", "max_giveback_r")]
    lines = [f"# Pre-breakout 1H structure audit — {len(feat)} events "
             f"({len(excluded)} excluded)\n",
             "Descriptive only. Cliff's delta: + means the first group sits higher. "
             "Spearman rho vs mfe_r and D5_close_r over all events.\n"]
    groups = [("confirmed six vs rest", feat.is_confirmed, ~feat.is_confirmed),
              ("reached 0.25R by D5 vs not", feat.reached_025R_by_D5, ~feat.reached_025R_by_D5)]
    for name, ga, gb in groups:
        lines.append(f"\n## {name}  (n={int(ga.sum())} vs {int(gb.sum())})\n")
        lines.append("| feature | median A | median B | Cliff's delta |")
        lines.append("|---|---|---|---|")
        for c in feature_cols:
            lines.append(f"| {c} | {feat.loc[ga, c].median():.3f} | {feat.loc[gb, c].median():.3f} "
                         f"| {cliffs_delta(feat.loc[ga, c], feat.loc[gb, c]):+.2f} |")
    lines.append("\n## Rank correlation with outcome axes (all events)\n")
    lines.append("| feature | rho vs mfe_r | rho vs D5_close_r | rho vs max_giveback_r |")
    lines.append("|---|---|---|---|")
    for c in feature_cols:
        ok = feat[c].notna()
        r1 = spearmanr(feat.loc[ok, c], feat.loc[ok, "mfe_r"]).correlation
        r2 = spearmanr(feat.loc[ok, c], feat.loc[ok, "D5_close_r"]).correlation
        r3 = spearmanr(feat.loc[ok, c], feat.loc[ok, "max_giveback_r"]).correlation
        lines.append(f"| {c} | {r1:+.2f} | {r2:+.2f} | {r3:+.2f} |")
    lines.append("\n## The confirmed six, raw\n")
    six = feat[feat.is_confirmed][["ticker", "entry_date", "breach_time", "n_entry_day_bars_before_breach",
                                   "range_contraction_6v24", "consolidation_width_pct_12",
                                   "trigger_vs_last_swing_high_pct", "higher_lows_run", "lower_highs_run",
                                   "n_alternations", "efficiency_ratio_30", "mfe_r"]]
    lines.append("| " + " | ".join(six.columns) + " |")
    lines.append("|" + "---|" * len(six.columns))
    for _, r in six.iterrows():
        lines.append("| " + " | ".join(f"{v:.2f}" if isinstance(v, float) else str(v) for v in r) + " |")
    report = "\n".join(lines)
    with open(f"{OUT_DIR}/AUDIT_SUMMARY.md", "w") as fh:
        fh.write(report + "\n")
    print(report)


if __name__ == "__main__":
    main()
