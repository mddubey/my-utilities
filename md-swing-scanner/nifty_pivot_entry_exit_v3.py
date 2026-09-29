"""Ad hoc (2026-09-27), v3 -- corrects a real error in v2: PP is the pivot MIDPOINT, not a
proper directional target for either side. Correct symmetric version, per direct user
feedback: BULLISH = support (S1) touch -> resistance (R1) target (the full swing). BEARISH
= resistance (R1) touch -> support (S1) target (the full swing, mirror image). Still
restricted to touches at/after 13:30 IST per the user's real trading window.
"""
import yfinance as yf
import pandas as pd

CUTOFF_TIME = "13:30"

nifty = pd.read_csv("data_cache/_NIFTY.csv")
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
    """side='bullish' (S1 touch -> R1 target) or 'bearish' (R1 touch -> S1 target)."""
    results = []
    for d in sorted(df.date.unique()):
        if d not in piv.index:
            continue
        row = piv.loc[d]
        entry_level = row.s1 if side == "bullish" else row.r1
        target_level = row.r1 if side == "bullish" else row.s1
        if pd.isna(entry_level) or pd.isna(target_level):
            continue
        day_bars = df[(df.date == d) & (df.time >= cutoff_t)]
        if day_bars.empty:
            continue
        if side == "bullish":
            touch = day_bars[day_bars.Low <= entry_level]
        else:
            touch = day_bars[day_bars.High >= entry_level]
        if touch.empty:
            results.append(dict(date=d, touched=False))
            continue
        touch_idx = touch.index[0]
        after = df.loc[touch_idx:][df.loc[touch_idx:].date == d]

        rec = dict(date=d, touched=True, touch_time=touch_idx.strftime("%H:%M"),
                   entry_level=round(entry_level, 1), target_level=round(target_level, 1))
        if side == "bullish":
            hit = after[after.High >= target_level]
            rec["extreme_after"] = after.High.max()
        else:
            hit = after[after.Low <= target_level]
            rec["extreme_after"] = after.Low.min()

        if not hit.empty:
            hit_idx = hit.index[0]
            rec["reached_target"] = True
            rec["mins_to_target"] = (hit_idx - touch_idx).total_seconds() / 60
        else:
            rec["reached_target"] = False
        rec["pts_travelled"] = abs(target_level - entry_level)
        rec["pts_captured_extreme"] = (rec["extreme_after"] - entry_level) if side == "bullish" else (entry_level - rec["extreme_after"])
        results.append(rec)
    return pd.DataFrame(results)


for side, label in [("bullish", "BULLISH (S1 touch >=13:30 -> R1 target, full swing)"),
                     ("bearish", "BEARISH (R1 touch >=13:30 -> S1 target, full swing)")]:
    res = run_side(side)
    touched = res[res.touched == True]
    print(f"=== {label} ===")
    print(f"  total days checked: {len(res)}")
    print(f"  touched entry level at/after {CUTOFF_TIME}: {len(touched)} ({len(touched)/len(res)*100:.1f}%)")
    if len(touched) == 0:
        print()
        continue
    print(f"  median distance entry->target (points needed): {touched.pts_travelled.median():.0f}")
    reached = touched[touched.reached_target == True]
    print(f"  fully reached target: {len(reached)} ({len(reached)/len(touched)*100:.1f}% of touches)")
    if not reached.empty:
        print(f"    median minutes to reach target: {reached.mins_to_target.median():.0f}")
    print(f"  ALL touches, real points captured toward target (extreme reached, whether full target hit or not):")
    print(f"    median: {touched.pts_captured_extreme.median():.1f}  mean: {touched.pts_captured_extreme.mean():.1f}")
    print(f"    % where at least SOME real progress made (captured >0 pts toward target): "
          f"{(touched.pts_captured_extreme>0).mean()*100:.1f}%")
    print()
    res.to_csv(f"nifty_pivot_entry_exit_v3_{side}.csv", index=False)

print("saved: nifty_pivot_entry_exit_v3_bullish.csv, nifty_pivot_entry_exit_v3_bearish.csv")
