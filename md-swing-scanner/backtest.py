from pathlib import Path

import numpy as np
import pandas as pd

from signals import build_indicators, entry_signal, breakout_continuation
from pivots import daily_pivots
from market_regime import market_trending
from vcp import stage2_trend_template, vcp_breakout

CACHE_DIR = Path(__file__).parent / "data_cache"
TEST_ADX_RISING = False  # tested True (2026-08-30): halved the sample (69->33), win rate and median
                          # pnl both got WORSE for both patterns, concentration blew past 100%
                          # (75.3%->113.1%) — rejected, reverted to the plain threshold (v18 baseline)
TEST_ADX_UPTREND = False  # tested True (2026-08-30): REJECTED. Cut the sample 37% (403->252),
                           # concentration got worse (36.5%->50.3%), median barely moved (2.06%->
                           # 2.11%) — and it specifically failed to fix the thing it was built for:
                           # of 32 trades in the Dec'24-May'25 VCP losing patch, only 14 got filtered
                           # out, and the remaining 18 were still bad (38.9% win, -5.72% median,
                           # actually worse than the original -4.91%). Many of those losses happened
                           # even as Nifty was recovering, not just declining — the patch looks like
                           # an ordinary bad stretch, not a trend-direction problem. `+DI`/`-DI` stay
                           # available in market_regime.py (real signal, just not this fix) in case
                           # they're useful for something else later.
# Nifty-above-its-own-200-day-SMA ADOPTED permanently (2026-08-30, `require_above_sma200=True`
# below) — a slower, structural "is the broad market actually in good shape" gauge, the
# better-specified version of the "don't go long against the tape" idea that the reactive
# +DI/-DI test (TEST_ADX_UPTREND above) tried and failed at. Real, validated win on the full
# 5-year dataset: sample cut only 18% (403->332, vs the DI test's 37%), concentration
# *improved* (36.5%->34.6%), overall median improved (2.06%->2.24%), and it specifically cut
# the Dec'24-May'25 VCP losing patch from 32 trades (34.4% win, -4.91% median) to 12 (50.0%
# win, -1.80% median) — more than half the bad trades gone, the rest meaningfully less bad.
# Both patterns improved (breakout_cont mean 1.66%->2.07%, VCP median 1.80%->2.29%), no
# per-pattern tradeoff worth a split this time (unlike the moving-target test).
# tested restricting the moving target to VCP only (2026-08-30): edged out the uniform
# version on every metric (median 2.86%->3.13%, win rate 78.3%->79.7%) but the margin was
# small on n=69 and not worth the added complexity of one more per-pattern special case —
# kept the simpler uniform version (applies to both patterns, see below) per explicit
# user instruction to only keep an added wrinkle if it's clearly significant.
CORP_ACTION_MOVE_PCT = 0.35  # single-day |close-to-close| move this large is a demerger/split/bonus
                              # event, not a real trading move — verified directly (2026-08-30, VEDL
                              # 2026-04-30: -64.9% in one day, identical in both raw and yfinance
                              # auto_adjust=True data, ruling out a stale-adjustment bug). On a real
                              # demerger record date the parent's price cut is largely offset by new
                              # shares in the spun-off entity landing in the same account — data we
                              # don't have — so crediting/blaming the strategy for that day's "return"
                              # is simply wrong, not bad luck. Trades spanning such a day are
                              # right-censored (see simulate_ticker) rather than left in as-is.
ATR_TRAIL_MULT = 3.0         # Breakout Continuation's base stop pre-engagement (see TRAIL_ENGAGE_PCT
                              # below — it tightens onto the 21-EMA once working, same as VCP) —
                              # published Chandelier Exit standard is 3x ATR on a 22-day lookback;
                              # testing at the sourced value in place of our earlier ad-hoc 2.0
MAX_INITIAL_RISK_PCT = 0.08  # Coiled Spring/VCP only — Minervini's published hard-cap stop
TRAIL_ENGAGE_PCT = 1.03      # Both patterns (2026-08-30, was VCP-only) — give a normal pivot retest
                              # room before trailing tightens onto the 21-EMA
CLIMAX_VOL_LOOKBACK = 20     # "heaviest volume of the run" — Wyckoff buying-climax / O'Neil exhaustion
CLIMAX_WEAK_CLOSE_PCT = 0.30 # close in the bottom 30% of the day's range — symmetric with the existing
                              # CLOSE_NEAR_HIGH_PCT=0.70 entry filter (signals.py), not a new arbitrary number
