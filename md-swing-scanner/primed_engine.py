"""Primed Gate execution engine (2026-09-20) — the settled Breakout Continuation
architecture from this weekend's research, promoted from scratchpad scripts into a real,
reusable module so backtest and live share the exact same functions (same reason
backtest.py's detect_entry_eod()/check_exit() were pulled out of simulate_ticker's loop).

Deliberately separate from backtest.py, not a modification of it: per the 2026-09-20
governance decision ("Primed Gate is canonical for research going forward; detect_entry_eod()/
Entry Gate is legacy-only... retained only for legacy comparisons and regression testing"),
backtest.py's own detect_entry_eod()/check_exit()/current_stop_level()/resistance_target() stay
exactly as they are (legacy Entry Gate + VCP/coiled_spring, both untouched, both still
covered by the existing test suite). This module implements ONLY the Breakout Continuation
leg, on the mechanism this weekend actually validated:

  - Entry: base_filters_pass() (signals.py) + a REAL intraday trigger-band touch
    (row.High >= high10_prior * TRIGGER_CLEARANCE), not close-based confirmation. No Nifty
    regime gate — matches daily_scan.py's own _passes_primed_checks() convention and every
    research script this weekend; the regime gate is an Entry-Gate-only addition.
  - Stop: structural_low (lowest Low over STRUCTURAL_LOOKBACK_BC days before entry), ATR0 —
    no ATR buffer subtracted (RQ-69/ATR-distance-audit finding, 2026-09-20).
  - Target: ZigZag (scipy find_peaks over prior swing highs, real detected peaks only) with
    an R_FLOOR=1.0 invariant — a target below 1x the trade's own initial risk is treated as
    non-actionable (falls back to stop/trail/max-hold), since it can otherwise book the trade
    before the profit-protection trail ever gets a chance to operate (target-floor bug,
    2026-09-20, real example: CEMPRO 2026-04-30).
  - Trail (post-engagement, TRAIL_ENGAGE_PCT=1.08 from backtest.py): K=2 confirmed swing-low
    floor, not SMA21 — validated as a real, non-fragile alternative this weekend (RQ-73A
    final-base investigation).
  - MAX_HOLD_DAYS, climax exit, corp-action right-censoring: unchanged, reused directly from
    backtest.py — these are population-invariant mechanics this weekend's research never
    touched, no reason to reimplement them differently here.
"""
import numpy as np
import pandas as pd
from scipy.signal import find_peaks

from backtest import (CLIMAX_MIN_GAIN_PCT, CLIMAX_WEAK_CLOSE_PCT, CORP_ACTION_MOVE_PCT,
                       MAX_HOLD_DAYS, STRUCTURAL_LOOKBACK_BC, TRAIL_ENGAGE_PCT)
from signals import base_filters_pass

TRIGGER_CLEARANCE = 1.005    # real intraday touch, 0.5% above the prior 10-day high — sits in
                              # the middle of live_checkpoint.py's own TRIGGER_CLEARANCE_LOW/HIGH
                              # (0.3%-0.6%) real fill-price band, already checked robust across it
SLIPPAGE_PCT = 0.005         # applied only on a stop exit (a forced sale, not a chosen one)
K_SWING = 2                  # swing-low trail: a low counts as confirmed once K bars on both
                              # sides are not lower than it
ZZ_LOOKBACK = 300            # target search window: how far back to look for a prior swing high
ZZ_BACKSTEP = 3              # scipy find_peaks distance param
ZZ_PROMINENCE_LOG = np.log(1.05)  # scipy find_peaks prominence, in log-price space
ATR_BUFFER = 0.0             # ATR0 — settled 2026-09-20, see module docstring
R_FLOOR = 1.0                # target-floor invariant, in units of the trade's own initial risk


def find_zigzag_target(high_arr, entry_idx, entry_price):
    """Nearest real prior swing high (scipy-detected peak) above entry_price, searched over
    the ZZ_LOOKBACK days strictly before entry_idx. None if no such peak exists — the trade
    falls back to stop/trail/max-hold with no target, exactly as if none were computed."""
    lo = max(0, entry_idx - ZZ_LOOKBACK)
    window = high_arr[lo:entry_idx]
    if len(window) < 2 * ZZ_BACKSTEP + 1:
        return None
    peaks, _ = find_peaks(np.log(window), distance=ZZ_BACKSTEP, prominence=ZZ_PROMINENCE_LOG)
    for p in reversed(peaks):
        val = window[p]
        if val > entry_price:
            return val
    return None


