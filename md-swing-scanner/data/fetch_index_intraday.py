"""NIFTY / BANKNIFTY intraday bars from Yahoo -> data/index_intraday/ (2026-10-03; these files were first written
inline by intradaygeeks_replica research, which still reads them via the index_1h/ symlink). Merges new bars into the
existing files, so history Yahoo no longer serves is kept: 60m (Yahoo serves roughly 730 days) and 5m (60 days).
File names keep their original form (_NIFTY_5m_60d.csv now holds everything accumulated, not just 60 days).
Usage: python3 data/fetch_index_intraday.py"""
from pathlib import Path
import pandas as pd
import yfinance as yf

OUT = Path(__file__).resolve().parent / "index_intraday"; OUT.mkdir(exist_ok=True)
JOBS = [("^NSEI", "60m", "730d", "_NIFTY_1h.csv"), ("^NSEBANK", "60m", "730d", "_BANKNIFTY_1h.csv"),
        ("^NSEI", "5m", "60d", "_NIFTY_5m_60d.csv")]

for sym, interval, period, name in JOBS:
    new = yf.download(sym, period=period, interval=interval, auto_adjust=False, progress=False, multi_level_index=False)
    new = new.dropna(subset=["Close"])
    if new.empty:
        print(f"{name}: Yahoo returned nothing -- kept existing file"); continue
    new.index = pd.to_datetime(new.index, utc=True); new.index.name = "Datetime"
    p = OUT / name
    if p.exists():
        old = pd.read_csv(p, index_col=0); old.index = pd.to_datetime(old.index, utc=True)
        new = pd.concat([old, new[old.columns.intersection(new.columns)]])
        new = new[~new.index.duplicated(keep="last")].sort_index()
    new.to_csv(p)
    print(f"{name}: {len(new)} bars, {new.index[0]} -> {new.index[-1]}")
