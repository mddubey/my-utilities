import io
import zipfile
import datetime as dt

import pandas as pd
import requests

URL_TMPL = "https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{ymd}_F_0000.csv.zip"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def get_fo_universe():
    """Returns the current list of F&O stock tickers (excludes indices), by reading
    the most recent available NSE FO bhavcopy and taking unique stock-option/future symbols."""
    day = dt.date.today()
    for _ in range(10):
        day -= dt.timedelta(days=1)
        if day.weekday() >= 5:
            continue
        resp = requests.get(URL_TMPL.format(ymd=day.strftime("%Y%m%d")), headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            continue
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            with zf.open(zf.namelist()[0]) as f:
                df = pd.read_csv(f)
        stocks = sorted(df[df.FinInstrmTp.isin(["STO", "STF"])]["TckrSymb"].unique())
        return stocks
    raise RuntimeError("no recent trading-day bhavcopy found")


if __name__ == "__main__":
    stocks = get_fo_universe()
    print(f"{len(stocks)} F&O stocks")
    pd.Series(stocks).to_csv("fo_universe.csv", index=False, header=False)
