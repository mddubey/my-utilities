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


def rs_rating(ticker, date):
    """Percentile rank (0-100) of this ticker's trailing RS_LOOKBACK-day return against
    every other F&O stock on the same date — the actual Minervini/IBD definition (a
    ranking within the universe), not just a raw outperformance-vs-Nifty ratio."""
    returns = _universe_returns()
    if ticker not in returns.columns or date not in returns.index:
        return None
    row = returns.loc[date]
    valid = row.dropna()
    if ticker not in valid.index or len(valid) < 10:
        return None
    return (valid < valid[ticker]).mean() * 100
