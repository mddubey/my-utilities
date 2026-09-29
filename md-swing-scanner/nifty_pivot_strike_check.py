"""Ad hoc (2026-09-27, tier #2 of the NIFTY pivot question): across every real NIFTY weekly
expiry day since weeklies started (2024-01 onward), does the CE strike closest to that day's
real R1 pivot (computed from the PRIOR day's H/L/C, no lookahead) show a bigger Open->High
move than strikes further away -- the exact mechanism found by hand for 2026-09-22 (23400 vs
23450/23500), now tested at scale instead of assumed from one example.
"""
import pandas as pd
import glob
import os

OPTIONS_DIR = "options_cache"

nifty = pd.read_csv("data_cache/_NIFTY.csv")
nifty["Date"] = pd.to_datetime(nifty.Date)
h, l, c = nifty.High.shift(1), nifty.Low.shift(1), nifty.Close.shift(1)
nifty["pp"] = (h + l + c) / 3
nifty["r1"] = 2 * nifty.pp - l
nifty["r2"] = nifty.pp + (h - l)
nifty["s1"] = 2 * nifty.pp - h
nifty["s2"] = nifty.pp - (h - l)
pivots_by_date = nifty.set_index(nifty.Date.dt.strftime("%Y%m%d"))[["pp", "r1", "r2", "s1", "s2"]].to_dict("index")

files = sorted(glob.glob(f"{OPTIONS_DIR}/*.csv"))
files = [f for f in files if os.path.basename(f)[:4] >= "2024"]  # weeklies start 2024-01

results = []
n_checked = 0
for f in files:
    date_str = os.path.basename(f)[:8]
    if date_str not in pivots_by_date:
        continue
    n_checked += 1
    df = pd.read_csv(f)
    nifty_ce = df[(df.TckrSymb == "NIFTY") & (df.FinInstrmTp == "IDO") & (df.OptnTp == "CE")]
    if nifty_ce.empty:
        continue
    exp_today = nifty_ce[nifty_ce.XpryDt == pd.to_datetime(date_str).strftime("%Y-%m-%d")]
    if exp_today.empty:
        continue  # not a real expiry day for NIFTY weeklies

    piv = pivots_by_date[date_str]
    r1 = piv["r1"]
    if pd.isna(r1):
        continue
    spot = exp_today.UndrlygPric.iloc[0]
    otm = exp_today[(exp_today.StrkPric > spot) & (exp_today.OpnPric > 0)].copy()
    if otm.empty:
        continue
    otm["dist_from_r1"] = (otm.StrkPric - r1).abs()
    otm["open_to_high_mult"] = otm.HghPric / otm.OpnPric
    otm["otm_pts"] = otm.StrkPric - spot

    near = otm.sort_values("dist_from_r1").iloc[0]   # strike closest to R1
    far_candidates = otm[otm.otm_pts >= near.otm_pts + 150]  # meaningfully further OTM
    if far_candidates.empty:
        continue
    far = far_candidates.sort_values("dist_from_r1").iloc[0]

    results.append(dict(date=date_str, spot=spot, r1=r1,
                         near_strike=near.StrkPric, near_dist_from_r1=near.dist_from_r1,
                         near_mult=near.open_to_high_mult,
                         far_strike=far.StrkPric, far_otm_pts=far.otm_pts,
                         far_mult=far.open_to_high_mult))

res = pd.DataFrame(results)
print(f"real NIFTY weekly expiry days checked: {n_checked}")
print(f"days with both a near-R1 strike and a meaningfully-further OTM strike, tradeable data: n={len(res)}")
print()
print(f"=== NEAR-R1 strike (median distance from R1: {res.near_dist_from_r1.median():.0f} pts) ===")
print(f"  median Open->High mult: {res.near_mult.median():.2f}x")
print(f"  mean Open->High mult: {res.near_mult.mean():.2f}x")
print(f"  % reaching >=1.5x: {(res.near_mult>=1.5).mean()*100:.1f}%")
print(f"  % reaching >=2x: {(res.near_mult>=2).mean()*100:.1f}%")
print()
print(f"=== FAR (further OTM by >=150pts beyond the near strike) strike ===")
print(f"  median Open->High mult: {res.far_mult.median():.2f}x")
print(f"  mean Open->High mult: {res.far_mult.mean():.2f}x")
print(f"  % reaching >=1.5x: {(res.far_mult>=1.5).mean()*100:.1f}%")
print(f"  % reaching >=2x: {(res.far_mult>=2).mean()*100:.1f}%")
print()
print(f"=== Head-to-head, same day: near beat far ===")
print(f"  {(res.near_mult > res.far_mult).mean()*100:.1f}% of days ({(res.near_mult > res.far_mult).sum()}/{len(res)})")

s = res.near_mult.sort_values(ascending=False)
top10pct_n = max(1, round(len(s)*0.10))
share = s.head(top10pct_n).sum()/s.sum()*100
print()
print(f"concentration check (near-R1 population, top10% by count={top10pct_n}, share of total mult sum): {share:.1f}%  n={len(s)}")

res.to_csv("nifty_pivot_strike_check.csv", index=False)
print()
print("saved: nifty_pivot_strike_check.csv")
