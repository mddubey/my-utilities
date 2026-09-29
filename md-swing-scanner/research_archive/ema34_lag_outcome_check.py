"""EMA34 lag outcome-quality check (2026-09-18) -- direct follow-up to
ema34_lag_check.py's fire-count timing table, per the standing "check both
options and swing" convention: does the lag actually cost real quality, not
just fire volume/timing?

Tags every real historical fire (base_filters_pass() + intraday High-cross,
full multi-year, same population as base_filters_threshold_sweep.py) with
Nifty's own up/down streak state on that exact date (a real, look-ahead-free
measure -- Nifty's close-to-close return is known by end of day), then splits
by "days into the current move" (1-2 / 3-5 / 6+) and reports real swing
(check_exit()) and real options (day+1-open, F&O-scoped) win/expectancy per
bucket.

Real finding (see FINDINGS.md "the live pipeline has never applied the Nifty
regime gate..." section): down-move fires degrade past day 2 (options flips to
a real loss by day 3-5); up-move fires show the opposite shape (the rare early
fires are the BEST quality, not the worst -- the lag costs volume there, not
quality). The down/6+ bucket (n=61/35) is well under Research Integrity Rule
#4's 500-trade minimum and is NOT a trustworthy result -- flagged explicitly,
not cited as a real signal.
"""
import warnings
warnings.filterwarnings("ignore")

import sys

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from breakout_failure_confirmation_cost import TRIGGER_CLEARANCE, simulate_swing, simulate_day1
from daily_scan import _fo_tickers
from research.metrics import expectancy, win_rate


def build_streak_state():
    """Nifty's own up/down streak length as of each real trading day's close --
    look-ahead free, known by end of that same day."""
    nifty = pd.read_csv("data_cache/_NIFTY.csv", index_col=0, parse_dates=True)
    nifty["ret_pct"] = nifty.Close.pct_change() * 100
    nifty = nifty.dropna(subset=["ret_pct"])

    state = {}
    cur_dir, cur_len = None, 0
    for date, r in nifty.ret_pct.items():
        d = "up" if r > 0 else "down"
        cur_len = cur_len + 1 if d == cur_dir else 1
        cur_dir = d
        state[date] = (d, cur_len)
    return state


def gather(tickers, streak_state, verbose=False):
    fo = _fo_tickers()
    rows = []
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  {n}/{len(tickers)}", file=sys.stderr)
        try:
            df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        for i in range(len(df) - 1):
            row = df.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            if not signals.base_filters_pass(row):
                continue
            trigger = row.high10_prior * TRIGGER_CLEARANCE
            if row.High < trigger:
                continue
            state = streak_state.get(pd.Timestamp(row.Date))
            if state is None:
                continue
            direction, streak_len = state
            rows.append(dict(
                ticker=t, date=row.Date, direction=direction, streak_len=streak_len,
                swing_pnl=simulate_swing(df, i, trigger),
                day1_pnl=simulate_day1(df, i, trigger) if t in fo else None,
            ))
    return pd.DataFrame(rows)


def bucket(streak_len):
    if streak_len <= 2:
        return "1-2 (fresh move)"
    if streak_len <= 5:
        return "3-5"
    return "6+ (established move)"


def report(df, direction, label):
    d_all = df[df.direction == direction].copy()
    d_all["bucket"] = d_all.streak_len.apply(bucket)
    print(f"\n=== {label} ===")
    for b in ["1-2 (fresh move)", "3-5", "6+ (established move)"]:
        d = d_all[d_all.bucket == b]
        d1 = d.day1_pnl.dropna()
        flag = "  <-- n<500, DO NOT TRUST (Research Integrity Rule #4)" if len(d) < 500 or len(d1) < 500 else ""
        print(f"  {b:<24} n={len(d):<6} SWING win={win_rate(d.swing_pnl):5.1f}% exp={expectancy(d.swing_pnl):+.3f}%   "
              f"n_opt={len(d1):<5} OPT win={win_rate(d1):5.1f}% exp={expectancy(d1):+.3f}%{flag}")


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    streak_state = build_streak_state()
    print("Gathering real fires with Nifty streak state...", file=sys.stderr)
    df = gather(tickers, streak_state, verbose=True)
    df.to_csv("lag_outcome_check.csv", index=False)
    print(f"\nn={len(df)}")

    report(df, "up", "UP-move fires: is day1-2 (fresh, filter hasn't caught up) different from 6+ (established)?")
    report(df, "down", "DOWN-move fires: is day1-2 (stale qualification from prior uptrend) different from 6+ (established decline)?")
