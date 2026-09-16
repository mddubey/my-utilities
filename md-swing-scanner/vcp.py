import pandas as pd

from relative_strength import rs_rating, RS_RATING_MIN

# --- Stage 2 trend template (Minervini) ---
LOW_52W_MIN_MULT = 1.25   # price must be at least 25% above its 52-week low
HIGH_52W_MAX_MULT = 0.75  # price must be within 25% of its 52-week high (i.e. >= 75% of it)


def stage2_trend_breakdown(row, ticker, date, live_closes=None):
    """The individual Stage-2 sub-conditions, exposed separately (2026-09-16) so a live
    monitoring tool can show WHICH conditions passed and by what margin, not just the
    collapsed True/False stage2_trend_template() returns -- same reasoning as detect_entry/
    check_exit being the single source of truth elsewhere in this project: one place
    computes these conditions, stage2_trend_template() below is now a thin wrapper over
    this, not a second copy.

    Returns a dict with each sub-condition (bool) plus the raw rs_rating (float or None)
    and an "all_pass" key matching stage2_trend_template()'s own return value exactly.
    If any required column is NaN, every sub-condition and all_pass come back None/False
    rather than raising -- same missing-data behavior as before this refactor."""
    required = ["sma50", "sma150", "sma200", "sma200_20ago", "high_252", "low_252"]
    if row[required].isna().any():
        return dict(above_all_smas=None, ma_stack=None, sma200_rising=None,
                     off_52w_low=None, near_52w_high=None, rs_rating=None,
                     strong_rs=None, all_pass=False)
    above_all_smas = row.Close > row.sma50 and row.Close > row.sma150 and row.Close > row.sma200
    ma_stack = row.sma50 > row.sma150 > row.sma200
    sma200_rising = row.sma200 > row.sma200_20ago
    off_52w_low = row.Close >= LOW_52W_MIN_MULT * row.low_252
    near_52w_high = row.Close >= HIGH_52W_MAX_MULT * row.high_252
    rs = rs_rating(ticker, date, live_closes=live_closes)
    strong_rs = rs is not None and rs >= RS_RATING_MIN
    all_pass = (above_all_smas and ma_stack and sma200_rising
                and off_52w_low and near_52w_high and strong_rs)
    return dict(above_all_smas=above_all_smas, ma_stack=ma_stack, sma200_rising=sma200_rising,
                 off_52w_low=off_52w_low, near_52w_high=near_52w_high, rs_rating=rs,
                 strong_rs=strong_rs, all_pass=all_pass)


def stage2_trend_template(row, ticker, date, live_closes=None):
    """Long-term uptrend confirmation, checked BEFORE looking at any short-term pattern
    at all — this is the actual gate that separates a real base-building leader from a
    random quiet patch inside an unremarkable or declining stock.

    live_closes (optional): passed straight through to rs_rating() for a live `date`
    not yet cached to disk anywhere — see its docstring. Never set by backtests."""
    return stage2_trend_breakdown(row, ticker, date, live_closes=live_closes)["all_pass"]


# --- multi-contraction base detection ---
ZIGZAG_PCT = 0.03          # % reversal to register a new swing point
BASE_LOOKBACK = 60         # trading days (~12 weeks) — Minervini: bases run 5+ weeks, often longer
MIN_LEGS = 2               # need at least 2 pullback legs for a real multi-contraction base
TIGHTENING_RATIO = 0.75    # final leg's depth must be at most this fraction of the first leg's
RECENT_LOW_MAX_DAYS = 15   # the most recent contraction low must be this fresh, not stale history
VCP_BREAKOUT_VOL_MULT = 1.8   # fallback only — the flat-ratio check, kept for zscore_min=None callers
VCP_VOL_ZSCORE_MIN = 0.5      # actual default — verified via sweep (2026-08-30): even the
                               # loosest z-score version (>=0, "just above average") tripled
                               # the sample (14->41) AND improved every quality metric versus
                               # the flat 1.8x ratio; 0.5 was the smooth optimum, not a cherry-pick
VCP_VOL_Z_WINDOW = 50    # ADOPTED (2026-09-13, was implicitly signals.BC_VOL_Z_WINDOW=8,
                               # shared with Breakout Continuation). RQ-34 audit: re-swept this
                               # pattern's own volume-baseline window in isolation (5-60 days,
                               # live-equivalent population -- structural base_pivot() + intraday
                               # breach, no vol_zscore gate at entry time) rather than assuming
                               # BC's 8-day answer transfers. Rank-correlation between this
                               # window's z-score and real day+1 pnl climbs steadily from 5
                               # through 30 (0.028->0.288), then genuinely plateaus 32-60
                               # (0.288-0.295, flat) -- confirmed a real plateau, not thinning-
                               # sample noise, since this metric uses the full population at
                               # every window (not a shrinking threshold-cut subset). 50 sits
                               # inside that empirical plateau AND matches the externally-cited
                               # Minervini/IBD convention (breakout volume commonly measured
                               # against a 50-day average) -- both the data and the published
                               # methodology agree, so 50 rather than an arbitrary point in the
                               # 32-60 flat range. Makes sense structurally too: VCP measures a
                               # slow multi-week volume dry-up/expansion, a genuinely different
                               # timescale from BC's fast momentum burst -- the two patterns were
                               # never going to share one optimal window.
