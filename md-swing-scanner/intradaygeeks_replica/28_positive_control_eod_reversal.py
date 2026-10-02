"""POSITIVE CONTROL: can our 5m data detect a documented intraday effect? End-of-day reversal (Baltussen, Da & Soebhag
2025, https://academicweb.nd.edu/~zda/EOD.pdf). Spec fixed 2026-10-01 before running:
liquid (prior-day tv20 >= Rs 10 cr), days with >= 70 5m bars. r_day = close of the 14:55 bar (known 15:00) / day open - 1.
r_last = last bar close / that 15:00 close - 1. Daily cross-sectional quintiles of r_day; mean r_last per quintile,
Q5-Q1 spread, t-stat over days, each month separately. Prediction: Q5 (day's winners) < Q1 (day's losers)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
HERE = Path(__file__).resolve().parent
M5 = HERE.parent / "intraday_cache"


def one(t):
    try: d = load(t)
    except Exception: return []
    tv = d.traded_value_sma20.shift(1)
    x = pd.read_csv(M5 / f"{t}.csv", index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    x = x[(x.Volume > 0) | (x.High != x.Low)]
    out = []
    for day, g in x.groupby(x.index.normalize()):
        if len(g) < 70 or tv.get(day, 0) < 1e8: continue
        t1500 = g[g.index.strftime("%H:%M") == "14:55"]
        if t1500.empty or g.index[-1].strftime("%H:%M") < "15:20": continue
        c15 = t1500.Close.iloc[0]
        out.append((t, day, c15 / g.Open.iloc[0] - 1, g.Close.iloc[-1] / c15 - 1))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    tick = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p: rows = sum(p.map(one, tick, chunksize=20), [])
    D = pd.DataFrame(rows, columns=["ticker", "day", "r_day", "r_last"])
    D = D[D.groupby("day").ticker.transform("count") >= 100]
    D["q"] = D.groupby("day").r_day.transform(lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) + 1)
    print(f"stock-days {len(D)} | days {D.day.nunique()} | {D.day.min().date()} -> {D.day.max().date()}")
    Q = D.groupby("q").agg(n=("r_last", "size"), r_day=("r_day", "mean"), r_last=("r_last", "mean"))
    Q["r_day"] *= 100; Q["r_last"] *= 100
    print(Q.round(3).to_string())
    daily = D.groupby(["day", "q"]).r_last.mean().unstack()
    spread = (daily[5] - daily[1]) * 100
    print(f"\nQ5 - Q1 last-30-min return: mean {spread.mean():+.3f}% per day, t = {spread.mean() / spread.std() * np.sqrt(len(spread)):.2f}, "
          f"negative on {(spread < 0).mean() * 100:.0f}% of days")
    print("by month:", spread.groupby(spread.index.month).mean().round(3).to_dict())
