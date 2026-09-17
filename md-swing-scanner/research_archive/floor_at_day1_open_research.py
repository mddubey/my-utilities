"""Isolated research only (2026-09-12). Real question: instead of selling flat at day+1's
open (the already-validated 82% win / +5.03% median ATM rule), what if day+1's OPEN PRICE
itself becomes a hard floor -- you don't sell there, you keep holding, and the worst case
is you eventually get stopped out AT that floor (preserving the gap-up gain), never below
it, until the position's own normal trail/target/climax mechanism naturally overtakes the
floor and takes over. Reuses the real 291-event fireset from overnight_sl_realism_check.py
(runs/overnight_sl_realism.csv) for entry/day1-open, then walks forward using this
project's OWN real check_exit() pieces (resistance target, climax, ATR/EMA21 trail) with
one addition: the effective stop is max(the organic trailing stop, day1's open price) until
the organic trail naturally climbs past it.

Methodology note on exit price: on the day the FLOOR itself is what's binding (organic
trail hasn't grown past day1's open yet), exit_price is modeled as day1's open (a resting
stop-order sitting exactly there would fill there, not at that day's close) -- an
optimistic-but-reasonable assumption, no slippage modeled. Once the organic trail has
grown past the floor, reverts to this project's existing daily-bar convention (exit at
Close), same as everywhere else in this codebase.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots


def simulate_floor_from_day1(ticker, pattern, entry_price, day1_date):
    df = backtest.load(ticker, daily_pivots)
    rows = df.reset_index()
    match = rows.index[rows.Date == day1_date]
    if len(match) == 0:
        return None
    i = match[0]
    day1_row = rows.iloc[i]
    day1_open = day1_row.Open

    state = dict(entry_price=entry_price, peak_close=day1_open, peak_high=day1_row.High,
                 structural_low=0.0, target=backtest.resistance_target(day1_open, day1_row))

    for j in range(i, len(rows)):
        row = rows.iloc[j]
        if row.corp_action_day:
            prev = rows.iloc[j - 1] if j > i else day1_row
            return dict(exit_date=prev.Date, exit_price=state["peak_close"],
                        exit_reason="corp_action", days_held=j - i)

        made_new_high = row.High > state["peak_high"]
        state["peak_close"] = max(state["peak_close"], row.Close)
        state["peak_high"] = max(state["peak_high"], row.High)
        day_range = row.High - row.Low
        close_pos = (row.Close - row.Low) / day_range if day_range > 0 else 1.0

        fresh_target = backtest.resistance_target(row.Close, row)
        if fresh_target is not None:
            state["target"] = fresh_target if state["target"] is None else max(state["target"], fresh_target)
        hit_resistance = state["target"] is not None and row.Close >= state["target"]

        climax_volume = pd.notna(row.vol_max_run) and row.Volume >= row.vol_max_run
        already_extended = state["peak_close"] >= state["entry_price"] * backtest.CLIMAX_MIN_GAIN_PCT
        hit_climax = (already_extended and made_new_high and climax_volume
                      and close_pos <= backtest.CLIMAX_WEAK_CLOSE_PCT)

        raw_stop = backtest.current_stop_level(pattern, state, row)
        floor_binding = raw_stop < day1_open
        effective_stop = day1_open if floor_binding else raw_stop
        # TOUCH-based, not Close-based: a real resting stop order fires the moment
        # intraday price reaches it, recovery-by-the-close or not. Checked directly
        # against the user's own "assume it always gets hit" instruction -- Low is
        # already in the daily bar, no extra intraday data needed for this fix.
        hit_stop = row.Low <= effective_stop

        if hit_stop or hit_resistance or hit_climax:
            reason = "floor_or_trail_stop" if hit_stop else "resistance" if hit_resistance else "climax"
            exit_price = effective_stop if hit_stop else row.Close
            return dict(exit_date=row.Date, exit_price=exit_price, exit_reason=reason, days_held=j - i + 1)

    last = rows.iloc[-1]
    return dict(exit_date=last.Date, exit_price=last.Close, exit_reason="open_at_end", days_held=len(rows) - 1 - i + 1)


def run():
    base = pd.read_csv("runs/overnight_sl_realism.csv", parse_dates=["entry_date"])
    results = []
    for _, r in base.iterrows():
        day1_row_lookup = backtest.load(r.ticker, daily_pivots).reset_index()
        idx = day1_row_lookup.index[day1_row_lookup.Date > r.entry_date]
        if len(idx) == 0:
            continue
        day1_date = day1_row_lookup.iloc[idx[0]].Date

        floored = simulate_floor_from_day1(r.ticker, r.pattern, r.entry_price, day1_date)
        if floored is None:
            continue
        flat_pnl = (r.exit_price / r.entry_price - 1) * 100  # the already-known day1-open-exit result
        floor_pnl = (floored["exit_price"] / r.entry_price - 1) * 100
        results.append(dict(
            ticker=r.ticker, entry_date=r.entry_date, pattern=r.pattern,
            entry_price=r.entry_price, day1_open=r.exit_price,
            flat_pnl_pct=flat_pnl, floor_pnl_pct=floor_pnl,
            floor_exit_reason=floored["exit_reason"], floor_days_held=floored["days_held"],
            gap_up_at_open=r.exit_price > r.entry_price,
        ))

    out = pd.DataFrame(results)
    out.to_csv("runs/floor_at_day1_open.csv", index=False)

    print(f"n = {len(out)}")
    print()
    print("=== ALL (regardless of whether day1 open was itself profitable) ===")
    print(f"flat (sell at day1 open):  win {  (out.flat_pnl_pct>0).mean()*100:.1f}%  median {out.flat_pnl_pct.median():.2f}%  mean {out.flat_pnl_pct.mean():.2f}%")
    print(f"floor (ride, floor=open): win {(out.floor_pnl_pct>0).mean()*100:.1f}%  median {out.floor_pnl_pct.median():.2f}%  mean {out.floor_pnl_pct.mean():.2f}%")
    print(f"floor exit_reason breakdown:\n{out.floor_exit_reason.value_counts()}")
    print(f"median days held under floor strategy: {out.floor_days_held.median()}")
    print(f"floor strictly beat flat: {(out.floor_pnl_pct > out.flat_pnl_pct).mean()*100:.1f}% of trades")
    print(f"floor strictly worse than flat: {(out.floor_pnl_pct < out.flat_pnl_pct).mean()*100:.1f}% of trades")
    print(f"floor exactly == flat (floor day itself): {(out.floor_pnl_pct == out.flat_pnl_pct).mean()*100:.1f}% of trades")

    sub = out[out.gap_up_at_open]
    print(f"\n=== Only trades already profitable at day1 open (n={len(sub)}) ===")
    print(f"flat:  win {(sub.flat_pnl_pct>0).mean()*100:.1f}%  median {sub.flat_pnl_pct.median():.2f}%  mean {sub.flat_pnl_pct.mean():.2f}%")
    print(f"floor: win {(sub.floor_pnl_pct>0).mean()*100:.1f}%  median {sub.floor_pnl_pct.median():.2f}%  mean {sub.floor_pnl_pct.mean():.2f}%")
    print(f"floor strictly beat flat: {(sub.floor_pnl_pct > sub.flat_pnl_pct).mean()*100:.1f}% of trades")


if __name__ == "__main__":
    run()
