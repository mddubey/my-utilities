"""Is Nifty's own intraday path forecastable from information known at the time? Spec fixed 2026-10-02 before running.
Data: Yahoo Nifty 1H (Oct 2023 - Oct 2026), bars 09:15..15:15; daily Nifty (data_cache/_NIFTY.csv) rows strictly before
each day for pivots/gap/regime. One observation per day per test (no overlap). Pass bar: |t| > 3 and same sign all years.
  P1 momentum   : first-hour return (09:15 bar close / open - 1) -> rest of day (close / 10:15 close - 1)
  P2 pivots     : FIRST hourly close (10:15..13:15 bars) below daily S1 / above daily R1 -> next 2 hours
  P3 open range : FIRST hourly close (10:15..13:15) below the first hour's low / above its high -> next 2 hours
  P4 gap        : open / prior close - 1 (< -0.5 / mid / > +0.5 %) -> rest of day after the first hour
  P5 prior day  : prior day's return sign -> rest of day after the first hour
  P6 regime     : prior-day daily EMA8 < EMA34 -> rest of day after the first hour"""
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
h = pd.read_csv(HERE / "index_1h" / "_NIFTY_1h.csv", index_col=0)
h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
h = h[h.Close.notna() & (h.High != h.Low)]
D = pd.read_csv(HERE.parent / "data_cache" / "_NIFTY.csv", parse_dates=["Date"]).set_index("Date").sort_index()
pp = (D.High + D.Low + D.Close) / 3
prior = pd.DataFrame({"pc": D.Close, "R1": 2 * pp - D.Low, "S1": 2 * pp - D.High,
                      "pret": D.Close.pct_change(), "down": (D.Close.ewm(span=8, adjust=False).mean() < D.Close.ewm(span=34, adjust=False).mean())}).shift(1)
rows = []
for day, g in h.groupby(h.index.normalize()):
    t = g.index.strftime("%H:%M")
    if list(t[:7]) != ["09:15", "10:15", "11:15", "12:15", "13:15", "14:15", "15:15"] or day not in prior.index: continue
    p = prior.loc[day]
    if p.isna().any(): continue
    O, C = g.Open.values, g.Close.values; Hh, Ll = g.High.values, g.Low.values
    r = dict(day=day, first=C[0] / O[0] - 1, rest=C[6] / C[0] - 1, gap=O[0] / p.pc - 1, pret=p.pret, down=bool(p.down))
    for name, cond_dn, cond_up in (("piv", lambda k: C[k] < p.S1, lambda k: C[k] > p.R1),
                                   ("orb", lambda k: C[k] < Ll[0], lambda k: C[k] > Hh[0])):
        for side, cond in (("dn", cond_dn), ("up", cond_up)):
            k = next((k for k in range(1, 5) if cond(k)), None)
            r[f"{name}_{side}"] = np.nan if k is None else C[min(k + 2, 6)] / C[k] - 1
    rows.append(r)
X = pd.DataFrame(rows).set_index("day")
print(f"days {len(X)} ({X.index.min().date()} -> {X.index.max().date()})\n")
def stat(y, lab, pred_sign):
    y = y.dropna() * 100
    if len(y) < 30: print(f"| {lab} | {len(y)} | too few |"); return
    t = y.mean() / y.std() * np.sqrt(len(y)); yr = y.groupby(y.index.year).mean()
    hit = (np.sign(y) == pred_sign).mean() * 100
    ok = abs(t) > 3 and (np.sign(yr) == np.sign(y.mean())).all()
    print(f"| {lab} | {len(y)} | {y.mean():+.3f} | {t:+.2f} | {hit:.0f}% | " + " / ".join(f"{a}:{b:+.2f}" for a, b in yr.items()) + f" | {'PASS' if ok else '-'} |")
print("| pattern -> next move (predicted direction) | days | mean % | t | hit rate of predicted direction | by year | verdict |\n|---|---|---|---|---|---|---|")
stat(X.rest[X["first"] < -0.003], "P1 first hour < -0.3% -> rest of day (down)", -1)
stat(X.rest[X["first"] > 0.003], "P1 first hour > +0.3% -> rest of day (up)", 1)
stat(X.rest * np.sign(X["first"]), "P1 rest of day signed by first-hour direction (all days)", 1)
stat(X.piv_dn, "P2 first close below daily S1 -> next 2h (down)", -1)
stat(X.piv_up, "P2 first close above daily R1 -> next 2h (up)", 1)
stat(X.orb_dn, "P3 first close below first-hour low -> next 2h (down)", -1)
stat(X.orb_up, "P3 first close above first-hour high -> next 2h (up)", 1)
stat(X.rest[X.gap < -0.005], "P4 gap down > 0.5% -> rest of day", -1)
stat(X.rest[X.gap > 0.005], "P4 gap up > 0.5% -> rest of day", 1)
stat(X.rest[X.pret < 0], "P5 prior day down -> rest of day (down)", -1)
stat(X.rest[X.pret > 0], "P5 prior day up -> rest of day (up)", 1)
stat(X.rest[X.down], "P6 daily 8<34 regime -> rest of day (down)", -1)
stat(X.rest[~X.down], "P6 daily 8>34 regime -> rest of day (up)", 1)
stat(X.rest, "BASELINE rest of day, all days", 1)
print(f"\ncorr(first hour, rest of day) = {X['first'].corr(X.rest):+.3f}")
X.to_csv(HERE / "nifty_intraday_patterns.csv")