def detect_primed_entry(ticker, rows, i):
    """Returns (trigger_price, structural_low) if a Primed Gate breach fires at rows.iloc[i],
    else None. trigger_price IS the entry price — real intraday execution at the trigger
    touch, not row.Close. Caller is responsible for skipping corp_action_day rows same as
    backtest.detect_entry_eod()'s callers already do."""
    row = rows.iloc[i]
    if pd.isna(row.high10_prior):
        return None
    trigger_price = row.high10_prior * TRIGGER_CLEARANCE
    if row.High < trigger_price:
        return None
    if not base_filters_pass(row):
        return None
    lo = max(0, i - STRUCTURAL_LOOKBACK_BC)
    structural_low = rows.iloc[lo:i].Low.min() if i > lo else row.Close * 0.9
    return trigger_price, structural_low


def _new_state(row, trigger_price, structural_low, high_arr, entry_idx):
    zz_target = find_zigzag_target(high_arr, entry_idx, trigger_price)
    initial_risk_pct = (trigger_price - structural_low) / trigger_price * 100
    if zz_target is not None and initial_risk_pct > 0:
        target_r = (zz_target - trigger_price) / trigger_price * 100 / initial_risk_pct
        if target_r < R_FLOOR:
            zz_target = None  # target-floor invariant — non-actionable, falls back to normal exits
    return dict(
        entry_price=trigger_price, peak_close=trigger_price, peak_high=row.High, min_low=row.Low,
        structural_low=structural_low, target=zz_target, days_held=0,
        swing_low_floor=None, low_history=[], ever_engaged=False,
        initial_risk_pct=initial_risk_pct,
    )


def current_primed_stop_level(state):
    """The actual stop PRICE right now, for a live position monitor to report "move your SL
    to X" — mirrors backtest.current_stop_level()'s role for the legacy engine. ATR0, so the
    pre-engagement base stop is simply structural_low (no buffer subtracted)."""
    base_stop = state["structural_low"]
    if state["ever_engaged"] and state["swing_low_floor"] is not None:
        return max(base_stop, state["swing_low_floor"])
    return base_stop


def check_primed_exit(state, row):
    """Pure function, no side effects — (exit_reason_or_None, updated_state). Mirrors
    backtest.check_exit()'s contract exactly, so both a backtest loop and a live position
    monitor share one implementation. state["days_held"] must be initialized to 0 by the
    caller at entry; incremented once per call here, same convention as check_exit()."""
    state = dict(state)
    state["days_held"] += 1
    made_new_high = row.High > state["peak_high"]
    state["peak_close"] = max(state["peak_close"], row.Close)
    state["peak_high"] = max(state["peak_high"], row.High)
    state["min_low"] = min(state["min_low"], row.Low)
    day_range = row.High - row.Low
    close_pos = (row.Close - row.Low) / day_range if day_range > 0 else 1.0

    # K=2 swing-low trail bookkeeping — a low becomes a confirmed swing low once K bars on
    # both sides are not lower than it (needs 2K+1 bars of history to evaluate the midpoint)
    state["low_history"].append(row.Low)
    hist = state["low_history"]
    if len(hist) >= 2 * K_SWING + 1:
        idx2 = len(hist) - 1 - K_SWING
        window2 = hist[max(0, idx2 - K_SWING):idx2 + K_SWING + 1]
        if hist[idx2] == min(window2):
            cur_floor = state["swing_low_floor"]
            state["swing_low_floor"] = hist[idx2] if cur_floor is None else max(cur_floor, hist[idx2])

    hit_target = state["target"] is not None and row.High >= state["target"]
    engaged = state["peak_close"] >= state["entry_price"] * TRAIL_ENGAGE_PCT
    if engaged:
        state["ever_engaged"] = True
    stop_level = current_primed_stop_level(state)
    hit_stop = row.Low <= stop_level

    already_extended = state["peak_close"] >= state["entry_price"] * CLIMAX_MIN_GAIN_PCT
    hit_climax = (already_extended and made_new_high
                  and (row.Volume >= row.vol_max_run if pd.notna(row.vol_max_run) else False)
                  and close_pos <= CLIMAX_WEAK_CLOSE_PCT)
    hit_max_hold = state["days_held"] >= MAX_HOLD_DAYS

    if hit_stop:
        return "stop", state
    if hit_climax:
        return "climax", state
    if hit_target:
        return "target", state
    if hit_max_hold:
        return "max_hold_cap", state
    return None, state


