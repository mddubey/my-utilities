"""RQ-53 pre-check (2026-09-18): before building the "Breakout Failure Exit" rule,
quantify the same cost that already killed the symmetric ENTRY-side idea (RQ-37 /
2026-09-13 acceptance-delay finding: waiting to observe a signal costs you the exact
move that made the signal observable -- median 0.44-0.90% of the stock, "even one 5-min
bar of delay costs more than it buys").

Direct user question: does the same mechanism apply on the EXIT side? If we require
2 consecutive 5-min closes below trigger*(1-0.5%) before exiting (the critic's proposed
Breakout Failure Exit condition), how much further does price fall DURING that ~10-min
confirmation wait, vs exiting immediately on the first signal bar? And does the
confirmation window ever save us from a false alarm (price recovers back above the
band during the wait)?

Uses the REAL 5-min intraday cache (intraday_cache/, ~69 trading days,
2026-06-10..2026-09-16) -- not the daily-OHLC proxy used elsewhere for the larger
multi-year populations, because this question is specifically about intraday
minute-to-minute path, which daily bars cannot answer. Same base_filters_pass() +
trigger-cross gate as base_filters_threshold_sweep.py/live_equivalent_population.py
(TRIGGER_CLEARANCE=1.005), so this is the real live-equivalent breach population,
just restricted to the window where 5-min data actually exists.
"""
import warnings
warnings.filterwarnings("ignore")

import sys
from pathlib import Path

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from daily_scan import _fo_tickers
from research.metrics import win_rate, expectancy

TRIGGER_CLEARANCE = 1.005
SIGNAL_DROP = 0.005      # critic's proposed FAILURE_THRESHOLD: close back below trigger by >=0.5%
CONFIRM_BARS = 2          # 2 consecutive 5-min closes below FAILURE_THRESHOLD before "confirmed"

INTRADAY_CACHE_DIR = Path(__file__).parent / "intraday_cache"


def _load_intraday(ticker):
    path = INTRADAY_CACHE_DIR / f"{ticker}.csv"
    if not path.exists():
        return None, None
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    if df.empty:
        return None, None
    df.index = df.index.tz_convert("Asia/Kolkata")
    naive_day = df.index.tz_localize(None).normalize()
    return df, naive_day


def simulate_swing(daily_df, i, trigger_price):
    row = daily_df.iloc[i]
    lo = max(0, i - backtest.STRUCTURAL_LOOKBACK_BC)
    structural_low = daily_df.iloc[lo:i].Low.min() if i > lo else trigger_price * 0.9
    state = dict(entry_price=trigger_price, peak_close=trigger_price, peak_high=row.High,
                 structural_low=structural_low, target=None, days_held=0, atr_entry=row.atr14)
    for j in range(i + 1, len(daily_df)):
        r2 = daily_df.iloc[j]
        if r2.corp_action_day:
            return (state["peak_close"] / trigger_price - 1) * 100
        reason, state = backtest.check_exit("breakout_cont", state, r2)
        if reason is not None:
            return (r2.Close / trigger_price - 1) * 100
    return (daily_df.iloc[-1].Close / trigger_price - 1) * 100


def simulate_day1(daily_df, i, trigger_price):
    if i + 1 >= len(daily_df):
        return None
    return (daily_df.iloc[i + 1].Open / trigger_price - 1) * 100