LAST_LEG_TOLERANCE = 0.40     # ADOPTED (2026-08-31): the strict last_depth<=depths[-2] rule
                               # required the final leg to be tighter than the PRIOR leg with
                               # zero slack — a human reading a chart wouldn't reject a base
                               # over a fractional-percentage-point wobble on the last leg (real
                               # case: AUROPHARMA missed by 4.97% vs 4.40%, a 13% relative miss,
                               # on an otherwise clean 4-leg tightening base, later confirmed to
                               # be a genuine breakout). Full-backtest sweep 0%-100%: gains
                               # mostly land by 20-30%, then plateau flat/noisy out to 100% —
                               # 40% sits in that plateau (n 543->654, win 56.2%->57.2%, median
                               # +1.46%->+1.60%, conc 37.5%->31.6%), tied-or-better than 30% on
                               # every metric, no principled reason to prefer 30 over 40. Checked
                               # the marginal trades specifically (the 130 unlocked at 40% that
                               # don't exist at 0%), not just before/after averages: they're
                               # BETTER quality than the existing pool (60.8% win/+2.63% median
                               # vs baseline 56.2%/+1.46%), though thinner (70% concentration
                               # for that subgroup alone vs ~32% overall) — still under the 100%
                               # reject line, not disqualifying.


def _find_swings(high, low, pct=ZIGZAG_PCT):
    """Percentage-reversal zigzag. Returns [(pos_in_window, price, 'H'|'L'), ...]."""
    n = len(high)
    if n < 2:
        return []
    pivots = []
    trend_up = None
    ref_price = high.iloc[0]
    ext_price, ext_idx = high.iloc[0], 0

    for i in range(1, n):
        h, l = high.iloc[i], low.iloc[i]
        if trend_up is None:
            if h >= ref_price * (1 + pct):
                trend_up = True
                ext_price, ext_idx = h, i
            elif l <= ref_price * (1 - pct):
                trend_up = False
                ext_price, ext_idx = l, i
            else:
                ref_price = max(ref_price, h)
            continue
        if trend_up:
            if h > ext_price:
                ext_price, ext_idx = h, i
            elif l <= ext_price * (1 - pct):
                pivots.append((ext_idx, ext_price, "H"))
                trend_up = False
                ext_price, ext_idx = l, i
        else:
            if l < ext_price:
                ext_price, ext_idx = l, i
            elif h >= ext_price * (1 + pct):
                pivots.append((ext_idx, ext_price, "L"))
                trend_up = True
                ext_price, ext_idx = h, i
    return pivots


def _legs(pivots):
    """Pair up consecutive H->L pivots into pullback legs: (h_idx, h_price, l_idx, l_price)."""
    legs = []
    for a, b in zip(pivots, pivots[1:]):
        if a[2] == "H" and b[2] == "L":
            legs.append((a[0], a[1], b[0], b[1]))
    return legs


def base_pivot(df, i):
    """Look back BASE_LOOKBACK days before today (index i) for a genuine multi-contraction
    base: >=2 pullback legs, each shallower and on lower volume than the one before, the
    most recent low still fresh. Returns (pivot_price, structural_low) if found, else None
    — pivot is the high to break out above, structural_low is the final contraction's low,
    used as the trade's actual stop level (real VCP practice: a hard stop under the
    breakout structure itself, not an arbitrary short EMA)."""
    start = max(0, i - BASE_LOOKBACK)
    window = df.iloc[start:i]
    if len(window) < 10:
        return None
    pivots = _find_swings(window.High, window.Low)
    legs = _legs(pivots)
    if len(legs) < MIN_LEGS:
        return None

    depths = [(h_p - l_p) / h_p for _, h_p, _, l_p in legs]
    first_depth, last_depth = depths[0], depths[-1]
    if not (last_depth <= TIGHTENING_RATIO * first_depth
            and last_depth <= depths[-2] * (1 + LAST_LEG_TOLERANCE)):
        return None

    first_leg_vol = window.Volume.iloc[legs[0][0]:legs[0][2] + 1].mean()
    last_leg_vol = window.Volume.iloc[legs[-1][0]:legs[-1][2] + 1].mean()
    if not (last_leg_vol < first_leg_vol):
        return None

    last_low_idx = legs[-1][2]
    if (len(window) - 1 - last_low_idx) > RECENT_LOW_MAX_DAYS:
        return None  # the tightest contraction is stale, not a fresh coil about to release

    return legs[-1][1], legs[-1][3]  # (swing high before the final pullback, that pullback's low)


def _vcp_vol_zscore(df, i, window=VCP_VOL_Z_WINDOW):
    """This pattern's own volume z-score, using VCP_VOL_Z_WINDOW (not the shared,
    BC-tuned signals.BC_VOL_Z_WINDOW=8 column) — same no-lookahead convention as
    signals.py (window is the `window` days strictly BEFORE today, excluding today)."""
    start = max(0, i - window)
    window_vol = df.Volume.iloc[start:i]
    if len(window_vol) < window:
        return None
    std = window_vol.std()
    if not std:
        return None
    return (df.Volume.iloc[i] - window_vol.mean()) / std


def vcp_breakout(df, i, zscore_min=VCP_VOL_ZSCORE_MIN):
    """Returns (pivot, structural_low) if today (index i) breaks out of a genuine
    multi-contraction base on real volume, else None. Does NOT include the trend
    template — call stage2_trend_template separately. Pass zscore_min=None to fall
    back to the old flat VCP_BREAKOUT_VOL_MULT ratio instead (kept for comparison)."""
    base = base_pivot(df, i)
    if base is None:
        return None
    pivot, structural_low = base
    row = df.iloc[i]
    if zscore_min is not None:
        vz = _vcp_vol_zscore(df, i)
        volume_ok = vz is not None and vz >= zscore_min
    else:
        baseline_vol = df.Volume.iloc[max(0, i - 10):i].mean()
        volume_ok = row.Volume >= VCP_BREAKOUT_VOL_MULT * baseline_vol
    if row.Close > pivot and volume_ok:
        return pivot, structural_low
    return None
