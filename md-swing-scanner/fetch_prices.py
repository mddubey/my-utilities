from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).parent / "data_cache"
PERIOD = "5y"


def fetch_all(tickers):
    yf_tickers = [f"{t}.NS" for t in tickers]
    data = yf.download(yf_tickers, period=PERIOD, interval="1d", group_by="ticker",
                        threads=True, progress=False, auto_adjust=False)

    CACHE_DIR.mkdir(exist_ok=True)
    ok, empty = [], []
    for t, yft in zip(tickers, yf_tickers):
        df = data[yft].dropna(how="all")
        if df.empty:
            empty.append(t)
            continue
        df.to_csv(CACHE_DIR / f"{t}.csv")
        ok.append(t)
    return ok, empty


if __name__ == "__main__":
    tickers = pd.read_csv("fo_universe.csv", header=None)[0].tolist()
    ok, empty = fetch_all(tickers)
    print(f"{len(ok)} fetched, {len(empty)} empty/failed: {empty}")
