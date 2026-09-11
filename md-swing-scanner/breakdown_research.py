"""Phase R1 -- Breakdown Continuation research (2026-09-11), the critic's recommended
smallest first step for the bearish-mirror discussion (critic_update_23.md / response-20).

PAPER-ONLY, ISOLATED research branch. Does NOT modify or import from daily_scan.py,
live_checkpoint.py, trader_dashboard.py, backtest.py's detect_entry/check_exit, or
signals.py's own breakout_continuation()/base_filters_pass()/entry_signal() -- v30
production stays completely frozen, per the critic's explicit instruction ("do not
change: trader dashboard, daily scanner, ranking, exits, regime gate"). Only reuses
signals.py's pure, direction-agnostic math helpers (ema/rsi/atr/reject_theta_trap).

Scope, deliberately narrow, exactly as recommended:
  - Breakdown Continuation ONLY -- the mirror of breakout_cont. No bearish VCP/topping
    pattern: the critic flagged this as the biggest architectural warning in the whole
    discussion -- bullish VCP is built around ACCUMULATION (contracting pullbacks,
    shrinking volatility), a real distribution/topping top has the OPPOSITE geometry
    (expanding volatility, false breakouts, failed rallies) -- the zigzag-leg logic's
    core assumptions break entirely for that case. Separate future project, not this one.
  - Same NIFTY 500 universe. NO new regime gate. Ordinary corrections inside an overall
    bull market are real, valid downside-continuation training examples on their own --
    requiring Nifty below its 200-SMA as a prerequisite would throw away almost every
    usable example (the critic's point: market regime controls EXPOSURE, breakdown
    pattern detects the SETUP -- these should not be tightly coupled).
  - No new exit invented -- just the direct chandelier-stop mirror, nothing else
    (no target/climax mirror, no parameter sweep). The critic explicitly flagged this
    exit as UNVERIFIED, not assumed-correct: ATR expands exactly when downside
    volatility increases, which could keep a losing short open through violent
    rebounds -- something for this research to OBSERVE, not something to trust yet.
  - Paper-only, stock-level simulation. No PE/options translation in this file --
    that's flagged as a separate, arguably harder research problem (bid-ask widening
    in panics, IV crush after a bounce, asymmetric OI) -- stock-side numbers first.

Falsifiable prediction, written down BEFORE running this against real data (per the
critic's own explicit ask, so results can't retroactively rewrite the hypothesis):
a bearish Breakdown Continuation scanner will produce FEWER but MORE EXPLOSIVE trades
than the bullish scanner -- lower trade count, higher average ATR-normalized move,
shorter holding periods, much higher gap risk (measured via entry-day and exit-day
overnight gap magnitude, since fast/violent breakdowns are expected to gap more than
gradual breakouts do).
"""
from pathlib import Path

import pandas as pd

from signals import ema, rsi, atr, reject_theta_trap

CACHE_DIR = Path(__file__).parent / "data_cache"

VOL_ZSCORE_WINDOW = 8              # same as signals.py's own adopted value -- no reason to differ yet
VOL_ZSCORE_MIN = 1.5               # mirrored as-is. DI-based bearish confirmation (-DI>+DI) was
                                    # explicitly rejected by the critic as too reactive -- same
                                    # asymmetry as the bullish +DI>-DI rejection already found --
                                    # not tested here.
RSI_MIN = 32                       # critic's proposed starting band ("roughly 32-45") --
RSI_MAX = 45                       # explicitly flagged as a RESEARCH QUESTION, not a settled number.
EMA34_FALLING_DAYS_MIN = 9         # mirror of EMA34_RISING_DAYS_MIN
MIN_TRADED_VALUE = 1_000_000_000   # same liquidity floor, direction-agnostic
MOMENTUM_20D_MAX = 0.95            # mirror of MOMENTUM_20D_MIN=1.05 -- close must be <=5% below
                                    # its level 20 trading days ago
CLOSE_NEAR_LOW_PCT = 0.30          # mirror of CLOSE_NEAR_HIGH_PCT=0.70 -- close in bottom 30% of range
VOL_SURGE_MIN = 1.20               # unchanged, direction-agnostic
BREAKDOWN_MIN_PCT = 0.995          # mirror of BREAKOUT_MIN_PCT=1.005 -- close must clear
                                    # yesterday's low by >=0.5% to the downside
ATR_TRAIL_MULT = 3.0               # same magnitude as the long side's chandelier
TRAIL_ENGAGE_PCT = 0.97            # mirror of TRAIL_ENGAGE_PCT=1.03 -- engage once down >=3%
CORP_ACTION_MOVE_PCT = 0.35        # same threshold as backtest.py -- direction-agnostic


