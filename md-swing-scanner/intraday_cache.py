"""5-minute intraday bar cache — built to survive past yfinance's own rolling
60-day retention window (confirmed 2026-09-01: any request older than 60 days is
rejected outright, "The requested range must be within the last 60 days"). Once a
day falls out of that window it's gone from Yahoo for good unless we've already
saved it ourselves — this module's whole point is to own that data permanently
instead of losing it day by day.

Motivated directly by the Closing Auction Session (CAS, effective 2026-08-03,
Phase 1 = F&O stocks only — see FINDINGS.md): CAS's transition sits inside the
still-retrievable window right now, but is aging out day by day. Scoped to the
FULL nifty500_universe.csv (500 tickers), not just fo_universe.csv's 210 — even
though CAS Phase 1 only covers F&O names, daily_scan.py's real candidates span the
whole universe (several real recent ones, e.g. KAJARIACER/NAVINFLUOR/USHAMART,
are [NO OPTIONS]), and non-F&O tickers are a genuinely useful CONTROL GROUP for
telling whether any effect found is CAS-specific or just general market behavior.

refresh() is safe to run repeatedly: a ticker with no cache yet gets a full 60-day
backfill; an already-cached ticker only needs a short overlapping top-up window
(default 10 days, comfortably more than any realistic gap between runs) merged
into what's already saved — new bars get appended, everything already captured
stays, even once yfinance itself would no longer serve it."""
from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).parent / "intraday_cache"
TOPUP_PERIOD = "10d"  # comfortably more than any realistic gap between refresh() runs


def _flatten(df):
    df = df.copy()
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def _fetch(ticker, period):
    df = yf.download(f"{ticker}.NS", period=period, interval="5m",
                      progress=False, auto_adjust=False)
    if df.empty:
        return df
    df = _flatten(df)
    df.index.name = "Datetime"
    return df[["Open", "High", "Low", "Close", "Volume"]]


def refresh(tickers=None):
    CACHE_DIR.mkdir(exist_ok=True)
    if tickers is None:
        tickers = pd.read_csv(Path(__file__).parent / "nifty500_universe.csv", header=None)[0].tolist()

    for i, t in enumerate(tickers):
        path = CACHE_DIR / f"{t}.csv"
        try:
            if path.exists():
                existing = pd.read_csv(path, index_col="Datetime", parse_dates=True)
                fresh = _fetch(t, TOPUP_PERIOD)
                if not fresh.empty:
                    combined = pd.concat([existing, fresh])
                    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
                else:
                    combined = existing
            else:
                combined = _fetch(t, "60d")
            if not combined.empty:
                combined.to_csv(path)
        except Exception as e:
            print(f"{t}: failed ({e})")
        if (i + 1) % 25 == 0:
            print(f"{i + 1}/{len(tickers)}", flush=True)


def load(ticker):
    path = CACHE_DIR / f"{ticker}.csv"
    if not path.exists():
        raise FileNotFoundError(f"no intraday cache for {ticker} — run intraday_cache.refresh()")
    return pd.read_csv(path, index_col="Datetime", parse_dates=True)


if __name__ == "__main__":
    refresh()
