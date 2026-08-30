import pandas as pd


def _levels(pp, h, l):
    return pd.DataFrame({
        "pp": pp,
        "r1": 2 * pp - l, "s1": 2 * pp - h,
        "r2": pp + (h - l), "s2": pp - (h - l),
    })


def weekly_pivots(df):
    """Weekly floor-trader pivots (PP, R1/R2, S1/S2), computed from the PRIOR completed
    week's H/L/C and held constant for every day of the current week. No lookahead.

    Found by the project's first deterministic test (2026-08-30) — a real, previously
    undiscovered bug, silently present in every backtest run all session: the old
    implementation resampled to a Friday-labeled weekly series, shifted it, then
    reindexed onto the daily index with ffill. Since ffill looks up "the latest
    AVAILABLE weekly label <= this day", and weekly labels only exist on Fridays,
    Monday-Thursday of any week picked up the PREVIOUS Friday's (already-shifted)
    value — i.e. TWO weeks stale, not one — and only the Friday itself showed the
    correct "prior completed week" pivot. Verified directly against real cached data
    (RELIANCE, June 2026): pp changed only on Fridays and held for the following
    Mon-Thu, one extra week behind what the docstring always claimed. Fixed by
    grouping on explicit week PERIODS instead of date-based ffill — every day within
    a period maps to that exact period's (shifted) row, no ambiguity."""
    week = df.index.to_period("W-FRI")
    weekly = df.groupby(week).agg({"High": "max", "Low": "min", "Close": "last"})
    pp = (weekly.High + weekly.Low + weekly.Close) / 3
    levels = _levels(pp, weekly.High, weekly.Low).shift(1)  # use PRIOR week's levels
    result = levels.reindex(week)
    result.index = df.index
    return result


def daily_pivots(df):
    """Floor-trader pivots from the PRIOR day's H/L/C. No lookahead."""
    h, l, c = df.High.shift(1), df.Low.shift(1), df.Close.shift(1)
    pp = (h + l + c) / 3
    return _levels(pp, h, l)