def build_bearish_indicators(df):
    """Mirror of signals.py's build_indicators() -- a separate function, not a
    modification of the original, so production is never touched by this research
    branch. Only the direction-dependent pieces are actually flipped; volume/ATR/
    liquidity math is identical since it's direction-agnostic already."""
    df = df.copy()
    df["ema8"] = ema(df.Close, 8)
    df["ema21"] = ema(df.Close, 21)
    df["ema34"] = ema(df.Close, 34)
    df["rsi14"] = rsi(df.Close, 14)
    df["atr14"] = atr(df, 14)
    df["vol_yday"] = df.Volume.shift(1)
    df["vol_avg10_prior"] = df.Volume.shift(3).rolling(10).mean()
    df["low_prev"] = df.Low.shift(1)
    df["low10_prior"] = df.Low.shift(1).rolling(10).min()          # mirror of high10_prior
    df["atr14_60ago"] = df.atr14.shift(60)
    df["vol_declining5"] = (df.Volume.diff() < 0).rolling(5).sum() == 5
    df["ema34_falling10"] = (df.ema34 < df.ema34.shift(1)).rolling(10).sum()  # mirror of ema34_rising10
    df["traded_value_sma20"] = (df.Close * df.Volume).rolling(20).mean()
    df["close_20ago"] = df.Close.shift(20)
    df["corp_action_day"] = df.Close.pct_change().abs() > CORP_ACTION_MOVE_PCT
    vol_prior = df.Volume.shift(1).rolling(VOL_ZSCORE_WINDOW)
    df["vol_mean20_prior"] = vol_prior.mean()
    df["vol_std20_prior"] = vol_prior.std()
    df["vol_zscore"] = (df.Volume - df.vol_mean20_prior) / df.vol_std20_prior
    return df


def bearish_base_filters_pass(row):
    """Mirror of base_filters_pass() -- universal gates, direction-flipped."""
    trend_bearish = row.Close < row.ema34 and row.ema8 < row.ema34
    rsi_band = RSI_MIN < row.rsi14 < RSI_MAX
    ema34_persistent = row.ema34_falling10 >= EMA34_FALLING_DAYS_MIN
    liquid_enough = row.traded_value_sma20 >= MIN_TRADED_VALUE
    momentum_20d = row.Close <= MOMENTUM_20D_MAX * row.close_20ago
    return trend_bearish and rsi_band and ema34_persistent and liquid_enough and momentum_20d


def bearish_checklist_pass(row):
    """Mirror of checklist_pass() -- direction-flipped."""
    day_range = row.High - row.Low
    close_near_low = day_range > 0 and (row.Close - row.Low) / day_range <= CLOSE_NEAR_LOW_PCT
    conditions = [
        row.Close < row.ema8,
        row.Volume >= VOL_SURGE_MIN * row.vol_yday,
        close_near_low,
        row.Close <= BREAKDOWN_MIN_PCT * row.low_prev,
    ]
    return sum(bool(c) for c in conditions) == 4


def breakdown_continuation(row):
    """Mirror of breakout_continuation() -- the core Phase R1 signal."""
    return row.Close < row.low10_prior and pd.notna(row.vol_zscore) and row.vol_zscore >= VOL_ZSCORE_MIN


def bearish_entry_signal(row):
    """Mirror of entry_signal() -- same structure, direction-flipped. reject_theta_trap
    is reused UNCHANGED (imported, not redefined) since a quiet/dead stock is a quiet/
    dead stock regardless of direction -- it's already direction-agnostic."""
    required = ["ema34", "vol_avg10_prior", "low10_prior", "atr14_60ago",
                "ema34_falling10", "traded_value_sma20", "close_20ago"]
    if row[required].isna().any():
        return False
    if not bearish_base_filters_pass(row):
        return False
    if not bearish_checklist_pass(row):
        return False
    if reject_theta_trap(row):
        return False
    return breakdown_continuation(row)


def bearish_stop_level(state, row):
    """Mirror of current_stop_level() -- Breakdown Continuation only (no VCP-mirror
    stop in Phase R1). Chandelier trail: trough_close + 3xATR, tightening onto the
    21-EMA once down >=3% from entry. UNVERIFIED, per the module docstring -- ATR
    expanding during a selloff could keep this open through a violent bounce; that's
    exactly the behavior this research is meant to observe, not assume away."""
    base_stop = state["trough_close"] + ATR_TRAIL_MULT * row.atr14
    if state["trough_close"] <= state["entry_price"] * TRAIL_ENGAGE_PCT:
        return min(base_stop, row.ema21)
    return base_stop


