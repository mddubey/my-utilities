"""NSE Margin Trading Facility (MTF) daily disclosure -> data/nse_mtf/{yyyymmdd}.csv (2026-10-25, intraday shorts telemetry).

One file per reporting date: ticker, qty (shares funded by all members), amt_lakh (amount funded, Rs lakh). Average funded
price = amt_lakh * 1e5 / qty. Source: nsearchives .../content/equities/mrg_trading_DDMMYY.zip (public). PUBLISHING LAG: the
file for day t appears the evening of t+1, so at 09:21 on day T the latest file is usually T-2. A "revised" layout (late member
submissions, e.g. 2026-08-18) has two blocks side by side -- the right-hand (current date) block is used.
Incremental: dates already on disk are skipped; a date not yet published is retried next run.
Usage: python3 data/fetch_nse_mtf.py [start_yyyy-mm-dd]   (default: 15 sessions back)"""
import io
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import fetch_cash_bhav as fcb  # noqa: E402
from data.paths import DAILY_DIR, NSE_MTF_DIR  # noqa: E402

URL_TMPL = "https://nsearchives.nseindia.com/content/equities/mrg_trading_{ddmmyy}.zip"


def parse(content):
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        lines = zf.read(zf.namelist()[0]).decode("latin1").splitlines()
    hi = next(i for i, l in enumerate(lines) if "Symbol" in l.split(","))
    head = [c.strip() for c in lines[hi].split(",")]
    c0 = max(i for i, c in enumerate(head) if c == "Symbol")          # revised layout: last block = current data
    rows = []
    for l in lines[hi + 1:]:
        p = l.split(",")
        if len(p) < c0 + 4 or not p[c0].strip():
            continue
        rows.append((p[c0].strip(), p[c0 + 2], p[c0 + 3]))
    d = pd.DataFrame(rows, columns=["ticker", "qty", "amt_lakh"])
    d["qty"] = pd.to_numeric(d.qty, errors="coerce"); d["amt_lakh"] = pd.to_numeric(d.amt_lakh, errors="coerce")
    return d.dropna()


def fetch(day):
    path = NSE_MTF_DIR / (day.strftime("%Y%m%d") + ".csv")
    if path.exists():
        return "cached"
    r = fcb._get_with_backoff(URL_TMPL.format(ddmmyy=day.strftime("%d%m%y")))
    if r is None:
        return "not published"
    d = parse(r.content)
    if len(d) < 100:
        return "bad file"
    d.to_csv(path, index=False)
    return "ok"


def latest_before(day):
    """(date, DataFrame indexed by ticker) of the newest MTF file strictly before `day`; (None, None) if none on disk."""
    fs = sorted(p for p in NSE_MTF_DIR.glob("*.csv") if p.stem < pd.Timestamp(day).strftime("%Y%m%d"))
    if not fs:
        return None, None
    return pd.Timestamp(fs[-1].stem), pd.read_csv(fs[-1]).drop_duplicates("ticker").set_index("ticker")


if __name__ == "__main__":
    NSE_MTF_DIR.mkdir(exist_ok=True)
    cal = pd.to_datetime(pd.read_csv(DAILY_DIR / "_NIFTY.csv", usecols=["Date"]).Date)
    start = pd.Timestamp(sys.argv[1]) if len(sys.argv) > 1 else cal.iloc[-15]
    days = [d.date() for d in cal if d >= start]
    counts = {}
    for d in days:
        res = fetch(d)
        counts[res] = counts.get(res, 0) + 1
        if res not in ("cached", "ok"):
            print(f"  {res} {d}", flush=True)
        if res != "cached":
            time.sleep(1.0)
    print(f"MTF files: {counts}", flush=True)
