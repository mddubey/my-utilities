"""User's actual cue: the MARKET REGIME (Nifty in a daily downtrend -> bias to shorts), known before the day starts.
Pre-declared 2026-10-01, three definitions, all from Nifty daily data as of the PRIOR close:
  ema   : Nifty daily EMA8 < EMA34  -> down regime
  sma50 : Nifty close < SMA50       -> down regime
  ret20 : Nifty 20-day return < 0   -> down regime
'with regime' = short in down regime, long in up regime. Sets: 15's 1H-close trades (2024-26), 18's 5m held (Jun-Sep 2026)."""
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
N = pd.read_csv(HERE.parent / "data_cache" / "_NIFTY.csv", parse_dates=["Date"]).set_index("Date").sort_index()
c = N.Close
reg = pd.DataFrame({"ema": c.ewm(span=8, adjust=False).mean() < c.ewm(span=34, adjust=False).mean(),
                    "sma50": c < c.rolling(50).mean(), "ret20": c.pct_change(20) < 0}).astype(float).shift(1)   # prior close
print("Nifty last daily close", N.index[-1].date(), round(c.iloc[-1], 1), "| from 52w high", round((c.iloc[-1] / c.tail(252).max() - 1) * 100, 1), "%")
print("regime TODAY (as of last close):", {k: ("DOWN" if v else "up") for k, v in
      {"ema": c.ewm(span=8, adjust=False).mean().iloc[-1] < c.ewm(span=34, adjust=False).mean().iloc[-1],
       "sma50": c.iloc[-1] < c.rolling(50).mean().iloc[-1], "ret20": c.pct_change(20).iloc[-1] < 0}.items()})
print("share of days in DOWN regime by year (ema):", reg.ema.groupby(reg.index.year).mean().round(2).loc[2024:].to_dict())
A = pd.read_csv(HERE / "intraday_1h34_daily8_results.csv", parse_dates=["date"])
A["bt"] = pd.to_datetime(A.ts, utc=True).dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
A = A[A.trend & (A.dstate != "wrong") & (A.bt.dt.strftime("%H:%M") != "09:15") & (A.date >= "2024-01-01")]
P = pd.read_csv(HERE / "pin_rejection_held_results.csv", parse_dates=["date"]); P = P[P.variant == "held"]
def line(x, l, per):
    if len(x) < 100: print(f"| {l} | {len(x)} | too few |"); return
    y = x.groupby(per(x)).ret.mean()
    print(f"| {l} | {len(x)} | {(x.R>0).mean()*100:.0f} | {x.ret.mean():+.3f} | {x.ret.median():+.3f} | {x.R.mean():+.2f} | " + " / ".join(f"{k}:{v:+.2f}" for k, v in y.items()) + " |")
for nm, R, per in (("1H close, 2024-26", A, lambda x: x.date.dt.year), ("5m held, Jun-Sep 2026", P, lambda x: x.date.dt.month)):
    R = R.join(reg, on="date")
    print(f"\n### {nm}\n| group | n | win% | mean% | med% | meanR | by period |\n|---|---|---|---|---|---|---|")
    line(R, "BASELINE", per)
    for k in ("ema", "sma50", "ret20"):
        down = R[k] == 1
        line(R[(R.side == "short") & down], f"{k}: SHORT in down regime", per)
        line(R[(R.side == "short") & ~down], f"{k}: short in up regime", per)
        line(R[(R.side == "long") & ~down], f"{k}: LONG in up regime", per)
        line(R[(R.side == "long") & down], f"{k}: long in down regime", per)
