"""Single source of truth for where base market data lives (2026-10-03). Every cache is one folder under data/;
see data/README.md for source, fetcher, coverage and caveats of each. Import from here instead of hard-coding a
folder name, so the next move is a one-line change."""
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent

DAILY_DIR = DATA_DIR / "daily"                    # yfinance daily OHLCV (+ _NIFTY, _BANKNIFTY, _BREADTH, _sectors)
INTRADAY_5M_DIR = DATA_DIR / "intraday_5m"        # yfinance 5-min bars
INTRADAY_60M_DIR = DATA_DIR / "intraday_60m"      # yfinance native 60-min bars
INDEX_INTRADAY_DIR = DATA_DIR / "index_intraday"  # NIFTY / BANKNIFTY intraday
NSE_FO_BHAV_DIR = DATA_DIR / "nse_fo_bhav"        # NSE F&O bhavcopy (options)
NSE_CASH_CLOSE_DIR = DATA_DIR / "nse_cash_close"  # NSE cash bhavcopy, close only, sparse dates
NSE_BHAV_DIR = DATA_DIR / "nse_bhav"              # NSE full cash bhavcopy (OHLC + PREVCLOSE), all sessions
NSE_BANDS_DIR = DATA_DIR / "nse_bands"            # NSE point-in-time price bands
NSE_CORP_ACTIONS_FILE = DATA_DIR / "nse_corp_actions.csv"
