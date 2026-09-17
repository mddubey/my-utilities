"""Isolated research only (2026-09-13). Compares three entry-timing options against the
REAL swing/stock exit mechanism (check_exit -- resistance/stop/climax, multi-day), not the
options day+1 metric: (A) day0 raw trigger (immediate), (B) day0 streak-confirmed price
(~15-25 min delay, real entry price), (C) day1's open (the very original "wait for close,
enter next day" idea). Same population, same exit logic, only the entry point differs.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import intraday_cache
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005
STREAK_THRESHOLD = 3


def simulate_swing(rows, entry_i, entry_price):
    state = dict(entry_price=entry_price, peak_close=entry_price, peak_high=entry_price,
                 structural_low=0.0, target=None)
    for j in range(entry_i + 1, len(rows)):
        row = rows.iloc[j]
        if row.corp_action_day:
            prev = rows.iloc[j - 1]
            return dict(exit_price=state["peak_close"], exit_reason="corp_action",
                       holding_days=j - entry_i, open_at_end=False)
        exit_reason, state = backtest.check_exit("breakout_cont", state, row, use_resistance=True)
        if exit_reason is not None:
            return dict(exit_price=row.Close, exit_reason=exit_reason,
                       holding_days=j - entry_i, open_at_end=False)
    last = rows.iloc[-1]
    return dict(exit_price=last.Close, exit_reason="open", holding_days=len(rows) - 1 - entry_i, open_at_end=True)


def first_acceptance(day_bars, trigger, threshold):
    streak = 0
    for close in day_bars.Close:
        if close > trigger:
            streak += 1
            if streak >= threshold:
                return close
        else:
            streak = 0
    return None


def run():
    pool = pd.read_csv("runs/vwap_and_timeofday_check.csv", parse_dates=["entry_date"])
    cache = {}
    results = []
    for _, r in pool.iterrows():
        if r.ticker not in cache:
            cache[r.ticker] = (backtest.load(r.ticker, daily_pivots).reset_index(),
                               intraday_cache.load(r.ticker))
        rows, intraday = cache[r.ticker]
        match = rows.index[rows.Date == r.entry_date]
        if len(match) == 0 or match[0] + 1 >= len(rows):
            continue
        i = match[0]
        trigger = rows.iloc[i].high10_prior * TRIGGER_CLEARANCE

        idx = intraday.index.tz_convert("Asia/Kolkata").tz_localize(None)
        day_bars = intraday.set_axis(idx)[idx.normalize() == r.entry_date]
        if day_bars.empty:
            continue
        streak_price = first_acceptance(day_bars, trigger, STREAK_THRESHOLD)
        if streak_price is None:
            continue  # only compare on trades where all three entry options are actually available

        day1_open = rows.iloc[i + 1].Open

        out_A = simulate_swing(rows, i, trigger)
        out_B = simulate_swing(rows, i, streak_price)
        out_C = simulate_swing(rows, i + 1, day1_open)  # entry day becomes i+1 (day1), check starts day2

        results.append(dict(
            ticker=r.ticker, entry_date=r.entry_date,
            A_entry=trigger, A_pnl=(out_A["exit_price"]/trigger-1)*100, A_days=out_A["holding_days"], A_open=out_A["open_at_end"],
            B_entry=streak_price, B_pnl=(out_B["exit_price"]/streak_price-1)*100, B_days=out_B["holding_days"], B_open=out_B["open_at_end"],
            C_entry=day1_open, C_pnl=(out_C["exit_price"]/day1_open-1)*100, C_days=out_C["holding_days"], C_open=out_C["open_at_end"],
        ))

    out = pd.DataFrame(results)
    out.to_csv("runs/swing_entry_timing_compare.csv", index=False)
    print(f"n = {len(out)} (only trades where all three entry options exist)")
    for label in ["A", "B", "C"]:
        closed = out[~out[f"{label}_open"]]
        win = (closed[f"{label}_pnl"] > 0).mean() * 100
        med = closed[f"{label}_pnl"].median()
        days = closed[f"{label}_days"].median()
        names = {"A": "day0 raw trigger (immediate)", "B": f"day0 streak-confirmed (>={STREAK_THRESHOLD})", "C": "day1 open (wait for close)"}
        print(f"  {names[label]}: n={len(closed)} ({out[f'{label}_open'].sum()} open)  win {win:.1f}%  median {med:.2f}%  median hold {days:.0f}d")


if __name__ == "__main__":
    run()
