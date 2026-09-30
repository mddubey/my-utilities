"""RQ-QS-07A-6T -- Weak-State Transition Anatomy (2026-09-30, critic-specified).

Tests whether the "sharp drop -> pause -> fast move" hypothesis (from 07A-6,
robustness-confirmed in 07A-6R) is actually visible in the real day-by-day
price path, or merely a plausible retrospective reading of cross-sectional
statistics. NOT another predictor search -- no new features, no thresholds,
no composite, no strategy simulation, no architecture decision.

The exact hypothesis being examined (critic's precise wording, defined BEFORE
looking at the result, to avoid hindsight leakage): "The stock has undergone
unusually severe recent deterioration, but by T the deterioration has lost
momentum; the subsequent move begins from a state of stabilization rather
than continued acceleration downward" -- i.e. sharp deterioration ->
stabilization/pause -> upside expansion, NOT sharp deterioration -> immediate
reversal candle -> upside expansion (already rejected in 07A-6: close_loc_pct
and lower_wick_pct were both null).

GUARDRAIL (critic's explicit instruction, honored): "pause" is NOT defined
using the eventual D3 outcome -- no new threshold like "T->D1 downside < X."
The existing group definitions (Cohort A, D0, D2) were already fixed in prior
RQs; this script only shows the DESCRIPTIVE distributions of already-existing
path variables for those already-fixed groups. The evidence emerges from the
anatomy, not from a newly-invented "pause feature."

Groups (all frozen, none redefined, none further filtered):
  D0_A         = D0 Cohort A (166,831-row D0 population, decile==0, & cohort_a)
  D0_ordinary  = D0 & ~cohort_a -- critic's explicit instruction: do NOT filter
                 this further. It stays a heterogeneous mix (falls further,
                 stagnates, recovers modestly, or moves substantially without
                 crossing the P95 threshold) -- that heterogeneity is the
                 point of the comparison, not something to clean up.
  D2_A         = D2 Cohort A -- SECONDARY reference only (per critic: "don't
                 overinterpret... A difference would simply mean same
                 endpoint class, different post-entry anatomy").

PRIMARY comparison: D0_A vs D0_ordinary -- does the anatomy actually separate
the successful tail from the natural heterogeneous background?
SECONDARY comparison: D0_A vs D2_A -- is the weak-state pathway's post-T
trajectory similar to the already-established continuation pathway's, despite
arriving via a substantially different pre-T route?

No new computation needed -- every column reused directly from
10_trend_state_anatomy.py (max_return_d1/d2/d3, adverse_d1/d2/d3,
close_ret_d1/d2/d3, day_of_max, path_shape -- all production-verified
formulas from 01_event_matrix.py) and 12_weak_state_mechanism.py (ret_1d,
ret_3d, dist_low10d_pct, decline_from_high10d_pct, close_loc_pct,
lower_wick_pct -- already-tested candidates, shown here purely as
descriptive PATH context, not re-tested as new candidates).

Distinguishing critic's two competing readings, both pre-declared before
looking at the result:
  A. Deep drawdown + stabilization -- much deeper prior drawdown, relatively
     benign T/D1 downside, then rapid upside expansion.
  B. Accelerating short-term selloff -- continued extreme downside through
     T/D1, violent reversal only afterwards.
"""
import pandas as pd
import numpy as np

OUT_DIR = "."

print("Loading D0/D2 populations (state + trajectory columns from 10_, pre-T anatomy from 12_)...", flush=True)
state = pd.read_csv("trend_state_anatomy.csv", parse_dates=["date"])
mech = pd.read_csv("weak_state_mechanism_features.csv", parse_dates=["date"])[
    ["ticker", "date", "ret_1d", "ret_3d", "dist_low10d_pct", "decline_from_high10d_pct",
     "close_loc_pct", "lower_wick_pct"]]

d0 = state[state.decile == 0].merge(mech, on=["ticker", "date"], how="inner")
assert len(d0) == (state.decile == 0).sum(), "D0 merge changed row count -- investigate before trusting anything below"
d2 = state[state.decile == 2]

d0_a = d0[d0.cohort_a]
d0_ordinary = d0[~d0.cohort_a]
d2_a = d2[d2.cohort_a]
print(f"D0_A: {len(d0_a):,}  D0_ordinary: {len(d0_ordinary):,} (NOT further filtered)  D2_A: {len(d2_a):,}")


def pstack(s):
    s = s.dropna()
    if len(s) == 0:
        return "n=0"
    return f"P25={np.percentile(s,25):+.2f} P50={np.percentile(s,50):+.2f} P75={np.percentile(s,75):+.2f}"


PRE_T_VARS = [
    ("decline_from_high10d_pct", "depth of decline from 10D high (into T)"),
    ("ret_3d", "3-day return into T (recent velocity)"),
    ("ret_1d", "T's own close return"),
    ("dist_low10d_pct", "T close, distance above 10D low"),
    ("close_loc_pct", "T candle: close location in T's H-L range (descriptive, already tested+null in 07A-6)"),
    ("lower_wick_pct", "T candle: lower wick % of T's H-L range (descriptive, already tested+null in 07A-6)"),
]

