"""Sector-level relative strength — is a stock's SECTOR currently leading or lagging
the broader market, not just the stock itself. Adopted (2026-09-01) as a RANKING
signal for daily_scan.py, not a hard gate: real backtest data (see FINDINGS.md's
"Veteran trader review" ideas section) shows VCP trades in leading sectors win more
(68.1% vs 55-61% in the bottom three quartiles) and are far less lumpy (30.5% vs
75-200% concentration) than trades in lagging ones — but this is meant to help
decide which of several same-day candidates to prioritize, not to exclude anything.
Same reasoning as keeping MOMENTUM_20D_MIN/MIN_TRADED_VALUE as candidate-list
controls rather than hard-proven filters (see signals.py's own comment): don't
shrink the daily list on a ranking signal, just help order it. Checked separately
(same finding) that sector strength does NOT explain the Oct'24-Feb'26 VCP weak
window specifically — even leading-sector trades failed at nearly the same rate
during that stretch, so this is a general-quality signal, not a fix for that episode.
"""
import functools

import pandas as pd

from relative_strength import _universe_returns_for
import sectors

SECTOR_UNIVERSE_FILE = "nifty500_universe.csv"  # always the full universe, regardless
                                                  # of whatever relative_strength.py's
                                                  # own UNIVERSE_FILE is currently set to
                                                  # elsewhere — sector leadership should
                                                  # reflect the whole market, not whichever
                                                  # narrower universe some other caller
                                                  # happens to be using right now


@functools.lru_cache(maxsize=None)
def _sector_returns():
    """date x sector frame — each cell is the mean trailing RS_LOOKBACK-day return of
    that sector's member tickers on that date."""
    returns = _universe_returns_for(SECTOR_UNIVERSE_FILE)
    sector_map = sectors.load().reindex(returns.columns)
    return returns.T.groupby(sector_map).mean().T


def sector_rs(ticker, date):
    """Returns (sector_name, rs_percentile). rs_percentile is a 0-100 rank of this
    ticker's SECTOR against every other sector on this date (None if the ticker has
    no sector classification, or there isn't enough same-date data to rank against)."""
    sector = sectors.load().get(ticker)
    if sector is None or pd.isna(sector):
        return None, None
    sr = _sector_returns()
    if sector not in sr.columns or date not in sr.index:
        return sector, None
    row = sr.loc[date].dropna()
    if sector not in row.index or len(row) < 3:
        return sector, None
    return sector, (row < row[sector]).mean() * 100
