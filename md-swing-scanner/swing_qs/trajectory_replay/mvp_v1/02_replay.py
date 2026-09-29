"""QS Trajectory Replay -- Minimum Viable Replay, Step 2: Replay engine (critic-
approved spec, sections B/C). For each of the 100 sampled candidates: find the real
intraday entry touch, replay every 5-min bar through D0-D5, record the must-have
per-bar fields and events. NO exit simulation, NO replacement, NO new filters, NO
Blast/Failure labels -- pure observation data, per the approved MVP scope.

Entry price/stop use the exact same formulas validated all session (daily_pivots'
high_prior*TRIGGER_CLEARANCE, S1b = prior day's Low) -- not reimplemented.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd
import numpy as np

from backtest import load
from pivots import daily_pivots
import primed_engine as pe
from breakout_failure_confirmation_cost import _load_intraday

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
N_FORWARD_DAYS = 5  # D0 (entry day) + D1..D5
R_THRESHOLDS = [0.25, 0.5, 1.0, 2.0]


def entry_info(ticker, entry_date, lookback):
    rows = load(ticker, daily_pivots).reset_index()
    i = rows.index[rows.Date == pd.Timestamp(entry_date)]
    if len(i) == 0:
        return None
    i = i[0]
    hp = rows.High.shift(1).rolling(lookback).max().iloc[i]
    if pd.isna(hp):
        return None
    entry_price = hp * pe.TRIGGER_CLEARANCE
    initial_stop_price = rows.iloc[i - 1].Low
    initial_risk_pct = (entry_price - initial_stop_price) / entry_price * 100
    if initial_risk_pct <= 0:
        return None
    return rows, i, entry_price, initial_stop_price, initial_risk_pct


def replay_one(trade_id, ticker, entry_date, lookback):
    info = entry_info(ticker, entry_date, lookback)
    if info is None:
        return None, None
    rows, i, entry_price, initial_stop_price, initial_risk_pct = info

    idf, naive_day = _load_intraday(ticker)
    if idf is None:
        return None, None
    entry_day = pd.Timestamp(entry_date)
    day0_bars = idf[naive_day == entry_day].sort_index()
    touch = day0_bars[day0_bars.High >= entry_price]
    if len(touch) == 0:
        return None, None  # couldn't find the real intraday touch -- exclude, don't guess
    entry_ts = touch.index[0]
    entry_bar_high = day0_bars.loc[entry_ts].High

    # collect the trading-day sequence D0..D5 from daily bars (handles holidays correctly)
    day_dates = [rows.iloc[i + k].Date for k in range(0, N_FORWARD_DAYS + 1) if i + k < len(rows)]

    per_bar = []
    running_high = entry_bar_high
    first_above_entry_close = first_return_to_trigger = first_reclaim_after_return = None
    first_new_post_entry_high = None
    touched_below_since_entry = False
    r_threshold_hit = {t: None for t in R_THRESHOLDS}
    mae, mfe = 0.0, 0.0

    for day_num, d in enumerate(day_dates):
        day_bars = idf[naive_day == d].sort_index()
        if day_num == 0:
            day_bars = day_bars[day_bars.index >= entry_ts]
        if len(day_bars) == 0:
            continue  # no intraday coverage this day (e.g. late-period trade past cache end)
        for ts, bar in day_bars.iterrows():
            minutes_since_entry = (ts - entry_ts).total_seconds() / 60.0
            pct_from_entry = (bar.Close / entry_price - 1) * 100
            high_r = (bar.High / entry_price - 1) * 100 / initial_risk_pct
            low_r = (bar.Low / entry_price - 1) * 100 / initial_risk_pct
            close_r = (bar.Close / entry_price - 1) * 100 / initial_risk_pct
            mae = min(mae, low_r)
            mfe = max(mfe, high_r)

            per_bar.append(dict(
                trade_id=trade_id, timestamp=ts, day_num=day_num, Open=bar.Open, High=bar.High,
                Low=bar.Low, Close=bar.Close, Volume=bar.Volume, pct_from_entry=round(pct_from_entry, 3),
                high_r=round(high_r, 3), low_r=round(low_r, 3), close_r=round(close_r, 3),
                minutes_since_entry=round(minutes_since_entry, 1),
            ))

            for t in R_THRESHOLDS:
                if r_threshold_hit[t] is None and high_r >= t:
                    r_threshold_hit[t] = minutes_since_entry
            if bar.High > running_high:
                running_high = bar.High
                if first_new_post_entry_high is None and ts != entry_ts:
                    first_new_post_entry_high = minutes_since_entry
            if first_above_entry_close is None and bar.Close > entry_price:
                first_above_entry_close = minutes_since_entry
            if ts != entry_ts and bar.Low <= entry_price:
                touched_below_since_entry = True
                if first_return_to_trigger is None:
                    first_return_to_trigger = minutes_since_entry
            elif touched_below_since_entry and first_reclaim_after_return is None and bar.Close > entry_price:
                first_reclaim_after_return = minutes_since_entry

    if not per_bar:
        return None, None
    per_bar_df = pd.DataFrame(per_bar)

    # daily EOD descriptors, D0..D5 -- from DAILY bars (always available, unlike intraday
    # coverage near the cache's tail), so state table is complete even where per-bar isn't
    daily_state = {}
    prev_close = rows.iloc[i - 1].Close
    for day_num, d in enumerate(day_dates):
        row_d = rows.iloc[i + day_num]
        close_r = (row_d.Close / entry_price - 1) * 100 / initial_risk_pct
        daily_range_pct = (row_d.High - row_d.Low) / row_d.Open * 100 if row_d.Open else None
        daily_state[f"D{day_num}_close_r"] = round(close_r, 3)
        daily_state[f"D{day_num}_close_vs_entry_pct"] = round((row_d.Close / entry_price - 1) * 100, 3)
        daily_state[f"D{day_num}_close_vs_trigger"] = "above" if row_d.Close > entry_price else "below"
        daily_state[f"D{day_num}_close_vs_prev_close_pct"] = round((row_d.Close / prev_close - 1) * 100, 3) if prev_close else None
        daily_state[f"D{day_num}_daily_range_pct"] = round(daily_range_pct, 3) if daily_range_pct else None
        daily_state[f"D{day_num}_new_high"] = bool(row_d.High > rows.iloc[i + day_num - 1].High) if day_num > 0 else None
        prev_close = row_d.Close

    events = dict(
        trade_id=trade_id, ticker=ticker, entry_date=str(entry_date), entry_definition=lookback,
        entry_price=round(entry_price, 2), initial_stop_price=round(initial_stop_price, 2),
        initial_risk_pct=round(initial_risk_pct, 3), entry_timestamp=entry_ts,
        n_intraday_days_covered=per_bar_df.day_num.nunique(), n_days_in_window=len(day_dates),
        first_close_above_entry_min=first_above_entry_close,
        first_return_to_trigger_min=first_return_to_trigger,
        first_reclaim_after_return_min=first_reclaim_after_return,
        first_new_post_entry_high_min=first_new_post_entry_high,
        mae_r=round(mae, 3), mfe_r=round(mfe, 3),
        **{f"first_{t}R_min": r_threshold_hit[t] for t in R_THRESHOLDS},
        **daily_state,
    )
    return per_bar_df, events


if __name__ == "__main__":
    sample = pd.read_csv(f"{OUT_DIR}/sample_100.csv", parse_dates=["entry_date"])
    all_bars, all_events = [], []
    excluded = []
    for n, tr in enumerate(sample.itertuples()):
        if n % 10 == 0:
            print(f"{n}/{len(sample)}", flush=True)
        per_bar_df, events = replay_one(tr.trade_id, tr.ticker, tr.entry_date, tr.entry_definition)
        if per_bar_df is None:
            excluded.append(dict(trade_id=tr.trade_id, ticker=tr.ticker, entry_date=str(tr.entry_date.date())))
            continue
        all_bars.append(per_bar_df)
        all_events.append(events)

    bars_df = pd.concat(all_bars, ignore_index=True)
    events_df = pd.DataFrame(all_events)
    bars_df.to_csv(f"{OUT_DIR}/per_bar_trajectory.csv", index=False)
    events_df.to_csv(f"{OUT_DIR}/events.csv", index=False)
    pd.DataFrame(excluded).to_csv(f"{OUT_DIR}/excluded.csv", index=False)

    print(f"\nDone. {len(events_df)}/{len(sample)} replayed successfully, {len(excluded)} excluded "
          f"(no intraday touch found or missing data -- see excluded.csv).")
    print(f"Per-bar rows: {len(bars_df)}")
    partial_coverage = events_df[events_df.n_intraday_days_covered < events_df.n_days_in_window]
    print(f"Trades with partial intraday coverage (late-period, cache tail): {len(partial_coverage)}")
