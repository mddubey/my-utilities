"""Isolated research only (2026-09-12). Follow-up to floor_at_day1_open_research.py --
that test showed a floor resting EXACTLY at day+1's open gets touched by ordinary intraday
noise on almost every trading day (291/291), collapsing the "ride" idea back to the flat
day+1-open exit. This sweeps a real buffer BELOW the open (0.5%/1%/2%/3%) to find whether
some cushion survives normal noise while still protecting most of the gap-up gain -- and
runs it on the FULL multi-year trigger-based breakout_cont population (matching the
679/696-trade population's own scope: trigger-based entry, breakout_cont only), restricted
to fo_universe.csv since the real question is the OPTIONS-side outcome.

Touch-based stop check throughout (row.Low <= floor), not Close-based -- same fix as the
previous script, and the same reason: a real resting order fires on touch, not on the
day's close. Pure daily bars from day+1 onward (Low is already in the daily bar) -- no
intraday cache dependency, which is why this isn't limited to the 3-month intraday window.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import option_backtest
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005  # matches the live daily_scan.py convention (0.5% clearance)
BUFFER_PCTS = [0.0, 0.005, 0.01, 0.02, 0.03]


def find_trigger_fires(tickers):
    """Real historical breakout_cont trigger-based entries: Close confirms above
    high10_prior*1.005 the same day the pattern's other conditions pass. Regime gate
    ignored (same precedent as every other test this session -- gate's been shut this
    whole recent window regardless, and this is about pattern/exit mechanics not the
    regime call)."""
    fires = []
    for t in tickers:
        try:
            df = backtest.load(t, daily_pivots)
        except FileNotFoundError:
            continue
        rows = df.reset_index()
        for i in range(len(rows) - 1):
            row = rows.iloc[i]
            if row.corp_action_day:
                continue
            candidate = backtest.detect_entry(t, rows, i, require_regime=False)
            if candidate is None:
                continue
            pattern, structural_low = candidate
            if pattern != "breakout_cont":
                continue
            trigger_price = row.high10_prior * TRIGGER_CLEARANCE
            if row.Close < trigger_price:
                continue  # daily-Close-based fire, but didn't clear the real trigger band
            fires.append(dict(ticker=t, i=i, entry_date=row.Date, entry_price=trigger_price,
                              pattern=pattern))
    return fires


def simulate_ride(ticker, i, entry_price, buffer_pct):
    df = backtest.load(ticker, daily_pivots)
    rows = df.reset_index()
    day1_row = rows.iloc[i + 1]
    day1_open = day1_row.Open
    floor_level = day1_open * (1 - buffer_pct)

    state = dict(entry_price=entry_price, peak_close=day1_open, peak_high=day1_row.High,
                 structural_low=0.0, target=backtest.resistance_target(day1_open, day1_row))

    for j in range(i + 1, len(rows)):
        row = rows.iloc[j]
        if row.corp_action_day:
            prev = rows.iloc[j - 1]
            return prev.Date, state["peak_close"], "corp_action"

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

        raw_stop = backtest.current_stop_level("breakout_cont", state, row)
        effective_stop = max(raw_stop, floor_level)
        hit_stop = row.Low <= effective_stop

        if hit_stop or hit_resistance or hit_climax:
            reason = "stop_or_floor" if hit_stop else "resistance" if hit_resistance else "climax"
            exit_price = effective_stop if hit_stop else row.Close
            return row.Date, exit_price, reason

    last = rows.iloc[-1]
    return last.Date, last.Close, "open_at_end"


def run():
    fo_tickers = pd.read_csv("fo_universe.csv", header=None)[0].tolist()
    print("Finding real trigger-based breakout_cont fires (full history, fo_universe)...")
    fires = find_trigger_fires(fo_tickers)
    print(f"n fires = {len(fires)}")

    flat_trades, ride_trades = [], {b: [] for b in BUFFER_PCTS}
    for f in fires:
        df = backtest.load(f["ticker"], daily_pivots)
        rows = df.reset_index()
        i = f["i"]
        if i + 1 >= len(rows):
            continue
        day1_row = rows.iloc[i + 1]
        day1_open = day1_row.Open
        flat_trades.append(dict(ticker=f["ticker"], entry_date=f["entry_date"], exit_date=day1_row.Date,
                                entry_price=f["entry_price"], exit_price=day1_open,
                                pnl_pct=(day1_open / f["entry_price"] - 1) * 100))
        for b in BUFFER_PCTS:
            exit_date, exit_price, reason = simulate_ride(f["ticker"], i, f["entry_price"], b)
            ride_trades[b].append(dict(ticker=f["ticker"], entry_date=f["entry_date"], exit_date=exit_date,
                                       entry_price=f["entry_price"], exit_price=exit_price,
                                       pnl_pct=(exit_price / f["entry_price"] - 1) * 100, exit_reason=reason))

    flat_df = pd.DataFrame(flat_trades)
    flat_df.to_csv("runs/buffer_sweep_flat.csv", index=False)
    print(f"\n=== FLAT (sell at day1 open), n={len(flat_df)} ===")
    print(f"win {(flat_df.pnl_pct>0).mean()*100:.1f}%  median {flat_df.pnl_pct.median():.2f}%  mean {flat_df.pnl_pct.mean():.2f}%")

    for b in BUFFER_PCTS:
        rdf = pd.DataFrame(ride_trades[b])
        rdf.to_csv(f"runs/buffer_sweep_ride_{int(b*1000)}.csv", index=False)
        merged = flat_df.merge(rdf, on=["ticker", "entry_date"], suffixes=("_flat", "_ride"))
        beat = (merged.pnl_pct_ride > merged.pnl_pct_flat).mean() * 100
        print(f"\n=== RIDE buffer={b*100:.1f}%, n={len(rdf)} ===")
        print(f"win {(rdf.pnl_pct>0).mean()*100:.1f}%  median {rdf.pnl_pct.median():.2f}%  mean {rdf.pnl_pct.mean():.2f}%")
        print(f"exit_reason: {rdf.exit_reason.value_counts().to_dict()}")
        print(f"beats flat: {beat:.1f}% of trades")


if __name__ == "__main__":
    run()
