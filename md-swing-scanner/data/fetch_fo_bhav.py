"""NSE F&O bhavcopy top-up (added to the EOD refresh 2026-11-03; the OI walls / expiry tables need yesterday's file daily).
Fetches every weekday after the latest cached file up to today with fetch_stock_options.fetch_day (the full unfiltered
file: all index + stock options and futures, ~5.8 MB/day). NSE publishes it some time after the close, so an early run just
reports "not published yet" -- WARN only, always exit 0. Run from the repo root: python3 data/fetch_fo_bhav.py"""
import sys, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import NSE_FO_BHAV_DIR
from fetch_stock_options import fetch_day

latest = max((p.stem for p in NSE_FO_BHAV_DIR.glob("*.csv")), default=None)
day = dt.datetime.strptime(latest, "%Y%m%d").date() + dt.timedelta(days=1) if latest else dt.date.today()
today = dt.date.today()
got, missing = [], []
while day <= today:
    if day.weekday() < 5:
        try: st = fetch_day(day)
        except Exception as e: st = f"error {type(e).__name__}"
        (got if st.startswith("ok") else missing).append(f"{day}" if st.startswith("ok") else f"{day} ({'not published yet / holiday' if st == 'no-file' else st})")
    day += dt.timedelta(days=1)
now = max((p.stem for p in NSE_FO_BHAV_DIR.glob("*.csv")), default="none")
print(f"F&O bhavcopy: was {latest}, now {now} | fetched {len(got)}: {', '.join(got) or '-'}"
      + (f" | not fetched: {', '.join(missing)}" if missing else ""))
