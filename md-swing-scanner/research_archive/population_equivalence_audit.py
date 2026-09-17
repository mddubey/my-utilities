"""RQ-47: Production Population Consistency Audit (2026-09-16, critic-specified after
Update 46's AEGISVOPAK finding). NOT a research project -- an engineering/regression
check: is every trade that would count in our backtest performance numbers also
something the LIVE dashboard would have shown, at the moment it triggered?

Invariant under test: "Every historical trade counted in performance metrics would have
appeared on the live dashboard at the moment it triggered." Any mismatch must be
attributable to a KNOWN, understood cause (freshness conditioning, the liquidity floor,
the 13:00 cutoff, checklist_pass/theta-trap being EOD-only telemetry, correctly not part
of the live gate) -- not to a hidden, undocumented divergence.

Two independent verdicts computed per real intraday breach (High crossed the trigger --
what a live IOC order would have filled on, regardless of what the close later did):

  LIVE verdict  = was this ticker "primed" as of YESTERDAY's frozen close
                  (daily_scan._passes_primed_checks(), the actual function
                  shortlist_primed() calls -- this is the real, current live mechanism,
                  not a re-derivation of it) AND did today's real High cross the trigger.

  BACKTEST verdict = does TODAY's fully-closed EOD row pass signals.entry_signal()
                  (the real function backtest.detect_entry()/simulate_ticker() use to
                  decide what counts in the performance population).

Where they disagree, the specific failing gate is identified by re-checking each
sub-condition directly (base_filters_pass's own five conditions individually,
checklist_pass, reject_theta_trap) -- reusing the real production functions throughout,
never reimplementing the logic.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import daily_scan
import signals
from pivots import daily_pivots
from signals import (entry_signal, base_filters_pass, checklist_pass, reject_theta_trap,
                      breakout_continuation, VOL_ZSCORE_MIN,
                      RSI_MIN, RSI_MAX, EMA34_RISING_DAYS_MIN, MIN_TRADED_VALUE, MOMENTUM_20D_MIN)

TRIGGER_CLEARANCE = 1.005

daily_cache = {}


def load_daily(ticker):
    if ticker not in daily_cache:
        daily_cache[ticker] = backtest.load(ticker, daily_pivots).reset_index()
    return daily_cache[ticker]


def base_filters_reason(row):
    """Which specific base_filters_pass sub-condition fails, if any."""
    if row.Close <= row.ema34 or row.ema8 <= row.ema34:
        return "trend_not_bullish"
    if not (RSI_MIN < row.rsi14 < RSI_MAX):
        return "rsi_band"
    if row.ema34_rising10 < EMA34_RISING_DAYS_MIN:
        return "ema34_persistence"
    if row.traded_value_sma20 < MIN_TRADED_VALUE:
        return "liquidity_floor"
    if row.Close < MOMENTUM_20D_MIN * row.close_20ago:
        return "momentum_20d"
    return None


def diagnose_mismatch(live, backtest_v, yday_row, today_row):
    """Returns the specific reason two verdicts disagree, reusing the real production
    checks directly rather than guessing."""
    if live and not backtest_v:
        # live said yes (primed yesterday + real breach today), backtest says no --
        # check today's own EOD-confirmed gates one at a time, in the order entry_signal
        # itself checks them.
        if today_row.Close <= today_row.high10_prior:
            return "weak_close_no_confirm"  # High crossed, Close reverted to/below the raw pivot
                                             # (<=, not < -- breakout_continuation()'s own check is
                                             # a strict >, so an exact tie also fails it)
        if pd.isna(today_row.vol_zscore) or today_row.vol_zscore < VOL_ZSCORE_MIN:
            return "vol_zscore_gate"  # breakout_continuation()'s own final volume-surge condition
        required = ["ema34", "vol_avg10_prior", "high10_prior", "atr14_60ago",
                    "ema34_rising10", "traded_value_sma20", "close_20ago"]
        if today_row[required].isna().any():
            return "missing_indicator_data"
        bfr = base_filters_reason(today_row)
        if bfr:
            return f"base_filters:{bfr}"
        if not checklist_pass(today_row):
            return "checklist_pass"
        if reject_theta_trap(today_row):
            return "theta_trap"
        return "OTHER_UNKNOWN"
    elif backtest_v and not live:
        # backtest confirmed a real entry, but live wouldn't have shown it -- check
        # whether it was the priming step (yesterday's row) that blocked it.
        required = ["ema34", "vol_avg10_prior", "high10_prior", "atr14_60ago",
                    "ema34_rising10", "traded_value_sma20", "close_20ago"]
        if yday_row[required].isna().any():
            return "missing_indicator_data_yday"
        bfr = base_filters_reason(yday_row)
        if bfr:
            return f"not_primed_yday:{bfr}"
        return "OTHER_UNKNOWN"
    return None


def scan(tickers):
    rows_out = []
    for t in tickers:
        df = load_daily(t)
        for i in range(1, len(df) - 1):
            today_row = df.iloc[i]
            yday_row = df.iloc[i - 1]
            if today_row.corp_action_day or pd.isna(today_row.high10_prior):
                continue
            trigger_price = today_row.high10_prior * TRIGGER_CLEARANCE
            real_breach = today_row.High >= trigger_price
            if not real_breach:
                continue

            live = bool(daily_scan._passes_primed_checks(t, df.iloc[:i], yday_row))
            backtest_v = bool(entry_signal(today_row))

            reason = diagnose_mismatch(live, backtest_v, yday_row, today_row) if live != backtest_v else None
            rows_out.append(dict(ticker=t, trigger_date=today_row.Date, live=live,
                                  backtest=backtest_v, mismatch_reason=reason))
    return pd.DataFrame(rows_out)


def run():
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    signals.MIN_TRADED_VALUE = 1_000_000_000  # current production value, explicit
    print("Scanning full history for every real intraday breach, both verdicts...")
    out = scan(tickers)
    out.to_csv("runs/population_equivalence_audit.csv", index=False)

    n_total = len(out)
    n_agree = (out.live == out.backtest).sum()
    n_mismatch = n_total - n_agree
    print(f"\nn total breach events = {n_total}")
    print(f"agree (both yes or both no) = {n_agree} ({n_agree/n_total*100:.1f}%)")
    print(f"mismatch = {n_mismatch} ({n_mismatch/n_total*100:.1f}%)")

    print("\n=== Mismatch reason breakdown ===")
    print(out.mismatch_reason.value_counts(dropna=False).to_string())

    unknown = out[out.mismatch_reason == "OTHER_UNKNOWN"]
    print(f"\nOTHER_UNKNOWN (undiagnosed drift, should be 0): {len(unknown)}")
    if len(unknown):
        print(unknown.head(20).to_string(index=False))


if __name__ == "__main__":
    run()
