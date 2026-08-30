import pandas as pd

from relative_strength import rs_rating, RS_RATING_MIN

# --- Stage 2 trend template (Minervini) ---
LOW_52W_MIN_MULT = 1.25   # price must be at least 25% above its 52-week low
HIGH_52W_MAX_MULT = 0.75  # price must be within 25% of its 52-week high (i.e. >= 75% of it)


def stage2_trend_template(row, ticker, date):
    """Long-term uptrend confirmation, checked BEFORE looking at any short-term pattern
    at all — this is the actual gate that separates a real base-building leader from a
    random quiet patch inside an unremarkable or declining stock."""
    required = ["sma50", "sma150", "sma200", "sma200_20ago", "high_252", "low_252"]
    if row[required].isna().any():
        return False
    above_all_smas = row.Close > row.sma50 and row.Close > row.sma150 and row.Close > row.sma200
    ma_stack = row.sma50 > row.sma150 > row.sma200
    sma200_rising = row.sma200 > row.sma200_20ago
    off_52w_low = row.Close >= LOW_52W_MIN_MULT * row.low_252
    near_52w_high = row.Close >= HIGH_52W_MAX_MULT * row.high_252
    rs = rs_rating(ticker, date)
    strong_rs = rs is not None and rs >= RS_RATING_MIN
    return above_all_smas and ma_stack and sma200_rising and off_52w_low and near_52w_high and strong_rs


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
    if not (last_depth <= TIGHTENING_RATIO * first_depth and last_depth <= depths[-2]):
        return None

    first_leg_vol = window.Volume.iloc[legs[0][0]:legs[0][2] + 1].mean()
    last_leg_vol = window.Volume.iloc[legs[-1][0]:legs[-1][2] + 1].mean()
    if not (last_leg_vol < first_leg_vol):
        return None

    last_low_idx = legs[-1][2]
    if (len(window) - 1 - last_low_idx) > RECENT_LOW_MAX_DAYS:
        return None  # the tightest contraction is stale, not a fresh coil about to release

    return legs[-1][1], legs[-1][3]  # (swing high before the final pullback, that pullback's low)


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
        volume_ok = pd.notna(row.vol_zscore) and row.vol_zscore >= zscore_min
    else:
        baseline_vol = df.Volume.iloc[max(0, i - 10):i].mean()
        volume_ok = row.Volume >= VCP_BREAKOUT_VOL_MULT * baseline_vol
    if row.Close > pivot and volume_ok:
        return pivot, structural_low
    return None
