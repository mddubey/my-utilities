"""Shared fix for every ORB script (2026-10-12): Yahoo's 5-min 09:15 bar 'Open' is not the official NSE open (equal on only 11% of
days). read5_official() returns a stock's 5-min bars with each day's 09:15 bar corrected the way Dhan / TradingView draw it:
Open = the official open (Yahoo daily open, = NSE bhavcopy open on 100% of days), High / Low extended to include it."""
import pandas as pd
from data.paths import INTRADAY_5M_DIR, DAILY_DIR
_cache = {}


def read5_official(t):
    if t in _cache: return _cache[t].copy()
    m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
    try:
        od = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).Open
        first = m.index.strftime("%H:%M") == "09:15"; oo = od.reindex(m.index[first].normalize()).values
        ok = pd.notna(oo); rows = m.index[first][ok]
        m.loc[rows, "Open"] = oo[ok]
        m.loc[rows, "High"] = m.loc[rows, "High"].where(m.loc[rows, "High"] >= oo[ok], oo[ok])
        m.loc[rows, "Low"] = m.loc[rows, "Low"].where(m.loc[rows, "Low"] <= oo[ok], oo[ok])
    except FileNotFoundError: pass
    _cache[t] = m; return m.copy()
