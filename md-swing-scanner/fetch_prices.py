from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).parent / "data_cache"
PERIOD = "5y"  # only used for a ticker with no cache yet — everything else fetches
                # incrementally (see fetch_all), since re-pulling 5 years daily for the
                # whole universe was wasteful and fetch_stock_options.py already proved
                # the "skip what's cached" pattern out for the options side

IST = ZoneInfo("Asia/Kolkata")
SAME_DAY_SAFE_HOUR = 16  # NSE closes continuous trading at 15:30 IST, but the OFFICIAL
                          # closing-auction print isn't reliably settled on Yahoo's
                          # backend right away — confirmed directly (2026-08-31): a
                          # fetch run before this hour returned a real-looking (non-
                          # null) Close for "today" that was still wrong, silently
                          # revised by ~1% (AUROPHARMA 1699.30 -> 1717.00, LTF 310.85
                          # -> 321.00) once fetched again later the same day. Since the
                          # cache is purely incremental, that stale value would have
                          # been locked in FOREVER. Before this hour IST, treat today as
                          # not-yet-fetchable at all — same treatment as a future date —
                          # rather than risk caching a value that's still in flux.


def _now_ist():
    return datetime.now(IST)


def _safe_today():
    """The most recent date it's safe to treat as a genuinely settled close. Equals
    today only at/after SAME_DAY_SAFE_HOUR IST; before that, today doesn't count yet."""
    now = _now_ist()
    today = now.date()
    return today if now.hour >= SAME_DAY_SAFE_HOUR else today - timedelta(days=1)


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
    safe_today = pd.Timestamp(_safe_today())
    last_dates = {t: _last_cached_date(t) for t in tickers}
    new_tickers = [t for t in tickers if last_dates[t] is None]
    existing_tickers = [t for t in tickers if last_dates[t] is not None]
    result = {"new": [], "updated": [], "current": [], "empty": []}

    if new_tickers:
        yf_tickers = [f"{t}.NS" for t in new_tickers]
        data = yf.download(yf_tickers, period=PERIOD, interval="1d", group_by="ticker",
                            threads=True, progress=False, auto_adjust=False)
        for t, yft in zip(new_tickers, yf_tickers):
            # dropna(subset=["Close"]), not how="all" — a row fetched while the market's
            # still open (or right at close, before yfinance settles the final print)
            # can have real Open/High/Low/Volume but a still-null Close; how="all" let
            # that row through, and since it's incremental-only, it then poisoned the
            # cache PERMANENTLY (next run's start date skips right past it). Confirmed
            # 2026-08-31: 184/500 tickers had exactly this on 2026-08-28, silently
            # breaking that day's RS-rating calc (relative_strength.py) and any pattern
            # check depending on Close for those tickers, with zero visible error.
            df = data[yft].dropna(subset=["Close"])
            df = df[df.index <= safe_today]  # today isn't safe to trust before SAME_DAY_SAFE_HOUR
            if df.empty:
                result["empty"].append(t)
                continue
            df.to_csv(CACHE_DIR / f"{t}.csv")
            result["new"].append(t)

    if existing_tickers:
        start = min(last_dates[t] for t in existing_tickers) + timedelta(days=1)
        if start.date() > safe_today.date():
            # already fetched through the safe date (or later) — a same-day rerun, OR
            # a rerun before SAME_DAY_SAFE_HOUR with yesterday already cached. Either
            # way nothing NEW can safely exist yet, so skip the network call entirely
            # rather than ask and get an empty (or worse, unsafe) answer back. This
            # does NOT cover weekends/holidays before the first same-day run (start is
            # still <= safe_today then) — telling those apart needs an NSE trading-day
            # calendar, which isn't worth building just to save one wasted API call.
            result["current"].extend(existing_tickers)
        else:
            yf_tickers = [f"{t}.NS" for t in existing_tickers]
            data = yf.download(yf_tickers, start=start.strftime("%Y-%m-%d"), interval="1d",
                                group_by="ticker", threads=True, progress=False, auto_adjust=False)
            for t, yft in zip(existing_tickers, yf_tickers):
                new_df = data[yft].dropna(subset=["Close"])  # see new_tickers branch above
                new_df = new_df[(new_df.index > last_dates[t]) & (new_df.index <= safe_today)]
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