print(f"\n{'='*115}\nPART 1 (PRIMARY) -- PRE-T ANATOMY: D0_A vs D0_ordinary (descriptive, not new candidates)\n{'='*115}")
for col, label in PRE_T_VARS:
    print(f"  {col:26s} ({label})")
    print(f"    D0_A:        {pstack(d0_a[col])}")
    print(f"    D0_ordinary: {pstack(d0_ordinary[col])}")

print(f"\n{'='*115}\nPART 2 (PRIMARY) -- T->D1->D2->D3 TRAJECTORY: D0_A vs D0_ordinary\n{'='*115}")


def trajectory_block(df, label):
    print(f"\n-- {label} (n={len(df):,}) --")
    print(f"  Cumulative MFE (max_return):    D1={df.max_return_d1.median():+.2f}  "
          f"D2={df.max_return_d2.median():+.2f}  D3={df.max_return_d3.median():+.2f}")
    print(f"  Incremental MFE:                D1={df.max_return_d1.median():+.2f}  "
          f"D1->D2={df.max_return_d2.median()-df.max_return_d1.median():+.2f}  "
          f"D2->D3={df.max_return_d3.median()-df.max_return_d2.median():+.2f}")
    print(f"  Cumulative MAE (adverse):       D1={df.adverse_d1.median():+.2f}  "
          f"D2={df.adverse_d2.median():+.2f}  D3={df.adverse_d3.median():+.2f}")
    print(f"  Cumulative close return:        D1={df.close_ret_d1.median():+.2f}  "
          f"D2={df.close_ret_d2.median():+.2f}  D3={df.close_ret_d3.median():+.2f}")
    print(f"  Fraction positive at close:     D1={(df.close_ret_d1>0).mean()*100:.1f}%  "
          f"D2={(df.close_ret_d2>0).mean()*100:.1f}%  D3={(df.close_ret_d3>0).mean()*100:.1f}%")
    print(f"  Fraction fresh high vs prior:   D1->D2={(df.max_return_d2>df.max_return_d1).mean()*100:.1f}%  "
          f"D2->D3={(df.max_return_d3>df.max_return_d2).mean()*100:.1f}%")
    print(f"  day_of_max distribution:        {(df.day_of_max.value_counts(normalize=True).sort_index()*100).round(1).to_dict()}")
    print(f"  path_shape distribution:        {(df.path_shape.value_counts(normalize=True)*100).round(1).to_dict()}")


trajectory_block(d0_a, "D0_A (fast movers)")
trajectory_block(d0_ordinary, "D0_ordinary (NOT filtered -- heterogeneous background)")

print(f"\n{'='*115}\nPART 3 (SECONDARY) -- D0_A vs D2_A: is the weak-state pathway's post-T trajectory similar to the\n"
      f"already-established continuation pathway's, despite a different pre-T route?\n{'='*115}")
trajectory_block(d0_a, "D0_A (weak-state pathway)")
trajectory_block(d2_a, "D2_A (continuation-pathway reference)")

summary = pd.DataFrame([
    dict(group="D0_A", n=len(d0_a), mfe_d1=d0_a.max_return_d1.median(), mfe_d2=d0_a.max_return_d2.median(),
          mfe_d3=d0_a.max_return_d3.median(), mae_d1=d0_a.adverse_d1.median(), mae_d3=d0_a.adverse_d3.median(),
          close_d1=d0_a.close_ret_d1.median(), close_d3=d0_a.close_ret_d3.median(),
          pct_positive_d1=(d0_a.close_ret_d1 > 0).mean() * 100),
    dict(group="D0_ordinary", n=len(d0_ordinary), mfe_d1=d0_ordinary.max_return_d1.median(),
          mfe_d2=d0_ordinary.max_return_d2.median(), mfe_d3=d0_ordinary.max_return_d3.median(),
          mae_d1=d0_ordinary.adverse_d1.median(), mae_d3=d0_ordinary.adverse_d3.median(),
          close_d1=d0_ordinary.close_ret_d1.median(), close_d3=d0_ordinary.close_ret_d3.median(),
          pct_positive_d1=(d0_ordinary.close_ret_d1 > 0).mean() * 100),
    dict(group="D2_A", n=len(d2_a), mfe_d1=d2_a.max_return_d1.median(), mfe_d2=d2_a.max_return_d2.median(),
          mfe_d3=d2_a.max_return_d3.median(), mae_d1=d2_a.adverse_d1.median(), mae_d3=d2_a.adverse_d3.median(),
          close_d1=d2_a.close_ret_d1.median(), close_d3=d2_a.close_ret_d3.median(),
          pct_positive_d1=(d2_a.close_ret_d1 > 0).mean() * 100),
]).round(3)
summary.to_csv(f"{OUT_DIR}/weak_state_transition_anatomy_summary.csv", index=False)
print(f"\nsaved weak_state_transition_anatomy_summary.csv\n{summary.to_string(index=False)}")

print("\nDONE")
