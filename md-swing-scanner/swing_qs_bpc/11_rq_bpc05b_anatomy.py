"""RQ-BPC-05 step 2 -- apply the EXACT 04B enrichment (08_rq04b_anatomy.py's `enrich()`,
reused unchanged) to the corrected (volume-confirmed) holds-above-A population, to get the
decisive comparison metric: does B's Close actually finish above the consolidation high,
and the full duration x width matrix. Same method as the original 04B, different input
population.

Usage: python3 swing_qs_bpc/11_rq_bpc05b_anatomy.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from importlib.util import spec_from_file_location, module_from_spec


def _load_module(name, path):
    spec = spec_from_file_location(name, path)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rq04b = _load_module("rq04b", os.path.join(HERE, "08_rq04b_anatomy.py"))
enrich = rq04b.enrich


def main():
    anat = pd.read_csv(f"{HERE}/rq_bpc05_corrected_a_anatomy.csv")
    holds = anat[anat.consolidation_detected & anat.consolidation_low_above_a.fillna(False)].copy()
    print(f"corrected holds-above-A population going into enrich(): {len(holds):,}")

    enriched = enrich(holds)
    enriched.to_csv(f"{HERE}/rq_bpc05_holds_above_a_enriched.csv", index=False)
    print(f"enriched: {len(enriched):,} rows (after date-mismatch skips)")

    print(f"\n=== RQ-BPC-05 vs original RQ-QS-04B, side by side ===")
    print(f"{'metric':45} {'original (n=8,391)':22} {'corrected (n=' + str(len(enriched)) + ')':22}")
    dur = enriched.duration
    print(f"{'duration P25/50/75/90':45} {'1 / 2 / 4 / 9':22} "
          f"{dur.quantile(.25):.0f} / {dur.quantile(.5):.0f} / {dur.quantile(.75):.0f} / {dur.quantile(.9):.0f}")
    rw = enriched.range_width_pct
    print(f"{'range width % P25/50/75/90':45} {'2.91 / 4.33 / 6.68 / 10.17':22} "
          f"{rw.quantile(.25):.2f} / {rw.quantile(.5):.2f} / {rw.quantile(.75):.2f} / {rw.quantile(.9):.2f}")
    print(f"{'range width / ATR, median':45} {'1.36x':22} {enriched.range_width_over_atr.median():.2f}x")
    ccr = enriched.pause_close_range_pct
    print(f"{'close-to-close range % P50':45} {'0.48%':22} {ccr.median():.2f}%")
    print(f"{'pause vol / 10d avg, median':45} {'1.29x':22} {enriched.vol_ratio_vs_10d_avg.median():.2f}x")
    resolved = enriched[enriched.resolved]
    print(f"{'resolved %':45} {'90.7%':22} {len(resolved)/len(enriched)*100:.1f}%")
    if len(resolved):
        bch = resolved.b_close_above_high.mean() * 100
        print(f"{'B close above consolidation high':45} {'45.6%':22} {bch:.1f}%  <-- THE decisive metric")
        print(f"{'B close vs high, median %':45} {'-0.13%':22} {resolved.b_close_vs_high_pct.median():.2f}%")
        print(f"{'B gap-open above high':45} {'9.0%':22} {resolved.b_open_gap_above_high.mean()*100:.1f}%")

    print(f"\n=== Duration x width matrix (% of corrected population) ===")
    enriched["dur_bucket"] = pd.cut(enriched.duration, [0, 1, 2, 4, 7, 999], labels=["1d", "2d", "3-4d", "5-7d", "8+d"])
    enriched["width_bucket"] = pd.cut(enriched.range_width_pct, [0, 2, 4, 6, 10, 999], labels=["<2%", "2-4%", "4-6%", "6-10%", "10%+"])
    mat = pd.crosstab(enriched.dur_bucket, enriched.width_bucket, normalize=True) * 100
    print(mat.round(1).to_string())

    print(f"\n=== B-close-above-high rate by duration bucket (does it improve with longer pauses?) ===")
    g = enriched[enriched.resolved].groupby("dur_bucket", observed=True).b_close_above_high.mean().astype(float) * 100
    print(g.round(1).to_string())

    print(f"\n=== Split: high-volume subgroup (>=3x) vs 1.5-3x ===")
    for label, sub in [(">=3x", enriched[enriched.high_vol_subgroup]), ("1.5-3x", enriched[~enriched.high_vol_subgroup])]:
        r = sub[sub.resolved]
        print(f"{label}: n={len(sub):,}  resolved={len(r)/len(sub)*100:.1f}%  "
              f"B-close-above-high={r.b_close_above_high.mean()*100:.1f}%  "
              f"pause-vol/10d={sub.vol_ratio_vs_10d_avg.median():.2f}x  "
              f"close-to-close-range%={sub.pause_close_range_pct.median():.2f}%")

    print(f"\n=== Split: has_bigger_preceding_thrust (A may be a late echo) vs not ===")
    for label, sub in [("has bigger preceding thrust", enriched[enriched.has_bigger_preceding_thrust]),
                        ("A is the standout day", enriched[~enriched.has_bigger_preceding_thrust])]:
        r = sub[sub.resolved]
        print(f"{label}: n={len(sub):,}  B-close-above-high={r.b_close_above_high.mean()*100:.1f}%  "
              f"close-to-close-range%={sub.pause_close_range_pct.median():.2f}%")


if __name__ == "__main__":
    main()
