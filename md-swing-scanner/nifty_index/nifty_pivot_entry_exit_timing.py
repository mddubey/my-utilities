"""Ad hoc (2026-09-27), corrected per direct user feedback: using the day's Low as the
entry reference is unusable in practice -- you only know it's the low in hindsight. The
real, actionable version uses S1 (support, computed from the PRIOR day's H/L/C -- known
BEFORE the market even opens) as the entry trigger, and PP/R1 (also pre-known) as the exit
target -- exactly what you could actually set an alert/order for in real time.

For each of the real ~51 days with intraday data: does price actually TOUCH S1 intraday
(the real, watchable entry signal)? If so, at what time, and does it subsequently reach PP
or R1 (the exit target) -- and if so, how many points and how many minutes did that take.
This directly answers "if I watch for S1, buy there, and plan to exit at PP/R1, how often
does that actually work, how much do I capture, and how fast."
"""
import yfinance as yf
import pandas as pd

# real, pre-computable pivots (prior-day H/L/C, no lookahead) -- same as nifty_pivot_bounce_check.py
nifty = pd.read_csv("../data_cache/_NIFTY.csv")
nifty["Date"] = pd.to_datetime(nifty.Date)
h, l, c = nifty.High.shift(1), nifty.Low.shift(1), nifty.Close.shift(1)
nifty["pp"] = (h + l + c) / 3
nifty["r1"] = 2 * nifty.pp - l
nifty["s1"] = 2 * nifty.pp - h
nifty["s2"] = nifty.pp - (h - l)
piv = nifty.set_index(nifty.Date.dt.date)[["pp", "r1", "s1", "s2"]]

df = yf.download("^NSEI", period="60d", interval="5m", progress=False)
df.columns = df.columns.droplevel(1) if isinstance(df.columns, pd.MultiIndex) else df.columns
df.index = df.index.tz_convert("Asia/Kolkata")
df["date"] = df.index.date

results = []
for d in sorted(df.date.unique()):
    if d not in piv.index:
        continue
    row = piv.loc[d]
    s1, pp, r1 = row.s1, row.pp, row.r1
    if pd.isna(s1):
        continue
    day_bars = df[df.date == d]
    touch = day_bars[day_bars.Low <= s1]
    if touch.empty:
        results.append(dict(date=d, s1=s1, pp=pp, r1=r1, touched_s1=False))
        continue
    touch_idx = touch.index[0]  # first real touch of S1 intraday
    touch_time = touch_idx.strftime("%H:%M")
    after = day_bars.loc[touch_idx:]

    reached_pp = after[after.High >= pp]
    reached_r1 = after[after.High >= r1]

    rec = dict(date=d, s1=round(s1, 1), pp=round(pp, 1), r1=round(r1, 1),
               touched_s1=True, touch_time=touch_time)
    if not reached_pp.empty:
        pp_idx = reached_pp.index[0]
        rec["reached_pp"] = True
        rec["mins_to_pp"] = (pp_idx - touch_idx).total_seconds() / 60
        rec["pts_captured_to_pp"] = pp - s1
    else:
        rec["reached_pp"] = False
    if not reached_r1.empty:
        r1_idx = reached_r1.index[0]
        rec["reached_r1"] = True
        rec["mins_to_r1"] = (r1_idx - touch_idx).total_seconds() / 60
        rec["pts_captured_to_r1"] = r1 - s1
    else:
        rec["reached_r1"] = False
    rec["day_peak_after_touch"] = after.High.max()
    rec["pts_captured_to_peak"] = after.High.max() - s1
    results.append(rec)

res = pd.DataFrame(results)
print(f"total days checked: {len(res)}")
print(f"days where price actually touched S1 intraday: {res.touched_s1.sum()} ({res.touched_s1.mean()*100:.1f}%)")
print()

touched = res[res.touched_s1 == True].copy()
print(f"=== Of the {len(touched)} S1-touch days ===")
print(f"  reached PP afterward same day: {touched.reached_pp.sum()} ({touched.reached_pp.mean()*100:.1f}%)")
print(f"  reached R1 afterward same day: {touched.reached_r1.sum()} ({touched.reached_r1.mean()*100:.1f}%)")
print()

pp_hit = touched[touched.reached_pp == True]
if not pp_hit.empty:
    print(f"=== Of the {len(pp_hit)} that reached PP ===")
    print(f"  median points captured (S1->PP): {pp_hit.pts_captured_to_pp.median():.1f} pts")
    print(f"  median minutes to reach PP: {pp_hit.mins_to_pp.median():.0f} min")
    print()

r1_hit = touched[touched.reached_r1 == True]
if not r1_hit.empty:
    print(f"=== Of the {len(r1_hit)} that reached R1 ===")
    print(f"  median points captured (S1->R1): {r1_hit.pts_captured_to_r1.median():.1f} pts")
    print(f"  median minutes to reach R1: {r1_hit.mins_to_r1.median():.0f} min")
    print()

print(f"=== ALL S1-touch days, real peak captured after touch (whether or not it formally reached PP/R1) ===")
print(f"  median points captured (S1->real subsequent peak): {touched.pts_captured_to_peak.median():.1f} pts")
print(f"  mean: {touched.pts_captured_to_peak.mean():.1f} pts")

s = touched.pts_captured_to_peak.sort_values(ascending=False)
top10pct_n = max(1, round(len(s)*0.10))
share = s.head(top10pct_n).sum()/s.sum()*100
print()
print(f"concentration check (top10% by count={top10pct_n}, share of total pts_captured sum): {share:.1f}%  n={len(s)}")

res.to_csv("nifty_pivot_entry_exit_timing.csv", index=False)
print()
print("saved: nifty_pivot_entry_exit_timing.csv")
