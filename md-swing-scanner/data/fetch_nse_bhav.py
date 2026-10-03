"""NSE full cash-market bhavcopy -> data/nse_bhav/{yyyymmdd}.csv (moved 2026-10-03 from
short_discovery/s01_fetch_nse_bhav_full.py + short_discovery/nse_bhav_full/; old path is a symlink).

One file per NIFTY-calendar session, every equity series (EQ/BE/BZ/SM/ST/...), columns:
ticker, series, open, high, low, close, prevclose, volume. Prices are NSE's raw, never-adjusted
prints. PREVCLOSE is NOT adjusted on corporate-action ex-dates (verified: 8 of 769 one-day
>=30% drops) -- use data/nse_corp_actions.csv for ex-dates. See data/README.md.

Legacy archive (cm{DDMMMYYYY}bhav.csv.zip) for dates before 2024-07-08, UDiFF after; URL
templates and backoff reused from fetch_cash_bhav.py. Incremental: dates already on disk are
skipped. Usage: python3 data/fetch_nse_bhav.py [start_yyyy-mm-dd]   (default 2021-11-20)
"""
import io
import sys
import time
import zipfile
import datetime as dt
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import fetch_cash_bhav as fcb  # noqa: E402
from data.paths import DAILY_DIR, NSE_BHAV_DIR  # noqa: E402

NSE_BHAV_DIR.mkdir(exist_ok=True)
COLS = ['ticker', 'series', 'open', 'high', 'low', 'close', 'prevclose', 'volume']


def _legacy(content):
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        d = pd.read_csv(zf.open(zf.namelist()[0]))
    d = d.rename(columns={'SYMBOL': 'ticker', 'SERIES': 'series', 'OPEN': 'open', 'HIGH': 'high', 'LOW': 'low',
                          'CLOSE': 'close', 'PREVCLOSE': 'prevclose', 'TOTTRDQTY': 'volume'})
    return d[COLS]


def _udiff(content):
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        d = pd.read_csv(zf.open(zf.namelist()[0]))
    d = d.rename(columns={'TckrSymb': 'ticker', 'SctySrs': 'series', 'OpnPric': 'open', 'HghPric': 'high',
                          'LwPric': 'low', 'ClsPric': 'close', 'PrvsClsgPric': 'prevclose', 'TtlTradgVol': 'volume'})
    return d[COLS]


def fetch(day):
    path = NSE_BHAV_DIR / (day.strftime('%Y%m%d') + '.csv')
    if path.exists():
        return 'cached'
    legacy_url = fcb.LEGACY_URL_TMPL.format(yyyy=day.year, mon=day.strftime('%b').upper(),
                                            ddmmmyyyy=day.strftime('%d%b%Y').upper())
    udiff_url = fcb.UDIFF_URL_TMPL.format(ymd=day.strftime('%Y%m%d'))
    order = [(udiff_url, _udiff), (legacy_url, _legacy)] if day >= dt.date(2024, 7, 8) else \
            [(legacy_url, _legacy), (udiff_url, _udiff)]
    for url, parser in order:
        r = fcb._get_with_backoff(url)
        if r is not None:
            try:
                parser(r.content).to_csv(path, index=False)
                return 'ok'
            except Exception:  # noqa: BLE001
                pass
        time.sleep(0.5)
    return 'no-file'


if __name__ == '__main__':
    start = pd.Timestamp(sys.argv[1] if len(sys.argv) > 1 else '2021-11-20')
    cal = pd.to_datetime(pd.read_csv(DAILY_DIR / '_NIFTY.csv', usecols=['Date']).Date)
    days = [d.date() for d in cal if d >= start]
    print(f'{len(days)} sessions in range', flush=True)
    counts, t0 = {}, time.time()
    for i, d in enumerate(days):
        res = fetch(d)
        counts[res] = counts.get(res, 0) + 1
        if res == 'no-file':
            print(f'  no-file {d}', flush=True)
        if res != 'cached':
            time.sleep(1.0)
        if (i + 1) % 50 == 0:
            print(f'  {i + 1}/{len(days)}  {time.time() - t0:.0f}s  {counts}', flush=True)
    print(f'done {counts} in {time.time() - t0:.0f}s', flush=True)