def run(tickers, verbose=False):
    n_breaches = 0
    n_signals = 0
    n_unconfirmable = 0   # day ended before we could check 2 more bars
    confirmed = []        # dicts: immediate_price, confirmed_price, slippage_pct, swing_pnl, day1_pnl
    reversed_ = []         # signal fired but price recovered above FAILURE_THRESHOLD within the confirm window

    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  {n}/{len(tickers)} tickers, {n_breaches} breaches, {len(confirmed)} confirmed so far", file=sys.stderr)
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
            n_breaches += 1

            breach_idx = day_bars.High.reset_index(drop=True).ge(trigger_price).idxmax()
            closes = day_bars.Close.reset_index(drop=True)
            FAILURE_THRESHOLD = trigger_price * (1 - SIGNAL_DROP)

            signal_idx = None
            for k in range(breach_idx, len(closes)):
                if closes.iloc[k] < FAILURE_THRESHOLD:
                    signal_idx = k
                    break
            if signal_idx is None:
                continue
            n_signals += 1

            remaining = closes.iloc[signal_idx + 1: signal_idx + 1 + CONFIRM_BARS]
            if len(remaining) < CONFIRM_BARS:
                n_unconfirmable += 1
                continue

            immediate_price = closes.iloc[signal_idx]
            if (remaining < FAILURE_THRESHOLD).all():
                confirmed_price = remaining.iloc[-1]
                slippage_pct = (immediate_price - confirmed_price) / trigger_price * 100
                confirmed.append(dict(
                    ticker=t, date=row.Date,
                    slippage_pct=slippage_pct,
                    immediate_exit_pnl=(immediate_price / trigger_price - 1) * 100,
                    confirmed_exit_pnl=(confirmed_price / trigger_price - 1) * 100,
                    swing_pnl=simulate_swing(daily_df, i, trigger_price),
                    day1_pnl=simulate_day1(daily_df, i, trigger_price),
                ))
            else:
                reversed_.append(dict(
                    ticker=t, date=row.Date,
                    immediate_exit_pnl=(immediate_price / trigger_price - 1) * 100,
                ))

    print(f"\nReal breaches in intraday-cache window: {n_breaches}")
    print(f"Signal fires (close < FAILURE_THRESHOLD, trigger-{SIGNAL_DROP*100:.1f}% same day): {n_signals}")
    print(f"  -- unconfirmable (day ended before {CONFIRM_BARS} more bars): {n_unconfirmable}")
    print(f"  -- reversed during confirm window (price back >= FAILURE_THRESHOLD within {CONFIRM_BARS} bars): {len(reversed_)}")
    print(f"  -- confirmed (stayed below FAILURE_THRESHOLD for {CONFIRM_BARS} consecutive bars): {len(confirmed)}")

    if not confirmed:
        print("\nNo confirmed signals -- cannot quantify confirmation cost.")
        return

    cdf = pd.DataFrame(confirmed)
    print(f"\nConfirmation-wait cost (price given up during the {CONFIRM_BARS}-bar / "
          f"~{CONFIRM_BARS*5}-min wait, as % of entry price):")
    print(f"  median {cdf.slippage_pct.median():+.3f}%   mean {cdf.slippage_pct.mean():+.3f}%   "
          f"min {cdf.slippage_pct.min():+.3f}%   max {cdf.slippage_pct.max():+.3f}%")
    pct_further_drop = (cdf.slippage_pct > 0).mean() * 100
    print(f"  price kept falling during the wait in {pct_further_drop:.1f}% of confirmed cases")

    swing = cdf.swing_pnl.dropna()
    day1 = cdf.day1_pnl.dropna()
    print(f"\nBaseline outcome (current production exit, NO early exit at all) for these "
          f"same {len(confirmed)} trades -- confirms whether the rule targets real bad trades:")
    print(f"  SWING  n={len(swing):<4} win={win_rate(swing):5.1f}%  exp={expectancy(swing):+.3f}%")
    if len(day1):
        print(f"  OPT(d+1) n={len(day1):<4} win={win_rate(day1):5.1f}%  exp={expectancy(day1):+.3f}%")

    imm = cdf.immediate_exit_pnl
    conf = cdf.confirmed_exit_pnl
    print(f"\nDirect three-way comparison on this same {len(confirmed)}-trade population "
          f"(all real losers-in-progress by construction -- this is exactly the population "
          f"an exit rule would fire on):")
    print(f"  exit immediately at signal   exp={expectancy(imm):+.3f}%  (cuts loss earliest, no wait)")
    print(f"  exit after 2-bar confirm     exp={expectancy(conf):+.3f}%  (waits ~10 min, {pct_further_drop:.0f}% of the time it costs you)")
    print(f"  hold to current full exit    exp={expectancy(swing):+.3f}%  (today's baseline, no early exit)")

    rev_swing = pd.Series(dtype=float)
    rev_imm = pd.Series(dtype=float)
    if reversed_:
        rdf = pd.DataFrame(reversed_)
        print(f"\n{len(rdf)} signals reversed (recovered above FAILURE_THRESHOLD) during the confirm "
              f"window -- these are exactly what waiting is meant to protect against "
              f"(an immediate-exit rule would have cut all of these; a confirmed rule "
              f"would have held them). Whether that's worth the slippage above depends "
              f"on what THEIR baseline outcome looks like too:")
        rev_swing_list, rev_day1_list = [], []
        for r in reversed_:
            t, date = r["ticker"], r["date"]
            daily_df = backtest.load(t, daily_pivots).reset_index()
            i = daily_df.index[daily_df.Date == date]
            if len(i):
                row = daily_df.iloc[i[0]]
                trigger_price = row.high10_prior * TRIGGER_CLEARANCE
                rev_swing_list.append(simulate_swing(daily_df, i[0], trigger_price))
                rev_day1_list.append(simulate_day1(daily_df, i[0], trigger_price))
            else:
                rev_swing_list.append(None)
                rev_day1_list.append(None)
        rdf["swing_pnl"] = rev_swing_list
        rdf["day1_pnl"] = rev_day1_list
        rev_swing = rdf.swing_pnl.dropna()
        rev_imm = rdf.immediate_exit_pnl
        print(f"  reversed-group SWING (hold, no early exit) n={len(rev_swing)} win={win_rate(rev_swing):5.1f}% exp={expectancy(rev_swing):+.3f}%")
        print(f"  reversed-group would-have-been-cut-immediately exp={expectancy(rev_imm):+.3f}%  "
              f"(the cost an immediate-always rule pays on false alarms)")

    print(f"\nPortfolio-level answer -- all {n_signals} signal fires blended, the number that "
          f"actually matters for deciding which policy to run live:")
    all_hold = pd.concat([swing, rev_swing])
    all_immediate = pd.concat([imm, rev_imm])
    all_confirmed = pd.concat([conf, rev_swing])  # confirmed policy never touches the reversed group -- they ride to full exit
    print(f"  do nothing (current baseline)   exp={expectancy(all_hold):+.3f}%  n={len(all_hold)}")
    print(f"  exit immediately, no confirm    exp={expectancy(all_immediate):+.3f}%  n={len(all_immediate)}")
    print(f"  exit only after 2-bar confirm   exp={expectancy(all_confirmed):+.3f}%  n={len(all_confirmed)}")

    fo = _fo_tickers()
    cdf_fo = cdf[cdf.ticker.isin(fo)]
    rdf_fo = rdf[rdf.ticker.isin(fo)] if reversed_ else pd.DataFrame(columns=["day1_pnl", "immediate_exit_pnl"])
    print(f"\nOPTIONS-side version (F&O-scoped subset, day+1-open convention as 'do nothing' -- "
          f"same stock-move proxy this project always uses for the options number, since "
          f"'exit immediately'/'exit after confirm' both mean a same-day options exit instead "
          f"of holding to day+1 open):")
    print(f"  F&O-scoped signal fires: {len(cdf_fo) + len(rdf_fo)} of {len(cdf) + len(rdf if reversed_ else pd.DataFrame())}")

    day1_confirmed = cdf_fo.day1_pnl.dropna()
    day1_reversed = rdf_fo.day1_pnl.dropna() if reversed_ else pd.Series(dtype=float)
    imm_fo = pd.concat([cdf_fo.immediate_exit_pnl, rdf_fo.immediate_exit_pnl]) if reversed_ else cdf_fo.immediate_exit_pnl
    confirmed_fo = pd.concat([cdf_fo.confirmed_exit_pnl, day1_reversed])
    hold_fo = pd.concat([day1_confirmed, day1_reversed])

    print(f"  do nothing (day+1 open, current)   exp={expectancy(hold_fo):+.3f}%  win={win_rate(hold_fo):5.1f}%  n={len(hold_fo)}")
    print(f"  exit immediately, no confirm        exp={expectancy(imm_fo):+.3f}%  win={win_rate(imm_fo):5.1f}%  n={len(imm_fo)}")
    print(f"  exit only after 2-bar confirm        exp={expectancy(confirmed_fo):+.3f}%  win={win_rate(confirmed_fo):5.1f}%  n={len(confirmed_fo)}")

    cdf.to_csv("breakout_failure_confirmation_cost.csv", index=False)
    print("\nRaw confirmed-signal dataset saved to breakout_failure_confirmation_cost.csv")


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    run(tickers, verbose=True)
