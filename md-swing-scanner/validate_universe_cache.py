"""Post-fetch cache validation (2026-09-29, built during RQ-QS-07U's universe fetch).

Caught a real bug the hard way: A2ZINFRA (listed 2010-12-23) ended up with exactly 1
cached row after the big universe fetch, because fetch_prices.py's retry logic only
re-tries a ticker whose result is fully EMPTY -- a malformed/partial response (a
yfinance-internal error for that specific ticker within a chunk) that leaves even
ONE valid row behind slips through as "not empty," gets written to cache, and looks
like a real (if thin) history unless someone checks the row count against how long
the stock has actually existed.

NOT folded into fetch_prices.py itself on purpose: that module is a generic fetcher
and shouldn't need to know about listing-date metadata (nse_equity_universe.csv is a
research-layer concept, not a fetch-layer one) -- keeping this as a separate,
reusable post-fetch check is the cleaner boundary, and it's meant to be rerun after
ANY large fetch, not just tonight's.

Deliberately conservative: only flags tickers listed well before the 5-year window
(so a brand-new listing's genuinely tiny row count is never a false positive) with a
row count far below what continuous daily trading since listing would produce.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd
from data.paths import DAILY_DIR

MIN_ROWS_FLOOR = 200  # far below a real ~1,240-day 5y history, but well above what a
                       # genuinely thin/illiquid (but real) stock would still show


def validate(universe_file="nse_equity_universe.csv", cutoff_days=5 * 365):
    uni = pd.read_csv(universe_file, parse_dates=["listing_date"])
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=cutoff_days)
    old_enough = uni[uni.listing_date < cutoff]

    rows = []
    for t in old_enough.ticker:
        p = DAILY_DIR / f"{t}.csv"
        n = (sum(1 for _ in open(p)) - 1) if os.path.exists(p) else None
        rows.append((t, n))
    df = pd.DataFrame(rows, columns=["ticker", "n_rows"])
    missing = df[df.n_rows.isna()]
    suspicious = df[df.n_rows.notna() & (df.n_rows < MIN_ROWS_FLOOR)]
    return old_enough, missing, suspicious


if __name__ == "__main__":
    old_enough, missing, suspicious = validate()
    print(f"Checked {len(old_enough)} tickers listed >5y ago (should have a near-full history).")
    print(f"Missing cache file entirely: {len(missing)}")
    if len(missing):
        print(missing.ticker.tolist())
    print(f"Suspiciously incomplete (<{MIN_ROWS_FLOOR} rows): {len(suspicious)}")
    if len(suspicious):
        print(suspicious.sort_values("n_rows").to_string(index=False))
    else:
        print("Clean -- no incomplete long-established histories found.")
