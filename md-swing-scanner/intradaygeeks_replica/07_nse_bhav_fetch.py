"""Fetch NSE's official daily OHLC (UDiFF bhavcopy) for every date that has a channel call,
keeping only the tickers we need. Cached in this scratch folder, never in production's
cash_bhav_cache (which stores close only and is used by option_backtest)."""
import io, time, zipfile
from pathlib import Path
import pandas as pd
import requests

HERE = Path(__file__).parent
OUT = HERE / "nse_bhav_ohlc.csv"
URL = "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{ymd}_F_0000.csv.zip"


def fetch(ymd):
    for attempt in range(4):
        try:
            r = requests.get(URL.format(ymd=ymd), headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        except requests.RequestException:
            time.sleep(3 * (attempt + 1)); continue
        if r.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(r.content)) as z, z.open(z.namelist()[0]) as f:
                return pd.read_csv(f)
        if r.status_code == 404:
            return None
        time.sleep(3 * (attempt + 1))
    return None


if __name__ == "__main__":
    att = pd.read_csv(HERE / "telegram_attempts_scored.csv", parse_dates=["ts"])
    need = att.groupby(att.ts.dt.strftime("%Y%m%d")).ticker.apply(set).to_dict()
    done = pd.read_csv(OUT) if OUT.exists() else pd.DataFrame(columns=["date"])
    have = set(done.date.astype(str))
    rows = [done] if len(done) else []
    todo = [d for d in sorted(need) if d not in have]
    print(f"{len(need)} dates needed, {len(todo)} to fetch", flush=True)
    for i, ymd in enumerate(todo, 1):
        df = fetch(ymd)
        if df is not None:
            df = df[(df.SctySrs == "EQ") & df.TckrSymb.isin(need[ymd])]
            rows.append(pd.DataFrame({"date": ymd, "ticker": df.TckrSymb, "open": df.OpnPric,
                                      "high": df.HghPric, "low": df.LwPric, "close": df.ClsPric}))
        if i % 20 == 0 or i == len(todo):
            pd.concat(rows).to_csv(OUT, index=False)
            print(f"  {i}/{len(todo)} dates", flush=True)
        time.sleep(1.5)
    print("done", flush=True)