CLIMAX_MIN_GAIN_PCT = 1.15   # bug found by direct inspection (2026-08-30): without this gate, the
                              # ENTRY bar itself (or the day right after) routinely satisfies "fresh
                              # high + heaviest volume in 20d" by construction — that's what the entry
                              # filter selects for, not a climax. Cut UNIONBANK from a 132-day/+21.75%
                              # winner (v16) down to -3.2% after 2 days (v17). A "climax run" is
                              # specifically a large move over a SHORT period late in a trend (per
                              # sourced research) — must already be well up from entry first.
# Both patterns, applies on top of the normal stop/trail/resistance exits: a fresh high for the
# move, made on the heaviest volume of the whole trade, that closes weak instead of near the high,
# is the textbook professional-distribution signature — real technicality, not a day-count guess.
# Coiled Spring/VCP no longer has a fixed day-count cap: checked directly (2026-08-30) —
# real VCP practice (Minervini) holds a working breakout for weeks to months, not a fixed
# few days; failure shows up structurally (price falls back below the pivot/base), not on
# a calendar. The 3-day cap was inherited from the old, much looser 5-day-window spec and
# didn't belong here once the entry became a real multi-week base.


def _finish_load(df, pivot_fn):
    df = build_indicators(df)
    df = df.join(pivot_fn(df))
    df["corp_action_day"] = df.Close.pct_change().abs() > CORP_ACTION_MOVE_PCT
    df["vol_max_run"] = df.Volume.rolling(CLIMAX_VOL_LOOKBACK).max()  # today's own volume included —
                                                                       # "is today the heaviest in the window"
    return df


def load(ticker, pivot_fn=daily_pivots):
    """pivot_fn defaults to daily_pivots, not weekly_pivots (2026-08-31, v27) — a
    weekly resistance ladder is fixed Mon-Fri and can be fully used up by a single
    big-range day (real case: CGPOWER hit its entire week's R2 on day one, then had
    zero room the rest of the week), whereas a daily-recomputed ladder stays in
    lockstep with the stock's actual pace. Clean re-test on the same v25 entries:
    win 58.3%->61.8%, median +1.64%->+2.83%, concentration 30.7%->22.6%,
    resistance-exit share 47.9%->59.2%. weekly_pivots is kept in pivots.py (still
    tested) but no longer wired in anywhere in this file or the live-use scripts."""
    df = pd.read_csv(CACHE_DIR / f"{ticker}.csv", index_col="Date", parse_dates=True)
    return _finish_load(df, pivot_fn)


def load_with_extra_row(ticker, extra_row, pivot_fn=daily_pivots):
    """Like load(), but appends one synthetic OHLCV row in-memory before computing
    indicators — for daily_scan.py's --live mode (2026-08-30): a partial-day intraday
    bar (extra_row: dict with Date/Open/High/Low/Close/Volume) run through the EXACT
    same build_indicators()/pivot_fn() as any real cached day, so vol_zscore/ema/rsi/etc
    are computed identically, not a special partial-day formula. If extra_row's date is
    already <= the last cached date (today's real close already landed), this is a
    no-op — falls back to the real cached data, nothing synthetic to add."""
    raw = pd.read_csv(CACHE_DIR / f"{ticker}.csv", index_col="Date", parse_dates=True)
    date = pd.Timestamp(extra_row["Date"])
    if len(raw) and date <= raw.index.max():
        df = raw
    else:
        new_row = pd.DataFrame([{
            "Open": extra_row["Open"], "High": extra_row["High"], "Low": extra_row["Low"],
            "Close": extra_row["Close"], "Adj Close": extra_row["Close"], "Volume": extra_row["Volume"],
        }], index=pd.Index([date], name="Date"))
        df = pd.concat([raw, new_row])
    return _finish_load(df, pivot_fn)


def resistance_target(entry_price, row):
    for level in (row.pp, row.r1, row.r2):
        if pd.notna(level) and level > entry_price:
            return level
    return None


def support_level(entry_price, row):
    for level in (row.pp, row.s1, row.s2):
        if pd.notna(level) and level < entry_price:
            return level
    return None


