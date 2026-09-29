"""RQ-53 gap/sustain check (2026-09-18), prompted directly by a real user loss
(LAURUSLABS, DIVISLAB): "gap up and fade means we don't get time to book the
options benefit." Two questions:

1. Does the current day+1-open exit even depend on a real gap? (Full multi-year
   population, no intraday-cache restriction needed -- daily bars only.)
2. Of the trades that DO gap up, how many actually sustain the gap for long
   enough to realistically execute an exit (10/20/30 min), vs fade back below
   the open before you could react? (Needs real 5-min day+1 data, so scoped to
   the intraday-cache window.)

See FINDINGS.md, "RQ-53 closed" (2026-09-18) for the full writeup, including the
real LAURUSLABS 2026-09-11 breach traced through this exact mechanism.
"""
import warnings
warnings.filterwarnings("ignore")

import sys

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from breakout_failure_confirmation_cost import _load_intraday, TRIGGER_CLEARANCE
from research.metrics import expectancy, win_rate


def gap_vs_no_gap(tickers, verbose=False):
    rows = []
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  {n}/{len(tickers)}", file=sys.stderr)
        try:
            daily_df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        for i in range(len(daily_df) - 1):
            row = daily_df.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            if not signals.base_filters_pass(row):
                continue
            trigger_price = row.high10_prior * TRIGGER_CLEARANCE
            if row.High < trigger_price:
                continue
            d1 = daily_df.iloc[i + 1]
            gap_pct = (d1.Open / row.Close - 1) * 100
            day0_close_pnl = (row.Close / trigger_price - 1) * 100
            day1_open_pnl = (d1.Open / trigger_price - 1) * 100
            rows.append(dict(gap_pct=gap_pct, day0_close_pnl=day0_close_pnl, day1_open_pnl=day1_open_pnl))
    df = pd.DataFrame(rows)
    print(f"\n=== 1. Gap up vs no gap (full multi-year population, n={len(df)}) ===")
    print(f"gapped up: {(df.gap_pct>0).mean()*100:.1f}%   not gapped: {(df.gap_pct<=0).mean()*100:.1f}%")
    gapped, not_gapped = df[df.gap_pct > 0], df[df.gap_pct <= 0]
    print(f"GAPPED UP  (n={len(gapped)}): day0_close exp={expectancy(gapped.day0_close_pnl):+.3f}% win={win_rate(gapped.day0_close_pnl):.1f}%  |  "
          f"day1_open exp={expectancy(gapped.day1_open_pnl):+.3f}% win={win_rate(gapped.day1_open_pnl):.1f}%")
    print(f"NOT GAPPED (n={len(not_gapped)}): day0_close exp={expectancy(not_gapped.day0_close_pnl):+.3f}% win={win_rate(not_gapped.day0_close_pnl):.1f}%  |  "
          f"day1_open exp={expectancy(not_gapped.day1_open_pnl):+.3f}% win={win_rate(not_gapped.day1_open_pnl):.1f}%")
    return df


def sustain_check(tickers, verbose=False):
    rows = []
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  {n}/{len(tickers)}", file=sys.stderr)
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
            if i + 1 >= len(daily_df):
                continue
            d1_date = pd.Timestamp(daily_df.iloc[i + 1].Date).normalize()
            if d1_date not in intraday_dates:
                continue
            d1_bars = intraday_df[naive_day == d1_date].reset_index(drop=True)
            if len(d1_bars) < 7:
                continue
            gap_pct = (d1_bars.Open.iloc[0] / row.Close - 1) * 100
            if gap_pct <= 0:
                continue
            d1_open = d1_bars.Open.iloc[0]
            theoretical_open_pct = (d1_open / trigger_price - 1) * 100
            closes_pct = (d1_bars.Close / trigger_price - 1) * 100
            lows = d1_bars.Low
            rows.append(dict(
                theoretical_open_pct=theoretical_open_pct,
                sustained_2=(lows.iloc[:2] >= d1_open).all(),
                sustained_4=(lows.iloc[:4] >= d1_open).all(),
                sustained_6=(lows.iloc[:6] >= d1_open).all(),
                price_at_2=closes_pct.iloc[1], price_at_4=closes_pct.iloc[3], price_at_6=closes_pct.iloc[5],
            ))
    df = pd.DataFrame(rows)
    print(f"\n=== 2. Gap-sustain check across reaction windows (n={len(df)} real gap-up trades) ===")
    for bars, mins, sustain_col, price_col in [(2, 10, "sustained_2", "price_at_2"),
                                                 (4, 20, "sustained_4", "price_at_4"),
                                                 (6, 30, "sustained_6", "price_at_6")]:
        faded, sustained = df[~df[sustain_col]], df[df[sustain_col]]
        print(f"\n{mins}-min window: sustained {df[sustain_col].mean()*100:.1f}% / faded {(~df[sustain_col]).mean()*100:.1f}%")
        print(f"  FADED (n={len(faded)}):     theoretical={expectancy(faded.theoretical_open_pct):+.3f}%  "
              f"realistic@{mins}min={expectancy(faded[price_col]):+.3f}%  "
              f"give_back={expectancy(faded.theoretical_open_pct)-expectancy(faded[price_col]):+.3f}pp")
        print(f"  SUSTAINED (n={len(sustained)}): theoretical={expectancy(sustained.theoretical_open_pct):+.3f}%  "
              f"realistic@{mins}min={expectancy(sustained[price_col]):+.3f}%  "
              f"give_back={expectancy(sustained.theoretical_open_pct)-expectancy(sustained[price_col]):+.3f}pp")
    return df


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    gap_vs_no_gap(tickers, verbose=True)
    sustain_check(tickers, verbose=True)
