"""RQ-QS-07A-3, pivot-distance supplement (2026-09-29, direct user request).

Motivating observation: a real, live COAL INDIA R1-rejection (2026-09-28: poked
above R1, failed R2, closed back below the pivot) -- checked and confirmed
against real cached bars before building anything (see FINDINGS.md). User's
ask: does distance to classical floor-trader pivot levels (R1/R2/PP), at
DAILY/WEEKLY/MONTHLY scale, show any of the same kind of pre-event signal the
trend/momentum features did in 05_?

Adds monthly_pivots() to pivots.py (new, reuses the existing weekly_pivots()'s
shared `_levels()` formula and PRIOR-period-shift convention exactly -- same
no-lookahead discipline, own dedicated test added to tests/test_pivots.py).

HOURLY, explicitly NOT included in this population-wide pass: real intraday
data in this project only covers 2026-06-10 to 2026-09-23 (~3.5 months) --
confirmed directly (RELIANCE intraday_cache), not assumed. That's a tiny sliver
of the 5-year Cohort A population. Reported separately, honestly, as its own
small side-check on whatever Cohort A events happen to fall in that window --
NOT presented as a population-wide finding the way daily/weekly/monthly are.

Same population as 05_: full Cohort A (102,837) + matched controls
(reconstructed identically, same seed=42). Same information cutoff: every
pivot level is computed from the PRIOR completed day/week/month, decision-time-
safe at T.

Features (all as % distance from Close at T, decision-time-safe):
  dist_daily_pp/r1/r2_pct    -- already-cached production columns (pp/r1/r2),
                                 reused directly, not recomputed
  dist_weekly_pp/r1/r2_pct   -- `weekly_pivots()`, computed fresh per ticker
  dist_monthly_pp/r1/r2_pct  -- `monthly_pivots()`, computed fresh per ticker

No threshold chosen. No filter. Distribution comparison only, same as 05_.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots
from pivots import weekly_pivots, monthly_pivots

OUT_DIR = "swing_qs_07a"
SEED = 42

print("Reconstructing Cohort A + matched controls (identical to 03_/05_)...", flush=True)
df = pd.read_csv(f"{OUT_DIR}/event_matrix.csv", parse_dates=["date"])
P95_MFE = np.percentile(df.max_return_d3, 95)
df["cohort_a"] = df.max_return_d3 >= P95_MFE
df["cohort_b"] = df.close_ret_d3 >= np.percentile(df.close_ret_d3, 95)
df["liq_decile"] = df.groupby("date")["traded_value_sma20"].transform(
    lambda x: pd.qcut(x, 10, labels=False, duplicates="drop"))

rng = np.random.RandomState(SEED)
noncohort = df[~df.cohort_a & ~df.cohort_b]
pool_by_key = noncohort.groupby(["date", "liq_decile"]).apply(lambda g: g.index.tolist(), include_groups=False)

def draw_control(row):
    pool = pool_by_key.get((row["date"], row["liq_decile"]))
    return pool[rng.randint(len(pool))] if pool else None

a = df[df.cohort_a].copy()
control_idx = a.apply(draw_control, axis=1)
a = a[control_idx.notna()].copy()
controls = df.loc[control_idx.dropna().astype(int)].copy()
a["group"], controls["group"] = "cohort_a", "control"
work = pd.concat([a, controls], ignore_index=True)[["ticker", "date", "group"]]
print(f"Cohort A: {len(a):,}  Controls: {len(controls):,}")

INTRADAY_START, INTRADAY_END = pd.Timestamp("2026-06-10"), pd.Timestamp("2026-09-23")
in_intraday_window = work.date.between(INTRADAY_START, INTRADAY_END)
print(f"Events falling inside the real intraday-data window ({INTRADAY_START.date()} to "
      f"{INTRADAY_END.date()}): {in_intraday_window.sum():,} of {len(work):,} "
      f"({in_intraday_window.mean()*100:.2f}%) -- too small a slice for a population-wide "
      f"hourly-pivot check; not attempted here, reported as a known gap only.")

print("Computing pivot-distance features (per-ticker, decision-time-safe)...", flush=True)
cache = {}
rows_out = []
for n, r in enumerate(work.itertuples()):
    if n % 20000 == 0:
        print(f"  {n}/{len(work)}", flush=True)
    if r.ticker not in cache:
        try:
            idf = load(r.ticker, daily_pivots)  # gives Close + daily pp/r1/r2 already
            idf = idf.join(weekly_pivots(idf).add_prefix("wk_"))
            idf = idf.join(monthly_pivots(idf).add_prefix("mo_"))
            cache[r.ticker] = idf
        except FileNotFoundError:
            cache[r.ticker] = None
    idf = cache[r.ticker]
    if idf is None or r.date not in idf.index:
        continue
    row = idf.loc[r.date]
    close = row.Close

    def dist(level):
        return (close / level - 1) * 100 if pd.notna(level) and level else np.nan

    rows_out.append(dict(
        ticker=r.ticker, date=r.date, group=r.group,
        dist_daily_pp_pct=dist(row.pp), dist_daily_r1_pct=dist(row.r1), dist_daily_r2_pct=dist(row.r2),
        dist_weekly_pp_pct=dist(row.wk_pp), dist_weekly_r1_pct=dist(row.wk_r1), dist_weekly_r2_pct=dist(row.wk_r2),
        dist_monthly_pp_pct=dist(row.mo_pp), dist_monthly_r1_pct=dist(row.mo_r1), dist_monthly_r2_pct=dist(row.mo_r2),
    ))

feats = pd.DataFrame(rows_out)
feats.to_csv(f"{OUT_DIR}/pivot_distance_features.csv", index=False)
print(f"\n{len(feats):,} rows, saved pivot_distance_features.csv")


def pstack(s, fmt="{:.2f}"):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        return "n=0"
    return f"P25={fmt.format(np.percentile(s,25))} P50={fmt.format(np.percentile(s,50))} P75={fmt.format(np.percentile(s,75))} (n={len(s):,})"


print("\n" + "=" * 100 + "\nPIVOT-DISTANCE FEATURES -- Cohort A vs matched control\n" + "=" * 100)
ca, ct = feats[feats.group == "cohort_a"], feats[feats.group == "control"]
for f in ["dist_daily_pp_pct", "dist_daily_r1_pct", "dist_daily_r2_pct",
          "dist_weekly_pp_pct", "dist_weekly_r1_pct", "dist_weekly_r2_pct",
          "dist_monthly_pp_pct", "dist_monthly_r1_pct", "dist_monthly_r2_pct"]:
    ca_med, ct_med = ca[f].median(), ct[f].median()
    print(f"  {f:24s} cohort_a: {pstack(ca[f])}   control: {pstack(ct[f])}   gap={ca_med-ct_med:+.2f}")
