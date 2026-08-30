from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).parent / "data_cache"
PERIOD = "5y"  # only used for a ticker with no cache yet — everything else fetches
                # incrementally (see fetch_all), since re-pulling 5 years daily for the
                # whole universe was wasteful and fetch_stock_options.py already proved
                # the "skip what's cached" pattern out for the options side


def _last_cached_date(ticker):
    path = CACHE_DIR / f"{ticker}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, index_col="Date", parse_dates=True)
    return df.index.max() if len(df) else None


def fetch_all(tickers):
    """Returns {'new': [...], 'updated': [...], 'current': [...], 'empty': [...]} —
    kept as 4 distinct buckets (not collapsed into one "ok" list) after a real,
    confusing moment (2026-08-30): a run on a Sunday printed "210 fetched" when in
    truth every single ticker was a no-op (no trading day since the prior Friday) —
    correct behavior, but the old "ok"/"empty" split couldn't say so honestly."""
    CACHE_DIR.mkdir(exist_ok=True)
    last_dates = {t: _last_cached_date(t) for t in tickers}
    new_tickers = [t for t in tickers if last_dates[t] is None]
    existing_tickers = [t for t in tickers if last_dates[t] is not None]
    result = {"new": [], "updated": [], "current": [], "empty": []}

    if new_tickers:
        yf_tickers = [f"{t}.NS" for t in new_tickers]
        data = yf.download(yf_tickers, period=PERIOD, interval="1d", group_by="ticker",
                            threads=True, progress=False, auto_adjust=False)
        for t, yft in zip(new_tickers, yf_tickers):
            df = data[yft].dropna(how="all")
            if df.empty:
                result["empty"].append(t)
                continue
            df.to_csv(CACHE_DIR / f"{t}.csv")
            result["new"].append(t)

    if existing_tickers:
        start = min(last_dates[t] for t in existing_tickers) + timedelta(days=1)
        if start.date() > date.today():
            # already fetched through today (or later) — a same-day rerun. No trading
            # day can possibly exist yet in the future, so skip the network call
            # entirely rather than ask and get an empty answer back. This does NOT
            # cover weekends/holidays before the first same-day run (start is still
            # <= today then) — telling those apart needs an NSE trading-day calendar,
            # which isn't worth building just to save one wasted API call.
            result["current"].extend(existing_tickers)
        else:
            yf_tickers = [f"{t}.NS" for t in existing_tickers]
            data = yf.download(yf_tickers, start=start.strftime("%Y-%m-%d"), interval="1d",
                                group_by="ticker", threads=True, progress=False, auto_adjust=False)
            for t, yft in zip(existing_tickers, yf_tickers):
                new_df = data[yft].dropna(how="all")
                new_df = new_df[new_df.index > last_dates[t]]
                if not new_df.empty:
                    new_df.to_csv(CACHE_DIR / f"{t}.csv", mode="a", header=False)
                    result["updated"].append(t)
                else:
                    result["current"].append(t)

    return result


if __name__ == "__main__":
    # NIFTY 500 — the pure-swing universe (superset of fo_universe.csv's 210 F&O names,
    # so this single refresh covers both the swing scanner and the options layer's needs)
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    result = fetch_all(tickers)
    print(f"{len(result['new'])} new, {len(result['updated'])} updated, "
          f"{len(result['current'])} already current, "
          f"{len(result['empty'])} empty/failed: {result['empty']}")
