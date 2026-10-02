"""Do Yahoo 5m bars miss the true day extremes, and does it bias the thin-stop backtest (18 'held')?
Ground truth = NSE UDiFF bhavcopy day high/low (same source as 07/08). Fetch every date in 18's window, all EQ.
Bound on bias: a trade whose stop lies beyond Yahoo's day extreme but within NSE's day extreme MAY have been stopped
by a print Yahoo doesn't show (timing unknown) -> pessimistic re-grade = treat as stopped."""
import io, time, zipfile, sys
from pathlib import Path
import numpy as np, pandas as pd, requests
HERE = Path(__file__).resolve().parent
OUT = HERE / "nse_bhav_jun_sep26.csv"
URL = "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{ymd}_F_0000.csv.zip"
R = pd.read_csv(HERE / "pin_rejection_held_results.csv", parse_dates=["date"]); R = R[R.variant == "held"]
if not OUT.exists():
    rows = []
    for k, d in enumerate(sorted(R.date.dt.strftime("%Y%m%d").unique()), 1):
        for a in range(4):
            try: r = requests.get(URL.format(ymd=d), headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            except requests.RequestException: time.sleep(3); continue
            if r.status_code == 200:
                with zipfile.ZipFile(io.BytesIO(r.content)) as z, z.open(z.namelist()[0]) as f: b = pd.read_csv(f)
                b = b[b.SctySrs == "EQ"]
                rows.append(pd.DataFrame({"date": d, "ticker": b.TckrSymb, "high": b.HghPric, "low": b.LwPric, "close": b.ClsPric})); break
            time.sleep(3)
        if k % 20 == 0: print(f"  {k} dates", flush=True)
        time.sleep(1.2)
    pd.concat(rows).to_csv(OUT, index=False)
N = pd.read_csv(OUT, dtype={"date": str}).set_index(["date", "ticker"])
M5 = HERE.parent / "intraday_cache"
ext = {}
for t in R.ticker.unique():
    x = pd.read_csv(M5 / f"{t}.csv", index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    g = x.groupby(x.index.strftime("%Y%m%d")).agg(yh=("High", "max"), yl=("Low", "min"), yc=("Close", "last"))
    for d, r in g.iterrows(): ext[(d, t)] = r
E = pd.DataFrame(ext).T; E.index.names = ["date", "ticker"]
J = E.join(N, how="inner")
J = J[(J.yc / J.close - 1).abs() < 0.02]                     # same price scale
J["miss_hi"] = (J.high - J.yh) / J.close * 100                # >0: NSE printed higher than Yahoo shows
J["miss_lo"] = (J.yl - J.low) / J.close * 100                 # >0: NSE printed lower than Yahoo shows
print(f"ticker-days compared: {len(J)}")
for c in ("miss_hi", "miss_lo"):
    s = J[c]; print(f"  {c}: Yahoo misses extreme on {(s > 1e-6).mean()*100:.1f}% of days | when missed: median {s[s>1e-6].median():.3f}%  p90 {s[s>1e-6].quantile(.9):.3f}% | Yahoo BEYOND NSE {(s < -1e-6).mean()*100:.1f}%")
# bias bound on 18's trades
R["d"] = R.date.dt.strftime("%Y%m%d"); R = R.join(J, on=["d", "ticker"], how="inner")
s = np.where(R.side == "long", 1, -1)
stop_px = R.entry - s * R.stop_rs
# not stopped on Yahoo bars, but NSE's true day extreme went past BOTH the stop and Yahoo's own day extreme:
# the unseen print may have come after entry (stopping the trade) or before it (then only the stop level was off).
at_risk = np.where(s == 1, (R.low <= stop_px) & (R.low < R.yl), (R.high >= stop_px) & (R.high > R.yh)) & (R.exit != "stop")
R["at_risk"] = at_risk
pess = R.ret.where(~R.at_risk, -R.stop_pct)
print(f"\n18 'held' trades matched to NSE: {len(R)} | possibly stopped by an unseen print: {R.at_risk.sum()} ({R.at_risk.mean()*100:.1f}%)")
print(f"  mean % as backtested {R.ret.mean():+.3f} | pessimistic (those = stopped) {pess.mean():+.3f}")
print(f"  stop median {R.stop_pct.median():.2f}% vs median missed-extreme gap {J.miss_hi[J.miss_hi>1e-6].median():.3f}%")
