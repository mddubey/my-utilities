"""RQ-QS-07A-6 -- Weak-State Fast-Mover Mechanism (2026-09-30, critic-specified).

Narrow core question (critic's exact wording): "Within the already-frozen
weak-state D0 population, what decision-time price/volume/volatility
transition distinguishes the 3-day fast movers from ordinary D0 days?"

WITHIN-D0 discrimination, not D0-vs-D2 anymore (07A-5R already closed that
question -- PASS, robust, compatible timing). This compares D0 Cohort A
against D0 stock-days that did NOT become Cohort A ("D0 ordinary"), same
comparison repeated for Cohort B per this project's standing A/B-separate
discipline (critic's prose focused on A; B is added here as the same
established convention, not a new complexity).

FROZEN, per critic's instruction: event_matrix.csv, same D0 definition
(decile==0 of the already-built composite from 10_trend_state_anatomy.py,
NOT redefined), same 1,668,305-row-population-derived D0 subset (166,831
rows), same Cohort A/B definitions, same decision-time boundary. No
rebuilding the state score. No new D0 threshold. No new outcome definition.

CRITICAL METHODOLOGICAL REQUIREMENT (critic's explicit composite-decomposition
rule): the 5 variables that DEFINE D0 (dist_sma200_pct, ret_20d,
dist_low252_pct, dist_ema34_pct, rsi14) are reported SEPARATELY, as
descriptive context only -- NOT claimed as an independent mechanism finding,
since D0 is a bottom-decile bucket of exactly these 5 variables by
construction, so any within-D0 gap in them is expected/partially circular,
not new information. The actual mechanism candidates below are ALL distinct
from these 5 (verified: none share a formula or lookback window with the
composite's own inputs).

DECISION-TIME BOUNDARY: every feature below is computed strictly from T's own
closed daily candle and backward-looking rolling windows -- the same
EOD-confirmed research convention as every other 07A feature-discovery script
(05_/06_/08_), not a live-intraday gate (Rule #18 concerns a GATE mixed with a
live intraday TRIGGER; this is pure retrospective EOD research where T's
candle is fully realized before the D1-D3 forward outcome window even
starts). T's own same-day OHLC (close location, today's return, gap) is
legitimate here precisely because Cohort A/B are determined by D1-D3, strictly
AFTER T.

MECHANISM FAMILIES, tested in critic's exact priority order:

Family 1 -- Reversal/capitulation anatomy (most important, per critic):
  ret_1d, ret_3d          -- short-horizon decline/recovery into T (NOT ret_5d/
                              ret_20d, which are already state-definition-
                              adjacent; kept clear of the composite's ret_20d)
  dist_low10d_pct         -- % above the 10-day local low (SHORT lookback,
                              deliberately distinct from the composite's
                              252-day dist_low252_pct)
  decline_from_high10d_pct -- % below the 10-day local high (magnitude of the
                              recent slide that produced this D0 state)
  close_loc_pct           -- T's own close location in T's H-L range (0=at
                              the low, 100=at the high) -- "is T itself a
                              reversal day"
  lower_wick_pct          -- T's own lower-wick size as % of T's H-L range
  body_atr                -- reused directly from signals.py's production
                              formula (Close-Open)/ATR14, no reimplementation

Family 2 -- Volume/participation shock:
  vol_ratio_10d, vol_zscore, vol_declining5, ad_fraction -- all reused
  directly from signals.py's production formulas (verified against source,
  same as 05_precursor_discovery.py -- no reimplementation)

Family 3 -- Volatility-state transition:
  atr_expansion            -- reused directly (atr14/atr14_60ago, production
                              formula) -- "vs 60 days ago" baseline
  atr_accel                -- NEW, shorter horizon (atr14/atr14.shift(10)) --
                              "is volatility expanding RIGHT NOW," distinct
                              lookback from atr_expansion
  range5_width_over_atr    -- reused directly (production formula)
  gap_pct                  -- NEW, (Open/Close.shift(1)-1)*100, T's own
                              opening gap

Explicitly NOT built this pass, per critic's instruction: catalyst/news
infrastructure (open-ended rabbit hole risk -- only pursued if price/volume/
volatility anatomy fails to separate the tail).

PRE-REGISTERED DECISION RULES (critic's exact wording, locked before running):
  - If no feature separates D0 fast movers from D0 ordinary: mechanism branch
    remains unexplained. Do not manufacture a filter.
  - If one mechanism family separates: audit it across years/liquidity/F&O/
    circuit-clean in a FOLLOW-UP RQ (07A-6R, matching the 07A-5->07A-5R
    pattern) -- NOT in this same pass.
  - If several variables separate but are highly correlated: treat as ONE
    mechanism family, not multiple independent signals (Spearman check
    below, same diagnostic style as 07A-3R).
  - If separation is strong and robust (after the follow-up robustness pass):
    THEN, and only then, revisit product architecture -- explicitly NOT this
    RQ's job.

No threshold chosen. No filter. No model. No strategy simulation. No
catalyst/news data pulled.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots

OUT_DIR = "swing_qs_07a"
STATE_DEFINITION_VARS = ["dist_sma200_pct", "ret_20d", "dist_low252_pct", "dist_ema34_pct", "rsi14"]
FAMILY1 = ["ret_1d", "ret_3d", "dist_low10d_pct", "decline_from_high10d_pct",
            "close_loc_pct", "lower_wick_pct", "body_atr"]
FAMILY2 = ["vol_ratio_10d", "vol_zscore", "vol_declining5", "ad_fraction"]
FAMILY3 = ["atr_expansion", "atr_accel", "range5_width_over_atr", "gap_pct"]
MECHANISM_FEATURES = FAMILY1 + FAMILY2 + FAMILY3

print("Loading D0 population (frozen, from 10_trend_state_anatomy.py's already-built decile)...", flush=True)
full = pd.read_csv(f"{OUT_DIR}/trend_state_anatomy.csv", parse_dates=["date"])
d0 = full[full.decile == 0][["ticker", "date", "close", "cohort_a", "cohort_b"] + STATE_DEFINITION_VARS].copy()
print(f"D0 population: {len(d0):,}  Cohort A: {d0.cohort_a.sum():,}  Cohort B: {d0.cohort_b.sum():,}")

print("Computing mechanism-candidate features (per-ticker, decision-time-safe)...", flush=True)
grouped = list(d0.groupby("ticker", sort=False))
rows_out = []
for n, (t, sub) in enumerate(grouped):
    if n % 300 == 0:
        print(f"  {n}/{len(grouped)}", flush=True)
    try:
        idf = load(t, daily_pivots)
    except FileNotFoundError:
        continue
    idx = idf.index
    for r in sub.itertuples():
        if r.date not in idx:
            continue
        pos = idx.get_loc(r.date)
        row = idf.loc[r.date]
        close, open_, high, low = row.Close, row.Open, row.High, row.Low
        hl_range = high - low
        close_1ago = idf.Close.iloc[pos - 1] if pos >= 1 else np.nan
        close_3ago = idf.Close.iloc[pos - 3] if pos >= 3 else np.nan
        low10 = idf.Low.iloc[max(0, pos - 9):pos + 1].min() if pos >= 9 else np.nan
        high10 = idf.High.iloc[max(0, pos - 9):pos + 1].max() if pos >= 9 else np.nan
        atr14_10ago = idf.atr14.iloc[pos - 10] if pos >= 10 else np.nan
        rows_out.append(dict(
            idx=r.Index,
            ret_1d=(close / close_1ago - 1) * 100 if pd.notna(close_1ago) else np.nan,
            ret_3d=(close / close_3ago - 1) * 100 if pd.notna(close_3ago) else np.nan,
            dist_low10d_pct=(close / low10 - 1) * 100 if pd.notna(low10) and low10 else np.nan,
            decline_from_high10d_pct=(close / high10 - 1) * 100 if pd.notna(high10) and high10 else np.nan,
            close_loc_pct=((close - low) / hl_range * 100) if hl_range else np.nan,
            lower_wick_pct=((min(open_, close) - low) / hl_range * 100) if hl_range else np.nan,
            body_atr=row.body_atr,
            vol_ratio_10d=(row.Volume / row.vol_avg10_prior) if pd.notna(row.vol_avg10_prior) and row.vol_avg10_prior else np.nan,
            vol_zscore=row.vol_zscore,
            vol_declining5=bool(row.vol_declining5) if pd.notna(row.vol_declining5) else np.nan,
            ad_fraction=row.ad_fraction,
            atr_expansion=(row.atr14 / row.atr14_60ago) if pd.notna(row.atr14_60ago) and row.atr14_60ago else np.nan,
            atr_accel=(row.atr14 / atr14_10ago) if pd.notna(atr14_10ago) and atr14_10ago else np.nan,
            range5_width_over_atr=((row.range5_high - row.range5_low) / row.atr14) if pd.notna(row.atr14) and row.atr14 and pd.notna(row.range5_high) else np.nan,
            gap_pct=(open_ / close_1ago - 1) * 100 if pd.notna(close_1ago) and close_1ago else np.nan,
        ))

feat = pd.DataFrame(rows_out).set_index("idx")
d0 = d0.join(feat)
d0.to_csv(f"{OUT_DIR}/weak_state_mechanism_features.csv", index=False)
print(f"saved weak_state_mechanism_features.csv ({len(d0):,} rows)")


BOOLEAN_FEATURES = {"vol_declining5"}


def pstack(s, colname=None):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        return "n=0"
    if colname in BOOLEAN_FEATURES:
        return f"rate={s.astype(float).mean()*100:.2f}%"
    return f"P25={np.percentile(s,25):.2f} P50={np.percentile(s,50):.2f} P75={np.percentile(s,75):.2f}"


def central(s, colname=None):
    s = pd.Series(s).dropna()
    if colname in BOOLEAN_FEATURES:
        return s.astype(float).mean() * 100
    return s.median()


def leaderboard_style_table(cohort_col, cohort_label):
    fast = d0[d0[cohort_col]]
    ordinary = d0[~d0[cohort_col]]
    print(f"\n{'='*115}\nD0 {cohort_label} fast movers (n={len(fast):,}) vs D0 ordinary (n={len(ordinary):,})\n{'='*115}")
    print(f"\n-- STATE-DEFINITION VARIABLES (descriptive only -- D0 is a bottom-decile bucket of exactly "
          f"these 5, do NOT read a gap here as an independent mechanism finding) --")
    for f in STATE_DEFINITION_VARS:
        fm, om = central(fast[f], f), central(ordinary[f], f)
        print(f"  {f:20s} fast: {pstack(fast[f], f):35s} ordinary: {pstack(ordinary[f], f):35s} gap={fm-om:+.2f}")

    print(f"\n-- MECHANISM CANDIDATES (Family 1: reversal/capitulation anatomy) --")
    rows = []
    for f in FAMILY1:
        fm, om = central(fast[f], f), central(ordinary[f], f)
        gap = fm - om
        rows.append((f, fast[f], ordinary[f], fm, om, gap))
        print(f"  {f:26s} fast: {pstack(fast[f], f):35s} ordinary: {pstack(ordinary[f], f):35s} gap={gap:+.2f}")

    print(f"\n-- MECHANISM CANDIDATES (Family 2: volume/participation shock) --")
    for f in FAMILY2:
        fm, om = central(fast[f], f), central(ordinary[f], f)
        gap = fm - om
        rows.append((f, fast[f], ordinary[f], fm, om, gap))
        print(f"  {f:26s} fast: {pstack(fast[f], f):35s} ordinary: {pstack(ordinary[f], f):35s} gap={gap:+.2f}")

    print(f"\n-- MECHANISM CANDIDATES (Family 3: volatility-state transition) --")
    for f in FAMILY3:
        fm, om = central(fast[f], f), central(ordinary[f], f)
        gap = fm - om
        rows.append((f, fast[f], ordinary[f], fm, om, gap))
        print(f"  {f:26s} fast: {pstack(fast[f], f):35s} ordinary: {pstack(ordinary[f], f):35s} gap={gap:+.2f}")

    return fast, ordinary, rows


fast_a, ordinary_a, rows_a = leaderboard_style_table("cohort_a", "Cohort A")
fast_b, ordinary_b, rows_b = leaderboard_style_table("cohort_b", "Cohort B")

print(f"\n{'='*115}\nCORRELATION DIAGNOSTIC (Spearman) among mechanism candidates, within D0 Cohort A fast movers\n"
      f"(checks whether several 'separating' variables are actually one latent mechanism)\n{'='*115}")
print(fast_a[MECHANISM_FEATURES].corr(method="spearman").round(2).to_string())

print(f"\n{'='*115}\nSEPARATION TABLE -- standardized effect size (median gap / ordinary-population IQR), critic's exact "
      f"requested format. Pre-declared bands (fixed before computing): |z|>=0.30 IQR = CANDIDATE, "
      f"0.10-0.30 = weak, <0.10 = null.\n{'='*115}")


def separation_table(cohort_col, cohort_label):
    fast = d0[d0[cohort_col]]
    ordinary = d0[~d0[cohort_col]]
    out = []
    for family_name, fam in [("Family1-Reversal", FAMILY1), ("Family2-Volume", FAMILY2), ("Family3-Volatility", FAMILY3)]:
        for f in fam:
            fa, oa = fast[f].dropna(), ordinary[f].dropna()
            if f in BOOLEAN_FEATURES:
                fm, om = fa.astype(float).mean() * 100, oa.astype(float).mean() * 100
                z = np.nan
            else:
                fm, om = fa.median(), oa.median()
                iqr = np.percentile(oa, 75) - np.percentile(oa, 25)
                z = (fm - om) / iqr if iqr else np.nan
            label = "n/a (rate)" if pd.isna(z) else ("CANDIDATE" if abs(z) >= 0.30 else ("weak" if abs(z) >= 0.10 else "null"))
            out.append(dict(cohort=cohort_label, family=family_name, feature=f, fast=round(fm, 3),
                              ordinary=round(om, 3), gap=round(fm - om, 3),
                              z_iqr=round(z, 3) if pd.notna(z) else np.nan, interpretation=label))
    return pd.DataFrame(out)


sep_a = separation_table("cohort_a", "CohortA")
sep_b = separation_table("cohort_b", "CohortB")
sep = pd.concat([sep_a, sep_b], ignore_index=True)
print(sep.to_string(index=False))
sep.to_csv(f"{OUT_DIR}/weak_state_mechanism_separation.csv", index=False)
print(f"\nsaved weak_state_mechanism_separation.csv ({len(sep)} rows)")

print("\nDONE")
