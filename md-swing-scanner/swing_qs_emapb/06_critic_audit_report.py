"""RQ-EMAPB-02 -- produce all critic-requested tracks from the audit panel.
Usage: python3 swing_qs_emapb/06_critic_audit_report.py
"""
import pandas as pd
import numpy as np

HERE = "swing_qs_emapb"
pd.set_option("display.width", 180)


def pct_table(df, col_ret, label):
    s = df[col_ret].dropna()
    return dict(n=len(s), median=s.median(), p25=s.quantile(.25), p75=s.quantile(.75),
                pct_pos=(s > 0).mean() * 100)


def main():
    lines = []
    def p(s=""):
        print(s); lines.append(str(s))

    df = pd.read_csv(f"{HERE}/rq_emapb02_audit_panel.csv")
    p(f"=== RQ-EMAPB-02 critic audit -- {pd.Timestamp.now():%Y-%m-%d %H:%M} ===")
    p(f"Total A's: {len(df):,}")

    # ============ TRACK 1: retracement-depth diagnostic, D1 metrics ============
    p("\n--- TRACK 1: retracement-depth diagnostic (D1, not D3) ---")
    for name in ["retest", "fib382", "fib50", "fib618"]:
        touched = df[df[f"{name}_touched"] == True]
        n = len(touched)
        d1o = touched[f"{name}_d1_open_pct"].dropna()
        d1p = touched[f"{name}_d1_peak_pct"].dropna()
        d1c = touched[f"{name}_d1_close_pct"].dropna()
        d1m = touched[f"{name}_d1_mae_pct"].dropna()
        p(f"{name:8} touch_rate={n/len(df)*100:5.1f}%  med_offset={touched[f'{name}_offset'].median():.0f}  "
          f"D1open={d1o.median():+.3f}%(pos{(d1o>0).mean()*100:.0f}%) "
          f"D1peak={d1p.median():+.3f}%(pos{(d1p>0).mean()*100:.0f}%,P75={d1p.quantile(.75):+.2f}%,P90={d1p.quantile(.9):+.2f}%) "
          f"D1close={d1c.median():+.3f}%(pos{(d1c>0).mean()*100:.0f}%) D1MAE={d1m.median():+.3f}%")

    # ============ TRACK 3: component diagnostics ============
    p("\n--- TRACK 3: structural components (Fib50 population only, n with span data) ---")
    span_pop = df[df.range_compression.notna()]
    n_span = len(span_pop)
    p(f"n={n_span:,}")
    for comp in ["range_compression", "atr_contraction", "vol_contraction", "combined_base", "contained"]:
        p(f"  {comp:20}: {span_pop[comp].mean()*100:5.1f}%")

    # ============ TRACK 2 & 4: A (touch) vs B (stabilized) vs C (stabilized+resumed) ============
    p("\n--- TRACK 2 & 4: Population comparison, D1 metrics ---")
    pops = {
        "A: touch only (C0)": span_pop,
        "B: stabilized pullback": span_pop[span_pop.is_B_stabilized == True],
        "C: stabilized + resumed (C2)": span_pop[span_pop.is_C_resumed == True],
    }
    anchor_map = {"A: touch only (C0)": "c0", "B: stabilized pullback": "spanend", "C: stabilized + resumed (C2)": "c2"}
    for label, sub in pops.items():
        anchor = anchor_map[label]
        d1o = sub[f"{anchor}_d1_open_pct"].dropna()
        d1p = sub[f"{anchor}_d1_peak_pct"].dropna()
        d1c = sub[f"{anchor}_d1_close_pct"].dropna()
        d1m = sub[f"{anchor}_d1_mae_pct"].dropna()
        p(f"{label:30} n={len(sub):5,}  D1open={d1o.median():+.3f}%  "
          f"D1peak={d1p.median():+.3f}%(P75={d1p.quantile(.75):+.2f}%) "
          f"D1close={d1c.median():+.3f}%(pos{(d1c>0).mean()*100:.0f}%) D1MAE={d1m.median():+.3f}%")

    # ============ TRACK 5: confirmation quality C0/C1/C2 ============
    p("\n--- TRACK 5: confirmation quality (C0 vs C1 early-resumption vs C2 structural) ---")
    for label, anchor, mask in [
        ("C0 (touch, no confirm)", "c0", span_pop.index),
        ("C1 (early resumption)", "c1", span_pop[span_pop.c1_offset.notna()].index),
        ("C2 (structural confirm)", "c2", span_pop[span_pop.c2_offset.notna()].index),
    ]:
        sub = span_pop.loc[mask]
        trigger_rate = len(sub) / n_span * 100
        d1c = sub[f"{anchor}_d1_close_pct"].dropna()
        d1p = sub[f"{anchor}_d1_peak_pct"].dropna()
        d1m = sub[f"{anchor}_d1_mae_pct"].dropna()
        delay = (sub[f"{anchor.replace('c0','touch_offset_f50') if anchor=='c0' else anchor+'_offset'}"]
                 - sub.touch_offset_f50) if anchor != "c0" else pd.Series([0]*len(sub))
        p(f"{label:26} trigger={trigger_rate:5.1f}%  med_delay_vs_touch={delay.median():.1f}bars  "
          f"D1close={d1c.median():+.3f}%(pos{(d1c>0).mean()*100:.0f}%)  D1peak={d1p.median():+.3f}%  D1MAE={d1m.median():+.3f}%")

    # ============ TRACK 6: genuine digestion (range_compression) vs random oscillation ============
    p("\n--- TRACK 6: genuine digestion (range_compression=True) vs random oscillation (False) ---")
    for label, sub in [("genuine digestion", span_pop[span_pop.range_compression == True]),
                       ("random oscillation", span_pop[span_pop.range_compression == False])]:
        d1p = sub["c0_d1_peak_pct"].dropna()
        d1c = sub["c0_d1_close_pct"].dropna()
        d1m = sub["c0_d1_mae_pct"].dropna()
        p(f"{label:20} n={len(sub):5,}  D1peak={d1p.median():+.3f}%  D1close={d1c.median():+.3f}%(pos{(d1c>0).mean()*100:.0f}%)  D1MAE={d1m.median():+.3f}%")

    # ============ TRACK 7: peak vs close explicit, by population ============
    p("\n--- TRACK 7: peak vs close gap, by population ---")
    for label, sub in pops.items():
        anchor = anchor_map[label]
        d1p = sub[f"{anchor}_d1_peak_pct"].dropna()
        d1c = sub[f"{anchor}_d1_close_pct"].dropna()
        gap = d1p.median() - d1c.median()
        p(f"{label:30} D1peak={d1p.median():+.3f}%  D1close={d1c.median():+.3f}%  gap(give-back)={gap:.3f}pp")

    # ============ TRACK 8: timing cost ============
    p("\n--- TRACK 8: timing cost of confirmation ---")
    c1_pop = span_pop[span_pop.c1_offset.notna()]
    c2_pop = span_pop[span_pop.c2_offset.notna()]
    p(f"A -> touch, median offset from A: {span_pop.touch_offset_f50.median():.1f} bars")
    p(f"touch -> span end (fixed): {3-1} bars")
    p(f"span end -> C1, median: {(c1_pop.c1_offset - c1_pop.span_end_offset).median():.1f} bars  "
      f"(total A->C1: {c1_pop.c1_offset.median():.1f})")
    p(f"span end -> C2, median: {(c2_pop.c2_offset - c2_pop.span_end_offset).median():.1f} bars  "
      f"(total A->C2: {c2_pop.c2_offset.median():.1f})")

    # ============ BIAS / OVERFIT CHECKS ============
    p("\n--- BIAS/OVERFIT CHECKS ---")
    p(f"N at each stage: all A's={len(df):,}, fib50 touched={df.fib50_touched.sum():,}, "
      f"span fits={n_span:,}, B={len(pops['B: stabilized pullback']):,}, C={len(pops['C: stabilized + resumed (C2)']):,}")
    p(f"\nYear-by-year, C population D1close median:")
    cpop = pops["C: stabilized + resumed (C2)"]
    for yr, g in cpop.groupby("year"):
        d1c = g["c2_d1_close_pct"].dropna()
        if len(d1c) >= 10:
            p(f"  {yr}: n={len(d1c):,}  median D1close={d1c.median():+.3f}%  pos={(d1c>0).mean()*100:.0f}%")
    p(f"\nTicker concentration, C population: top 5 tickers' share of n = "
      f"{cpop.ticker.value_counts().head(5).sum()/len(cpop)*100:.1f}%  (n_unique_tickers={cpop.ticker.nunique()})")
    d1c_full = cpop["c2_d1_close_pct"].dropna()
    trimmed = d1c_full[(d1c_full > d1c_full.quantile(.01)) & (d1c_full < d1c_full.quantile(.99))]
    p(f"\nTop/bottom 1% removed: median D1close {d1c_full.median():+.3f}% -> {trimmed.median():+.3f}%  "
      f"(n {len(d1c_full)}->{len(trimmed)})")
    trimmed5 = d1c_full[(d1c_full > d1c_full.quantile(.05)) & (d1c_full < d1c_full.quantile(.95))]
    p(f"Top/bottom 5% removed: median D1close {d1c_full.median():+.3f}% -> {trimmed5.median():+.3f}%")

    (open(f"{HERE}/rq_emapb02_audit_output.txt", "w")).write("\n".join(lines) + "\n")
    p(f"\n[written to {HERE}/rq_emapb02_audit_output.txt]")


if __name__ == "__main__":
    main()
