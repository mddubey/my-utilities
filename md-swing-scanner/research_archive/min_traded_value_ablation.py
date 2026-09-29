"""Isolated research only (2026-09-16). Revisits the 2026-08-30 MIN_TRADED_VALUE
leave-one-out ablation (see signals.py's own comment, ~line 48) on the CURRENT,
validated methodology -- the original test used a 210-stock/21-month population,
predates freshness-conditioning and the standard daily/intraday/intraday+cutoff
population-choice discipline this project now applies to everything. Prompted by a
real, direct example: a StrykeX-published trade (AEGISVOPAK, 2026-09-15) that our own
scanner's price/momentum logic would have caught (Close>high10_prior, clean RSI, positive
momentum, RS=94.4) but MIN_TRADED_VALUE alone excludes (traded_value_sma20 ~Rs.31cr vs
the Rs.100cr floor).

Reuses backtest.detect_entry()/entry_signal()/base_filters_pass() UNMODIFIED -- tests by
monkeypatching signals.MIN_TRADED_VALUE (same technique as stop_tightening_research.py),
not by reimplementing the liquidity check separately.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from live_checkpoint import _percentile_from_breaks, RSI_PCT_BREAKS, MOMENTUM_PCT_BREAKS

daily_cache = {}


def load_daily(ticker):
    if ticker not in daily_cache:
        daily_cache[ticker] = backtest.load(ticker, daily_pivots).reset_index()
    return daily_cache[ticker]


def freshness(rsi14, mom20):
    if pd.isna(rsi14) or pd.isna(mom20):
        return None
    return 0.5 * _percentile_from_breaks(rsi14, RSI_PCT_BREAKS) + 0.5 * _percentile_from_breaks(mom20, MOMENTUM_PCT_BREAKS)


def concentration(s):
    s = s.abs()
    total = s.sum()
    return s.sort_values(ascending=False).head(10).sum() / total * 100 if total else float("nan")


def scan_and_simulate(tickers):
    rows_out = []
    for t in tickers:
        df = load_daily(t)
        for i in range(len(df) - 1):
            row = df.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            candidate = backtest.detect_entry(t, df, i, require_regime=False)
            if candidate is None or candidate[0] != "breakout_cont":
                continue

            rsi14 = row.get("rsi14")
            close_20ago = row.get("close_20ago")
            mom20 = ((row.Close / close_20ago - 1) * 100) if close_20ago else None
            fscore = freshness(rsi14, mom20)

            entry_price = row.high10_prior * 1.005
            structural_low = df.iloc[max(0, i - backtest.STRUCTURAL_LOOKBACK_BC):i].Low.min() if i > 0 else entry_price * 0.9
            state = dict(entry_price=entry_price, peak_close=entry_price, peak_high=row.High,
                         structural_low=structural_low, target=None, days_held=0, atr_entry=row.atr14)
            exit_price, hold_days = None, None
            for j in range(i + 1, len(df)):
                r2 = df.iloc[j]
                if r2.corp_action_day:
                    exit_price, hold_days = state["peak_close"], state["days_held"]
                    break
                reason, state = backtest.check_exit("breakout_cont", state, r2)
                if reason is not None:
                    exit_price, hold_days = r2.Close, state["days_held"]
                    break
            if exit_price is None:
                exit_price = df.iloc[-1].Close
            swing_pnl = (exit_price / entry_price - 1) * 100

            day1_open = df.iloc[i + 1].Open
            day1_pnl = (day1_open / entry_price - 1) * 100

            rows_out.append(dict(ticker=t, entry_date=row.Date, freshness_score=fscore,
                                  swing_pnl_pct=swing_pnl, day1_pnl_pct=day1_pnl,
                                  traded_value_sma20=row.traded_value_sma20))
    return pd.DataFrame(rows_out)


def report(sub, label):
    for col, name in [("day1_pnl_pct", "options day1"), ("swing_pnl_pct", "swing")]:
        wins = sub[sub[col] > 0][col]
        wr = len(wins) / len(sub) * 100 if len(sub) else float("nan")
        exp = (wr / 100) * wins.mean() + (1 - wr / 100) * sub[sub[col] <= 0][col].mean() if len(sub) else float("nan")
        print(f"  {label:<28} {name:<12} n={len(sub):<6} win={wr:5.1f}%  med={sub[col].median():+.2f}%  "
              f"exp={exp:+.3f}%  conc={concentration(sub[col]):.1f}%")


def run():
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()

    variants = {
        "current (Rs.100cr floor)": 1_000_000_000,
        "Rs.50cr floor": 500_000_000,
        "no floor": 0,
    }

    for label, threshold in variants.items():
        signals.MIN_TRADED_VALUE = threshold
        out = scan_and_simulate(tickers)
        out.to_csv(f"runs/min_traded_value_{threshold}.csv", index=False)
        print(f"\n=== {label}: total candidates (all freshness) n={len(out)} ===")
        fresh = out.dropna(subset=["freshness_score"])
        fresh = fresh[fresh.freshness_score <= 0.40]
        report(out, "full population")
        report(fresh, "freshness<=0.40")

        added = out[out.traded_value_sma20 < 1_000_000_000]
        if len(added):
            print(f"  --> {len(added)} of these trades ONLY exist because of this lower floor (below Rs.100cr)")
            added_fresh = added.dropna(subset=["freshness_score"])
            added_fresh = added_fresh[added_fresh.freshness_score <= 0.40]
            report(added_fresh, "  just the newly-added, freshness<=0.40")


if __name__ == "__main__":
    run()
