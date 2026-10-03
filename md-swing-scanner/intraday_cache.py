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
import time
from pathlib import Path

import pandas as pd

from fetch_prices import _chunked_download, _latest_nifty_session, _safe_today
from data.paths import INTRADAY_5M_DIR, holds_full_session

CACHE_DIR = INTRADAY_5M_DIR
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
        tickers = _load_universe("nse_equity")  # 2026-10-03: fetch everything by default (data/README.md)

    new_tickers = [t for t in tickers if not _cache_path(t).exists()]
    existing_tickers = [t for t in tickers if _cache_path(t).exists()]
    # 2026-10-03: skip stocks that already hold the latest real NSE session (Nifty check, see
    # fetch_prices._latest_nifty_session) -- weekend/holiday runs no longer re-download ~2,300 stocks.
    # Lookup failure -> session None -> nothing skipped (old behaviour).
    session = _latest_nifty_session(pd.Timestamp(_safe_today()))
    n_current = 0
    if session is not None:
        behind = [t for t in existing_tickers if not holds_full_session(_cache_path(t), session)]
        n_current = len(existing_tickers) - len(behind)
        existing_tickers = behind
        if progress:
            print(f"latest NSE session {session.date()}: {n_current} stocks already hold it, skipped", flush=True)

    def _extract(dfs, t):
        df = dfs.get(t, pd.DataFrame())
        if df.empty:
            return df
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        df.index.name = "Datetime"
        return df

    n_new = n_updated = n_failed = 0

    def _save_new(dfs, batch):
        """Write fresh backfills; return the tickers that came back empty."""
        nonlocal n_new
        empty = []
        for t in batch:
            df = _extract(dfs, t)
            if df.empty:
                empty.append(t)
                continue
            df.to_csv(_cache_path(t))
            n_new += 1
        return empty

    def _merge_topups(dfs, batch):
        """Merge top-ups into existing files; return the tickers whose top-up came back empty.
        An empty top-up is NOT counted as updated (2026-10-02): under Yahoo throttling every
        ticker in a chunk can come back empty with no error, which used to be silently
        rewritten as-is and reported as 'updated'."""
        nonlocal n_updated, n_failed
        empty = []
        for t in batch:
            fresh = _extract(dfs, t)
            if fresh.empty:
                empty.append(t)
                continue
            path = _cache_path(t)
            try:
                existing = pd.read_csv(path, index_col="Datetime", parse_dates=True)
            except Exception as e:
                print(f"{t}: failed to read existing cache ({e})")
                n_failed += 1
                continue
            combined = pd.concat([existing, fresh])
            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
            combined.to_csv(path)
            n_updated += 1
        return empty

    retry_new, retry_topup = [], []
    if new_tickers:
        if progress:
            print(f"backfilling {len(new_tickers)} new tickers (60d)...", flush=True)
        dfs = _chunked_download([f"{t}.NS" for t in new_tickers], period="60d",
                                  interval="5m", group_by="ticker", progress=progress)
        retry_new = _save_new(dfs, new_tickers)

    if existing_tickers:
        if progress:
            print(f"topping up {len(existing_tickers)} existing tickers ({TOPUP_PERIOD})...", flush=True)
        dfs = _chunked_download([f"{t}.NS" for t in existing_tickers], period=TOPUP_PERIOD,
                                  interval="5m", group_by="ticker", progress=progress)
        retry_topup = _merge_topups(dfs, existing_tickers)

    # One retry pass for anything that came back empty, slower and in smaller chunks.
    # Many empties at once looks like Yahoo throttling, so back off longer first.
    # Genuinely suspended/delisted names stay empty after the retry -- that's normal.
    n_retry = len(retry_new) + len(retry_topup)
    if n_retry:
        wait = 90 if n_retry > 0.25 * len(tickers) else 20
        if progress:
            print(f"{n_retry} came back empty; waiting {wait}s, then retrying in chunks of 10...", flush=True)
        time.sleep(wait)
        if retry_new:
            dfs = _chunked_download([f"{t}.NS" for t in retry_new], chunk_size=10, pause=5,
                                      period="60d", interval="5m", group_by="ticker", progress=progress)
            retry_new = _save_new(dfs, retry_new)
        if retry_topup:
            dfs = _chunked_download([f"{t}.NS" for t in retry_topup], chunk_size=10, pause=5,
                                      period=TOPUP_PERIOD, interval="5m", group_by="ticker", progress=progress)
            retry_topup = _merge_topups(dfs, retry_topup)
    still_empty = retry_new + retry_topup
    n_failed += len(still_empty)

    if progress:
        print(f"done: {n_new} new, {n_updated} updated, {n_current} already current, {n_failed} failed/empty after retry "
              f"(of {len(tickers)} requested)", flush=True)
        if still_empty:
            print(f"still empty after retry ({len(still_empty)}): "
                  f"{', '.join(still_empty[:30])}{' ...' if len(still_empty) > 30 else ''}", flush=True)
    return dict(new=n_new, updated=n_updated, current=n_current, failed=n_failed, total=len(tickers), still_empty=still_empty)


def load(ticker):
    path = _cache_path(ticker)
    if not path.exists():
        raise FileNotFoundError(f"no intraday cache for {ticker} — run intraday_cache.refresh()")
    return pd.read_csv(path, index_col="Datetime", parse_dates=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", choices=list(UNIVERSE_FILES), default="nse_equity",
                         help="nse_equity (default since 2026-10-03: fetch everything, ~2,300 NSE-listed "
                              "equity names) or nifty500 (500 tickers, the pre-2026-10-03 default)")
    args = parser.parse_args()
    refresh(tickers=_load_universe(args.universe), progress=True)
