import functools
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).parent / "data_cache"
NIFTY_FILE = CACHE_DIR / "_NIFTY.csv"

# verified directly (2026-08-30) against trades_v5.csv: Breakout Continuation shows
# 51.8% win rate / +0.25% median pnl when Nifty ADX is below this line ("choppy"),
# vs 71-73% win rate / ~+2% median at or above it ("neutral"/"trending") — the split
# point itself, not a borrowed rule of thumb.
NIFTY_ADX_MIN = 20
NIFTY_ADX_RISING_LOOKBACK = 5  # trading days — testing the originally-suggested ">22 and rising"
                                # variant (using the already-verified 20 threshold, just adding the
                                # rising requirement on top, one change at a time); a short window
                                # instead of a single-day delta since ADX is already a smoothed
                                # indicator and day-to-day noise isn't a meaningful "rising" signal


def _compute_adx(df, period=14):
    """Returns (adx, plus_di, minus_di) — the directional components were previously
    computed and thrown away, keeping only the final ADX (trend STRENGTH). Checked
    directly (2026-08-30): the Dec'24-May'25 VCP losing patch (34.4% win rate, -4.91%
    median) coincides almost exactly with a genuine ~9% Nifty correction (24,304->
    22,125) where ADX stayed elevated (24-37, well above NIFTY_ADX_MIN=20) throughout
    — the regime gate correctly said "trending" while the market was trending DOWN.
    +DI/-DI (already computed, just unused before) let us also check direction."""
    up_move = df.High.diff()
    down_move = -df.Low.diff()
    plus_dm = ((up_move > down_move) & (up_move > 0)) * up_move
    minus_dm = ((down_move > up_move) & (down_move > 0)) * down_move
    tr = pd.concat([
        df.High - df.Low,
        (df.High - df.Close.shift()).abs(),
        (df.Low - df.Close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx, plus_di, minus_di


def refresh():
    """Re-fetch Nifty daily OHLC and recompute ADX14 + DI14 + SMA200 — run standalone
    when the cached file is stale, not on every backtest."""
    import yfinance as yf
    df = yf.download("^NSEI", period="5y", interval="1d", auto_adjust=True)
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df["adx14"], df["plus_di14"], df["minus_di14"] = _compute_adx(df)
    df["sma50"] = df.Close.rolling(50).mean()
    df["sma200"] = df.Close.rolling(200).mean()
    df.to_csv(NIFTY_FILE)


@functools.lru_cache(maxsize=None)
def _regime_frame():
    df = pd.read_csv(NIFTY_FILE, index_col="Date", parse_dates=True)
    return df[["Close", "adx14", "plus_di14", "minus_di14", "sma50", "sma200"]]


def market_trending(date, require_rising=False, require_uptrend=False, require_above_sma200=False,
                     require_above_sma50=False, require_sma50_rising=False):
    """Nifty ADX at or after the most recent trading day on/before `date` is >= the
    verified choppy/neutral split. Used to gate BOTH patterns (docstring here was
    stale — VCP got the same gate in v11 once it was checked directly and also showed
    a regime-dependent edge, contrary to the original "Coiled Spring showed no rescue
    pattern" note, which predates the full VCP rebuild). Pass require_rising=True to
    additionally require ADX(date) >= ADX(date - NIFTY_ADX_RISING_LOOKBACK trading
    days) — the originally-suggested ">22 and rising" variant, tested separately
    rather than silently changed as the default. Pass require_uptrend=True to
    additionally require +DI14 > -DI14 — REJECTED (2026-08-30): too reactive (flips
    every ~11 trading days vs ADX's ~21), didn't discriminate the Dec'24-May'25 VCP
    losing patch at all (down-days 31.25% win vs up-days 37.5% win — no difference),
    kept only for reference. Pass require_above_sma200=True to additionally require
    Nifty Close > its own 200-day SMA — a slower, structural "is the broad market
    actually in good shape" gauge (same published methodology already used for
    individual stocks in vcp.py's stage2_trend_template), tested as the better-
    specified version of the same "don't go long against the tape" idea.

    Pass require_above_sma50 and/or require_sma50_rising (2026-09-01, REJECTED — kept
    for reference, same as require_uptrend above): motivated by a real gap in the
    VCP-collapse investigation (ADX+SMA200 gate stayed open 62-100% of days through
    Oct-Dec 2024's ~1650-point Nifty correction, since ADX measures trend STRENGTH not
    direction and SMA200 lags 2-3 months behind), and a Nifty-level check showed
    SMA50-based filters would have closed the gate 1-2 months faster in that window.
    Backwards once actually backtested, though: within the exact window this was meant
    to fix, the VCP trades it REMOVES (Nifty below/falling its 50-SMA) were the BETTER
    half (55.1% win) and the ones it KEEPS were worse (38.1% win) — see backtest.py's
    TEST_SMA50_ABOVE/TEST_SMA50_RISING comments for the full numbers. Nifty's own
    medium-term trend strength isn't what's driving VCP's weak window."""
    df = _regime_frame()
    pos = df.index.searchsorted(date, side="right") - 1
    if pos < 0:
        return False
    row = df.iloc[pos]
    if row.adx14 < NIFTY_ADX_MIN:
        return False
    if require_rising:
        prior_pos = pos - NIFTY_ADX_RISING_LOOKBACK
        if prior_pos < 0:
            return False
        if not (row.adx14 >= df.iloc[prior_pos].adx14):
            return False
    if require_uptrend and not (row.plus_di14 > row.minus_di14):
        return False
    if require_above_sma200:
        if pd.isna(row.sma200) or not (row.Close > row.sma200):
            return False
    if require_above_sma50:
        if pd.isna(row.sma50) or not (row.Close > row.sma50):
            return False
    if require_sma50_rising:
        prior_pos = pos - NIFTY_ADX_RISING_LOOKBACK
        if prior_pos < 0:
            return False
        prior_sma50 = df.iloc[prior_pos].sma50
        if pd.isna(row.sma50) or pd.isna(prior_sma50) or not (row.sma50 >= prior_sma50):
            return False
    return True


if __name__ == "__main__":
    refresh()
