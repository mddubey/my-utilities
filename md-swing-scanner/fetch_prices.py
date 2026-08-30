from datetime import timedelta
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
    CACHE_DIR.mkdir(exist_ok=True)
    last_dates = {t: _last_cached_date(t) for t in tickers}
    new_tickers = [t for t in tickers if last_dates[t] is None]
    existing_tickers = [t for t in tickers if last_dates[t] is not None]
    ok, empty = [], []

    if new_tickers:
        yf_tickers = [f"{t}.NS" for t in new_tickers]
        data = yf.download(yf_tickers, period=PERIOD, interval="1d", group_by="ticker",
                            threads=True, progress=False, auto_adjust=False)
        for t, yft in zip(new_tickers, yf_tickers):
            df = data[yft].dropna(how="all")
            if df.empty:
                empty.append(t)
                continue
            df.to_csv(CACHE_DIR / f"{t}.csv")
            ok.append(t)

    if existing_tickers:
        start = min(last_dates[t] for t in existing_tickers) + timedelta(days=1)
        yf_tickers = [f"{t}.NS" for t in existing_tickers]
        data = yf.download(yf_tickers, start=start.strftime("%Y-%m-%d"), interval="1d",
                            group_by="ticker", threads=True, progress=False, auto_adjust=False)
        for t, yft in zip(existing_tickers, yf_tickers):
            new_df = data[yft].dropna(how="all")
            new_df = new_df[new_df.index > last_dates[t]]
            if not new_df.empty:
                new_df.to_csv(CACHE_DIR / f"{t}.csv", mode="a", header=False)
            ok.append(t)  # already up to date is success, not a failure

    return ok, empty


if __name__ == "__main__":
    tickers = pd.read_csv("fo_universe.csv", header=None)[0].tolist()
    ok, empty = fetch_all(tickers)
    print(f"{len(ok)} fetched, {len(empty)} empty/failed: {empty}")
