"""RQ-53 sensitivity sweep (2026-09-18) -- direct follow-up to
breakout_failure_confirmation_cost.py, which only tested one fixed combination
(FAILURE_THRESHOLD=0.5% below trigger, CONFIRM_BARS=2). Direct user question: why
was 0.5% picked as the fixed scenario instead of sweeping the critic's whole
proposed 0.4-0.6% range (and the confirm-window length)?

Reuses the exact same breach population, entry price (trigger_price = high10_prior
x 1.005), and real 5-min intraday path as breakout_failure_confirmation_cost.py --
gathers each breach's full same-day closes ONCE, then evaluates every
(FAILURE_THRESHOLD, CONFIRM_BARS) combination against that cached path in memory
(cheap), instead of re-scanning the 500-ticker universe once per combination.

Swing-side only (real backtest.check_exit(), no live-quote dependency). The
options-side variant is deliberately NOT swept here -- already flagged in
FINDINGS.md/chat that the "options" version of this test isn't a real options
result (no intraday option premium data exists anywhere in this project; only
day+1-open has ever been validated against real option OHLC).
"""
import warnings
warnings.filterwarnings("ignore")

import sys

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from research.metrics import expectancy
from breakout_failure_confirmation_cost import _load_intraday, simulate_swing, TRIGGER_CLEARANCE

SIGNAL_DROP_GRID = [0.004, 0.005, 0.006]
CONFIRM_BARS_GRID = [1, 2, 3]
MAX_CONFIRM_BARS = max(CONFIRM_BARS_GRID)


def gather_breaches(tickers, verbose=False):
    """One pass over the universe: find every real breach, cache its full
    same-day closes-from-breach array plus trigger_price and the real swing_pnl
    baseline. Independent of FAILURE_THRESHOLD/CONFIRM_BARS -- computed once."""
    breaches = []
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  {n}/{len(tickers)} tickers, {len(breaches)} breaches so far", file=sys.stderr)
        try:
            daily_df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        intraday_df, naive_day = _load_intraday(t)
        if intraday_df is None:
            continue
        intraday_dates = set(naive_day.unique())

        for i in range(len(daily_df) - 1):
            row = daily_df.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            date_norm = pd.Timestamp(row.Date).normalize()
            if date_norm not in intraday_dates:
                continue
            if not signals.base_filters_pass(row):
                continue

            trigger_price = row.high10_prior * TRIGGER_CLEARANCE
            day_bars = intraday_df[naive_day == date_norm]
            if day_bars.empty or day_bars.High.max() < trigger_price:
                continue

            breach_idx = day_bars.High.reset_index(drop=True).ge(trigger_price).idxmax()
            closes = day_bars.Close.reset_index(drop=True).iloc[breach_idx:].reset_index(drop=True)
            breaches.append(dict(
                ticker=t, date=row.Date, trigger_price=trigger_price,
                closes=closes.tolist(),
                swing_pnl=simulate_swing(daily_df, i, trigger_price),
            ))
    return breaches


def evaluate(breaches, signal_drop, confirm_bars):
    """Cheap, in-memory: given the cached closes-from-breach array, find the
    signal bar and classify confirmed/reversed/unconfirmable for this specific
    (signal_drop, confirm_bars) combination."""
    hold, immediate, confirmed_policy = [], [], []
    n_signals = n_confirmed = n_reversed = n_unconfirmable = 0

    for b in breaches:
        trigger_price = b["trigger_price"]
        closes = b["closes"]
        threshold = trigger_price * (1 - signal_drop)

        signal_idx = None
        for k, c in enumerate(closes):
            if c < threshold:
                signal_idx = k
                break
        if signal_idx is None:
            continue
        n_signals += 1

        remaining = closes[signal_idx + 1: signal_idx + 1 + confirm_bars]
        if len(remaining) < confirm_bars:
            n_unconfirmable += 1
            continue

        immediate_price = closes[signal_idx]
        immediate_pnl = (immediate_price / trigger_price - 1) * 100
        hold.append(b["swing_pnl"])
        immediate.append(immediate_pnl)

        if all(c < threshold for c in remaining):
            n_confirmed += 1
            confirmed_price = remaining[-1]
            confirmed_policy.append((confirmed_price / trigger_price - 1) * 100)
        else:
            n_reversed += 1
            confirmed_policy.append(b["swing_pnl"])  # confirmed policy never fires -- rides to baseline

    return dict(
        n_signals=n_signals, n_confirmed=n_confirmed, n_reversed=n_reversed,
        n_unconfirmable=n_unconfirmable,
        hold_exp=expectancy(pd.Series(hold)) if hold else None,
        immediate_exp=expectancy(pd.Series(immediate)) if immediate else None,
        confirmed_exp=expectancy(pd.Series(confirmed_policy)) if confirmed_policy else None,
    )


def main():
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    print(f"Gathering breaches once from {len(tickers)} tickers (independent of threshold/confirm-bars)...", file=sys.stderr)
    breaches = gather_breaches(tickers, verbose=True)
    print(f"\n{len(breaches)} real breaches cached. Evaluating {len(SIGNAL_DROP_GRID)}x{len(CONFIRM_BARS_GRID)} grid...\n")

    print(f"{'thresh':>7} | {'bars':>4} | {'n_sig':>6} | {'n_conf':>6} | {'n_rev':>5} |   do-nothing |    immediate |  confirm-exit")
    for sd in SIGNAL_DROP_GRID:
        for cb in CONFIRM_BARS_GRID:
            r = evaluate(breaches, sd, cb)
            def fmt(x):
                return f"{x:+.3f}%" if x is not None else "   n/a "
            marker = "  <- tested in first pass" if (sd == 0.005 and cb == 2) else ""
            print(f"{sd*100:6.1f}% | {cb:>4} | {r['n_signals']:>6} | {r['n_confirmed']:>6} | {r['n_reversed']:>5} | "
                  f"{fmt(r['hold_exp']):>12} | {fmt(r['immediate_exp']):>12} | {fmt(r['confirmed_exp']):>12}{marker}")


if __name__ == "__main__":
    main()
