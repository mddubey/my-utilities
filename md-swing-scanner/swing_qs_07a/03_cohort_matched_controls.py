"""RQ-QS-07A-2 -- Fast-Mover Cohort Characterization + Matched Controls
(2026-09-29, critic-specified, pre-registered before running).

TWO cohorts, kept deliberately separate (critic's core point from 07A-1: "large
short-horizon opportunity and large short-horizon sustained movement are not the
same phenomenon"):
  Cohort A (Opportunity fast movers): D3 MFE >= its own empirical P95 (12.94%,
      from RQ-QS-07A-1). A research cohort, NOT a trading threshold.
  Cohort B (Sustained fast movers): D3 close-to-close return >= ITS OWN empirical
      P95 (8.89% -- NOT the MFE threshold forced onto a different distribution).

CONTROL: for each cohort event, one matched stock-day -- same calendar DATE (same
market/regime day) and the same cross-sectional LIQUIDITY DECILE that day
(traded_value_sma20, decision-time-safe at T, ranked among all eligible stock-days
on that date), excluding anything that is itself a Cohort A or B member. Fixed
seed (42), drawn once, not re-drawn to chase a result.

ANNOTATIONS kept as STRATIFICATION, per critic's explicit instruction -- NOT
filters, nothing removed from either cohort: nifty500_member, fo_eligible,
circuit_days_in_window (0-3, the KOTYARK-style price-band-hit signature),
liquidity decile.

TRADEABILITY AUDIT (critic's exact ask): of Cohort A specifically, how much is
circuit-involved / F&O / adequately liquid vs. the opposite -- not a filter, an
honest breakdown of what the P95 MFE tail is actually made of.

burst_v0 (path_shape=="burst", pre-registered 07A-1, NOT rewritten) and
burst_clean (max_return_d1>0 AND day_of_max==1 AND not spike_and_fade, added
2026-09-29 as a secondary descriptive label, per critic: "don't rerun... carry
burst_v0... optionally carry burst_clean") are both already columns on
event_matrix.csv -- reported here, not re-derived.
"""
import os
import numpy as np
import pandas as pd

os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
OUT_DIR = "swing_qs_07a"
SEED = 42

df = pd.read_csv(f"{OUT_DIR}/event_matrix.csv", parse_dates=["date"])
print(f"n={len(df):,} eligible stock-days\n")

P95_MFE = np.percentile(df.max_return_d3, 95)
P95_CLOSE = np.percentile(df.close_ret_d3, 95)
df["cohort_a"] = df.max_return_d3 >= P95_MFE
df["cohort_b"] = df.close_ret_d3 >= P95_CLOSE
print(f"Cohort A (opportunity, D3 MFE >= {P95_MFE:.2f}%): n={df.cohort_a.sum():,}")
print(f"Cohort B (sustained, D3 close_ret >= {P95_CLOSE:.2f}%): n={df.cohort_b.sum():,}")
overlap = (df.cohort_a & df.cohort_b).sum()
print(f"Overlap (in BOTH): {overlap:,} ({overlap/df.cohort_a.sum()*100:.1f}% of A, "
      f"{overlap/df.cohort_b.sum()*100:.1f}% of B)")

# --- per-date cross-sectional liquidity decile (decision-time-safe: traded_value_sma20 at T) ---
df["liq_decile"] = df.groupby("date")["traded_value_sma20"].transform(
    lambda x: pd.qcut(x, 10, labels=False, duplicates="drop"))

# --- matched control: same date, same liquidity decile, not itself a cohort member ---
rng = np.random.RandomState(SEED)
noncohort = df[~df.cohort_a & ~df.cohort_b]
noncohort_idx_by_key = noncohort.groupby(["date", "liq_decile"]).apply(lambda g: g.index.tolist(), include_groups=False)

def draw_control(row):
    key = (row["date"], row["liq_decile"])
    pool = noncohort_idx_by_key.get(key)
    if not pool:
        return None
    return pool[rng.randint(len(pool))]