def simulate_ticker_short(ticker, df):
    """Mirror of backtest.py's simulate_ticker() -- Breakdown Continuation only, stock-
    level short simulation, stop-only exit (no target/climax mirror -- explicitly out
    of scope for Phase R1, see module docstring). Records extra fields the falsifiable
    prediction needs: entry-day gap (vs prior close) and exit-day gap, to directly
    measure "gap risk" against the bullish baseline."""
    trades = []
    in_position = False
    entry_date = None
    state = None

    rows = df.reset_index()
    prev_row = None
    for i in range(len(rows)):
        row = rows.iloc[i]
        if row.get("corp_action_day", False):
            if in_position:
                trades.append(dict(
                    ticker=ticker, entry_date=entry_date, exit_date=prev_row.Date,
                    entry_price=state["entry_price"], exit_price=prev_row.Close,
                    pnl_pct=(state["entry_price"] / prev_row.Close - 1) * 100,
                    holding_days=(prev_row.Date - entry_date).days,
                    exit_reason="corp_action", entry_gap_pct=state["entry_gap_pct"],
                    entry_atr_pct=state["entry_atr_pct"], open_at_end=False,
                ))
                in_position = False
            prev_row = row
            continue
        if not in_position:
            if bearish_entry_signal(row):
                entry_date, entry_price = row.Date, row.Close
                entry_gap_pct = ((row.Open / prev_row.Close - 1) * 100
                                 if prev_row is not None and prev_row.Close else None)
                entry_atr_pct = (row.atr14 / row.Close * 100) if row.Close else None
                in_position = True
                state = dict(entry_price=entry_price, trough_close=entry_price,
                              trough_low=row.Low, entry_gap_pct=entry_gap_pct,
                              entry_atr_pct=entry_atr_pct)
        else:
            state = dict(state)
            state["trough_close"] = min(state["trough_close"], row.Close)
            state["trough_low"] = min(state["trough_low"], row.Low)
            hit_stop = row.Close > bearish_stop_level(state, row)
            if hit_stop:
                exit_gap_pct = ((row.Open / prev_row.Close - 1) * 100
                                 if prev_row is not None and prev_row.Close else None)
                trades.append(dict(
                    ticker=ticker, entry_date=entry_date, exit_date=row.Date,
                    entry_price=state["entry_price"], exit_price=row.Close,
                    pnl_pct=(state["entry_price"] / row.Close - 1) * 100,
                    holding_days=(row.Date - entry_date).days,
                    exit_reason="stop", entry_gap_pct=state["entry_gap_pct"],
                    entry_atr_pct=state["entry_atr_pct"], exit_gap_pct=exit_gap_pct,
                    open_at_end=False,
                ))
                in_position = False
        prev_row = row

    if in_position:
        last = rows.iloc[-1]
        trades.append(dict(
            ticker=ticker, entry_date=entry_date, exit_date=last.Date,
            entry_price=state["entry_price"], exit_price=last.Close,
            pnl_pct=(state["entry_price"] / last.Close - 1) * 100,
            holding_days=(last.Date - entry_date).days,
            exit_reason="open_at_end", entry_gap_pct=state["entry_gap_pct"],
            entry_atr_pct=state["entry_atr_pct"], open_at_end=True,
        ))
    return trades


def load_bearish(ticker):
    """No pivot_fn joined -- Phase R1 has no resistance/target mirror at all (explicitly
    out of scope, stop-only exit), so daily_pivots' pp/r1/r2/s1/s2 columns aren't needed."""
    df = pd.read_csv(CACHE_DIR / f"{ticker}.csv", index_col="Date", parse_dates=True)
    return build_bearish_indicators(df)


def run_backtest(tickers, verbose=False):
    all_trades = []
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  {n}/{len(tickers)} tickers processed, {len(all_trades)} trades so far")
        try:
            df = load_bearish(t)
        except FileNotFoundError:
            continue
        all_trades.extend(simulate_ticker_short(t, df))
    return pd.DataFrame(all_trades)


def summarize(trades):
    if trades.empty:
        return "no trades"
    closed = trades[~trades.open_at_end]
    lines = []
    lines.append(f"n={len(closed)} closed trades ({len(trades) - len(closed)} still open at data end)")
    lines.append(f"win rate: {(closed.pnl_pct > 0).mean() * 100:.1f}%")
    lines.append(f"median pnl: {closed.pnl_pct.median():+.2f}%   mean pnl: {closed.pnl_pct.mean():+.2f}%")
    total = closed.pnl_pct.sum()
    top10 = closed.pnl_pct.sort_values(ascending=False).head(10).sum()
    conc = (top10 / total * 100) if total else float("nan")
    lines.append(f"top-10 concentration: {conc:.1f}%")
    lines.append(f"median holding days: {closed.holding_days.median():.1f}   mean: {closed.holding_days.mean():.1f}")
    lines.append(f"median |entry_atr_pct|: {closed.entry_atr_pct.abs().median():.2f}%")
    gaps = closed.entry_gap_pct.dropna()
    lines.append(f"median |entry gap|: {gaps.abs().median():.2f}%   "
                 f"% of entries with >1% gap: {(gaps.abs() > 1).mean() * 100:.1f}%")
    return "\n".join(lines)


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    print(f"Running Phase R1 (Breakdown Continuation, paper-only) on {len(tickers)} tickers...")
    trades = run_backtest(tickers, verbose=True)
    trades.to_csv("runs/breakdown_research_v1.csv", index=False)
    print()
    print(summarize(trades))
    print()
    print("Falsifiable prediction (written down before this run): fewer but more explosive")
    print("trades than the bullish scanner -- lower n, higher ATR%, shorter holds, bigger gaps.")
    print("Bullish baseline (v28, for comparison): n=1430, win 65.0%, median +2.89%, conc 10.3%.")
