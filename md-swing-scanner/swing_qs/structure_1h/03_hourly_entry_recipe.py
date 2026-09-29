"""Run the QS raw-breakout recipe with the bar being an HOUR instead of a day, per the
user's explicit clarification (relayed from another session): not "1H structure before
a daily breakout" (that was Stage A, already done, closed negative) -- literally
redefine the entry population using intraday_cache_1h/ as the base timeframe. Same
recipe as qs_dashboard.py's frozen v0.1 (raw N-bar-high breakout, base_duration/
gap_to_trigger conditional gate, S1b-style stop = prior BAR's low, not prior day) --
just with hourly bars.

Two lookback conventions tested side by side, since there is no single established
hourly-swing-trading standard (checked: 20-bar lookback is a commonly cited retail
convention, but nothing universal):
  LITERAL:    N_hours = 10, 20, 40      (same numbers as daily, unit changed to hours)
  WALL_CLOCK: N_hours = 65, 130, 260    (10/20/40 TRADING DAYS' worth of hours, at the
              cache's own measured ~6.5 bars/session average -- same real-world context
              window as the daily recipe, just measured with hourly precision)

Only ~70 days / ~455-481 hourly bars per ticker exist (intraday_cache_1h/) -- the
260-hour lookback consumes more than half that window before any event can even be
found; flagged explicitly in the output, not hidden.

No corp-action-day flag exists in this hourly cache (unlike backtest.load()'s daily
data) -- accepted limitation for this exploratory pass, disclosed here.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd
import numpy as np

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = 'intraday_cache_1h'
CONSOLIDATION_TOLERANCE_PCT = 3.0
GAP_BAD_THRESHOLD_PCT = 2.343
TRIGGER_CLEARANCE = 1.005
STOP_R = -1.0
PROOF_R = 0.25
MAX_TRACK_BARS = 98  # ~15 trading days * 6.5 bars/session, wall-clock-consistent
                     # forward-tracking window for ALL variants, so only the ENTRY
                     # lookback changes between literal and wall-clock runs.
LITERAL_HOURS = [10, 20, 40]
WALLCLOCK_HOURS = [65, 130, 260]


def base_duration_bars(rows, high_prior_series, i):
    cnt = 0
    for k in range(i - 1, max(i - 200, 0), -1):
        hp = high_prior_series.iloc[k]
        if pd.isna(hp) or not hp:
            break
        gap_pct = (hp - rows.iloc[k].Close) / hp * 100
        if 0 <= gap_pct <= CONSOLIDATION_TOLERANCE_PCT:
            cnt += 1
        else:
            break
    return cnt


def walk_ticker(rows, lookback_bars):
    n_rows = len(rows)
    high_prior_series = rows.High.shift(1).rolling(lookback_bars).max()

    # S1b = prior TRADING DAY's low (matching the real daily-product semantics), not
    # the prior HOURLY bar's low -- that was too tight/noise-driven (caught by direct
    # user question; explains the ~80% stop rate in the first pass). Build a per-
    # session daily low, shift by one whole session, then map back onto every hourly
    # row belonging to that session.
    session_low = rows.groupby("session").Low.min()
    prior_session_low = session_low.shift(1)
    rows = rows.copy()
    rows["prior_day_low"] = rows.session.map(prior_session_low)
    trades = []
    in_position = False
    cur = None
    for i in range(n_rows):
        row = rows.iloc[i]
        if in_position:
            days_held = i - cur["entry_i"]
            high_r = (row.High / cur["entry_price"] - 1) * 100 / cur["initial_risk_pct"]
            low_r = (row.Low / cur["entry_price"] - 1) * 100 / cur["initial_risk_pct"]
            close_r = (row.Close / cur["entry_price"] - 1) * 100 / cur["initial_risk_pct"]
            cur["max_r"] = max(cur["max_r"], high_r)
            stopped = low_r <= STOP_R
            capped = days_held >= MAX_TRACK_BARS
            if stopped or capped:
                cur["exit_r"] = STOP_R if stopped else close_r
                cur["exit_reason"] = "stop" if stopped else "max_bars"
                trades.append(cur)
                in_position, cur = False, None

        if i < lookback_bars + 1:
            continue
        hp = high_prior_series.iloc[i]
        if pd.isna(hp):
            continue
        entry_price = hp * TRIGGER_CLEARANCE
        if row.High < entry_price:
            continue
        base_dur = base_duration_bars(rows, high_prior_series, i)
        row_prev = rows.iloc[i - 1]
        gap_to_trigger_pct = (entry_price / row_prev.Close - 1) * 100 if row_prev.Close else None
        gate_pass = not (base_dur == 0 and gap_to_trigger_pct is not None and gap_to_trigger_pct > GAP_BAD_THRESHOLD_PCT)

        if in_position:
            continue  # occupied -- same single-position convention as the daily recipe
        if not gate_pass:
            continue
        initial_stop_price = row.prior_day_low  # prior TRADING DAY's low, not prior hourly bar's
        if pd.isna(initial_stop_price):
            continue
        initial_risk_pct = (entry_price - initial_stop_price) / entry_price * 100
        if initial_risk_pct <= 0:
            continue
        in_position = True
        cur = dict(entry_i=i, entry_price=entry_price, initial_risk_pct=initial_risk_pct, max_r=-np.inf)
    return trades


def run_variant(tickers, lookback_bars, label):
    all_trades = []
    n_raw_triggers = 0
    for n, t in enumerate(tickers):
        try:
            rows = pd.read_csv(f"{CACHE_DIR}/{t}.csv", parse_dates=["Datetime"])
        except FileNotFoundError:
            continue
        if len(rows) < lookback_bars + 5:
            continue
        trades = walk_ticker(rows, lookback_bars)
        all_trades.extend(trades)
    df = pd.DataFrame(all_trades)
    if len(df) == 0:
        print(f"{label} (lookback={lookback_bars}h): 0 trades -- lookback likely too long for available data")
        return None
    print(f"{label} (lookback={lookback_bars}h): n={len(df)}  mean_r={df.exit_r.mean():.4f}  "
          f"median_r={df.exit_r.median():.4f}  win%={(df.exit_r>0).mean()*100:.1f}  "
          f"stopped%={(df.exit_reason=='stop').mean()*100:.1f}")
    return df


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    print(f"Available hourly bars per ticker: ~455-481 (70-day cache, ~6.5 bars/session, 74 sessions)\n")

    print("=== LITERAL (N_hours = 10/20/40, same numbers as daily) ===")
    literal_results = {lb: run_variant(tickers, lb, "literal") for lb in LITERAL_HOURS}

    print("\n=== WALL-CLOCK (N_hours = 65/130/260, ~10/20/40 trading days of context) ===")
    wallclock_results = {lb: run_variant(tickers, lb, "wall-clock") for lb in WALLCLOCK_HOURS}

    for lb, df in {**literal_results, **wallclock_results}.items():
        if df is not None:
            df.to_csv(f"{OUT_DIR}/hourly_recipe_{lb}h_trades.csv", index=False)
    print("\nSaved per-variant trade CSVs.")