cohort_events = df[df.cohort_a | df.cohort_b].copy()
print(f"\nDrawing matched controls for {len(cohort_events):,} cohort events...", flush=True)
control_idx = cohort_events.apply(draw_control, axis=1)
matched = control_idx.notna().sum()
print(f"Matched: {matched:,} ({matched/len(cohort_events)*100:.1f}%); unmatched (no same-date/decile non-cohort pool): "
      f"{len(cohort_events)-matched:,}")
controls = df.loc[control_idx.dropna().astype(int)].copy()

OUTCOME_COLS = ["max_return_d1", "max_return_d2", "max_return_d3", "adverse_d1", "adverse_d2", "adverse_d3",
                "close_ret_d1", "close_ret_d2", "close_ret_d3"]


def report_group(name, g):
    print(f"\n--- {name} (n={len(g):,}) ---")
    print(g[OUTCOME_COLS].median().round(2).to_string())
    print(f"  path_shape: {dict(g.path_shape.value_counts())}")
    print(f"  burst_v0={g.path_shape.eq('burst').sum()}  burst_clean={g.burst_clean.sum() if 'burst_clean' in g else 'n/a'}")
    print(f"  nifty500_member: {g.nifty500_member.mean()*100:.1f}%   fo_eligible: {g.fo_eligible.mean()*100:.1f}%")
    print(f"  circuit_days_in_window: {dict(g.circuit_days_in_window.value_counts().sort_index())}")


print("\n" + "=" * 100 + "\nCOHORT A (Opportunity) vs its matched control\n" + "=" * 100)
a = df[df.cohort_a]
a_controls = df.loc[control_idx[cohort_events.cohort_a].dropna().astype(int)]
report_group("Cohort A", a)
report_group("Cohort A matched control", a_controls)

print("\n" + "=" * 100 + "\nCOHORT B (Sustained) vs its matched control\n" + "=" * 100)
b = df[df.cohort_b]
b_controls = df.loc[control_idx[cohort_events.cohort_b].dropna().astype(int)]
report_group("Cohort B", b)
report_group("Cohort B matched control", b_controls)

print("\n" + "=" * 100 + "\nTRADEABILITY AUDIT of Cohort A (P95 MFE tail) -- not a filter, a breakdown\n" + "=" * 100)
print("By circuit involvement:")
print((a.circuit_days_in_window.value_counts(normalize=True).sort_index() * 100).round(1))
print("\nBy F&O eligibility:")
print((a.fo_eligible.value_counts(normalize=True) * 100).round(1))
print("\nBy NIFTY 500 membership:")
print((a.nifty500_member.value_counts(normalize=True) * 100).round(1))
print("\nCross-tab: circuit involvement x F&O (row %):")
print(pd.crosstab(a.circuit_days_in_window, a.fo_eligible, normalize="index").mul(100).round(1))
print("\nLiquidity decile distribution of Cohort A vs whole population:")
print("  Cohort A:", (a.liq_decile.value_counts(normalize=True).sort_index() * 100).round(1).to_dict())
print("  Whole pop:", (df.liq_decile.value_counts(normalize=True).sort_index() * 100).round(1).to_dict())
no_circuit_fo = a[(a.circuit_days_in_window == 0) & a.fo_eligible]
print(f"\nClean, tradeable-looking subset (0 circuit days AND F&O-eligible): {len(no_circuit_fo):,} "
      f"({len(no_circuit_fo)/len(a)*100:.1f}% of Cohort A)")
print(no_circuit_fo[OUTCOME_COLS].median().round(2).to_string())

print("\n" + "=" * 100 + "\nYear-by-year, Cohort A vs whole population (Rule #16)\n" + "=" * 100)
a["year"] = a.date.dt.year
df["year"] = df.date.dt.year
print(pd.concat([
    a.groupby("year").size().rename("cohort_a_n"),
    df.groupby("year").size().rename("total_n"),
], axis=1).assign(pct=lambda x: (x.cohort_a_n / x.total_n * 100).round(2)))

a.assign(role="cohort_a").to_csv(f"{OUT_DIR}/cohort_a_events.csv", index=False)
b.assign(role="cohort_b").to_csv(f"{OUT_DIR}/cohort_b_events.csv", index=False)
print(f"\nsaved cohort_a_events.csv ({len(a):,} rows), cohort_b_events.csv ({len(b):,} rows)")
