"""RQ-BPC-05 -- Volume-Confirmed A Population Audit (critic pre-registered, 2026-10-04).
See RQ-BPC-05_SPEC.md for the full design. Reuses find_a_positions (04_rq03c_define_b.py)
and analyze_one (07_rq04a_consolidation_anatomy.py) UNCHANGED -- only the A qualification
(a volume filter) is new; everything downstream is identical to the original 04A method.

Usage: python3 swing_qs_bpc/10_rq_bpc05_volume_confirmed_a.py
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


rq03c = _load_module("rq03c", os.path.join(HERE, "04_rq03c_define_b.py"))
rq04a = _load_module("rq04a", os.path.join(HERE, "07_rq04a_consolidation_anatomy.py"))
find_a_positions = rq03c.find_a_positions
analyze_one = rq04a.analyze_one

LOOKBACKS = (10, 20, 40)
PRIMARY_VOL_THRESH = 1.5     # pre-registered gate, literature-informed (not the 3x examples)
HIGH_VOL_THRESH = 3.0        # diagnostic subgroup only
PRECEDING_LOOKBACK = 10      # trading days, for "bigger thrust nearby" check
PRIOR_HIGH_LOOKBACK = 60     # trading days, for "meaningful prior high" distance


def vol_ratio_at(rows, i):
    if i < 0 or i >= len(rows):
        return None
    row = rows.iloc[i]
    v10 = row.vol_avg10_prior
    if pd.isna(v10) or not v10:
        return None
    return row.Volume / v10


def diagnose_a(rows, a):
    """New fields per RQ-BPC-05_SPEC.md: confirm A's volume spike and price breakout are
    the same event, not just 'some volume nearby'."""
    ia = a["entry_i"]
    a_row = rows.iloc[ia]
    vol_ratio = vol_ratio_at(rows, ia)
    prev_ratio = vol_ratio_at(rows, ia - 1)
    next_ratio = vol_ratio_at(rows, ia + 1)
    price_disp_pct = ((a_row.Close / rows.iloc[ia - 1].Close - 1) * 100
                       if ia >= 1 and rows.iloc[ia - 1].Close else None)
    lb0 = max(0, ia - PRIOR_HIGH_LOOKBACK)
    prior_high_60 = rows.High.iloc[lb0:ia].max() if ia > lb0 else None
    dist_from_60d_high_pct = ((a["entry_price"] / prior_high_60 - 1) * 100
                               if prior_high_60 else None)
    pre0 = max(0, ia - PRECEDING_LOOKBACK)
    preceding_ratios = [vol_ratio_at(rows, k) for k in range(pre0, ia)]
    preceding_ratios = [r for r in preceding_ratios if r is not None]
    preceding_max_ratio = max(preceding_ratios) if preceding_ratios else None
    has_bigger_preceding_thrust = bool(
        preceding_max_ratio is not None and vol_ratio is not None
        and preceding_max_ratio > vol_ratio and preceding_max_ratio >= PRIMARY_VOL_THRESH)
    return dict(
        vol_ratio=vol_ratio, prev_day_vol_ratio=prev_ratio, next_day_vol_ratio=next_ratio,
        price_displacement_pct=price_disp_pct, dist_from_60d_high_pct=dist_from_60d_high_pct,
        preceding_max_vol_ratio=preceding_max_ratio,
        has_bigger_preceding_thrust=has_bigger_preceding_thrust,
    )


def bucket(vr):
    if vr is None or pd.isna(vr):
        return None
    if vr < 1.0:
        return "<1x"
    if vr < 1.5:
        return "1-1.5x"
    if vr < 2.0:
        return "1.5-2x"
    if vr < 3.0:
        return "2-3x"
    return ">=3x"


def main():
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    diag_rows, anat_rows = [], []
    t0 = __import__("time").time()
    for n, t in enumerate(tickers):
        if n % 100 == 0:
            print(f"{n}/{len(tickers)}  {__import__('time').time()-t0:.0f}s", flush=True)
        for lb in LOOKBACKS:
            a_list, rows = find_a_positions(t, lb)
            if rows is None:
                continue
            for a in a_list:
                a["ticker"] = t
                d = diagnose_a(rows, a)
                diag_rows.append(dict(ticker=t, entry_definition=lb, a_entry_i=a["entry_i"],
                                       a_entry_date=str(rows.iloc[a["entry_i"]].Date.date()),
                                       a_entry_price=a["entry_price"], **d))
                if d["vol_ratio"] is not None and d["vol_ratio"] >= PRIMARY_VOL_THRESH:
                    anat = analyze_one(rows, a)
                    anat["vol_ratio"] = d["vol_ratio"]
                    anat["high_vol_subgroup"] = d["vol_ratio"] >= HIGH_VOL_THRESH
                    anat["has_bigger_preceding_thrust"] = d["has_bigger_preceding_thrust"]
                    anat_rows.append(anat)

    diag = pd.DataFrame(diag_rows)
    anat = pd.DataFrame(anat_rows)
    diag.to_csv(f"{HERE}/rq_bpc05_a_volume_diagnostics.csv", index=False)
    anat.to_csv(f"{HERE}/rq_bpc05_corrected_a_anatomy.csv", index=False)

    print(f"\n=== Full A population: {len(diag):,} events ===")
    diag["bucket"] = diag.vol_ratio.apply(bucket)
    print(diag.bucket.value_counts(dropna=False).reindex(["<1x", "1-1.5x", "1.5-2x", "2-3x", ">=3x", None]))

    print(f"\n=== has_bigger_preceding_thrust (A fired on a late/secondary pop): "
          f"{diag.has_bigger_preceding_thrust.sum():,} ({diag.has_bigger_preceding_thrust.mean()*100:.1f}% of all A's) ===")
    print(f"Within the corrected (>=1.5x) population specifically: "
          f"{diag[diag.vol_ratio >= PRIMARY_VOL_THRESH].has_bigger_preceding_thrust.mean()*100:.1f}%")

    n_corrected = (diag.vol_ratio >= PRIMARY_VOL_THRESH).sum()
    print(f"\n=== Corrected population (vol_ratio >= {PRIMARY_VOL_THRESH}x): {n_corrected:,} / {len(diag):,} "
          f"({n_corrected/len(diag)*100:.1f}%) ===")
    print(f"High-volume subgroup (>= {HIGH_VOL_THRESH}x) within corrected: "
          f"{(anat.high_vol_subgroup.sum() if len(anat) else 0):,}")

    print(f"\n=== Anatomy re-run on corrected population: {len(anat):,} rows ===")
    print(f"consolidation_detected: {anat.consolidation_detected.mean()*100:.1f}%")
    holds = anat[anat.consolidation_detected & anat.consolidation_low_above_a.fillna(False)]
    print(f"holds-above-A subset: {len(holds):,} ({len(holds)/len(anat)*100:.1f}% of corrected A's with a pause)")
    if len(holds):
        print(f"duration P25/50/75/90: {holds.duration.quantile([.25,.5,.75,.9]).round(1).to_dict()}")
        print(f"range_width_pct P25/50/75/90: {holds.range_width_pct.quantile([.25,.5,.75,.9]).round(2).to_dict()}")
        print(f"range_width_over_atr P50: {holds.range_width_over_atr.median():.2f}x")
        print(f"vol_ratio_vs_10d_avg (pause volume) P50: {holds.vol_ratio_vs_10d_avg.median():.2f}x")
        resolved = holds[holds.resolved]
        print(f"resolved: {len(resolved):,} ({len(resolved)/len(holds)*100:.1f}%)")
        if len(resolved):
            close_above = (resolved.b_price > resolved.consolidation_high)  # b_price is the High that triggered B; need close separately -- flagged below
            print("NOTE: b_price in analyze_one's output is the triggering High, not B's Close -- "
                  "B-close-above-consolidation-high rate needs the 04B-style enrichment pass (next script), "
                  "not computed here.")


if __name__ == "__main__":
    main()
