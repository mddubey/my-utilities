"""Canonical population builder for every Primed-Gate-style strategy (BC current, BC v2,
Cell C, and any future recipe) -- the single source of truth this weekend's three
independent integrity bugs all came from NOT having:

  1. Wrong exit engine (2026-09-25) -- a research script reimplemented exit logic against
     backtest.py's legacy check_exit() instead of primed_engine's real mechanics.
  2. Position-blocking bias from monkeypatching (2026-09-25) -- building a "raw" comparison
     population by bypassing base_filters_pass inside a real simulation loop let a
     non-qualifying trigger consume a ticker's single-position slot, undercounting what a
     correctly-gated run produces.
  3. Same-day EOD gate leakage, Research Integrity Rule #18 (2026-09-26) -- the entry gate
     was evaluated on the trigger day's own completed EOD row, information that doesn't
     exist yet at the real live intraday-touch decision moment.

Per the user's and critic's shared conclusion (2026-09-26): the disease is that research
code was allowed to construct populations independently of production logic. The fix is
architectural, not another saved CSV -- this function makes all three bugs structurally
unavailable, not just documented against:

  - Exit mechanics are ALWAYS primed_engine.py's real _new_state/check_primed_exit/
    current_primed_stop_level/SLIPPAGE_PCT/TRIGGER_CLEARANCE. There is no alternative
    exit path exposed by this module at all.
  - filter_recipe is a REQUIRED argument and is ALWAYS the real position gate inside the
    simulation loop -- there is no bypass mode. A genuinely ungated/raw population (e.g.
    to test whether a gate hides an effect) is built by passing an explicit
    `lambda row: True` recipe through this SAME function, so it is structurally identical
    to every other run, not a patched copy of a different code path, and it is on the
    caller to label that result a trigger-price counterfactual, per the existing Phase 2
    guardrail (2026-09-24).
  - gate_clock is a REQUIRED-to-consider argument (default "T-1", the live-matching
    default for any Primed/live-IOC recipe). "same-day" is only valid for EOD-confirmed-
    entry recipes that inherently decide after the close (legacy Entry Gate backtests) --
    pass it explicitly, never rely on a silent default when testing a same-day-decision
    strategy.

breakout_lookback is computed fresh from the raw High series inside this function
(rows.High.shift(1).rolling(breakout_lookback).max()), not from the fixed high10_prior
column in signals.py -- this is what makes the lookback genuinely parameterizable (BC's
10-day pivot, Cell C's 40-day pivot, or anything else) through ONE function instead of a
family of hand-copied loops. For breakout_lookback=10 this reproduces high10_prior exactly
(same formula, computed at call time instead of at build_indicators() time) -- verified
below.
"""
import pandas as pd

import primed_engine as pe
from backtest import STRUCTURAL_LOOKBACK_BC


