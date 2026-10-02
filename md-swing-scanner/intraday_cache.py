"""5-minute intraday bar cache — built to survive past yfinance's own rolling
60-day retention window (confirmed 2026-09-01: any request older than 60 days is
rejected outright, "The requested range must be within the last 60 days"). Once a
day falls out of that window it's gone from Yahoo for good unless we've already
saved it ourselves — this module's whole point is to own that data permanently
instead of losing it day by day.

Motivated directly by the Closing Auction Session (CAS, effective 2026-08-03,
Phase 1 = F&O stocks only — see FINDINGS.md): CAS's transition sits inside the
still-retrievable window right now, but is aging out day by day. Scoped to the
FULL nifty500_universe.csv (500 tickers) by default, not just fo_universe.csv's
210 — even though CAS Phase 1 only covers F&O names, daily_scan.py's real
candidates span the whole universe (several real recent ones, e.g.
KAJARIACER/NAVINFLUOR/USHAMART, are [NO OPTIONS]), and non-F&O tickers are a
genuinely useful CONTROL GROUP for telling whether any effect found is
CAS-specific or just general market behavior. Pass tickers=<list> (or run
`python3 intraday_cache.py --universe nse_equity` from the CLI) to widen scope to
`nse_equity_universe.csv`'s 2,327 NSE-listed tickers (RQ-QS-07U, 2026-09-29) — the
default stays nifty500_universe.csv so no existing caller silently changes scope.

refresh() is safe to run repeatedly: a ticker with no cache yet gets a full 60-day
backfill; an already-cached ticker only needs a short overlapping top-up window
(default 10 days, comfortably more than any realistic gap between runs) merged
into what's already saved — new bars get appended, everything already captured
stays, even once yfinance itself would no longer serve it.

Fetching reuses fetch_prices.py's own _chunked_download (2026-09-29,
PARKING_LOT #10) rather than re-deriving it — that fix was found the hard way:
a single yf.download(threads=True) call across a wide ticker list silently drops
tickers under Yahoo throttling, with no error, indistinguishable from "genuinely
no new data" until hand-checked. This module hit exactly that failure mode once
already (see the module's own git history) before fetch_prices.py's chunked
retry pattern existed; reusing it here instead of re-inventing a second, weaker
throttling fix.

A real, permanent ceiling this can't work around: any ticker with no existing
cache file only ever gets the trailing 60 days back on its first fetch — that's
Yahoo's hard limit, not a bug here. The current 500-ticker cache is ~3.5 months
deep only because refresh() has been run repeatedly since 2026-06-10; a newly
widened ticker starts at zero and only builds comparable depth by being fetched
daily from here forward. There is no way to backfill further than 60 days for a
ticker not already being tracked."""
import argparse
from pathlib import Path

import pandas as pd

from fetch_prices import _chunked_download

CACHE_DIR = Path(__file__).parent / "intraday_cache"
TOPUP_PERIOD = "10d"  # comfortably more than any realistic gap between refresh() runs

UNIVERSE_FILES = {
    "nifty500": "nifty500_universe.csv",   # default — matches every existing caller's scope
    "nse_equity": "nse_equity_universe.csv",  # 2,327 tickers, RQ-QS-07U (2026-09-29)
}


def _load_universe(name):
    path = Path(__file__).parent / UNIVERSE_FILES[name]
    if name == "nse_equity":
        return pd.read_csv(path)["ticker"].tolist()  # has a header row + extra metadata columns
    return pd.read_csv(path, header=None)[0].tolist()


def _cache_path(ticker):
    return CACHE_DIR / f"{ticker}.csv"


def refresh(tickers=None, progress=False):
    CACHE_DIR.mkdir(exist_ok=True)
    if tickers is None:
        tickers = _load_universe("nifty500")

    new_tickers = [t for t in tickers if not _cache_path(t).exists()]
    existing_tickers = [t for t in tickers if _cache_path(t).exists()]

    def _extract(dfs, t):
        df = dfs.get(t, pd.DataFrame())
        if df.empty:
            return df
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        df.index.name = "Datetime"
        return df

    n_new = n_updated = n_failed = 0

    if new_tickers:
        if progress:
            print(f"backfilling {len(new_tickers)} new tickers (60d)...", flush=True)
        dfs = _chunked_download([f"{t}.NS" for t in new_tickers], period="60d",
                                  interval="5m", group_by="ticker", progress=progress)
        for t in new_tickers:
            df = _extract(dfs, t)
            if df.empty:
                n_failed += 1
                continue
            df.to_csv(_cache_path(t))
            n_new += 1

    if existing_tickers:
        if progress:
            print(f"topping up {len(existing_tickers)} existing tickers ({TOPUP_PERIOD})...", flush=True)
        dfs = _chunked_download([f"{t}.NS" for t in existing_tickers], period=TOPUP_PERIOD,
                                  interval="5m", group_by="ticker", progress=progress)
        for t in existing_tickers:
            fresh = _extract(dfs, t)
            path = _cache_path(t)
            try:
                existing = pd.read_csv(path, index_col="Datetime", parse_dates=True)
            except Exception as e:
                print(f"{t}: failed to read existing cache ({e})")
                n_failed += 1
                continue
            combined = pd.concat([existing, fresh]) if not fresh.empty else existing
            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
            if not combined.empty:
                combined.to_csv(path)
                n_updated += 1
            else:
                n_failed += 1

    if progress:
        print(f"done: {n_new} new, {n_updated} updated, {n_failed} failed/empty "
              f"(of {len(tickers)} requested)", flush=True)
    return dict(new=n_new, updated=n_updated, failed=n_failed, total=len(tickers))


def load(ticker):
    path = _cache_path(ticker)
    if not path.exists():
        raise FileNotFoundError(f"no intraday cache for {ticker} — run intraday_cache.refresh()")
    return pd.read_csv(path, index_col="Datetime", parse_dates=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", choices=list(UNIVERSE_FILES), default="nifty500",
                         help="nifty500 (default, 500 tickers, matches every existing caller's "
                              "scope) or nse_equity (2,327 tickers, RQ-QS-07U's full NSE-listed "
                              "equity universe)")
    args = parser.parse_args()
    refresh(tickers=_load_universe(args.universe), progress=True)
