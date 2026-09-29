"""RQ-53 corrected window (2026-09-18): after a real user challenge ("did you run
that on the right place?"), this is everything re-tested against the ACTUAL
decision the trade faces -- entered at the breach (day 0), currently exits at
day+1's OPEN. Every variant here asks "does exiting early, sometime during day 0
itself, beat just holding to day+1's open" -- not day+1's own session (a
different, later window, mistakenly tested first and corrected here).

Uses the same real intraday cache / base_filters_pass population as
breakout_failure_confirmation_cost.py. Three things tested:
  1. MAE-anytime stop-loss (fires whenever day-0's remaining path touches a
     drawdown level below trigger, realistic resting-stop fill) vs hold-to-day+1-open.
  2. Volume+displacement gating (from breakout_failure_volume_displacement.py) vs
     the same correct baseline.
  3. Winner/loser MAE separation + the mean-reversion-from-extreme mechanism check
     (why a resting stop at any fixed drawdown backfires: the trades that touch it
     average a BETTER price by day+1 open than the threshold itself).

All three: REJECTED. Nothing beats the current day+1-open exit. See FINDINGS.md,
"RQ-53 closed" (2026-09-18) for the full writeup and numbers.
"""
import warnings
warnings.filterwarnings("ignore")

import sys

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from breakout_failure_confirmation_cost import _load_intraday, simulate_day1, TRIGGER_CLEARANCE
from daily_scan import _fo_tickers
from research.metrics import expectancy, win_rate, concentration_v2


def gather(tickers, fo_only, verbose=False):
    fo = _fo_tickers() if fo_only else None
    rows = []
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  {n}/{len(tickers)}", file=sys.stderr)
        if fo_only and t not in fo:
            continue
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
            if row.corp_action_day or pd.isna(row.high10_prior) or pd.isna(row.atr14):
                continue
            date_norm = pd.Timestamp(row.Date).normalize()
            if date_norm not in intraday_dates:
                continue
            if not signals.base_filters_pass(row):
                continue
            trigger_price = row.high10_prior * TRIGGER_CLEARANCE
            day_bars = intraday_df[naive_day == date_norm].reset_index(drop=True)
            if day_bars.empty or day_bars.High.max() < trigger_price:
                continue
            if i + 1 >= len(daily_df):
                continue
            day1_open_pnl = simulate_day1(daily_df, i, trigger_price)
            if day1_open_pnl is None:
                continue

            breach_idx = day_bars.High.ge(trigger_price).idxmax()
            after_breach = day_bars.iloc[breach_idx:]
            mae_pct = ((after_breach.Low / trigger_price - 1) * 100).min()

            sig_bar = None
            threshold_05 = trigger_price * (1 - 0.005)
            for k in range(breach_idx, len(day_bars)):
                if day_bars.Close.iloc[k] < threshold_05:
                    sig_bar = k
                    break
            vol_ratio = body_atr = immediate_exit_pnl = None
            if sig_bar is not None:
                sb = day_bars.iloc[sig_bar]
                prior_bars = day_bars.iloc[max(0, sig_bar - 3):sig_bar]
                pvm = prior_bars.Volume.mean() if len(prior_bars) and prior_bars.Volume.mean() > 0 else None
                vol_ratio = (sb.Volume / pvm) if pvm else None
                body_atr = abs(sb.Close - sb.Open) / row.atr14
                immediate_exit_pnl = (sb.Close / trigger_price - 1) * 100

            rows.append(dict(ticker=t, mae_pct=mae_pct, day1_open_pnl=day1_open_pnl,
                              vol_ratio=vol_ratio, body_atr=body_atr, immediate_exit_pnl=immediate_exit_pnl))
    return pd.DataFrame(rows)


def mae_stop_test(df):
    print("\n=== 1. MAE-anytime stop-loss vs hold-to-day+1-open (F&O-scoped) ===")
    print("stop     n_fired    rule_exp    rule_win   base_exp   base_win   improvement   rule_conc")
    for th in [-0.3, -0.5, -0.7, -1.0, -1.25, -1.5, -2.0]:
        touched = df.mae_pct <= th
        rule_pnl = pd.Series(th, index=df.index).where(touched, df.day1_open_pnl)
        print(f"{th:+.2f}%   {touched.sum():>4}/{len(df)}   {expectancy(rule_pnl):+.3f}%   {win_rate(rule_pnl):5.1f}%   "
              f"{expectancy(df.day1_open_pnl):+.3f}%   {win_rate(df.day1_open_pnl):5.1f}%   "
              f"{expectancy(rule_pnl)-expectancy(df.day1_open_pnl):+.3f}pp   {concentration_v2(rule_pnl):5.1f}%")


def vol_displacement_test(df):
    d = df.dropna(subset=["vol_ratio", "body_atr"])
    vol_med, body_med = d.vol_ratio.median(), d.body_atr.median()
    gate = (d.vol_ratio >= vol_med) & (d.body_atr >= body_med)
    rule_pnl = d.immediate_exit_pnl.where(gate, d.day1_open_pnl)
    print(f"\n=== 2. Volume+displacement-gated same-day exit vs hold-to-day+1-open (F&O-scoped, n={len(d)}) ===")
    print(f"baseline (hold to day+1 open)          exp={expectancy(d.day1_open_pnl):+.3f}%  win={win_rate(d.day1_open_pnl):.1f}%")
    print(f"vol+displacement-gated same-day exit   exp={expectancy(rule_pnl):+.3f}%  win={win_rate(rule_pnl):.1f}%  (fires {gate.sum()}/{len(d)})")


def winner_loser_mechanism(df_full):
    winners = df_full[df_full.day1_open_pnl > 0]
    losers = df_full[df_full.day1_open_pnl <= 0]
    print(f"\n=== 3. Winner/loser MAE separation is REAL, but acting on it backfires (full universe, n={len(df_full)}) ===")
    print(f"winners median MAE: {winners.mae_pct.median():+.3f}%   losers median MAE: {losers.mae_pct.median():+.3f}%")
    print("\nWhy a resting stop at any threshold underperforms -- trades that touch it recover on average by day+1 open:")
    for th in [-0.75, -1.0, -1.5, -2.0, -2.5]:
        cross = df_full[df_full.mae_pct <= th]
        print(f"  threshold {th:+.2f}%: n={len(cross):>4}  mean day1_open_pnl of crossers={expectancy(cross.day1_open_pnl):+.3f}%  "
              f"(vs the threshold itself, {th:+.2f}% -- cutting here would be worse than holding)")


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    print("Gathering F&O-scoped population...", file=sys.stderr)
    df_fo = gather(tickers, fo_only=True, verbose=True)
    mae_stop_test(df_fo)
    vol_displacement_test(df_fo)

    print("\nGathering full-universe population for the mechanism check...", file=sys.stderr)
    df_full = gather(tickers, fo_only=False, verbose=True)
    winner_loser_mechanism(df_full)
