"""RQ-QS-05A, Layer A0 -- Established Base/Range precondition (2026-09-29).

Caught by direct user pushback: Layer A ("novelty") only checks whether there was a
comparably large volume spike recently -- it never checks whether the stock was
actually sitting in a genuine sideways range beforehand. That's a different question,
and it's the FIRST box in the critic's own diagram ("ESTABLISHED BASE/RANGE"), which
this line skipped straight past into novelty + decay. Wyckoff's Trading Range and
Weinstein's Stage 1 both require a real prior base, not just "no recent big-volume
day" -- a stock can be "novel" while grinding in a slow trend with no real structure
at all. This script builds that missing precondition and crosses it against the
ALREADY-COMPUTED novelty (Layer A) and decay (Layer B) results for the SAME 14,032
episodes, rather than re-deriving a new population.

Two measures, both trailing-only (decision-time-safe) and both literature-anchored,
computed over the window ENDING THE DAY BEFORE the episode starts:
  prior_range_over_atr = (max(High) - min(Low)) over the window / atr14 as of that
                         day -- reuses RQ-QS-04A's own ATR-normalized base-width
                         convention (already validated in this project), applied to
                         the PRE-breakout period instead of a post-breakout pause.
                         Tight base = few ATRs wide; a trending/loose stock racks up
                         many ATRs of total range even day-to-day moves look similar.
  sma_slope_pct        = % change in sma50 across the window -- Weinstein's own
                         framing of Stage 1 as a FLATTENING moving average, not
                         "no volume spike." A stock can be novel-by-volume while its
                         sma50 is still marching up or down hard.

Two pre-declared windows (40/90 trading days, ~2/4.5 months -- Rule #19's
Parameterized Feature corollary), NOT tuned after seeing results. No thresholds
chosen here either -- report the full distribution, then cross-cut Layer B's own
decay/give-back stats by TERCILE of base tightness (not a single invented cutoff).
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_WINDOWS = [40, 90]


def base_quality(rows, episode_start_i, window):
    lo = episode_start_i - window
    if lo < 50:  # needs its own sma50 lookback too
        return None, None
    span = rows.iloc[lo:episode_start_i]
    ref_row = rows.iloc[episode_start_i - 1]
    atr = ref_row.atr14
    if not (pd.notna(atr) and atr > 0):
        return None, None
    range_over_atr = (span.High.max() - span.Low.min()) / atr
    sma_then = rows.iloc[lo].sma50
    sma_now = ref_row.sma50
    slope_pct = ((sma_now - sma_then) / sma_then * 100) if pd.notna(sma_then) and pd.notna(sma_now) and sma_then else None
    return range_over_atr, slope_pct


def pstack(s, fmt="{:.2f}", suffix=""):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        return "n=0"
    return "  ".join(f"P{p}={fmt.format(np.percentile(s, p))}{suffix}" for p in [10, 25, 50, 75, 90]) + f"  (n={len(s)})"


if __name__ == "__main__":
    ep = pd.read_csv("swing_qs_postbreakout/rq05a_layer_b_decay.csv")  # already has ticker + episode_start_i

    cache = {}
    recs = []
    for n, r in enumerate(ep.itertuples()):
        if n % 2000 == 0:
            print(f"{n}/{len(ep)}", flush=True)
        rows = cache.setdefault(r.ticker, load(r.ticker, daily_pivots).reset_index())
        rec = dict(ticker=r.ticker, episode_start_i=r.episode_start_i)
        for W in BASE_WINDOWS:
            rng, slope = base_quality(rows, int(r.episode_start_i), W)
            rec[f"prior_range_over_atr_{W}d"] = rng
            rec[f"sma_slope_pct_{W}d"] = slope
        recs.append(rec)
    base_df = pd.DataFrame(recs)
    out = ep.merge(base_df, on=["ticker", "episode_start_i"], how="left")
    out.to_csv(f"{OUT_DIR}/rq05a_layer_a0_base_quality.csv", index=False)

    for W in BASE_WINDOWS:
        print(f"\n=== Layer A0, base window = {W} trading days (n={len(out)} episodes) ===")
        print(f"prior_range_over_atr: {pstack(out[f'prior_range_over_atr_{W}d'], '{:.1f}', 'x')}")
        print(f"sma_slope_pct:        {pstack(out[f'sma_slope_pct_{W}d'], '{:.1f}', '%')}  "
              f"(% with |slope|<=5%, i.e. genuinely flat: "
              f"{(out[f'sma_slope_pct_{W}d'].abs() <= 5).mean()*100:.1f}%)")

    print("\n--- Rule #22 anchors ---")
    for tk in ["JUSTDIAL", "GOCLCORP"]:
        rows_tk = out[out.ticker == tk].sort_values("episode_start_i")
        # find the specific anchor episode by matching Layer B's own episode_start_date
        target_date = "2026-07-13" if tk == "JUSTDIAL" else "2026-09-03"
        r = rows_tk[rows_tk.episode_start_date == target_date]
        if r.empty:
            print(f"{tk}: anchor episode not found")
            continue
        r = r.iloc[0]
        print(f"\n{tk} {target_date}:")
        for W in BASE_WINDOWS:
            print(f"  {W}d: prior_range_over_atr={r[f'prior_range_over_atr_{W}d']:.1f}x  "
                  f"sma_slope_pct={r[f'sma_slope_pct_{W}d']:.1f}%")

    print("\n--- Cross-cut: Layer B's decay/give-back stats by TERCILE of base tightness (90d window) ---")
    valid = out[out["prior_range_over_atr_90d"].notna()].copy()
    valid["tightness_tercile"] = pd.qcut(valid["prior_range_over_atr_90d"], 3, labels=["tightest", "mid", "loosest"])
    for label in ["tightest", "mid", "loosest"]:
        sub = valid[valid.tightness_tercile == label]
        print(f"  {label:8s} (n={len(sub)}, range_over_atr {sub['prior_range_over_atr_90d'].min():.1f}-{sub['prior_range_over_atr_90d'].max():.1f}x):  "
              f"vol_trend_corr_15d med={sub['vol_trend_corr_15d'].median():.3f}  "
              f"holds-above-prebreakout_15d={(sub['min_low_vs_prebreakout_pct_15d']>0).mean()*100:.1f}%  "
              f"holds-above-prebreakout_40d={(sub['min_low_vs_prebreakout_pct_40d']>0).mean()*100:.1f}%  "
              f"subsequent-expansion_40d={sub['subsequent_expansion_day_40d'].notna().mean()*100:.1f}%")

    print("\n--- Same cross-cut, but ALSO requiring novel_252d (genuinely novel AND check base tightness) ---")
    nov = valid[valid.novel_252d]
    nov_tercile = pd.qcut(nov["prior_range_over_atr_90d"], 3, labels=["tightest", "mid", "loosest"]) if len(nov) >= 30 else None
    if nov_tercile is not None:
        nov = nov.assign(tightness_tercile=nov_tercile)
        for label in ["tightest", "mid", "loosest"]:
            sub = nov[nov.tightness_tercile == label]
            print(f"  novel & {label:8s} (n={len(sub)}):  "
                  f"vol_trend_corr_15d med={sub['vol_trend_corr_15d'].median():.3f}  "
                  f"holds-above-prebreakout_15d={(sub['min_low_vs_prebreakout_pct_15d']>0).mean()*100:.1f}%  "
                  f"holds-above-prebreakout_40d={(sub['min_low_vs_prebreakout_pct_40d']>0).mean()*100:.1f}%")
    else:
        print(f"  n={len(nov)} novel episodes with base data -- too few for tercile split")

    # --- Follow-on: is RANGE-tightness (contaminated by each stock's own already-elevated
    # ATR when it's already active) the wrong single dimension? Cross-cut by FLATNESS
    # (|sma_slope_pct|) instead, which doesn't share that confound, then the intersection
    # of all three (novel AND flat AND tight) -- per direct user question after seeing the
    # range-only cut show no effect. ---
    print("\n--- Cross-cut by |sma_slope_pct_90d| tercile instead (flattest = closest to a real Stage 1 base) ---")
    valid["flat_tercile"] = pd.qcut(valid.sma_slope_pct_90d.abs(), 3, labels=["flattest", "mid", "trendiest"])
    for label in ["flattest", "mid", "trendiest"]:
        sub = valid[valid.flat_tercile == label]
        lo, hi = sub.sma_slope_pct_90d.abs().min(), sub.sma_slope_pct_90d.abs().max()
        print(f"  {label:10s} (n={len(sub)}, |slope| {lo:.1f}-{hi:.1f}%):  "
              f"holds-above-prebreakout_40d={(sub.min_low_vs_prebreakout_pct_40d>0).mean()*100:.1f}%  "
              f"subsequent-expansion_40d={sub.subsequent_expansion_day_40d.notna().mean()*100:.1f}%")

    print("\n--- Same, novel_252d only ---")
    nov2 = valid[valid.novel_252d].assign(
        flat_tercile=pd.qcut(valid[valid.novel_252d].sma_slope_pct_90d.abs(), 3, labels=["flattest", "mid", "trendiest"]))
    for label in ["flattest", "mid", "trendiest"]:
        sub = nov2[nov2.flat_tercile == label]
        print(f"  novel & {label:10s} (n={len(sub)}):  "
              f"holds-above-prebreakout_40d={(sub.min_low_vs_prebreakout_pct_40d>0).mean()*100:.1f}%")

    print("\n--- Triple-cut: novel_252d AND flattest tercile AND tightest range tercile ---")
    triple = valid[(valid.novel_252d) & (valid.flat_tercile == "flattest") & (valid.tightness_tercile == "tightest")]
    baseline_40d = (valid.min_low_vs_prebreakout_pct_40d > 0).mean() * 100
    print(f"  n={len(triple)}  (full-population baseline holds-above-prebreakout_40d={baseline_40d:.1f}%)")
    if len(triple):
        print(f"  holds-above-prebreakout_15d={(triple.min_low_vs_prebreakout_pct_15d>0).mean()*100:.1f}%  "
              f"holds-above-prebreakout_40d={(triple.min_low_vs_prebreakout_pct_40d>0).mean()*100:.1f}%  "
              f"vol_trend_corr_15d med={triple.vol_trend_corr_15d.median():.3f}  "
              f"subsequent-expansion_40d={triple.subsequent_expansion_day_40d.notna().mean()*100:.1f}%")
        triple.to_csv(f"{OUT_DIR}/rq05a_triple_cut_candidates.csv", index=False)
        print(f"  saved candidate list to rq05a_triple_cut_candidates.csv for hand-verification (Rule #22 -- NOT yet done)")
