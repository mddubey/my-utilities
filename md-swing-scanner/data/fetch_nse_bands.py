"""NSE point-in-time price-band lists -> data/nse_bands/{yyyymmdd}.csv (moved 2026-10-03 from
short_discovery/s01_fetch_nse_bands.py + short_discovery/nse_bands/; old path is a symlink).

Source: nsearchives.nseindia.com/content/equities/sec_list_DDMMYYYY.csv. Columns kept:
Symbol, Series, Band ('2','5','10','20','40' or 'No Band').
CONVENTION (verified by hand 2026-10-02): the file dated D is published after D's close and
holds the bands EFFECTIVE FOR THE NEXT SESSION, i.e. band(session d) = sec_list(session d-1).
Evidence: sec_list_04042025 already shows the 10->20 changes listed in
eq_band_changes_07042025; AAREYDRUGS locked at exactly -5.01% on 2025-04-07 under its new
5% band; ANANTRAJ printed -17.6% under its new 20% band. 'No Band' ~= F&O names (99.9%
agreement with options listings). NSE returns empty files on a few dates (2021-12-09,
2022-05-10, 2022-07-12); those are logged as no-file, never written.
Incremental. Usage: python3 data/fetch_nse_bands.py [start_yyyy-mm-dd]   (default 2021-11-20)
"""
import io
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from data.paths import DAILY_DIR, NSE_BANDS_DIR  # noqa: E402

NSE_BANDS_DIR.mkdir(exist_ok=True)
URL = 'https://nsearchives.nseindia.com/content/equities/sec_list_{}.csv'
H = {'User-Agent': 'Mozilla/5.0'}


def get(url):
    delay = 2.0
    for _ in range(5):
        r = requests.get(url, headers=H, timeout=30)
        if r.status_code == 200:
            return r
        if r.status_code == 404:
            return None
        time.sleep(delay)
        delay *= 2
    return None


if __name__ == '__main__':
    start = pd.Timestamp(sys.argv[1] if len(sys.argv) > 1 else '2021-11-20')
    cal = pd.to_datetime(pd.read_csv(DAILY_DIR / '_NIFTY.csv', usecols=['Date']).Date)
    days = [d for d in cal if d >= start]
    counts, t0 = {}, time.time()
    for i, d in enumerate(days):
        p = NSE_BANDS_DIR / (d.strftime('%Y%m%d') + '.csv')
        if p.exists():
            res = 'cached'
        else:
            r = get(URL.format(d.strftime('%d%m%Y')))
            if r is None or not r.text.strip():
                res = 'no-file'
                print('  no-file/empty', d.date(), flush=True)
            else:
                x = pd.read_csv(io.StringIO(r.text))
                x.columns = [c.strip() for c in x.columns]
                x[['Symbol', 'Series', 'Band']].to_csv(p, index=False)
                res = 'ok'
            time.sleep(2.0)
        counts[res] = counts.get(res, 0) + 1
        if (i + 1) % 50 == 0:
            print(f'  {i + 1}/{len(days)} {time.time() - t0:.0f}s {counts}', flush=True)
    print('done', counts, flush=True)
