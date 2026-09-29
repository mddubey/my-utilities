"""RQ-57: Operational Capacity Test (2026-09-18), final spec after two rounds of
methodology correction (see FINDINGS.md, "EMA34=2 promoted from Tier A Research to
Tier A Candidate" section). NOT a portfolio-allocator replay -- `portfolio.py` was
checked directly and found disconnected from this whole investigation (no ranking,
input is a static v28-era CSV). Uses the REAL live 9:20 ranking mechanism instead
(`live_checkpoint.py`'s dist_to_trigger/velocity blend), replayed on real 5-min
intraday data (~69-93 days).

Question: does EMA34=2 create opportunities that survive the real Top-5 selection
bottleneck a human actually faces at 9:20, or do the extra candidates just get
pushed below what anyone would actually act on?

Mechanism, faithfully adapted from live_checkpoint.py's real ranking (VELOCITY_WEIGHT=
0.20 blended with dist_to_trigger rank):
  - At a fixed 9:20 AM snapshot each real day, build the WATCHING pool (base_filters_pass
    as of the prior close, real intraday data exists, not yet fired as of 9:20).
  - dist_rank = percentile rank of dist_to_trigger_pct at 9:20 (closer = better).
  - vel_rank = percentile rank of closing speed (9:20 close vs 9:15 close -- the
    closest available comparison this early in the session, same "not enough data
    yet" tolerance the live code applies to a true 10-min lookback).
  - combo_rank = 0.8*dist_rank + 0.2*vel_rank, ascending = higher priority.
  - Top 5 by combo_rank = the executable set for that day, under each EMA34 threshold.
  - For each Top-5 name, check if it actually fires later that same real day (any
    time up to the 13:00 cutoff) and record the real swing/options outcome if so.
"""
import warnings
warnings.filterwarnings("ignore")

import sys
from datetime import time as dtime

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from breakout_failure_confirmation_cost import _load_intraday, TRIGGER_CLEARANCE, simulate_swing, simulate_day1
from daily_scan import _fo_tickers
from research.metrics import expectancy, win_rate

SNAPSHOT = dtime(9, 20)
EARLY_BAR = dtime(9, 15)
CUTOFF = dtime(13, 0)
TOP_N = 5


def gather(tickers, ema34_min, verbose=False):
    """One pass, all real days: for each (ticker, day) where base_filters_pass holds
    (with EMA34_RISING_DAYS_MIN=ema34_min), record whether it fired by 9:20, its
    9:20-snapshot ranking inputs if still watching, whether/if it fires by 13:00
    otherwise, and the real swing/options outcome if it fires at all that day."""
    original = signals.EMA34_RISING_DAYS_MIN
    signals.EMA34_RISING_DAYS_MIN = ema34_min
    fo = _fo_tickers()
    rows = []
    try:
        for n, t in enumerate(tickers):
            if verbose and n % 100 == 0:
                print(f"  {n}/{len(tickers)}", file=sys.stderr)
            try:
                df = backtest.load(t, daily_pivots).reset_index()
            except FileNotFoundError:
                continue
            intraday_df, naive_day = _load_intraday(t)
            if intraday_df is None:
                continue
            intraday_dates = set(naive_day.unique())
            for i in range(len(df) - 1):
                row = df.iloc[i]
                if row.corp_action_day or pd.isna(row.high10_prior):
                    continue
                date_norm = pd.Timestamp(row.Date).normalize()
                if date_norm not in intraday_dates:
                    continue
                if not signals.base_filters_pass(row):
                    continue
                trigger = row.high10_prior * TRIGGER_CLEARANCE

                day_bars = intraday_df[naive_day == date_norm]
                if day_bars.empty:
                    continue

                bars_by_920 = day_bars[day_bars.index.time <= SNAPSHOT]
                bars_by_cutoff = day_bars[day_bars.index.time <= CUTOFF]
                if bars_by_920.empty or bars_by_cutoff.empty:
                    continue

                fired_by_920 = bars_by_920.High.max() >= trigger
                fired_by_cutoff = bars_by_cutoff.High.max() >= trigger

                close_920 = bars_by_920.Close.iloc[-1]
                dist_to_trigger_pct = (trigger / close_920 - 1) * 100
                early_bars = bars_by_920[bars_by_920.index.time <= EARLY_BAR]
                close_915 = early_bars.Close.iloc[-1] if not early_bars.empty else close_920
                velocity_pct = (close_920 / close_915 - 1) * 100 if close_915 else 0.0

                swing_pnl = day1_pnl = None
                if fired_by_cutoff:
                    swing_pnl = simulate_swing(df, i, trigger)
                    if t in fo:
                        day1_pnl = simulate_day1(df, i, trigger)

                rows.append(dict(
                    ticker=t, date=row.Date, fired_by_920=fired_by_920, fired_by_cutoff=fired_by_cutoff,
                    dist_to_trigger_pct=dist_to_trigger_pct, velocity_pct=velocity_pct,
                    swing_pnl=swing_pnl, day1_pnl=day1_pnl,
                ))
    finally:
        signals.EMA34_RISING_DAYS_MIN = original
    return pd.DataFrame(rows)


