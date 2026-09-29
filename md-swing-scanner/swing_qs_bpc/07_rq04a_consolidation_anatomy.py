"""RQ-QS-04A -- Post-Breakout Consolidation Anatomy (2026-09-29, critic-approved,
strictly bounded, observational only -- NO returns, NO expectancy, NO gate).

Separate hypothesis from BPC/D3. D3 asked "does price dip back below A's original
level and reclaim it." This asks a different question: after A, does price hold its
ground, pause in a NEW bounded range above/around A, then break a NEW pivot -- with
a candidate structural stop under THAT new range's own low, not S1b. Verified against
literature (Minervini VCP, O'Neil cup-and-handle, Strike Money's own VCP + ascending-
triangle pages) before building -- see FINDINGS.md.

Per critic: do not pre-define "consolidation" with a fixed N-day minimum or by
scanning the full forward window for the best-looking range (that manufactures a
pattern retrospectively). Instead, use a decision-time-safe definition and report
the NATURAL distribution of what falls out, unfiltered:

  running_high(d)   = max(High) from A's entry day through day d-1 (decision-time
                       safe -- known before day d's own bar prints).
  consolidation starts at the first day offset k>=1 where High_k does NOT exceed
                       running_high(k) -- i.e. the day the initial impulse first
                       fails to make a fresh high. If every day in the window keeps
                       making new highs, no consolidation is detected at all.
  consolidation_high = running_high as of the day the pause begins (the level a
                       later breakout must clear -- this IS the candidate new pivot,
                       fixed once the pause starts, never redefined by hindsight).
  B (candidate)      = the first subsequent day whose High > consolidation_high
                       (IOC/intraday touch, matching this project's raw-trigger
                       convention throughout).
  consolidation_low  = min(Low) over the actual observed span, from the pause's
                       start through B (or through the window edge if B never
                       fires within D15) -- this one field IS necessarily hindsight
                       (you only know how low a pause went once it's over), which is
                       fine for an anatomy AUDIT, not a live rule; flagged explicitly
                       below and in FINDINGS.md.

Structural risk is reported in plain % distance only -- explicitly NO R-multiple
(Rule #20: the stop convention here is a genuinely different candidate than S1b,
so R computed against it would not be comparable to any existing QS-A/QS-B R
number without saying so first).
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib.util import spec_from_file_location, module_from_spec
_spec = spec_from_file_location("rq03c", os.path.join(os.path.dirname(os.path.abspath(__file__)), "04_rq03c_define_b.py"))
rq03c = module_from_spec(_spec)
_spec.loader.exec_module(rq03c)
find_a_positions = rq03c.find_a_positions

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
WINDOW_DAYS = 15  # D0-D15, per critic's spec


def analyze_one(rows, a):
    ia = a["entry_i"]
    a_entry_price = a["entry_price"]
    a_row = rows.iloc[ia]
    n_rows = len(rows)
    end = min(ia + 1 + WINDOW_DAYS, n_rows)

    running_high = a_row.High
    consolidation_start_day = None
    consolidation_high = None

    # --- find where the initial impulse first fails to make a new high ---
    for k in range(ia + 1, end):
        if rows.iloc[k].corp_action_day:
            end = k  # truncate window at the corp action day
            break
        row = rows.iloc[k]
        if row.High > running_high:
            running_high = row.High
            continue
        consolidation_start_day = k - ia
        consolidation_high = running_high
        break

    base = dict(
        ticker=a["ticker"], entry_definition=a["entry_definition"],
        a_entry_i=ia, a_entry_date=str(a_row.Date.date()), a_entry_price=a_entry_price,
        consolidation_detected=consolidation_start_day is not None,
    )
    if consolidation_start_day is None:
        return base  # every day in the window kept making new highs -- no pause at all

    # --- walk forward from the pause, looking for the first break of consolidation_high ---
    lows_in_span = [rows.iloc[ia + consolidation_start_day].Low]
    b_day, b_price, resolved = None, None, False
    for k in range(ia + consolidation_start_day, end):
        row = rows.iloc[k]
        if k > ia + consolidation_start_day:
            lows_in_span.append(row.Low)
        if k > ia + consolidation_start_day and row.High > consolidation_high:
            b_day, b_price, resolved = k - ia, row.High, True
            break
    consolidation_low = min(lows_in_span)
    last_day_in_span = (b_day if resolved else (end - 1 - ia))
    duration = last_day_in_span - consolidation_start_day

    atr_entry = a_row.atr14
    range_width_pct = (consolidation_high - consolidation_low) / a_entry_price * 100
    range_width_over_atr = (consolidation_high - consolidation_low) / atr_entry if pd.notna(atr_entry) and atr_entry else None

    span_rows = rows.iloc[ia + consolidation_start_day: last_day_in_span + ia + 1]
    daily_range = (span_rows.High - span_rows.Low)
    range_contracting_corr = None
    if len(span_rows) >= 3:
        range_contracting_corr = float(np.corrcoef(np.arange(len(span_rows)), daily_range)[0, 1])
    vol_ratio_vs_a_breach = span_rows.Volume.mean() / a_row.Volume if a_row.Volume else None
    vol_ratio_vs_10d_avg = span_rows.Volume.mean() / a_row.vol_avg10_prior if pd.notna(a_row.vol_avg10_prior) and a_row.vol_avg10_prior else None

    base.update(
        consolidation_start_day=consolidation_start_day,
        consolidation_high=consolidation_high,
        consolidation_low=consolidation_low,
        consolidation_low_above_a=bool(consolidation_low > a_entry_price),
        duration=duration,
        resolved=resolved,
        b_day=b_day, b_price=b_price,
        b_structural_risk_pct=((b_price - consolidation_low) / b_price * 100) if resolved else None,
        range_width_pct=range_width_pct,
        range_width_over_atr=range_width_over_atr,
        range_contracting_corr=range_contracting_corr,
        vol_ratio_vs_a_breach=vol_ratio_vs_a_breach,
        vol_ratio_vs_10d_avg=vol_ratio_vs_10d_avg,
    )
    return base


def run(tickers, lookbacks=(10, 20, 40)):
    rows_out = []
    for n, t in enumerate(tickers):
        if n % 100 == 0:
            print(f"{n}/{len(tickers)}", flush=True)
        for lb in lookbacks:
            a_list, rows = find_a_positions(t, lb)
            if rows is None:
                continue
            for a in a_list:
                a["ticker"] = t
                rows_out.append(analyze_one(rows, a))
    return pd.DataFrame(rows_out)


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    df = run(tickers)
    df.to_csv(f"{OUT_DIR}/rq04a_consolidation_anatomy.csv", index=False)

    n_a = len(df)
    n_detected = df.consolidation_detected.sum()
    print(f"\n=== RQ-QS-04A: Post-Breakout Consolidation Anatomy (n A's = {n_a}) ===\n")
    print(f"Consolidation detected (any pause at all within D1-D15): {n_detected} ({n_detected/n_a*100:.1f}%)")
    print(f"No pause at all (continuous new highs through D15):       {n_a - n_detected} ({(n_a-n_detected)/n_a*100:.1f}%)")

    d = df[df.consolidation_detected]
    resolved = d[d.resolved]
    print(f"\nOf detected consolidations: {len(resolved)} ({len(resolved)/len(d)*100:.1f}%) resolved with a B breakout within the window; "
          f"{len(d)-len(resolved)} ({(len(d)-len(resolved))/len(d)*100:.1f}%) still unresolved at D15 cutoff.")

    print(f"\nconsolidation_start_day    median={d.consolidation_start_day.median():.1f}  mean={d.consolidation_start_day.mean():.1f}")
    print(f"duration (obs. or resolved) median={d.duration.median():.1f}  mean={d.duration.mean():.1f}")
    print(f"range_width_pct            median={d.range_width_pct.median():.2f}%  mean={d.range_width_pct.mean():.2f}%")
    print(f"range_width_over_atr       median={d.range_width_over_atr.median():.2f}x  mean={d.range_width_over_atr.mean():.2f}x")
    pct_low_above_a = d.consolidation_low_above_a.mean() * 100
    print(f"\nconsolidation_low stays ABOVE A's entry price: {pct_low_above_a:.1f}% "
          f"(the key diagnostic -- if this were low, we'd just be re-finding the already-closed D3/pullback-below-A pattern)")

    contract = d.range_contracting_corr.dropna()
    print(f"\nrange_contracting_corr (negative = shrinking): median={contract.median():.3f}  "
          f"% negative={len(contract[contract<0])/len(contract)*100:.1f}%  n={len(contract)}")

    vol_a = d.vol_ratio_vs_a_breach.dropna()
    vol_10d = d.vol_ratio_vs_10d_avg.dropna()
    print(f"vol_ratio_vs_a_breach      median={vol_a.median():.2f}x  n={len(vol_a)}")
    print(f"vol_ratio_vs_10d_avg       median={vol_10d.median():.2f}x  n={len(vol_10d)}")

    print(f"\nresolved b_structural_risk_pct (distance from B's entry to consolidation_low, %): "
          f"median={resolved.b_structural_risk_pct.median():.2f}%  mean={resolved.b_structural_risk_pct.mean():.2f}%")
