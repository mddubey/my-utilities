"""User's casual cue: 'Nifty falling' at the moment of entry. Spec fixed 2026-10-01 before running.
Real Nifty 5m from Yahoo (max ~60 days -> covers ~Aug-Sep 2026 of 18's window). Decision time = close of 18's entry bar.
  mom_N : Nifty close at decision / Nifty close N minutes earlier - 1, for N = 15, 30, 60 (same day only);
          'with' = move in the trade's direction (falling for shorts). Strong: |30-min move| > 0.15% in trade direction."""
import warnings; warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd, yfinance as yf
HERE = Path(__file__).resolve().parent
f = HERE / "index_1h" / "_NIFTY_5m_60d.csv"
if not f.exists():
    n = yf.download("^NSEI", period="60d", interval="5m", progress=False, auto_adjust=False).droplevel(1, axis=1)
    n.to_csv(f)
n = pd.read_csv(f, index_col=0); n.index = pd.to_datetime(n.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
end_close = pd.Series(n.Close.values, index=n.index + pd.Timedelta("5min"))        # close known at bar end
P = pd.read_csv(HERE / "pin_rejection_held_results.csv", parse_dates=["date"]); P = P[P.variant == "held"]
P["decide"] = pd.to_datetime(P.date.dt.strftime("%Y-%m-%d") + " " + P.entry_time) + pd.Timedelta("5min")
P = P[P.decide.isin(end_close.index)].copy()
s = np.where(P.side == "long", 1, -1)
for N in (15, 30, 60):
    back = P.decide - pd.Timedelta(f"{N}min")
    ok = back.isin(end_close.index) & (back.dt.normalize() == P.decide.dt.normalize())
    P[f"m{N}"] = np.where(ok, (end_close.reindex(P.decide).values / end_close.reindex(back).values - 1) * 100 * s, np.nan)
print(f"Nifty 5m {n.index.min().date()} -> {n.index.max().date()} | held trades covered: {len(P)} ({P.date.min().date()} -> {P.date.max().date()})")
def line(x, l):
    if len(x) < 100: print(f"| {l} | {len(x)} | too few | | | |"); return
    y = x.groupby(x.date.dt.month).ret.mean()
    print(f"| {l} | {len(x)} | {(x.R>0).mean()*100:.0f} | {x.ret.mean():+.3f} | {x.ret.median():+.3f} | " + " / ".join(f"{k}:{v:+.2f}" for k, v in y.items()) + " |")
print("| group | n | win% | mean% | med% | by month |\n|---|---|---|---|---|---|")
line(P, "BASELINE (covered window)")
for N in (15, 30, 60):
    x = P[P[f"m{N}"].notna()]
    line(x[x[f"m{N}"] > 0], f"Nifty last {N}m WITH trade"); line(x[x[f"m{N}"] <= 0], f"  ...against")
line(P[P.m30 > 0.15], "Nifty last 30m with trade by > 0.15% (strong)")
for side in ("short", "long"):
    x = P[(P.side == side) & P.m30.notna()]
    line(x[x.m30 > 0], f"{side}: Nifty last 30m with"); line(x[x.m30 <= 0], f"{side}: Nifty last 30m against")
