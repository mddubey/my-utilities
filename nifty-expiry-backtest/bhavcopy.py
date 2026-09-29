import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path(__file__).parent / "data_cache"
URL_TMPL = "https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{ymd}_F_0000.csv.zip"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch(date):
    """Returns the F&O bhavcopy for `date` as a DataFrame, or None if it wasn't a trading day."""
    ymd = date.strftime("%Y%m%d")
    cache_path = CACHE_DIR / f"{ymd}.csv"
    if cache_path.exists():
        return pd.read_csv(cache_path)

    resp = requests.get(URL_TMPL.format(ymd=ymd), headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        return None

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        with zf.open(zf.namelist()[0]) as f:
            df = pd.read_csv(f)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False)
    return df
