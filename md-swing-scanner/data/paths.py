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


def last_row_time(path):
    """Timestamp in the first column of a CSV's last row, read from the file's tail (fast on big files).
    None if the file is missing or empty."""
    import pandas as pd
    try:
        with open(path, "rb") as f:
            f.seek(0, 2); n = f.tell(); f.seek(max(0, n - 4096))
            line = f.read().decode(errors="ignore").strip().splitlines()[-1]
        return pd.Timestamp(line.split(",")[0])
    except Exception:
        return None


def holds_full_session(path, session, close_hhmm="15:10"):
    """True if an intraday CSV (tz-aware timestamps) already has `session`'s bars up to at least close_hhmm IST.
    A partial day (e.g. a mid-day top-up) does not count, so the evening run still completes it."""
    import pandas as pd
    t = last_row_time(path)
    if t is None:
        return False
    t = (t if t.tzinfo else t.tz_localize("UTC")).tz_convert("Asia/Kolkata")
    return t.date() > session.date() or (t.date() == session.date() and t.strftime("%H:%M") >= close_hhmm)
