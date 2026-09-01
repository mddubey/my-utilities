"""Ticker -> sector classification, cached once (2026-09-01) — yfinance's per-ticker
.info call is slow (~500 individual HTTP calls for the full universe) and sector
classification doesn't change often, so this is a standalone refresh script, not
fetched live during a scan or backtest. Motivated by a real gap flagged in a review
note (`feedback/2026-09-01_05-57-04_IST_veteran_trader_review.md`): "track sector
leadership — a breakout in a leading group deserves more trust than an isolated
stock in a weak group" — and ties directly into item 5's sector-concentration
hypothesis for the Oct'24-Feb'26 VCP weak window (see FINDINGS.md)."""
from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).parent / "data_cache"
SECTOR_FILE = CACHE_DIR / "_sectors.csv"


def refresh(universe_file="nifty500_universe.csv"):
    """Re-fetch sector/industry for every ticker in universe_file — run standalone
    when the cache is missing or stale, not on every analysis run."""
    tickers = pd.read_csv(Path(__file__).parent / universe_file, header=None)[0].tolist()
    rows = []
    for i, t in enumerate(tickers):
        try:
            info = yf.Ticker(f"{t}.NS").info
            sector, industry = info.get("sector"), info.get("industry")
        except Exception:
            sector, industry = None, None
        rows.append(dict(ticker=t, sector=sector, industry=industry))
        if (i + 1) % 50 == 0:
            print(f"{i + 1}/{len(tickers)}", flush=True)
    pd.DataFrame(rows).to_csv(SECTOR_FILE, index=False)


def load():
    """ticker -> sector Series. Missing/unclassified tickers get None — caller decides
    whether to drop them or bucket them as 'Unknown'."""
    return pd.read_csv(SECTOR_FILE, index_col="ticker")["sector"]


if __name__ == "__main__":
    refresh()
