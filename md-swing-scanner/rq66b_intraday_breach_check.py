"""RQ-66B (2026-09-19): does anything observable in the FIRST HOURS after an EMA34=2
Delta breach -- not day+1, not even end-of-breach-day -- predict which trades are about
to become Immediate Fade / true-Unique(15d) losers?

Motivated directly by the user's own refinement of RQ-66A: options only live in the
first few hours post-breach (entry to day+1-open), so any signal built from day+1/day+2
information (already ruled out) can't help options at all, and a same-session signal
would help both books. Real intraday cache only covers ~70-90 trading days (500 tickers),
so this is necessarily a small-sample test, unlike RQ-66 Stage 1's full 5-year daily-bar
population -- treat directional agreement as informative, exact magnitudes as noisy.

Same Research Integrity Rule (sibling to Rule #6, adopted in RQ-66 Stage 1) applies: any
feature tested for predictive power must be checked against forward returns anchored to
the breach day's own Close, not trigger, before being trusted -- avoids the exact
artifact that voided vol_zscore/body_atr_daily/dist_to_trigger_pct in Stage 1. Features
below are deliberately picked to NOT be simple restatements of the Close-vs-trigger gap:
  - time_of_breach_minutes   -- minutes since 9:15 when High first crossed trigger
  - pullback_from_high_pct   -- (post-breach intraday high - EOD Close) / that high --
                                 shape of the move (ran then gave back), not its level
  - intraday_vol_ratio       -- cumulative volume from open to breach vs. what a normal
                                 day's volume-so-far would be at that time of day
"""
import warnings
warnings.filterwarnings("ignore")

import sys

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from breakout_failure_confirmation_cost import TRIGGER_CLEARANCE, simulate_swing, simulate_day1, _load_intraday
from daily_scan import _fo_tickers
from research.metrics import expectancy, win_rate

MARKET_OPEN_MIN = 9 * 60 + 15
MARKET_CLOSE_MIN = 15 * 60 + 30
MARKET_MINUTES = MARKET_CLOSE_MIN - MARKET_OPEN_MIN

FEATURES = ["time_of_breach_minutes", "pullback_from_high_pct", "intraday_vol_ratio"]


def gather(tickers, verbose=False):
    fo = _fo_tickers()
    signals.EMA34_RISING_DAYS_MIN = 2
    rows = []
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

        for i in range(3, len(df) - 3):
            row = df.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            date_norm = pd.Timestamp(row.Date).normalize()
            if date_norm not in intraday_dates:
                continue
            if not signals.base_filters_pass(row):
                continue
            trigger = row.high10_prior * TRIGGER_CLEARANCE
            if row.High < trigger:
                continue
            if row.ema34_rising10 >= 9:
                continue  # Delta only

            day_bars = intraday_df[naive_day == date_norm].reset_index()
            if day_bars.empty or day_bars.High.max() < trigger:
                continue
            breach_idx = day_bars.High.ge(trigger).idxmax()
            breach_ts = day_bars.iloc[breach_idx]["Datetime"]
            minutes_since_open = breach_ts.hour * 60 + breach_ts.minute - MARKET_OPEN_MIN
            if minutes_since_open < 0:
                continue

            post_breach = day_bars.iloc[breach_idx:]
            post_breach_high = post_breach.High.max()
            eod_close = day_bars.iloc[-1].Close
            pullback_from_high_pct = (post_breach_high - eod_close) / post_breach_high * 100 if post_breach_high else None

            vol_to_breach = day_bars.iloc[:breach_idx + 1].Volume.sum()
            frac_elapsed = max(minutes_since_open, 5) / MARKET_MINUTES
            expected_vol_by_now = row.vol_avg10_prior * frac_elapsed if pd.notna(row.vol_avg10_prior) and row.vol_avg10_prior else None
            intraday_vol_ratio = vol_to_breach / expected_vol_by_now if expected_vol_by_now else None

            d1 = (df.iloc[i + 1].Close / trigger - 1) * 100
            d2 = (df.iloc[i + 2].Close / trigger - 1) * 100
            d3 = (df.iloc[i + 3].Close / trigger - 1) * 100
            immediate_fade = d1 < 0 and d2 < d1 and d3 < d2

            max_h = min(15, len(df) - i - 1)
            d3_from_close = (df.iloc[i + 3].Close / row.Close - 1) * 100 if max_h >= 3 else None
            d15_from_close = (df.iloc[i + max_h].Close / row.Close - 1) * 100 if max_h >= 1 else None

            rows.append(dict(
                ticker=t, i=i,
                time_of_breach_minutes=minutes_since_open,
                pullback_from_high_pct=pullback_from_high_pct,
                intraday_vol_ratio=intraday_vol_ratio,
                immediate_fade=immediate_fade,
                swing_pnl=simulate_swing(df, i, trigger),
                day1_pnl=simulate_day1(df, i, trigger) if t in fo else None,
                d3_from_close=d3_from_close, d15_from_close=d15_from_close,
            ))
    signals.EMA34_RISING_DAYS_MIN = 9
    return pd.DataFrame(rows)


def report(df, n_buckets=4):
    print(f"\nEMA34=2 Delta, real intraday cache window, n={len(df)}")
    print(f"Immediate Fade rate (overall): {df.immediate_fade.mean()*100:.1f}%")
    for feat in FEATURES:
        d = df.dropna(subset=[feat]).copy()
        try:
            d["bucket"] = pd.qcut(d[feat], n_buckets, duplicates="drop")
        except ValueError:
            print(f"\n=== {feat}: not enough distinct values ===")
            continue
        print(f"\n=== {feat} (trigger-anchored trade outcome) ===")
        for b, g in d.groupby("bucket", observed=True):
            go = g.dropna(subset=["day1_pnl"])
            print(f"  {str(b):<24} n={len(g):<5} fade={g.immediate_fade.mean()*100:5.1f}%  "
                  f"swing win={win_rate(g.swing_pnl):5.1f}%/exp={expectancy(g.swing_pnl):+.3f}%  "
                  f"opt win={win_rate(go.day1_pnl):5.1f}%/exp={expectancy(go.day1_pnl):+.3f}% (n={len(go)})")
        print(f"  --- sanity check: re-anchored to own Close ---")
        for b, g in d.groupby("bucket", observed=True):
            gg = g.dropna(subset=["d3_from_close"])
            print(f"  {str(b):<24} n={len(gg):<5} d3_from_own_close mean={gg.d3_from_close.mean():+.3f}% "
                  f"median={gg.d3_from_close.median():+.3f}%  d15 mean={gg.d15_from_close.mean():+.3f}%")


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    df = gather(tickers, verbose=True)
    df.to_csv("rq66b_intraday_breach.csv", index=False)
    report(df)
