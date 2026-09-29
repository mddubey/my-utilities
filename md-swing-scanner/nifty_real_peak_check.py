"""Ad hoc (2026-09-27): using the REAL ~60-trading-day intraday NIFTY spot window (the only
real intraday data available, via yfinance), find each weekly-expiry day's actual low (support
test) and the REAL subsequent recovery peak (not a pivot proxy like R1 -- the real, observed
high after that low). Then check, using real EOD option bhavcopy, whether the strike nearest
that REAL peak shows a bigger Open->High move than a strike 150+pts further OTM.

Important framing, not to be confused with the earlier R1 check: this is a MECHANISM check
(does proximity to the real, hindsight-known peak explain the multiplier), not a PREDICTIVE
check (can you know the peak in advance) -- the R1 check already answered the predictive
question honestly (no reliable edge). This answers a different, narrower question: given
where the bounce actually went, was the near-that-level strike the one that benefited most.
"""
import yfinance as yf
import pandas as pd
import glob
import os

df = yf.download("^NSEI", period="60d", interval="5m", progress=False)
df.columns = df.columns.droplevel(1) if isinstance(df.columns, pd.MultiIndex) else df.columns
df.index = df.index.tz_convert("Asia/Kolkata")
df["date"] = df.index.date

OPTIONS_DIR = "options_cache"
files = {os.path.basename(f)[:8]: f for f in glob.glob(f"{OPTIONS_DIR}/*.csv")}

results = []
for d in sorted(df.date.unique()):
    date_str = pd.Timestamp(d).strftime("%Y%m%d")
    if date_str not in files:
        continue
    odf = pd.read_csv(files[date_str])
    nifty_ce = odf[(odf.TckrSymb == "NIFTY") & (odf.FinInstrmTp == "IDO") & (odf.OptnTp == "CE")]
    exp_today = nifty_ce[nifty_ce.XpryDt == pd.Timestamp(d).strftime("%Y-%m-%d")]
    if exp_today.empty:
        continue  # not a real NIFTY weekly expiry day

    day_bars = df[df.date == d]
    low_idx = day_bars.Low.idxmin()
    low_val = day_bars.Low.min()
    after_low = day_bars.loc[low_idx:]
    if len(after_low) < 2:
        continue
    peak_val = after_low.High.max()
    peak_time = after_low.High.idxmax()

    spot = exp_today.UndrlygPric.iloc[0]
    otm = exp_today[(exp_today.StrkPric > spot) & (exp_today.OpnPric > 0)].copy()
    if otm.empty:
        continue
    otm["dist_from_peak"] = (otm.StrkPric - peak_val).abs()
    otm["open_to_high_mult"] = otm.HghPric / otm.OpnPric
    otm["otm_pts"] = otm.StrkPric - spot

    near = otm.sort_values("dist_from_peak").iloc[0]
    far_candidates = otm[otm.otm_pts >= near.otm_pts + 150]
    if far_candidates.empty:
        continue
    far = far_candidates.sort_values("dist_from_peak").iloc[0]

    results.append(dict(date=date_str, spot=spot, day_low=low_val, low_time=low_idx.strftime("%H:%M"),
                         real_peak=peak_val, peak_time=peak_time.strftime("%H:%M"),
                         near_strike=near.StrkPric, near_dist_from_peak=near.dist_from_peak,
                         near_mult=near.open_to_high_mult,
                         far_strike=far.StrkPric, far_otm_pts=far.otm_pts,
                         far_mult=far.open_to_high_mult))

res = pd.DataFrame(results)
print(f"real weekly expiry days with intraday data: n={len(res)}")
print()
print(res[["date", "day_low", "low_time", "real_peak", "peak_time", "near_strike", "near_mult", "far_strike", "far_mult"]].to_string(index=False))
print()
print(f"=== NEAR (real-peak-proximate) strike ===")
print(f"  median Open->High mult: {res.near_mult.median():.2f}x   mean: {res.near_mult.mean():.2f}x")
print(f"=== FAR (150+pts further OTM) strike ===")
print(f"  median Open->High mult: {res.far_mult.median():.2f}x   mean: {res.far_mult.mean():.2f}x")
print()
print(f"near beat far: {(res.near_mult>res.far_mult).mean()*100:.1f}% of days ({(res.near_mult>res.far_mult).sum()}/{len(res)})")

res.to_csv("nifty_real_peak_check.csv", index=False)
print()
print("saved: nifty_real_peak_check.csv")
