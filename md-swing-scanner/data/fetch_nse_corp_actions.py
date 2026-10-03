"""NSE corporate-actions list -> data/nse_corp_actions.csv (moved 2026-10-03 from
short_discovery/s01_fetch_nse_corp_actions.py + short_discovery/s01_nse_corp_actions.csv;
old path is a symlink).

Source: nseindia.com/api/corporates-corporateActions (needs the homepage cookie first),
fetched month by month for index=equities and index=sme. Columns: symbol, series, exDate,
subject, index. Needed because NSE bhavcopy PREVCLOSE is not adjusted on ex-dates, so the
bhavcopy alone cannot identify splits/bonuses/rights/demergers. Price-affecting subjects
(regex used by short_discovery): split|sub-division|bonus|rights|demerger|scheme|
arrangement|amalgamation|consolidation|reduction; dividends are separate ('dividend').
Rewrites the whole file each run (small: ~12.5k rows for 2021-11 .. 2026-10).
Usage: python3 data/fetch_nse_corp_actions.py [start_yyyy-mm] [end_yyyy-mm]   (default 2021-11 .. current month)
"""
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from data.paths import NSE_CORP_ACTIONS_FILE  # noqa: E402

H = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36',
     'Accept': 'application/json,text/plain,*/*', 'Referer': 'https://www.nseindia.com/companies-listing/corporate-filings-actions'}

if __name__ == '__main__':
    start = sys.argv[1] if len(sys.argv) > 1 else '2021-11'
    end = sys.argv[2] if len(sys.argv) > 2 else pd.Timestamp.today().strftime('%Y-%m')
    s = requests.Session()
    s.get('https://www.nseindia.com/', headers=H, timeout=20)
    out = []
    for m in pd.period_range(start, end, freq='M'):
        a, b = m.start_time.strftime('%d-%m-%Y'), m.end_time.strftime('%d-%m-%Y')
        for idx in ('equities', 'sme'):
            for attempt in range(4):
                r = s.get(f'https://www.nseindia.com/api/corporates-corporateActions?index={idx}&from_date={a}&to_date={b}',
                          headers=H, timeout=30)
                if r.status_code == 200:
                    d = r.json()
                    for x in d:
                        x['index'] = idx
                    out += d
                    break
                time.sleep(3 * (attempt + 1))
                s.get('https://www.nseindia.com/', headers=H, timeout=20)
            else:
                print('FAILED', m, idx, flush=True)
            time.sleep(1.2)
        print(m, len(out), flush=True)
    df = pd.DataFrame(out)[['symbol', 'series', 'exDate', 'subject', 'index']]
    df.to_csv(NSE_CORP_ACTIONS_FILE, index=False)
    print('done', len(df), '->', NSE_CORP_ACTIONS_FILE, flush=True)
