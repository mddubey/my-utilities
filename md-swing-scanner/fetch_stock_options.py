import io
import sys
import zipfile
import datetime as dt
from pathlib import Path

import pandas as pd
import requests

URL_TMPL = "https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{ymd}_F_0000.csv.zip"
HEADERS = {"User-Agent": "Mozilla/5.0"}
CACHE_DIR = Path(__file__).parent / "options_cache"


def fetch_day(day):
    """Caches the FULL, unfiltered daily bhavcopy — every column, every instrument
    type (~5.4MB/day, ~2.4GB for the whole 2024-2026 window). NSE's historical
    archive is static, so this is a one-time cost; no reason to re-fetch later
    just because a new column turns out to matter."""
    ymd = day.strftime("%Y%m%d")
    out_path = CACHE_DIR / f"{ymd}.csv"
    if out_path.exists():
        return "cached"

    resp = requests.get(URL_TMPL.format(ymd=ymd), headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        return "no-file"

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open(zf.namelist()[0]) as f:
            df = pd.read_csv(f)

    CACHE_DIR.mkdir(exist_ok=True)
    df.to_csv(out_path, index=False)
    return f"ok ({len(df)} rows)"


if __name__ == "__main__":
    start = dt.date.fromisoformat(sys.argv[1])
    end = dt.date.fromisoformat(sys.argv[2])
    day = start
    n_ok = n_skip = 0
    while day <= end:
        if day.weekday() < 5:
            status = fetch_day(day)
            if status == "no-file":
                n_skip += 1
            else:
                n_ok += 1
            print(f"{day} {status}", flush=True)
        day += dt.timedelta(days=1)
    print(f"\ndone: {n_ok} days fetched/cached, {n_skip} non-trading days")
