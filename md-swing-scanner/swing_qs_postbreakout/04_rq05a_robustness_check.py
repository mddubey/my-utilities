"""RQ-QS-05A, Robustness check on the Layer A0 triple-cut lead (2026-09-29).

The 90d-window triple-cut (novel_252d AND flattest tercile AND tightest range
tercile) showed a modest lift (38.2% vs 31.8% baseline hold-above-prebreakout_40d,
n=123) -- explicitly logged as a LEAD, not a finding, with two open concerns:
(1) an unchecked April-May 2022 regime concentration, (2) no check of whether the
result is specific to the exact tercile boundaries/90d window chosen.

Four variants, ALL PRE-DECLARED before running this script (not picked after seeing
which one looks best):
  A. Same cut, but using the ALREADY-COMPUTED 40d window's own measures instead of
     90d -- this was pre-declared as an alternate horizon back when Layer A0 was
     built (Rule #19's Parameterized Feature corollary), just not checked yet.
  B. Quartile split (bottom 25% by |slope| and by range/ATR) instead of terciles,
     on both windows -- tests whether the lift is an artifact of exactly where the
     tercile boundary happened to fall.
  C. Year-by-year breakdown of the ORIGINAL 90d triple-cut population (Rule #16:
     never pool years, show each one) -- n per year will be thin (single digits to
     teens), reported as such, not oversold.
  D. The original 90d triple-cut with April-May 2022 excluded entirely -- direct
     test of whether the lift survives outside that specific window.

No new thresholds are chosen based on what these variants show -- if the lift
reverses or vanishes in any of them, that's reported as-is, not explained away.
"""
import os
import pandas as pd

os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
OUT_DIR = "swing_qs_postbreakout"

out = pd.read_csv(f"{OUT_DIR}/rq05a_layer_a0_base_quality.csv", parse_dates=["episode_start_date"])
baseline_40d = (out.min_low_vs_prebreakout_pct_40d > 0).mean() * 100
print(f"Full population baseline (n={len(out)}): holds-above-prebreakout_40d = {baseline_40d:.1f}%\n")


def report(label, sub, baseline):
    if len(sub) == 0:
        print(f"  {label}: n=0")
        return
    rate = (sub.min_low_vs_prebreakout_pct_40d > 0).mean() * 100
    print(f"  {label}: n={len(sub):4d}  hold-rate_40d={rate:5.1f}%  (baseline {baseline:.1f}%, delta {rate-baseline:+.1f}pp)")


print("=== Variant A: same intersection, using the 40d window's own measures instead of 90d ===")
for W in [40, 90]:
    valid = out[out[f"prior_range_over_atr_{W}d"].notna() & out[f"sma_slope_pct_{W}d"].notna()].copy()
    valid["flat_tercile"] = pd.qcut(valid[f"sma_slope_pct_{W}d"].abs(), 3, labels=["flattest", "mid", "trendiest"])
    valid["tight_tercile"] = pd.qcut(valid[f"prior_range_over_atr_{W}d"], 3, labels=["tightest", "mid", "loosest"])
    triple = valid[(valid.novel_252d) & (valid.flat_tercile == "flattest") & (valid.tight_tercile == "tightest")]
    report(f"{W}d window, tercile intersection", triple, baseline_40d)

print("\n=== Variant B: quartile split (bottom 25% by |slope|, bottom 25% by range/ATR) instead of terciles ===")
for W in [40, 90]:
    valid = out[out[f"prior_range_over_atr_{W}d"].notna() & out[f"sma_slope_pct_{W}d"].notna()].copy()
    slope_q25 = valid[f"sma_slope_pct_{W}d"].abs().quantile(0.25)
    range_q25 = valid[f"prior_range_over_atr_{W}d"].quantile(0.25)
    quart = valid[(valid.novel_252d) & (valid[f"sma_slope_pct_{W}d"].abs() <= slope_q25)
                    & (valid[f"prior_range_over_atr_{W}d"] <= range_q25)]
    report(f"{W}d window, bottom-quartile intersection", quart, baseline_40d)

print("\n=== Variant C: year-by-year breakdown of the ORIGINAL 90d triple-cut (n=123), Rule #16 ===")
valid90 = out[out["prior_range_over_atr_90d"].notna() & out["sma_slope_pct_90d"].notna()].copy()
valid90["flat_tercile"] = pd.qcut(valid90["sma_slope_pct_90d"].abs(), 3, labels=["flattest", "mid", "trendiest"])
valid90["tight_tercile"] = pd.qcut(valid90["prior_range_over_atr_90d"], 3, labels=["tightest", "mid", "loosest"])
triple90 = valid90[(valid90.novel_252d) & (valid90.flat_tercile == "flattest") & (valid90.tight_tercile == "tightest")].copy()
triple90["year"] = triple90.episode_start_date.dt.year
for yr, grp in triple90.groupby("year"):
    rate = (grp.min_low_vs_prebreakout_pct_40d > 0).mean() * 100
    flag = "  <- n<10, too thin to trust on its own" if len(grp) < 10 else ""
    print(f"  {yr}: n={len(grp):3d}  hold-rate_40d={rate:5.1f}%{flag}")

print("\n=== Variant D: original 90d triple-cut with April-May 2022 excluded ===")
apr_may_2022 = (triple90.episode_start_date >= "2022-04-01") & (triple90.episode_start_date <= "2022-05-31")
print(f"  April-May 2022 rows in the triple-cut: {apr_may_2022.sum()} of {len(triple90)}")
ex_regime = triple90[~apr_may_2022]
report("ex-Apr/May-2022", ex_regime, baseline_40d)
report("Apr/May-2022 only (for contrast)", triple90[apr_may_2022], baseline_40d)

print("\n=== Summary ===")
print(f"Baseline: {baseline_40d:.1f}%. All variants above should be compared against this line, not against each other.")
