"""RQ-56: EMA34=2 uniqueness test (2026-09-18), critic-proposed falsification --
"the only EMA34 test I'd spend time on before freezing."

Question: does EMA34_RISING_DAYS_MIN=2 discover genuinely NEW trades, or does it
just enter the SAME trades a day or two earlier than EMA34=9 would have anyway?

For every Delta trade (fires at EMA34=2, fails at EMA34=9): check whether EMA34=9
ALSO fires on the SAME ticker within the next 1-3 REAL TRADING DAYS (not calendar
days -- uses the daily bar index, so weekends/holidays don't distort the window).
"Early version" = EMA34=9 fires on that ticker within [i+1, i+3]. "Unique" =
EMA34=9 never fires there in that window.

Critic's promotion rule: >=30% of Delta trades must be BOTH unique AND
profitable. If ~95% are just "one day earlier," leave EMA34=9 alone.
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

LOOKAHEAD_DAYS = 3


def gather(tickers, fo, verbose=False):
    original = signals.EMA34_RISING_DAYS_MIN
    signals.EMA34_RISING_DAYS_MIN = 2
    per_ticker_common_idx = {}  # ticker -> sorted list of daily-row indices where EMA34>=9 fired
    delta_rows = []
    try:
        for n, t in enumerate(tickers):
            if verbose and n % 100 == 0:
                print(f"  {n}/{len(tickers)}", file=sys.stderr)
            try:
                df = backtest.load(t, daily_pivots).reset_index()
            except FileNotFoundError:
                continue
            common_idx = []
            ticker_delta = []
            for i in range(len(df) - 1):
                row = df.iloc[i]
                if row.corp_action_day or pd.isna(row.high10_prior):
                    continue
                if not signals.base_filters_pass(row):
                    continue
                trigger = row.high10_prior * TRIGGER_CLEARANCE
                if row.High < trigger:
                    continue
                if row.ema34_rising10 >= 9:
                    common_idx.append(i)
                else:
                    ticker_delta.append((i, row.Date, trigger))
            per_ticker_common_idx[t] = common_idx
            for i, date, trigger in ticker_delta:
                delta_rows.append(dict(
                    ticker=t, i=i, date=date,
                    swing_pnl=simulate_swing(df, i, trigger),
                    day1_pnl=simulate_day1(df, i, trigger) if t in fo else None,
                ))
    finally:
        signals.EMA34_RISING_DAYS_MIN = original

    # classify each Delta row: does EMA34=9 fire on the SAME ticker within [i+1, i+LOOKAHEAD_DAYS]?
    for r in delta_rows:
        common_idx = per_ticker_common_idx.get(r["ticker"], [])
        r["early_version"] = any(r["i"] < c <= r["i"] + LOOKAHEAD_DAYS for c in common_idx)

    return pd.DataFrame(delta_rows)


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    fo = _fo_tickers()
    print("Gathering Delta trades and per-ticker EMA34=9 fire indices...", file=sys.stderr)
    df = gather(tickers, fo, verbose=True)
    df.to_csv("ema34_rq56_uniqueness.csv", index=False)

    n_total = len(df)
    n_early = df.early_version.sum()
    n_unique = n_total - n_early
    print(f"\nTotal Delta trades: {n_total}")
    print(f"Early version (EMA34=9 fires on same ticker within {LOOKAHEAD_DAYS} trading days): {n_early} ({n_early/n_total*100:.1f}%)")
    print(f"Unique (EMA34=9 never fires there in that window): {n_unique} ({n_unique/n_total*100:.1f}%)")

    for label, sub in [("Early version", df[df.early_version]), ("Unique", df[~df.early_version])]:
        d1 = sub.day1_pnl.dropna()
        print(f"\n{label} (n={len(sub)}):")
        print(f"  SWING win={win_rate(sub.swing_pnl):5.1f}%  exp={expectancy(sub.swing_pnl):+.3f}%")
        print(f"  OPT   n={len(d1):<5} win={win_rate(d1):5.1f}%  exp={expectancy(d1):+.3f}%")

    unique = df[~df.early_version]
    unique_profitable_swing = (unique.swing_pnl > 0).mean() * 100
    pct_unique_and_profitable = (unique.swing_pnl > 0).sum() / n_total * 100
    print(f"\nCritic's promotion rule: >=30% of ALL Delta trades must be unique AND profitable (swing).")
    print(f"  Of unique trades, {unique_profitable_swing:.1f}% are profitable (swing).")
    print(f"  As a % of ALL Delta trades: {pct_unique_and_profitable:.1f}% are unique AND profitable.")
    print(f"  {'PASSES' if pct_unique_and_profitable >= 30 else 'FAILS'} the critic's 30% threshold.")
