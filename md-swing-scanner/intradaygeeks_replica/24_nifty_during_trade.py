"""How much of the 1H-close setup's outcome is just Nifty? Spec fixed 2026-10-01 before running.
Set: 15's trades (1H trend, not daily-8 wrong side, no 09:15 setup, 2024-26). Entry = setup bar close, exit = close of
the bar `bars` hours later (same day). Nifty 1H closes matched at the same bar starts.
  during  : Nifty return from entry to exit, signed by trade side  (NOT knowable at entry -- descriptive only)
  cue_bar : the Nifty 1H candle that closed at entry, coloured with the trade (red for shorts)        (known at entry)
  cue_trend: Nifty 1H EMA8 vs EMA34, including that candle, aligned with the trade                    (known at entry)"""
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
n = pd.read_csv(HERE / "index_1h" / "_NIFTY_1h.csv", index_col=0)
n.index = pd.to_datetime(n.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
n = n[(n.Volume >= 0) & n.Close.notna()]
e8, e34 = n.Close.ewm(span=8, adjust=False).mean(), n.Close.ewm(span=34, adjust=False).mean()
A = pd.read_csv(HERE / "intraday_1h34_daily8_results.csv", parse_dates=["date"])
A["bt"] = pd.to_datetime(A.ts, utc=True).dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
A = A[A.trend & (A.dstate != "wrong") & (A.bt.dt.strftime("%H:%M") != "09:15") & (A.date >= "2024-01-01")].copy()
s = np.where(A.side == "long", 1, -1)
xb = A.bt + pd.to_timedelta(A.bars, unit="h")
ok = A.bt.isin(n.index) & xb.isin(n.index) & (xb.dt.normalize() == A.bt.dt.normalize())
A, s, xb = A[ok], s[ok.values], xb[ok]
A["during"] = (n.Close.reindex(xb).values / n.Close.reindex(A.bt).values - 1) * 100 * s
A["cue_bar"] = (n.Close.reindex(A.bt).values - n.Open.reindex(A.bt).values) * s > 0
A["cue_trend"] = (e8.reindex(A.bt).values - e34.reindex(A.bt).values) * s > 0
def line(x, l):
    y = x.groupby(x.date.dt.year).ret.mean()
    print(f"| {l} | {len(x)} | {(x.R>0).mean()*100:.0f} | {x.ret.mean():+.3f} | {x.ret.median():+.3f} | " + " / ".join(f"{v:+.2f}" for v in y) + " |")
print(f"matched {len(A)} trades\n| group | n | win% | mean% | med% | 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|")
line(A, "BASELINE")
for lo, hi, lab in ((-99, -0.3, "Nifty moved AGAINST trade by >0.3% (during)"), (-0.3, 0.3, "Nifty flat +/-0.3% (during)"),
                    (0.3, 99, "Nifty moved WITH trade by >0.3% (during)")):
    line(A[(A.during > lo) & (A.during <= hi)], lab)
for c, lab in (("cue_bar", "Nifty last 1H candle with trade (at entry)"), ("cue_trend", "Nifty 1H 8/34 trend with trade (at entry)")):
    line(A[A[c]], lab); line(A[~A[c]], "  ...against")
line(A[A.cue_trend & A.cue_bar], "both at-entry Nifty cues with trade")
for side in ("long", "short"): line(A[(A.side == side) & A.cue_trend], f"  {side}, Nifty trend with")
print("\ncorrelation of trade return with Nifty-during:", round(np.corrcoef(A.ret, A.during)[0, 1], 2),
      "| P(Nifty moves with the trade during | cue_trend) =", round((A[A.cue_trend].during > 0).mean() * 100, 1), "% vs",
      round((A[~A.cue_trend].during > 0).mean() * 100, 1), "% without")
