import io
import sys
import zipfile
import datetime as dt
from pathlib import Path

import pandas as pd
import requests

from option_backtest import OPT_CACHE_DIR, COLS

URL_TMPL = ("https://nsearchives.nseindia.com/content/historical/DERIVATIVES/"
            "{yyyy}/{mon}/fo{ddmmmyyyy}bhav.csv.zip")
HEADERS = {"User-Agent": "Mozilla/5.0"}

# NSE's pre-UDiFF bhavcopy (discontinued July 2024, migration to the new format
# started Jan 2024 — see fetch_stock_options.py) never carried lot size at all;
# it's contract-level metadata NSE publishes separately (and doesn't archive by
# date — checked 2026-08-31, no dated historical lot-size file exists). Per
# explicit instruction: backfill with the single lot size each ticker had in the
# EARLIEST UDiFF-era cached day it appears in — this only affects position
# SIZING in portfolio.py, not the underlying option % return, which is what the
# raw per-trade backtest actually measures. Real lot sizes do change over time
# (SEBI revises them periodically to keep contract value in a target band), so
# this is an approximation, not a real historical value — acceptable per the
# user's own framing ("just a position sizing thing which gets better").
RENAME = {
    "TIMESTAMP": "TradDt", "SYMBOL": "TckrSymb", "EXPIRY_DT": "XpryDt",
    "STRIKE_PR": "StrkPric", "OPTION_TYP": "OptnTp", "OPEN": "OpnPric",
    "HIGH": "HghPric", "LOW": "LwPric", "CLOSE": "ClsPric",
    "OPEN_INT": "OpnIntrst", "CONTRACTS": "TtlTradgVol",
}


def build_lot_size_map():
    """One lot size per ticker, from the first UDiFF-era (2024+) cached day it
    appears in — 'we only need one', per instruction, not a real time series."""
    lot_map = {}
    fo_tickers = set(pd.read_csv(Path(__file__).parent / "fo_universe.csv", header=None)[0])
    for f in sorted(OPT_CACHE_DIR.glob("2024*.csv")):
        df = pd.read_csv(f, usecols=["TckrSymb", "NewBrdLotQty", "FinInstrmTp"])
        df = df[df.FinInstrmTp == "STO"]
        for t, lot in df.groupby("TckrSymb").NewBrdLotQty.first().items():
            lot_map.setdefault(t, lot)
        if fo_tickers <= lot_map.keys():
            break
    return lot_map


def old_url(day):
    return URL_TMPL.format(yyyy=day.year, mon=day.strftime("%b").upper(),
                            ddmmmyyyy=day.strftime("%d%b%Y").upper())


def normalize(df, lot_map):
    """Old-format -> same column names/shapes load_day() already expects, so
    nothing downstream (option_backtest.py, portfolio.py) needs to change."""
    df = df[df.INSTRUMENT == "OPTSTK"].rename(columns=RENAME)
    df["FinInstrmTp"] = "STO"
    df["TradDt"] = pd.to_datetime(df.TradDt, format="%d-%b-%Y")
    df["XpryDt"] = pd.to_datetime(df.XpryDt, format="%d-%b-%Y")
    df["NewBrdLotQty"] = df.TckrSymb.map(lot_map)
    df = df.dropna(subset=["NewBrdLotQty"])  # no reference lot size at all -> can't size it, drop
    return df[COLS + ["FinInstrmTp"]]


def fetch_day(day, lot_map):
    ymd = day.strftime("%Y%m%d")
    out_path = OPT_CACHE_DIR / f"{ymd}.csv"
    if out_path.exists():
        return "cached"

    resp = requests.get(old_url(day), headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        return "no-file"

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open(zf.namelist()[0]) as f:
            raw = pd.read_csv(f)

    df = normalize(raw, lot_map)
    df.to_csv(out_path, index=False)
    return f"ok ({len(df)} rows)"


if __name__ == "__main__":
    start = dt.date.fromisoformat(sys.argv[1])
    end = dt.date.fromisoformat(sys.argv[2])

    lot_map = build_lot_size_map()
    print(f"lot-size reference: {len(lot_map)} tickers", flush=True)

    day = start
    n_ok = n_skip = 0
    while day <= end:
        if day.weekday() < 5:
            status = fetch_day(day, lot_map)
            if status == "no-file":
                n_skip += 1
            else:
                n_ok += 1
            print(f"{day} {status}", flush=True)
        day += dt.timedelta(days=1)
    print(f"\ndone: {n_ok} days fetched/cached, {n_skip} non-trading days")
