"""RQ-QS-07A-5R -- Weak-State Fast-Mover Robustness & Timing (2026-09-30, critic-specified).

Follow-up to 07A-5's headline discovery: the trend-strength/fast-mover
relationship is a U-shape, not monotonic -- decile 0 (weakest trend state)
shows a real, separate elevation on top of the already-established decile 9
(trend-continuation) tail. Critic's exact framing of what this RQ is and
isn't: "The important discovery here is not yet 'oversold reversal works.'
It is: the fast-mover phenomenon is heterogeneous... That is materially
different from the earlier single latent-trend-strength story." This script
tests whether that heterogeneity is ROBUST, and characterizes its TIMING --
it does NOT build a filter, does NOT choose a threshold, does NOT touch
QS-A, does NOT test trading performance. Critic's explicit prohibition list
(quoted): no oversold filter, no RSI<X test, no SMA200-distance<X% test, no
capitulation score, no adding D0 to the QS-A gate, no trading-performance
test, no reversal-indicator collection, no mean-reversion strategy build, no
abandoning the continuation branch, no sector-RS infrastructure.

FROZEN, per critic's explicit instruction:
  - D0 = bottom decile (decile==0) of the ALREADY-BUILT composite
    trend-strength score from 10_trend_state_anatomy.py. Not redefined,
    not re-thresholded, no decile-0-vs-decile-1 cherry-picking.
  - D2 = reference, NOT D1 and NOT the median decile -- D2 is the empirical
    TROUGH (07A-5's own shape-check found decile 2 is the minimum, not
    decile 1 or decile 5). Chosen because it's the natural "what does the
    baseline actually look like at its lowest point" comparison, not an
    arbitrary middle bucket.
  - Cohort A and B reported SEPARATELY throughout, never unioned.
  - Population: existing event_matrix.csv / trend_state_anatomy.csv (full
    neutral population, no matched-control rebuild).

PART 1 -- compact robustness matrix (critic's exact scope, deliberately NOT
07A-3R's full treatment reproduced wholesale -- liquidity/F&O radically
change the trend-state VARIABLES' magnitude, which isn't the question here;
the question is whether D0's ELEVATED RATE survives economically relevant
strata): Year (2022/2023/2024/2025/2026 YTD -- 2021 shown separately, extra
context, too little history to be a critic-requested stratum), Liquidity
tercile, F&O yes/no, Circuit zero/involved. For every cell: D0 rate, D2 rate,
D0/D2 ratio, n. No further subdivision, no threshold search.

PART 2 -- timing anatomy (critic's mandatory check): for D0 vs D2, Cohort A
and Cohort B separately, the D1/D2/D3 cumulative MFE and close-return
trajectory. Distinguishes "D0 events are already moving on D1" (an early
fast-mover state, could fit a short-horizon product) from "D0 events are
delayed 3-day reversals" (a different temporal phenotype) -- critic's own
worked example: D1+10/D2+20/D3+30 vs D1-2/D2+3/D3+15 tell very different
product-fit stories even with an identical final D3 number.

PART 3 -- definition-artifact check (critic's bullet F, "no obvious
definition artifact"): nominal price level of D0 vs D2 Cohort A events (thin,
low-priced names can show inflated % moves from tick-size/thin-float
effects). NOT re-testing corp-action-cleanliness or the 60-day min-history
floor -- both already enforced upstream in 01_event_matrix.py's own
eligibility rule, and every row here already required 252 days of price
history to have a populated dist_low252_pct (10_'s own feature-completeness
filter), which already rules out early-listing/cache-burn-in artifacts by
construction -- noted, not re-derived.

No new features. No thresholds chosen. No model. No strategy simulation.
"""
import pandas as pd
import numpy as np

OUT_DIR = "."

print("Loading trend_state_anatomy.csv (already-built composite/decile from 10_)...", flush=True)
df = pd.read_csv("trend_state_anatomy.csv", parse_dates=["date"])
df["liq_decile"] = df.groupby("date")["traded_value_sma20"].transform(
    lambda x: pd.qcut(x, 10, labels=False, duplicates="drop") if x.notna().sum() >= 10 else np.nan)
df["liq_tercile"] = pd.cut(df.liq_decile, [-1, 2, 6, 9], labels=["low", "mid", "high"])
df["circuit_involved"] = df.circuit_days_in_window > 0

d0 = df[df.decile == 0]
d2 = df[df.decile == 2]
print(f"D0 (frozen bottom decile): {len(d0):,}  D2 (empirical trough, reference): {len(d2):,}")
print(f"D0 Cohort A rate: {d0.cohort_a.mean()*100:.2f}%  D2 Cohort A rate: {d2.cohort_a.mean()*100:.2f}%  "
      f"ratio: {d0.cohort_a.mean()/d2.cohort_a.mean():.2f}x")


