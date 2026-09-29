"""Ad hoc (2026-09-27), v2 per direct user feedback on nifty_pivot_entry_exit_timing.py:
1. Only count an entry touch at or after 13:30 IST (ignore anything earlier -- matches the
   user's actual trading window, and avoids crediting a touch/reach pair that both happened
   in the morning when the user wouldn't have been trading yet).
2. Add the SYMMETRIC BEARISH case: R1 touched intraday (resistance test, a PE/short setup),
   does it pull back to PP/S1 afterward -- given the real regime context (Nifty has been in
   a sustained downtrend, last close above its own 200-SMA was 2026-02-26 per this project's
   own standing regime finding), the bearish version may be more prevalent than the bullish
   one tested so far, not less.
"""
import yfinance as yf
import pandas as pd

CUTOFF_TIME = "13:30"

nifty = pd.read_csv("../data_cache/_NIFTY.csv")
nifty["Date"] = pd.to_datetime(nifty.Date)
h, l, c = nifty.High.shift(1), nifty.Low.shift(1), nifty.Close.shift(1)
nifty["pp"] = (h + l + c) / 3
nifty["r1"] = 2 * nifty.pp - l
nifty["s1"] = 2 * nifty.pp - h
piv = nifty.set_index(nifty.Date.dt.date)[["pp", "r1", "s1"]]

df = yf.download("^NSEI", period="60d", interval="5m", progress=False)
df.columns = df.columns.droplevel(1) if isinstance(df.columns, pd.MultiIndex) else df.columns
df.index = df.index.tz_convert("Asia/Kolkata")
df["date"] = df.index.date
df["time"] = df.index.time
cutoff_t = pd.Timestamp(CUTOFF_TIME).time()


def run_side(side):
    """side='bullish' (S1 touch -> reach PP, CE angle) or 'bearish' (R1 touch -> reach PP, PE angle)."""
    results = []
    for d in sorted(df.date.unique()):
        if d not in piv.index:
            continue
        row = piv.loc[d]
        pp = row.pp
        level = row.s1 if side == "bullish" else row.r1
        if pd.isna(level):
            continue
        day_bars = df[(df.date == d) & (df.time >= cutoff_t)]
        if day_bars.empty:
            continue
        if side == "bullish":
            touch = day_bars[day_bars.Low <= level]
        else:
            touch = day_bars[day_bars.High >= level]
        if touch.empty:
            results.append(dict(date=d, touched=False))
            continue
        touch_idx = touch.index[0]
        after = df.loc[touch_idx:][df.loc[touch_idx:].date == d]

        rec = dict(date=d, touched=True, touch_time=touch_idx.strftime("%H:%M"), level=round(level, 1), pp=round(pp, 1))
        if side == "bullish":
            hit = after[after.High >= pp]
            if not hit.empty:
                hit_idx = hit.index[0]
                rec["reached_target"] = True
                rec["mins_to_target"] = (hit_idx - touch_idx).total_seconds() / 60
                rec["pts_captured"] = pp - level
            else:
                rec["reached_target"] = False
            rec["extreme_after"] = after.High.max()
            rec["pts_captured_extreme"] = after.High.max() - level
        else:
            hit = after[after.Low <= pp]
            if not hit.empty:
                hit_idx = hit.index[0]
                rec["reached_target"] = True
                rec["mins_to_target"] = (hit_idx - touch_idx).total_seconds() / 60
                rec["pts_captured"] = level - pp
            else:
                rec["reached_target"] = False
            rec["extreme_after"] = after.Low.min()
            rec["pts_captured_extreme"] = level - after.Low.min()
        results.append(rec)
    return pd.DataFrame(results)


for side, label in [("bullish", "BULLISH (S1 touch >=13:30 -> reach PP, the CE angle)"),
                     ("bearish", "BEARISH (R1 touch >=13:30 -> reach PP, the PE angle)")]:
    res = run_side(side)
    touched = res[res.touched == True]
    print(f"=== {label} ===")
    print(f"  total days checked: {len(res)}")
    print(f"  touched the level at/after {CUTOFF_TIME}: {len(touched)} ({len(touched)/len(res)*100:.1f}%)")
    if len(touched) == 0:
        print()
        continue
    reached = touched[touched.reached_target == True]
    print(f"  reached PP afterward same day: {len(reached)} ({len(reached)/len(touched)*100:.1f}% of touches)")
    if not reached.empty:
        print(f"    median pts captured: {reached.pts_captured.median():.1f}")
        print(f"    median minutes to target: {reached.mins_to_target.median():.0f}")
    print(f"  ALL touches, real subsequent extreme captured (whether or not PP formally hit):")
    print(f"    median pts: {touched.pts_captured_extreme.median():.1f}  mean: {touched.pts_captured_extreme.mean():.1f}")
    s = touched.pts_captured_extreme.sort_values(ascending=False)
    top10pct_n = max(1, round(len(s)*0.10))
    share = s.head(top10pct_n).sum()/s.sum()*100 if s.sum() else float("nan")
    print(f"    concentration check (top10% n={top10pct_n}): {share:.1f}% of total  (n={len(s)})")
    print()
    res.to_csv(f"nifty_pivot_entry_exit_v2_{side}.csv", index=False)

print("saved: nifty_pivot_entry_exit_v2_bullish.csv, nifty_pivot_entry_exit_v2_bearish.csv")
