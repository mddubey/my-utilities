import functools
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).parent / "data_cache"
RS_LOOKBACK = 126  # ~6 months of trading days — IBD/Minervini-style RS window
RS_RATING_MIN = 70  # percentile vs the universe; Minervini's published minimum bar
UNIVERSE_FILE = "nifty500_universe.csv"  # ADOPTED (2026-08-30) as the pure-swing default —
                                     # tested against the full NIFTY 500 (500 tickers, a
                                     # strict superset of fo_universe.csv's 210): win rate
                                     # 60.5%->58.0%, median 1.92%->1.66% (modest dip), but
                                     # concentration IMPROVED 43.4%->30.8% (best of the whole
                                     # project) on n=676 vs 329 — genuinely more diversified,
                                     # not just diluted with noise. VCP signal count grew far
                                     # more (221->543) than Breakout Continuation (108->133),
                                     # consistent with VCP's multi-week-base setups showing up
                                     # more in the broader mid/small-cap universe. Set this to
                                     # "fo_universe.csv" instead only for the options-specific
                                     # layer (option_backtest.py/portfolio.py), where the
                                     # universe is hard-constrained by what actually has
                                     # options, not a free choice — RS is a RANKING, so which
                                     # universe it's ranked against genuinely changes the
                                     # result, not just the candidate pool.


@functools.lru_cache(maxsize=None)
def _universe_returns_for(universe_file):
    tickers = pd.read_csv(Path(__file__).parent / universe_file, header=None)[0].tolist()
    closes = {}
    for t in tickers:
        path = CACHE_DIR / f"{t}.csv"
        if not path.exists():
            continue
        closes[t] = pd.read_csv(path, index_col="Date", parse_dates=True).Close
    wide = pd.DataFrame(closes)
    return wide.pct_change(RS_LOOKBACK, fill_method=None) * 100


def _universe_returns():
    """Trailing RS_LOOKBACK-day return for every ticker in UNIVERSE_FILE, aligned into
    one wide (date x ticker) frame. Cached per universe file (not just once), so
    switching UNIVERSE_FILE between runs recomputes correctly instead of silently
    reusing a stale result from whichever universe was cached first."""
    return _universe_returns_for(UNIVERSE_FILE)


def _universe_returns_live(live_closes):
    """RS_LOOKBACK-day % return for TODAY, a live-only day not yet on disk anywhere
    (2026-09-08 — see daily_scan.py's --refresh-primed): _universe_returns() reads
    every ticker's cache file straight off disk, so during real market hours,
    BEFORE fetch_prices.py has run, no ticker anywhere has today's date cached yet
    — rs_rating() would return None universally, not just for one ticker, silently
    killing stage2_trend_template's RS gate (and with it the whole coiled_spring/
    VCP path) for the entire live session. Tickers with a live intraday close
    (live_closes) get a real same-day return; everyone else falls back to their own
    last cached close as a stand-in for today, same "everyone else stays on
    yesterday's snapshot" approximation the rest of the live pipeline already
    makes — a one-day-stale reference point barely moves a 126-day trailing
    return, so ranking against it is a fine approximation, not a real gap."""
    tickers = pd.read_csv(Path(__file__).parent / UNIVERSE_FILE, header=None)[0].tolist()
    out = {}
    for t in tickers:
        path = CACHE_DIR / f"{t}.csv"
        if not path.exists():
            continue
        closes = pd.read_csv(path, index_col="Date", parse_dates=True).Close
        if len(closes) < RS_LOOKBACK:
            continue
        base = closes.iloc[-RS_LOOKBACK]
        if not base or pd.isna(base):
            continue
        today_close = live_closes.get(t, closes.iloc[-1])
        out[t] = (today_close / base - 1) * 100
    return pd.Series(out)


def rs_rating(ticker, date, live_closes=None):
    """Percentile rank (0-100) of this ticker's trailing RS_LOOKBACK-day return against
    every other F&O stock on the same date — the actual Minervini/IBD definition (a
    ranking within the universe), not just a raw outperformance-vs-Nifty ratio.

    live_closes (optional): {ticker: intraday close}, for a live `date` not yet
    cached to disk for anyone — see _universe_returns_live()'s docstring. Backtests
    and any post-EOD call never pass this, so historical results are untouched."""
    if live_closes:
        row = _universe_returns_live(live_closes)
    else:
        returns = _universe_returns()
        if ticker not in returns.columns or date not in returns.index:
            return None
        row = returns.loc[date]
    valid = row.dropna()
    if ticker not in valid.index or len(valid) < 10:
        return None
    return (valid < valid[ticker]).mean() * 100