def simulate_primed_ticker(ticker, df):
    """One ticker's full Primed Gate trade history — mirrors backtest.simulate_ticker()'s
    shape/contract (list of trade dicts) so it slots into the same summarize()/reporting
    tooling. Single position at a time per ticker, same as the legacy engine."""
    trades = []
    in_position = False
    state = None
    entry_date = None
    exit_price_fn = None  # set per-exit below

    rows = df.reset_index()
    high_arr = rows.High.values
    prev_row = None
    for i in range(len(rows)):
        row = rows.iloc[i]
        if row.corp_action_day:
            if in_position:
                trades.append(dict(
                    ticker=ticker, entry_date=entry_date, exit_date=prev_row.Date,
                    entry_price=state["entry_price"], exit_price=prev_row.Close,
                    pnl_pct=(prev_row.Close / state["entry_price"] - 1) * 100,
                    holding_days=(prev_row.Date - entry_date).days,
                    exit_reason="corp_action", pattern="primed_bc", open_at_end=False,
                ))
                in_position = False
            prev_row = row
            continue
        if not in_position:
            candidate = detect_primed_entry(ticker, rows, i)
            if candidate is not None:
                trigger_price, structural_low = candidate
                in_position = True
                entry_date = row.Date
                state = _new_state(row, trigger_price, structural_low, high_arr, i)
        else:
            exit_reason, state = check_primed_exit(state, row)
            if exit_reason is not None:
                exit_price = {
                    "stop": current_primed_stop_level(state) * (1 - SLIPPAGE_PCT),
                    "target": state["target"],
                    "climax": row.Close,
                    "max_hold_cap": row.Close,
                }[exit_reason]
                trades.append(dict(
                    ticker=ticker, entry_date=entry_date, exit_date=row.Date,
                    entry_price=state["entry_price"], exit_price=exit_price,
                    pnl_pct=(exit_price / state["entry_price"] - 1) * 100,
                    holding_days=(row.Date - entry_date).days,
                    exit_reason=exit_reason, pattern="primed_bc", open_at_end=False,
                ))
                in_position = False
        prev_row = row

    if in_position:
        last = rows.iloc[-1]
        trades.append(dict(
            ticker=ticker, entry_date=entry_date, exit_date=last.Date,
            entry_price=state["entry_price"], exit_price=last.Close,
            pnl_pct=(last.Close / state["entry_price"] - 1) * 100,
            holding_days=(last.Date - entry_date).days,
            exit_reason="still_open", pattern="primed_bc", open_at_end=True,
        ))
    return trades


RQ95_CARRY_THRESHOLD_PCT = -1.16  # EOD overnight-option-carry gate (2026-09-20, RQ-90->RQ-95
                                    # arc, critic-promoted candidate): if the stock's own close
                                    # sits below this % relative to the entry trigger by end of
                                    # entry day, exiting the OPTION at close beats carrying it
                                    # overnight to day+1's open, on real option-premium economics
                                    # (net exit value +590.5 at this cut, positive and stable
                                    # across a -0.75% to -3% neighborhood, all 5 calendar years
                                    # 2022-2026 independently, both chronological halves, and not
                                    # a 2023 artifact -- see FINDINGS.md). This checks the STOCK's
                                    # close only -- it says nothing about the swing/stock position,
                                    # which is unaffected; it is advisory for the separate options
                                    # decision, not wired to any stock exit. Check this between
                                    # 2:45-3:15 PM IST specifically (not later) -- the weak-breach
                                    # population this rule targets already carries lower volume
                                    # all session (RQ-90C), so option liquidity is likely to thin
                                    # further right into the close; a materially safer, more liquid
                                    # execution window is worth more than the extra few minutes of
                                    # closing-price precision. RQ-96 (an intraday version of this
                                    # check, evaluated as soon as the stock crosses the threshold
                                    # rather than waiting for EOD) is explicitly NOT implemented --
                                    # parked, blocked on real intraday option data, see FINDINGS.md.


def overnight_carry_recommendation(entry_price, today_close):
    """Only meaningful on the entry day itself (see RQ95_CARRY_THRESHOLD_PCT) -- caller is
    responsible for only surfacing this for a position whose entry_date is today. Returns
    (recommendation_str, close_vs_trigger_pct)."""
    close_vs_trigger_pct = (today_close / entry_price - 1) * 100
    if close_vs_trigger_pct < RQ95_CARRY_THRESHOLD_PCT:
        return "EXIT OPTION AT EOD — do not carry overnight", close_vs_trigger_pct
    return "carry overnight as normal", close_vs_trigger_pct


def run_primed(tickers, load_fn):
    """load_fn: backtest.load, injected rather than imported to avoid this module needing
    pivots.daily_pivots wired in twice — caller passes the same loader used elsewhere."""
    all_trades = []
    for t in tickers:
        try:
            df = load_fn(t)
        except FileNotFoundError:
            continue
        all_trades.extend(simulate_primed_ticker(t, df))
    return pd.DataFrame(all_trades)
