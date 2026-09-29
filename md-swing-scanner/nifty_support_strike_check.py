"""Ad hoc (2026-09-27, correcting nifty_pivot_strike_check.py's methodology per direct user
feedback): the earlier check picked the "near" strike by distance from R1 and measured
Open->High -- doesn't match the real trade (enter near SUPPORT intraday, exit at resistance).
Corrected: pick the near strike by distance from the day's own LOW (real proxy for "spot
when you entered near support"), measure Low->High (bought near the low, exited near the
day's high) -- matches the actual strategy being tested.
"""
import pandas as pd
import glob
import os

OPTIONS_DIR = "options_cache"

files = sorted(glob.glob(f"{OPTIONS_DIR}/*.csv"))
files = [f for f in files if os.path.basename(f)[:4] >= "2024"]

results = []
n_checked = 0
for f in files:
    date_str = os.path.basename(f)[:8]
    df = pd.read_csv(f)
    nifty_ce = df[(df.TckrSymb == "NIFTY") & (df.FinInstrmTp == "IDO") & (df.OptnTp == "CE")]
    if nifty_ce.empty:
        continue
    exp_today = nifty_ce[nifty_ce.XpryDt == pd.to_datetime(date_str).strftime("%Y-%m-%d")]
    if exp_today.empty:
        continue  # not a real NIFTY weekly expiry day
    n_checked += 1

    spot = exp_today.UndrlygPric.iloc[0]
    otm = exp_today[(exp_today.StrkPric > spot) & (exp_today.OpnPric > 0) & (exp_today.LwPric > 0)].copy()
    if otm.empty:
        continue
    otm["low_to_high_mult"] = otm.HghPric / otm.LwPric
    otm["otm_pts"] = otm.StrkPric - spot

    near = otm.sort_values("otm_pts").iloc[0]  # closest-to-spot OTM strike (proxy: near support entry)
    far_candidates = otm[otm.otm_pts >= near.otm_pts + 150]
    if far_candidates.empty:
        continue
    far = far_candidates.sort_values("otm_pts").iloc[0]  # nearest strike that's >=150pts further out

    results.append(dict(date=date_str, spot=spot,
                         near_strike=near.StrkPric, near_otm_pts=near.otm_pts,
                         near_mult=near.low_to_high_mult,
                         far_strike=far.StrkPric, far_otm_pts=far.otm_pts,
                         far_mult=far.low_to_high_mult))

res = pd.DataFrame(results)
print(f"real NIFTY weekly expiry days checked: {n_checked}")
print(f"days with usable near+far strike data: n={len(res)}")
print()
print(f"=== NEAR strike (closest-to-spot OTM, median dist: {res.near_otm_pts.median():.0f}pts) ===")
print(f"  median Low->High mult: {res.near_mult.median():.2f}x")
print(f"  mean Low->High mult: {res.near_mult.mean():.2f}x")
print(f"  % reaching >=3x: {(res.near_mult>=3).mean()*100:.1f}%")
print(f"  % reaching >=5x: {(res.near_mult>=5).mean()*100:.1f}%")
print(f"  % reaching >=10x: {(res.near_mult>=10).mean()*100:.1f}%")
print()
print(f"=== FAR strike (>=150pts further OTM than near, median dist: {res.far_otm_pts.median():.0f}pts) ===")
print(f"  median Low->High mult: {res.far_mult.median():.2f}x")
print(f"  mean Low->High mult: {res.far_mult.mean():.2f}x")
print(f"  % reaching >=3x: {(res.far_mult>=3).mean()*100:.1f}%")
print(f"  % reaching >=5x: {(res.far_mult>=5).mean()*100:.1f}%")
print(f"  % reaching >=10x: {(res.far_mult>=10).mean()*100:.1f}%")
print()
print(f"=== Head-to-head, same day: near beat far ===")
print(f"  {(res.near_mult > res.far_mult).mean()*100:.1f}% of days ({(res.near_mult > res.far_mult).sum()}/{len(res)})")

for label, col in [("NEAR", "near_mult"), ("FAR", "far_mult")]:
    s = res[col].sort_values(ascending=False)
    top10pct_n = max(1, round(len(s)*0.10))
    share = s.head(top10pct_n).sum()/s.sum()*100
    print(f"concentration check ({label}, top10% by count={top10pct_n}, share of total mult sum): {share:.1f}%  n={len(s)}")

res.to_csv("nifty_support_strike_check.csv", index=False)
print()
print("saved: nifty_support_strike_check.csv")