def detect_entry(ticker, rows, i, require_regime=True):
    """Two fully independent entry gates, checked in this order only because
    entry_signal() is cheap and VCP's trend-template + zigzag scan is not; first match
    wins (a ticker can't be both on the same day). Returns (pattern, structural_low) if
    a candidate fires at rows.iloc[i], else None — structural_low is raw/uncapped, only
    meaningful for coiled_spring (caller applies the MAX_INITIAL_RISK_PCT cap at actual
    entry time, since it needs the real entry_price to do that).

    Pulled out of simulate_ticker's loop (2026-08-30) so a live daily scanner can call
    the EXACT same entry logic against today's data instead of duplicating it — two
    copies of "what counts as a signal" drifting apart over time is a real risk for a
    tool meant to inform real trades.

    require_regime=False (2026-08-30) skips the Nifty regime gate below entirely, for
    daily_scan.py's observation-only mode during a regime drought (see its own
    --ignore-regime flag) — lets a real pattern breakout still surface for watching,
    without implying it's a validated signal to trade. The backtest itself (run()/
    simulate_ticker()) never passes False here — the validated v25 numbers assume the
    gate is on, so this only ever changes daily_scan.py's live output, not any
    backtested result."""
    row = rows.iloc[i]
    if entry_signal(row):
        # regime gate, Breakout Continuation only originally, now both patterns:
        # verified directly that this pattern's edge is real but concentrated outside
        # choppy markets (52% win rate / +0.25% median when Nifty ADX<20, vs 71-73% /
        # ~+2% otherwise).
        if not require_regime or market_trending(row.Date, require_rising=TEST_ADX_RISING, require_uptrend=TEST_ADX_UPTREND, require_above_sma200=True):
            return "breakout_cont", None
        return None
    if stage2_trend_template(row, ticker, row.Date) and (not require_regime or market_trending(row.Date, require_rising=TEST_ADX_RISING, require_uptrend=TEST_ADX_UPTREND, require_above_sma200=True)):
        # VCP is explicitly a bull-market pattern in the original methodology, not a
        # regime-agnostic one — same regime gate that rescued Breakout Continuation.
        vcp = vcp_breakout(rows, i)
        if vcp is not None:
            return "coiled_spring", vcp[1]
    return None


def current_stop_level(pattern, state, row):
    """The actual stop PRICE for `state`/`row` right now — same computation check_exit
    uses internally to decide hit_stop, exposed separately so a live position-monitor
    can report "move your SL to X" without re-deriving the logic by hand.

    Both patterns now share ONE mechanism (2026-08-30): a pattern-specific base stop,
    which tightens to the 21-EMA once the trade is up TRAIL_ENGAGE_PCT — previously
    only Coiled Spring/VCP had this second stage, Breakout Continuation trailed at a
    flat 3xATR for the whole hold no matter how extended (giving back the same % of
    any move, small or huge). The base stop itself still differs per pattern on
    purpose — VCP's is the real structural base low, Breakout Continuation's is the
    ATR chandelier — that's each pattern's actual entry logic, not incidental
    variation to remove."""
    base_stop = (state["structural_low"] if pattern == "coiled_spring"
                 else state["peak_close"] - ATR_TRAIL_MULT * row.atr14)
    if state["peak_close"] >= state["entry_price"] * TRAIL_ENGAGE_PCT:
        return max(base_stop, row.ema21)
    return base_stop


def check_exit(pattern, state, row, use_resistance=True):
    """Given a currently-open position's `state` (dict: entry_price, peak_close,
    peak_high, structural_low, target) and today's `row`, returns (exit_reason_or_None,
    updated_state) — a pure function, no side effects, so both the historical backtest
    loop and a live daily position-monitor share the exact same exit logic without risk
    of the two quietly drifting apart (pulled out of simulate_ticker 2026-08-30, same
    reason as detect_entry above).

    Exit rule for BOTH patterns: a hard structural stop, then an ATR trail (Breakout
    Continuation) or 21-EMA trail (VCP, published Minervini practice) once the trade is
    working — no fixed day-count cap for either, VCP holds a working breakout for weeks
    to months per the real methodology, failure shows up structurally not on a calendar.
    Plus a moving resistance target (refreshed to the current week's nearest pivot above
    price each day, ratchets up only) and a gated climax-top exit (fresh high on the
    heaviest volume of the run, closing weak — Wyckoff/O'Neil exhaustion signature, only
    evaluated once the position is already up >=CLIMAX_MIN_GAIN_PCT to avoid firing on
    the entry bar's own qualifying volume spike)."""
    state = dict(state)
    made_new_high = row.High > state["peak_high"]  # before updating — "did TODAY set a fresh high"
    state["peak_close"] = max(state["peak_close"], row.Close)
    state["peak_high"] = max(state["peak_high"], row.High)
    day_range = row.High - row.Low
    close_pos = (row.Close - row.Low) / day_range if day_range > 0 else 1.0

    if use_resistance:
        fresh_target = resistance_target(row.Close, row)
        if fresh_target is not None:
            state["target"] = fresh_target if state["target"] is None else max(state["target"], fresh_target)
    hit_resistance = state["target"] is not None and row.Close >= state["target"]

    climax_volume = pd.notna(row.vol_max_run) and row.Volume >= row.vol_max_run
    already_extended = state["peak_close"] >= state["entry_price"] * CLIMAX_MIN_GAIN_PCT
    hit_climax = (already_extended and made_new_high and climax_volume
                  and close_pos <= CLIMAX_WEAK_CLOSE_PCT)

    hit_stop = row.Close < current_stop_level(pattern, state, row)

    if hit_resistance or hit_stop or hit_climax:
        reason = "resistance" if hit_resistance else "climax" if hit_climax else "stop"
        return reason, state
    return None, state


