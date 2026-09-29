"""Ad hoc (2026-09-27): the part we CAN actually measure well -- real intraday NIFTY spot
data (~60 trading days via yfinance, the only real intraday window available). For every
day: find the day's Low (support test) and the real subsequent peak (highest High after that
Low), then measure the DELTA in points and the TIME elapsed to get there. No option magnitude
claims here -- underlying-only mechanics, split by expiry-Tuesday vs ordinary day to see if
expiry days genuinely behave differently (bigger/faster moves), which is the real, checkable
version of the "does this happen often enough to matter" question.
"""
import yfinance as yf
import pandas as pd
import glob
import os

df = yf.download("^NSEI", period="60d", interval="5m", progress=False)
df.columns = df.columns.droplevel(1) if isinstance(df.columns, pd.MultiIndex) else df.columns
df.index = df.index.tz_convert("Asia/Kolkata")
df["date"] = df.index.date

OPTIONS_DIR = "../options_cache"
expiry_dates = set()
for f in glob.glob(f"{OPTIONS_DIR}/*.csv"):
    date_str = os.path.basename(f)[:8]
    if date_str < "20240101":
        continue
# cheap check: reuse the file list, but only look up expiry status for dates actually in our
# intraday window to avoid re-reading ~700 files
candidate_dates = sorted(df.date.unique())
for d in candidate_dates:
    date_str = pd.Timestamp(d).strftime("%Y%m%d")
    path = f"{OPTIONS_DIR}/{date_str}.csv"
    if not os.path.exists(path):
        continue
    odf = pd.read_csv(path, usecols=["TckrSymb", "FinInstrmTp", "OptnTp", "XpryDt"])
    nifty_ce = odf[(odf.TckrSymb == "NIFTY") & (odf.FinInstrmTp == "IDO") & (odf.OptnTp == "CE")]
    if not nifty_ce.empty and (nifty_ce.XpryDt == pd.Timestamp(d).strftime("%Y-%m-%d")).any():
        expiry_dates.add(d)

results = []
for d in candidate_dates:
    day_bars = df[df.date == d]
    if len(day_bars) < 5:
        continue
    low_idx = day_bars.Low.idxmin()
    low_val = day_bars.Low.min()
    after_low = day_bars.loc[low_idx:]
    if len(after_low) < 2:
        continue
    peak_val = after_low.High.max()
    peak_time_idx = after_low.High.idxmax()
    delta_pts = peak_val - low_val
    delta_pct = delta_pts / low_val * 100
    minutes_to_peak = (peak_time_idx - low_idx).total_seconds() / 60

    results.append(dict(date=d, is_expiry=d in expiry_dates,
                         low=low_val, low_time=low_idx.strftime("%H:%M"),
                         peak=peak_val, peak_time=peak_time_idx.strftime("%H:%M"),
                         delta_pts=delta_pts, delta_pct=delta_pct,
                         minutes_to_peak=minutes_to_peak))

res = pd.DataFrame(results)
print(f"total trading days with intraday data: {len(res)}")
print(f"of which real NIFTY weekly expiry days: {res.is_expiry.sum()}")
print()

for label, sub in [("ALL DAYS", res), ("EXPIRY DAYS ONLY", res[res.is_expiry]), ("NON-EXPIRY DAYS", res[~res.is_expiry])]:
    print(f"=== {label} (n={len(sub)}) ===")
    print(f"  median delta (low->peak): {sub.delta_pts.median():.1f} pts ({sub.delta_pct.median():.2f}%)")
    print(f"  mean delta: {sub.delta_pts.mean():.1f} pts ({sub.delta_pct.mean():.2f}%)")
    print(f"  median time to peak: {sub.minutes_to_peak.median():.0f} min")
    print(f"  % with delta >=50pts (~0.2%): {(sub.delta_pts>=50).mean()*100:.1f}%")
    print(f"  % with delta >=100pts (~0.4%): {(sub.delta_pts>=100).mean()*100:.1f}%")
    print(f"  % where the move happened FAST (<=30 min to peak) AND delta>=50pts: "
          f"{((sub.minutes_to_peak<=30)&(sub.delta_pts>=50)).mean()*100:.1f}%")
    print()

s = res.delta_pts.sort_values(ascending=False)
top10pct_n = max(1, round(len(s)*0.10))
share = s.head(top10pct_n).sum()/s.sum()*100
print(f"concentration check (all days, top10% by count={top10pct_n}, share of total delta sum): {share:.1f}%  n={len(s)}")

res.to_csv("nifty_support_resistance_timing.csv", index=False)
print()
print("saved: nifty_support_resistance_timing.csv")
