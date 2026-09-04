"""Fetch NSE's cash-market (equities) bhavcopy for arbitrary historical dates —
the REAL, never-retroactively-adjusted close NSE published that day. Built
2026-09-03 to fix a real, previously-undiscovered bug: option_backtest.py's
pick_contract() compares option strikes (also never adjusted) against
`spot_price` sourced from data_cache (yfinance), which RETROACTIVELY rescales
historical prices for every stock split/bonus after the fact. Any ticker that
split between its trade's entry_date and whenever data_cache was last fetched
gets a systematically wrong reference price — real case found: BEL's
2022-08-23 close shows ₹99.48 in data_cache today (reflecting a ~3x split that
happened later) vs the real, contemporaneous ₹298.45 NSE actually published
that day, causing pick_contract() to select a wildly wrong "5% ITM" strike
(200 instead of ~283.5) since it compared against the wrong spot entirely.
Checked directly: 91 of 562 trades in the current ITM+next-month set (16.2%)
show a strike/spot ratio far outside the expected ~0.90-1.05 band for a
genuine 5%-ITM call, confirming this isn't a one-off.

Two archive formats, tried in order (older format first, since that's what
the bulk of this project's date range — 2022-2023 — needs):
  - Legacy (pre-UDiFF, works at least through 2023): cm{DDMMMYYYY}bhav.csv.zip
  - UDiFF (works from at least Jan 2024 onward): BhavCopy_NSE_CM_0_0_0_{ymd}bhav

NSE rate-limits aggressively on rapid repeated requests (confirmed directly:
a URL that returned 200 started returning 503 after a few rapid follow-up
requests, then 200 again after a short pause) — this fetcher paces requests
with a fixed delay and retries with backoff on 503, not on 404 (a real
non-trading day, e.g. weekend/holiday, isn't a rate-limit and shouldn't be
retried)."""
import io
import sys
import time
import zipfile
import datetime as dt
from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path(__file__).parent / "cash_bhav_cache"
CACHE_DIR.mkdir(exist_ok=True)

LEGACY_URL_TMPL = ("https://nsearchives.nseindia.com/content/historical/EQUITIES/"
                    "{yyyy}/{mon}/cm{ddmmmyyyy}bhav.csv.zip")
UDIFF_URL_TMPL = ("https://nsearchives.nseindia.com/content/cm/"
                   "BhavCopy_NSE_CM_0_0_0_{ymd}_F_0000.csv.zip")
HEADERS = {"User-Agent": "Mozilla/5.0"}
REQUEST_DELAY_S = 1.5
MAX_RETRIES = 4


def _get_with_backoff(url):
    delay = REQUEST_DELAY_S
    for attempt in range(MAX_RETRIES):
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 200:
            return resp
        if resp.status_code in (404,):
            return None  # genuinely not there (holiday/weekend) — don't retry
        time.sleep(delay)
        delay *= 2  # back off harder each retry, NSE's rate-limit is not gentle
    return None


def _parse_legacy(content):
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        with zf.open(zf.namelist()[0]) as f:
            df = pd.read_csv(f)
    df = df[df.SERIES == "EQ"]
    return df[["SYMBOL", "CLOSE"]].rename(columns={"SYMBOL": "ticker", "CLOSE": "close"})


def _parse_udiff(content):
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        with zf.open(zf.namelist()[0]) as f:
            df = pd.read_csv(f)
    df = df[df.SctySrs == "EQ"]
    return df[["TckrSymb", "ClsPric"]].rename(columns={"TckrSymb": "ticker", "ClsPric": "close"})


def fetch_day(day):
    """Returns 'cached' / 'ok (N rows)' / 'no-file' — never raises, so a batch
    run can just log and move on to the next date."""
    ymd = day.strftime("%Y%m%d")
    out_path = CACHE_DIR / f"{ymd}.csv"
    if out_path.exists():
        return "cached"

    legacy_url = LEGACY_URL_TMPL.format(yyyy=day.year, mon=day.strftime("%b").upper(),
                                         ddmmmyyyy=day.strftime("%d%b%Y").upper())
    resp = _get_with_backoff(legacy_url)
    if resp is not None:
        try:
            df = _parse_legacy(resp.content)
        except Exception:
            resp = None
    if resp is None:
        time.sleep(REQUEST_DELAY_S)
        udiff_url = UDIFF_URL_TMPL.format(ymd=ymd)
        resp = _get_with_backoff(udiff_url)
        if resp is None:
            return "no-file"
        df = _parse_udiff(resp.content)

    df.to_csv(out_path, index=False)
    return f"ok ({len(df)} rows)"


def close_on(ticker, date):
    """Look up one ticker's real, unadjusted close on `date` from the cache
    built by this module — returns None if that date hasn't been fetched or
    the ticker isn't in that day's file (e.g., no EQ series that day)."""
    ymd = pd.Timestamp(date).strftime("%Y%m%d")
    path = CACHE_DIR / f"{ymd}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    row = df[df.ticker == ticker]
    return float(row.close.iloc[0]) if len(row) else None


if __name__ == "__main__":
    # every unique entry_date across the swing FO-scoped trade set — this is the
    # exact set of dates option_backtest.py needs a real spot price for.
    trades = pd.read_csv("runs/trades_v28_fo.csv", parse_dates=["entry_date"])
    dates = sorted(trades.entry_date.dt.normalize().unique())
    print(f"fetching {len(dates)} unique dates...")

    counts = {}
    t0 = time.time()
    for i, d in enumerate(dates):
        day = pd.Timestamp(d).to_pydatetime()
        result = fetch_day(day)
        counts[result.split(" ")[0]] = counts.get(result.split(" ")[0], 0) + 1
        if result != "cached":
            time.sleep(REQUEST_DELAY_S)
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(dates)}, {time.time()-t0:.0f}s elapsed, {counts}")

    print(f"done in {time.time()-t0:.0f}s: {counts}")