def simulate_ticker(ticker, df, use_resistance, min_rr=0.0, require_regime=True):
    """Pure stock-level swing test — no options mechanics at all. Whether a real
    front-month contract exists, and when it would expire, is a separate downstream
    question (option_backtest.py), deliberately not asked here: mixing "is the option
    tradeable" into "is the stock signal any good" made it impossible to see the raw
    swing edge on its own (checked directly, 2026-08-30 — v12's numbers had both a
    contract-availability filter on entry and an expiry-driven forced exit baked in).

    require_regime=False (2026-08-31): threads through to detect_entry() to disable the
    Nifty regime gate for BOTH patterns in this run — used for the gate-isolation
    experiment (is the SMA200 gate pulling its weight for Breakout Continuation too, or
    only VCP). Default True preserves the exact v25 behavior for the real backtest."""
    trades = []
    in_position = False
    entry_date = pattern = None
    state = None

    rows = df.reset_index()
    prev_row = None
    for i in range(len(rows)):
        row = rows.iloc[i]
        if row.corp_action_day:
            if in_position:
                # right-censor: close out at the last known-good price, don't credit
                # or blame the strategy for an unmodeled corporate-action-day "return"
                trades.append(dict(
                    ticker=ticker, entry_date=entry_date, exit_date=prev_row.Date,
                    entry_price=state["entry_price"], exit_price=prev_row.Close,
                    pnl_pct=(prev_row.Close / state["entry_price"] - 1) * 100,
                    holding_days=(prev_row.Date - entry_date).days,
                    exit_reason="corp_action", pattern=pattern,
                    open_at_end=False,
                ))
                in_position = False
            prev_row = row
            continue  # don't evaluate a fresh entry off a corrupted day either
        if not in_position:
            candidate = detect_entry(ticker, rows, i, require_regime=require_regime)
            if candidate is not None:
                pattern_candidate, structural_low = candidate
                target = resistance_target(row.Close, row) if use_resistance else None
                if min_rr > 0:
                    support = support_level(row.Close, row)
                    risk = row.Close - support if support is not None else None
                    reward = target - row.Close if target is not None else None
                    if not risk or not reward or reward / risk < min_rr:
                        continue  # reward:risk doesn't clear the bar (or support/resistance undefined) — skip
                in_position = True
                entry_date, entry_price = row.Date, row.Close
                if pattern_candidate == "coiled_spring":
                    # Minervini's actual stop is TWO checks, not one — structural (below
                    # the base) capped at a hard 7-8% max risk.
                    structural_low = max(structural_low, entry_price * (1 - MAX_INITIAL_RISK_PCT))
                pattern = pattern_candidate
                state = dict(entry_price=entry_price, peak_close=entry_price,
                              peak_high=row.High, structural_low=structural_low, target=target)
        else:
            exit_reason, state = check_exit(pattern, state, row, use_resistance=use_resistance)
            if exit_reason is not None:
                trades.append(dict(
                    ticker=ticker, entry_date=entry_date, exit_date=row.Date,
                    entry_price=state["entry_price"], exit_price=row.Close,
                    pnl_pct=(row.Close / state["entry_price"] - 1) * 100,
                    holding_days=(row.Date - entry_date).days,
                    exit_reason=exit_reason, pattern=pattern,
                    open_at_end=False,
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
            exit_reason="open", pattern=pattern,
            open_at_end=True,
        ))
    return trades


def max_drawdown(returns_pct):
    equity = (1 + pd.Series(returns_pct) / 100).cumprod()
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return dd.min() * 100