def top5_by_day(df):
    """Rank the WATCHING (not-yet-fired-by-9:20) pool per day using the real
    live_checkpoint.py combo_rank (0.8*dist_rank + 0.2*vel_rank), return top-5
    tickers per day plus whether each ultimately fires by 13:00 and its outcome."""
    watching = df[~df.fired_by_920].copy()
    results = {}
    for date, g in watching.groupby("date"):
        g = g.copy()
        g["dist_rank"] = g.dist_to_trigger_pct.rank(pct=True, ascending=True)
        g["vel_rank"] = g.velocity_pct.rank(pct=True, ascending=False)
        g["combo_rank"] = 0.8 * g.dist_rank + 0.2 * g.vel_rank
        top5 = g.sort_values("combo_rank").head(TOP_N)
        results[date] = top5
    return results


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()

    print("Gathering EMA34>=9 (current production) universe...", file=sys.stderr)
    df9 = gather(tickers, 9, verbose=True)
    print("Gathering EMA34=2 (expanded) universe...", file=sys.stderr)
    df2 = gather(tickers, 2, verbose=True)

    df9.to_csv("ema34_rq57_ema9.csv", index=False)
    df2.to_csv("ema34_rq57_ema2.csv", index=False)

    n_days = df9.date.nunique()
    print(f"\nReal days covered: {n_days}")
    print(f"Total candidate-days: EMA34>=9={len(df9)}  EMA34=2={len(df2)}  "
          f"(avg/day: {len(df9)/n_days:.2f} vs {len(df2)/n_days:.2f})")

    top5_9 = top5_by_day(df9)
    top5_2 = top5_by_day(df2)

    all_dates = sorted(set(top5_9) | set(top5_2))
    changed_days = 0
    added, removed = [], []
    for d in all_dates:
        t9 = set(top5_9.get(d, pd.DataFrame()).get("ticker", pd.Series(dtype=str)))
        t2 = set(top5_2.get(d, pd.DataFrame()).get("ticker", pd.Series(dtype=str)))
        if t9 != t2:
            changed_days += 1
        added.extend(t2 - t9)
        removed.extend(t9 - t2)

    print(f"\nDays where the Top-5 composition differs: {changed_days}/{len(all_dates)}")
    print(f"Ticker-day slots added by EMA34=2 (in Top-5 at 2, not at 9): {len(added)}")
    print(f"Ticker-day slots removed by EMA34=2 (in Top-5 at 9, not at 2): {len(removed)}")

    def outcome_of(top5_dict):
        rows = pd.concat([v for v in top5_dict.values() if not v.empty], ignore_index=True) if top5_dict else pd.DataFrame()
        fired = rows[rows.fired_by_cutoff] if len(rows) else rows
        d1 = fired.day1_pnl.dropna() if len(fired) else pd.Series(dtype=float)
        return rows, fired, d1

    rows9, fired9, d1_9 = outcome_of(top5_9)
    rows2, fired2, d1_2 = outcome_of(top5_2)

    print(f"\n=== Top-5 executable outcomes ===")
    print(f"EMA34>=9: {len(rows9)} Top-5 slots/day, {len(fired9)} actually fired by cutoff ({len(fired9)/len(rows9)*100:.1f}%)")
    print(f"  SWING win={win_rate(fired9.swing_pnl):5.1f}%  exp={expectancy(fired9.swing_pnl):+.3f}%   "
          f"OPT n={len(d1_9):<4} win={win_rate(d1_9):5.1f}%  exp={expectancy(d1_9):+.3f}%")
    print(f"EMA34=2:  {len(rows2)} Top-5 slots/day, {len(fired2)} actually fired by cutoff ({len(fired2)/len(rows2)*100:.1f}%)")
    print(f"  SWING win={win_rate(fired2.swing_pnl):5.1f}%  exp={expectancy(fired2.swing_pnl):+.3f}%   "
          f"OPT n={len(d1_2):<4} win={win_rate(d1_2):5.1f}%  exp={expectancy(d1_2):+.3f}%")
