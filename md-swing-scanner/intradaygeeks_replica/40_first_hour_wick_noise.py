"""Is the 09:15 candle's wick a real rejection or opening noise? Spec fixed 2026-10-02 before running.
Set: checklist shorts from the 09:15 candle (entry 10:15), 0.5% cap, dates covered by 5m data (Jun 10 - Sep 30 2026);
1H-close outcomes from 15. Splits (from 5m bars of 09:15-10:15):
  A. time the hour's high was made: first 15 min (09:15-09:29) vs 09:30 or later
  B. opened at/above the 1H EMA34 (wick = the open, a fade) vs opened below and rallied up into it (rejection from below)
Reference: the 11:15 and 12:15 alarms in the same window."""
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
U = pd.read_csv(HERE / "checklist_shorts_with_0915.csv", parse_dates=["date", "bt"])
W = U[U.date >= "2026-06-10"].copy()
F = W[W.entry_time == "10:15"].copy()
def read(p):
    x = pd.read_csv(p, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None); return x
res = []
for t, g in F.groupby("ticker"):
    p = HERE.parent / "intraday_cache" / f"{t}.csv"
    if not p.exists(): continue
    m = read(p); h = read(HERE / "h1_cache" / f"{t}.csv"); e34 = h.Close.ewm(span=34, adjust=False).mean().shift(1)
    for r in g.itertuples():
        b = m[(m.index >= r.bt) & (m.index < r.bt + pd.Timedelta("60min"))]
        if len(b) < 10 or r.bt not in e34.index: continue
        E = e34.loc[r.bt]
        res.append(dict(i=r.Index, hi_time=b.High.idxmax().strftime("%H:%M"), opened_above=b.Open.iloc[0] >= E))
R = pd.DataFrame(res).set_index("i"); F = F.join(R, how="inner")
def line(x, lab):
    if len(x) < 20: print(f"| {lab} | {len(x)} | too few | | | |"); return
    print(f"| {lab} | {len(x)} | {x.stop_pct.median():.2f}% | {(x.ret>0).mean()*100:.0f} | {x.ret.mean():+.3f} | {(x.stop_pct<=0.5).mean()*100:.0f}% |")
print(f"10:15-alarm setups in the 5m window: {len(F)}\n| group | trades | median stop | win% | mean % | share with stop <= 0.5% |\n|---|---|---|---|---|---|")
line(F, "ALL 10:15-alarm setups")
line(F[F.hi_time < "09:30"], "A. hour's high made 09:15-09:29 (opening noise)")
line(F[F.hi_time >= "09:30"], "A. hour's high made 09:30 or later")
line(F[F.opened_above], "B. opened at/above the 1H EMA (fade from the open)")
line(F[~F.opened_above], "B. opened below, rallied INTO the EMA (rejection from below)")
line(F[(~F.opened_above) & (F.hi_time >= "09:30")], "A+B: opened below AND high at 09:30 or later")
for t in ("11:15", "12:15"): line(W[W.entry_time == t], f"reference: alarm {t}, same window")
print("\nshare of 10:15-alarm setups whose high came in the first 15 min:", round((F.hi_time < "09:30").mean() * 100), "%; opened above EMA:", round(F.opened_above.mean() * 100), "%")