def summarize(trades_df, label):
    corp_action = trades_df[trades_df.get("exit_reason") == "corp_action"] if "exit_reason" in trades_df else trades_df.iloc[0:0]
    # excluded from every stat below — a right-censored trade isn't a real win or
    # loss, it's a data gap (see CORP_ACTION_MOVE_PCT)
    closed = trades_df[(~trades_df.open_at_end) & (trades_df.get("exit_reason") != "corp_action")]
    wins = closed[closed.pnl_pct > 0]
    losses = closed[closed.pnl_pct <= 0]
    win_rate = len(wins) / len(closed) * 100 if len(closed) else float("nan")
    avg_win = wins.pnl_pct.mean() if len(wins) else 0
    avg_loss = losses.pnl_pct.mean() if len(losses) else 0
    expectancy = (win_rate / 100) * avg_win + (1 - win_rate / 100) * avg_loss
    ordered = closed.sort_values("exit_date")
    dd = max_drawdown(ordered.pnl_pct) if len(ordered) else float("nan")

    print(f"\n=== {label} ===")
    print(f"closed trades      : {len(closed)}  ({len(trades_df) - len(closed) - len(corp_action)} still open at data end, "
          f"{len(corp_action)} excluded as unmodeled corp actions)")
    print(f"win rate           : {win_rate:.1f}%")
    print(f"avg win / avg loss : {avg_win:.2f}% / {avg_loss:.2f}%")
    print(f"expectancy/trade   : {expectancy:.2f}%")
    print(f"avg holding days   : {closed.holding_days.mean():.1f}")
    print(f"sequential max DD  : {dd:.1f}%  (compounding trades in exit-date order, NOT a real concurrent-position portfolio curve)")
    if "exit_reason" in closed:
        print(f"exit via resistance: {(closed.exit_reason == 'resistance').sum()}  |  "
              f"exit via stop: {(closed.exit_reason == 'stop').sum()}  |  "
              f"exit via climax: {(closed.exit_reason == 'climax').sum()}")
    if "pattern" in closed:
        print(closed.groupby("pattern").apply(lambda g: pd.Series({
            "n": len(g), "win_rate": (g.pnl_pct > 0).mean() * 100,
            "median_pnl": g.pnl_pct.median(), "mean_pnl": g.pnl_pct.mean(),
            "avg_hold": g.holding_days.mean(),
        })))


def run(tickers, use_resistance, pivot_fn=daily_pivots, min_rr=0.0, require_regime=True):
    all_trades = []
    for t in tickers:
        try:
            df = load(t, pivot_fn)
        except FileNotFoundError:
            continue
        all_trades.extend(simulate_ticker(t, df, use_resistance, min_rr, require_regime))
    return pd.DataFrame(all_trades)


if __name__ == "__main__":
    # NIFTY 500 (500 tickers) — ADOPTED (2026-08-30) as the pure-swing universe, a strict
    # superset of fo_universe.csv's 210 F&O-eligible names. See relative_strength.py's
    # UNIVERSE_FILE comment for the full before/after numbers. fo_universe.csv stays the
    # right list ONLY for the options-specific layer (option_backtest.py/portfolio.py),
    # which is hard-constrained to names that actually have options.
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    trades = run(tickers, True, daily_pivots, 0.0)
    trades.to_csv("runs/trades_v28.csv", index=False)
    summarize(trades, "v28: v27 (daily pivots + vcp.LAST_LEG_TOLERANCE=0.40 + "
                       "signals.VOL_ZSCORE_WINDOW=8, n 677->924, win 58.3%->62.9%, median "
                       "+1.64%->+2.90%, concentration 30.7%->16.1%) + signals.RSI_MAX=80 (was 68 "
                       "— Breakout Continuation's own RSI ceiling, swept in isolation this time, "
                       "not inferred from VCP's data, see signals.py's own comment for the full "
                       "sweep/verification). Combined: n 924->1430, win 62.9%->65.0%, median "
                       "+2.90%->+2.89% (flat), concentration 16.1%->10.3%. Caveat: part of the "
                       "win-rate/concentration gain here is a mix-shift artifact, not new edge — "
                       "Breakout Cont's own win rate (67.9%) and VCP's own (61.7%) barely moved "
                       "from their isolated-test values, but Breakout Cont's share of the pool "
                       "roughly tripled, pulling the blended average toward the stronger pattern; "
                       "concentration also partly benefits from the same bigger-n dilution effect "
                       "already flagged for v27's own headline number. Drought-only trades still 0 "
                       "— orthogonal to the regime-gate drought, a detection-quality fix only.")
