import functools
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).parent / "data_cache"
RS_LOOKBACK = 126  # ~6 months of trading days — IBD/Minervini-style RS window
RS_RATING_MIN = 70  # percentile vs the F&O universe; Minervini's published minimum bar


@functools.lru_cache(maxsize=None)
def _universe_returns():
    """Trailing RS_LOOKBACK-day return for every ticker in fo_universe.csv, aligned
    into one wide (date x ticker) frame. Built once per process, reused for every
    rs_rating() lookup — recomputing per-call would mean reloading 210 CSVs per row."""
    tickers = pd.read_csv(Path(__file__).parent / "fo_universe.csv", header=None)[0].tolist()
    closes = {}
    for t in tickers:
        path = CACHE_DIR / f"{t}.csv"
        if not path.exists():
            continue
        closes[t] = pd.read_csv(path, index_col="Date", parse_dates=True).Close
    wide = pd.DataFrame(closes)
    return wide.pct_change(RS_LOOKBACK, fill_method=None) * 100


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