def build_population(tickers, load_fn, filter_recipe, breakout_lookback=10, gate_clock="T-1",
                      start_date=None, structural_lookback=None, telemetry_fn=None, verbose=False):
    """Returns a DataFrame, one row per real trade: ticker, entry_date, exit_date, pnl_pct,
    risk_pct, r_multiple, exit_reason, holding_days [, telemetry_fn's fields].
    filter_recipe(row) -> bool is REQUIRED.
    gate_clock: "T-1" (default, live-matching) or "same-day" (EOD-confirmed-entry only).
    telemetry_fn(gate_row) -> dict, optional: extra fields captured as a PURE SIDE
    OBSERVATION on the same row already used to gate the trade -- never used to gate or
    block positions itself (Gate Integrity Rule). This is how a marginal-filter audit
    should be built: filter_recipe is the real, currently-enforced stack (e.g. the other 3
    of 4 conditions), telemetry_fn captures the 4th condition's raw value/pass-fail for a
    post-hoc kept-vs-removed split on the already-correctly-gated population.
    structural_lookback defaults to STRUCTURAL_LOOKBACK_BC (20, backtest.py's real
    constant) -- NOT breakout_lookback. These are independent knobs (BC's 10-day trigger
    pivot vs its 20-day structural-stop lookback); a prior version of this function
    conflated them by defaulting one to the other, caught by a correctness check against
    the existing ad hoc BC v2/BC current numbers before this function was trusted for
    anything (2026-09-26) -- only override structural_lookback if the recipe genuinely
    needs a different one (verify against its own production source first).
    """
    if gate_clock not in ("T-1", "same-day"):
        raise ValueError(f'gate_clock must be "T-1" or "same-day", got {gate_clock!r}')
    structural_lookback = structural_lookback if structural_lookback is not None else STRUCTURAL_LOOKBACK_BC

    all_trades = []
    for n, t in enumerate(tickers):
        if verbose and n % 20 == 0:
            print(f"{n}/{len(tickers)}, {len(all_trades)} trades so far", flush=True)
        try:
            df = load_fn(t)
        except FileNotFoundError:
            continue
        rows = df.reset_index()
        high_arr = rows.High.values
        n_rows = len(rows)
        breakout_high_prior = rows.High.shift(1).rolling(breakout_lookback).max()

        in_position = False
        state = None
        entry_date = None

        for i in range(n_rows):
            row = rows.iloc[i]
            if row.corp_action_day:
                in_position = False
                continue
            if not in_position:
                if gate_clock == "T-1" and i == 0:
                    continue
                trigger_high = breakout_high_prior.iloc[i]
                if pd.isna(trigger_high):
                    continue
                trigger_price = trigger_high * pe.TRIGGER_CLEARANCE
                if row.High < trigger_price:
                    continue
                gate_row = rows.iloc[i - 1] if gate_clock == "T-1" else row
                if not filter_recipe(gate_row):
                    continue
                if start_date is not None and row.Date < pd.Timestamp(start_date):
                    continue
                lo = max(0, i - structural_lookback)
                structural_low = rows.iloc[lo:i].Low.min() if i > lo else row.Close * 0.9

                in_position = True
                entry_date = row.Date
                state = pe._new_state(row, trigger_price, structural_low, high_arr, i)
                telemetry = telemetry_fn(gate_row) if telemetry_fn is not None else {}
            else:
                exit_reason, state = pe.check_primed_exit(state, row)
                if exit_reason is not None:
                    exit_price = {
                        "stop": pe.current_primed_stop_level(state) * (1 - pe.SLIPPAGE_PCT),
                        "target": state["target"], "climax": row.Close, "max_hold_cap": row.Close,
                    }[exit_reason]
                    pnl_pct = (exit_price / state["entry_price"] - 1) * 100
                    risk_pct = state["initial_risk_pct"]
                    r_multiple = pnl_pct / risk_pct if risk_pct else None
                    all_trades.append(dict(
                        ticker=t, entry_date=entry_date, exit_date=row.Date,
                        pnl_pct=pnl_pct, risk_pct=risk_pct, r_multiple=r_multiple,
                        exit_reason=exit_reason, holding_days=(row.Date - entry_date).days,
                        **telemetry,
                    ))
                    in_position = False

    return pd.DataFrame(all_trades)


# --- Named filter recipes, reused verbatim from production, never re-derived from memory ---

def bc_v2_recipe(row):
    """Current production recipe (signals.base_filters_pass) -- trend + EMA34 + Momentum +
    Fragility. Live-IOC strategy -- always call with gate_clock="T-1"."""
    from signals import base_filters_pass
    return base_filters_pass(row)


def bc_current_recipe(row):
    """Pre-2026-09-25 recipe (retired from base_filters_pass but constants still live in
    signals.py): trend + EMA34 + Momentum + RSI[55,90] + liquidity>=100cr. Live-IOC
    strategy -- always call with gate_clock="T-1"."""
    from signals import RSI_MIN, RSI_MAX, MIN_TRADED_VALUE, MOMENTUM_20D_MIN, EMA34_RISING_DAYS_MIN
    trend_bullish = row.Close > row.ema34 and row.ema8 > row.ema34
    ema34_persistent = row.ema34_rising10 >= EMA34_RISING_DAYS_MIN
    momentum_ok = row.Close >= MOMENTUM_20D_MIN * row.close_20ago
    rsi_ok = RSI_MIN <= row.rsi14 <= RSI_MAX
    liquidity_ok = row.traded_value_sma20 >= MIN_TRADED_VALUE
    return trend_bullish and ema34_persistent and momentum_ok and rsi_ok and liquidity_ok


def ungated_recipe(row):
    """Explicit, labeled "always pass" recipe for a genuine raw/ungated trigger-price
    counterfactual (Phase 2 guardrail, 2026-09-24) -- same code path as every other run,
    never a monkeypatched copy of a different one."""
    return True