def matrix_row(sub0, sub2, label):
    n0, n2 = len(sub0), len(sub2)
    if n0 < 30 or n2 < 30:
        return dict(stratum=label, D0_n=n0, D2_n=n2, D0_pct_a=np.nan, D2_pct_a=np.nan, ratio_a=np.nan,
                     D0_pct_b=np.nan, D2_pct_b=np.nan, ratio_b=np.nan, note="too thin, <30, skipped")
    d0a, d2a = sub0.cohort_a.mean() * 100, sub2.cohort_a.mean() * 100
    d0b, d2b = sub0.cohort_b.mean() * 100, sub2.cohort_b.mean() * 100
    return dict(stratum=label, D0_n=n0, D2_n=n2, D0_pct_a=round(d0a, 2), D2_pct_a=round(d2a, 2),
                 ratio_a=round(d0a / d2a, 2) if d2a > 0 else np.nan,
                 D0_pct_b=round(d0b, 2), D2_pct_b=round(d2b, 2),
                 ratio_b=round(d0b / d2b, 2) if d2b > 0 else np.nan, note="")


print(f"\n{'='*110}\nPART 1 -- ROBUSTNESS MATRIX (D0 vs D2, no threshold search, no further subdivision)\n{'='*110}")
rows = []
print("\n-- By year (2021 shown as extra context, not part of critic's requested list) --")
for y in [2021, 2022, 2023, 2024, 2025, 2026]:
    label = f"{y} (YTD)" if y == 2026 else str(y)
    r = matrix_row(d0[d0.year == y], d2[d2.year == y], f"year={label}")
    rows.append(r)

print("\n-- By liquidity tercile --")
for t in ["low", "mid", "high"]:
    r = matrix_row(d0[d0.liq_tercile == t], d2[d2.liq_tercile == t], f"liq_tercile={t}")
    rows.append(r)

print("\n-- By F&O eligibility --")
for v in [True, False]:
    r = matrix_row(d0[d0.fo_eligible == v], d2[d2.fo_eligible == v], f"fo_eligible={v}")
    rows.append(r)

print("\n-- By circuit involvement --")
for v in [False, True]:
    r = matrix_row(d0[d0.circuit_involved == v], d2[d2.circuit_involved == v], f"circuit_involved={v}")
    rows.append(r)

matrix = pd.DataFrame(rows)
print(matrix.to_string(index=False))
matrix.to_csv(f"{OUT_DIR}/weak_state_robustness_matrix.csv", index=False)

print(f"\n{'='*110}\nPART 2 -- TIMING ANATOMY (D0 vs D2, Cohort A / Cohort B separately)\n{'='*110}")
timing_rows = []
for dec_label, sub in [("D0", d0), ("D2", d2)]:
    for cohort_label, cohort_col in [("CohortA", "cohort_a"), ("CohortB", "cohort_b")]:
        events = sub[sub[cohort_col]]
        timing_rows.append(dict(
            decile=dec_label, cohort=cohort_label, n=len(events),
            median_mfe_d1=events.max_return_d1.median(), median_mfe_d2=events.max_return_d2.median(),
            median_mfe_d3=events.max_return_d3.median(),
            median_close_d1=events.close_ret_d1.median(), median_close_d2=events.close_ret_d2.median(),
            median_close_d3=events.close_ret_d3.median(),
            incr_mfe_d1_to_d2=events.max_return_d2.median() - events.max_return_d1.median(),
            incr_mfe_d2_to_d3=events.max_return_d3.median() - events.max_return_d2.median(),
            d1_frac_of_d3_mfe=(events.max_return_d1.median() / events.max_return_d3.median() * 100)
                                if events.max_return_d3.median() else np.nan,
        ))
timing = pd.DataFrame(timing_rows).round(2)
print(timing.to_string(index=False))
timing.to_csv(f"{OUT_DIR}/weak_state_timing_anatomy.csv", index=False)

print(f"\n{'='*110}\nPART 3 -- DEFINITION-ARTIFACT CHECK: nominal price level (D0 vs D2 Cohort A)\n{'='*110}")
for dec_label, sub in [("D0", d0), ("D2", d2)]:
    ev = sub[sub.cohort_a]
    print(f"  {dec_label} Cohort A close price: P10={np.percentile(ev.close,10):.2f}  "
          f"median={ev.close.median():.2f}  P90={np.percentile(ev.close,90):.2f}  "
          f"%under_Rs20={(ev.close < 20).mean()*100:.2f}%  %under_Rs50={(ev.close < 50).mean()*100:.2f}%  (n={len(ev):,})")
print("\nNote: corp-action-day cleanliness and the 60-day min-history floor are already enforced upstream "
      "in 01_event_matrix.py's own eligibility rule. Every row here already required 252 days of price "
      "history for a populated dist_low252_pct (10_'s own feature-completeness filter) -- this already "
      "rules out early-listing/cache-burn-in artifacts by construction, not re-tested here.")

print("\nDONE")
