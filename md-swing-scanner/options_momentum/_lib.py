"""Shared loaders for options_momentum/ (RQ-OMD-01). Reads only from the root data/ folder --
no project-local cache. See RQ-OMD-01_PREFLIGHT.md for the conventions implemented here."""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from data.paths import INTRADAY_60M_DIR, DAILY_DIR, NSE_CORP_ACTIONS_FILE  # noqa: E402

IST = "Asia/Kolkata"
# same regex short_discovery/s01_nse_reconcile.py uses to classify price-affecting corp actions
PRICE_CA_RE = re.compile(
    r"split|sub-division|sub division|bonus|rights|demerger|scheme|arrangement|amalgamation|"
    r"consolidation|reduction", re.I)


def trading_calendar():
    """Master NSE session calendar (sorted, tz-naive dates) from the Nifty daily file."""
    nifty = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True)
    return pd.DatetimeIndex(sorted(nifty.index.normalize().unique()))


def price_affecting_ca_sessions(cal):
    """{ticker: set(cal_positions_to_exclude)} -- ex-date mapped to the first session on/after
    it (searchsorted on `cal`, matching short_discovery's convention), plus the immediately
    adjacent session on each side (+-1), per the preflight's corp-action exclusion rule."""
    c = pd.read_csv(NSE_CORP_ACTIONS_FILE)
    subj = c.subject.str.lower()
    c = c[subj.str.contains(PRICE_CA_RE)].copy()
    c["ex"] = pd.to_datetime(c.exDate, format="%d-%b-%Y", errors="coerce")
    c = c.dropna(subset=["ex"])
    cal_vals = cal.values
    n = len(cal_vals)
    s_ex = np.searchsorted(cal_vals, c.ex.values)
    out = {}
    for sym, s in zip(c.symbol, s_ex):
        for off in (-1, 0, 1):
            p = s + off
            if 0 <= p < n:
                out.setdefault(sym, set()).add(int(p))
    return out


def load_60m(ticker):
    """One ticker's 60m bars: IST, deduped/sorted, with session_date and bar_of_day
    (0 = the 09:15 gap bar, 1..6 = intraday bars). None if no usable file."""
    f = INTRADAY_60M_DIR / f"{ticker}.csv"
    if not f.exists():
        return None
    d = pd.read_csv(f, index_col=0)
    if d.empty or "Close" not in d.columns:
        return None
    d.index = pd.to_datetime(d.index, utc=True).tz_convert(IST)
    d = d[~d.index.duplicated(keep="last")].sort_index()
    d = d.dropna(subset=["Close", "High", "Low"])
    if len(d) < 100:
        return None
    d["session_date"] = d.index.normalize().tz_localize(None)
    d["bar_of_day"] = d.groupby("session_date").cumcount()
    return d.reset_index(drop=True)
