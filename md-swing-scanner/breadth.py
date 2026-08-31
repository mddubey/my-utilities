"""% of NIFTY 500 stocks trading above their OWN 200-day SMA, as an alternative/
supplementary regime signal to Nifty's own SMA200 (market_regime.py) — critique-3's
top swing-side idea (2026-08-31): a genuine institutional breadth measure, reasoned
to react earlier than the index-level gate since leadership can return "under the
surface" before the index itself crosses back above its own 200-SMA. Untested claim
until validated against real backtest numbers (see backtest.py/README for the result)."""
import functools
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).parent / "data_cache"
BREADTH_FILE = CACHE_DIR / "_BREADTH.csv"


def compute_breadth(tickers):
    """Returns a DataFrame indexed by Date: pct_above (% of tickers with Close > their
    own trailing 200-day SMA, among tickers with >=200 days of history as of that
    date) and n_counted (how many tickers had enough history — small/noisy early in
    the cache window)."""
    above_frames = []
    for t in tickers:
        try:
            df = pd.read_csv(CACHE_DIR / f"{t}.csv", index_col="Date", parse_dates=True)
        except FileNotFoundError:
            continue
        sma200 = df.Close.rolling(200).mean()
        above = (df.Close > sma200).where(sma200.notna())
        above.name = t
        above_frames.append(above)
    combined = pd.concat(above_frames, axis=1)
    return pd.DataFrame({
        "pct_above": combined.mean(axis=1, skipna=True) * 100,
        "n_counted": combined.notna().sum(axis=1),
    })


def refresh():
    tickers = pd.read_csv(Path(__file__).parent / "nifty500_universe.csv", header=None)[0].tolist()
    breadth = compute_breadth(tickers)
    breadth.to_csv(BREADTH_FILE)


@functools.lru_cache(maxsize=None)
def _breadth_frame():
    return pd.read_csv(BREADTH_FILE, index_col="Date", parse_dates=True)


def breadth_pct(date):
    """% breadth as of the most recent trading day on/before `date`, or NaN if none."""
    df = _breadth_frame()
    pos = df.index.searchsorted(date, side="right") - 1
    if pos < 0:
        return float("nan")
    return df.iloc[pos].pct_above


if __name__ == "__main__":
    refresh()
