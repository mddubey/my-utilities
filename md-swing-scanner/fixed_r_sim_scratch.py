import pandas as pd
from backtest import (detect_entry, current_stop_level, MAX_INITIAL_RISK_PCT,
                       CLIMAX_MIN_GAIN_PCT, CLIMAX_WEAK_CLOSE_PCT, load, daily_pivots)


def check_exit_fixed_target(pattern, state, row, fixed_target):
    state = dict(state)
    made_new_high = row.High > state["peak_high"]
    state["peak_close"] = max(state["peak_close"], row.Close)
    state["peak_high"] = max(state["peak_high"], row.High)
    day_range = row.High - row.Low
    close_pos = (row.Close - row.Low) / day_range if day_range > 0 else 1.0

    hit_target = row.Close >= fixed_target

    climax_volume = pd.notna(row.vol_max_run) and row.Volume >= row.vol_max_run
    already_extended = state["peak_close"] >= state["entry_price"] * CLIMAX_MIN_GAIN_PCT
    hit_climax = (already_extended and made_new_high and climax_volume and close_pos <= CLIMAX_WEAK_CLOSE_PCT)

    hit_stop = row.Close < current_stop_level(pattern, state, row)

    if hit_target or hit_stop or hit_climax:
        reason = "target_R" if hit_target else "climax" if hit_climax else "stop"
        return reason, state
    return None, state


def simulate_ticker_fixed_r(ticker, df, r_multiple_target=3.0, require_regime=True):
    trades = []
    in_position = False
    entry_date = pattern = None
    state = None
    fixed_target = None

    rows = df.reset_index()
    prev_row = None
    for i in range(len(rows)):
        row = rows.iloc[i]
        if row.corp_action_day:
            if in_position:
                trades.append(dict(ticker=ticker, entry_date=entry_date, exit_date=prev_row.Date,
                                    entry_price=state["entry_price"], exit_price=prev_row.Close,
                                    pnl_pct=(prev_row.Close / state["entry_price"] - 1) * 100,
                                    holding_days=(prev_row.Date - entry_date).days,
                                    exit_reason="corp_action", pattern=pattern, open_at_end=False))
                in_position = False
            prev_row = row
            continue
        if not in_position:
            candidate = detect_entry(ticker, rows, i, require_regime=require_regime)
            if candidate is not None:
                pattern_candidate, structural_low = candidate
                in_position = True
                entry_date, entry_price = row.Date, row.Close
                if pattern_candidate == "coiled_spring":
                    structural_low = max(structural_low, entry_price * (1 - MAX_INITIAL_RISK_PCT))
                pattern = pattern_candidate
                state = dict(entry_price=entry_price, peak_close=entry_price,
                             peak_high=row.High, structural_low=structural_low, target=None)
                initial_stop = current_stop_level(pattern, state, row)
                initial_risk = entry_price - initial_stop
                fixed_target = entry_price + r_multiple_target * initial_risk
        else:
            exit_reason, state = check_exit_fixed_target(pattern, state, row, fixed_target)
            if exit_reason is not None:
                trades.append(dict(ticker=ticker, entry_date=entry_date, exit_date=row.Date,
                                    entry_price=state["entry_price"], exit_price=row.Close,
                                    pnl_pct=(row.Close / state["entry_price"] - 1) * 100,
                                    holding_days=(row.Date - entry_date).days,
                                    exit_reason=exit_reason, pattern=pattern, open_at_end=False))
                in_position = False
        prev_row = row

    if in_position:
        last = rows.iloc[-1]
        trades.append(dict(ticker=ticker, entry_date=entry_date, exit_date=last.Date,
                            entry_price=state["entry_price"], exit_price=last.Close,
                            pnl_pct=(last.Close / state["entry_price"] - 1) * 100,
                            holding_days=(last.Date - entry_date).days,
                            exit_reason="still_open", pattern=pattern, open_at_end=True))
    return trades


def run_fixed_r(tickers, r_multiple_target=3.0):
    all_trades = []
    for t in tickers:
        try:
            df = load(t, daily_pivots)
        except FileNotFoundError:
            continue
        all_trades.extend(simulate_ticker_fixed_r(t, df, r_multiple_target))
    return pd.DataFrame(all_trades)
