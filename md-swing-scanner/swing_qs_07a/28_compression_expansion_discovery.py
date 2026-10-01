"""RQ-QS-07A-C1 -- Compression -> Expansion Discovery (2026-10-01, research-
board item #2, critic's explicit next-in-order pick). First discovery pass
for this hypothesis family: "before exceptional 3-day moves, do stocks
exhibit a measurable period of range contraction followed by expansion?"
Phase 1-2 of the reset research posture (outcome already frozen, this pass
is purely characteristics-discovery) -- NOT yet a candidate state, NOT an
entry construct. Per the breadth-before-depth rule: one pass, pre-declared,
then decide kill/promote before any further tuning.

LITERATURE CHECKED FIRST (per this project's own External Reading
Guardrail), not invented from the data: published, standard ways to
operationalize "volatility contraction" are (1) a SHORT/LONG ATR ratio
(commonly ATR(5)/ATR(20), contraction when short is meaningfully below
long), (2) a SHORT/LONG price-range ratio (5-day High-Low range vs. 20-day
range, contraction when the 5-day range is a small fraction of the 20-day
range), and (3) Bollinger Band Width expressed as a PERCENTILE of its own
trailing history (a stock-specific, not cross-sectional, percentile --
"the tightest the bands have been in N months"). These three are pre-
declared BEFORE looking at any result, per Rule #19's Parameterized Feature
corollary -- genuinely distinct mechanics (not the same feature at three
window sizes), not selected after seeing which one "wins."

VCP-ADJACENT, NOT VCP-PRESCRIPTIVE: this tests the general MECHANISM
(contraction precedes expansion) across the broad universe, not Minervini's
specific VCP entry rules (multiple progressively-tighter contractions,
volume-dry-up-then-surge, a specific base-depth ceiling, etc.) -- those are
a later, much more specific question if this first pass finds real signal.

POPULATION: the already-frozen Cohort A (102,837 events, D3 MFE >= P95) +
matched control (same-date + same-liquidity-decile, seed=42) -- IDENTICAL
construction to 03_/05_/07_/08_, reused not rebuilt. No new outcome
definition. Cohort B included for the standing A/B-separate discipline.

NO threshold chosen, no composite, no entry construct -- distribution
comparison only, same discipline as every other precursor-discovery script
in this line.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots
from signals import atr

OUT_DIR = "swing_qs_07a"
SEED = 42

print("Reconstructing Cohort A + matched controls (identical to 03_/05_/07_/08_)...", flush=True)
df = pd.read_csv(f"{OUT_DIR}/event_matrix.csv", parse_dates=["date"])
P95_MFE = np.percentile(df.max_return_d3, 95)
df["cohort_a"] = df.max_return_d3 >= P95_MFE
df["cohort_b"] = df.close_ret_d3 >= np.percentile(df.close_ret_d3, 95)
df["liq_decile"] = df.groupby("date")["traded_value_sma20"].transform(
    lambda x: pd.qcut(x, 10, labels=False, duplicates="drop"))

rng = np.random.RandomState(SEED)
noncohort = df[~df.cohort_a & ~df.cohort_b]
pool_by_key = noncohort.groupby(["date", "liq_decile"]).apply(lambda g: g.index.tolist(), include_groups=False)


def draw_control(row):
    pool = pool_by_key.get((row["date"], row["liq_decile"]))
    return pool[rng.randint(len(pool))] if pool else None


a = df[df.cohort_a].copy()
control_idx = a.apply(draw_control, axis=1)
a = a[control_idx.notna()].copy()
controls = df.loc[control_idx.dropna().astype(int)].copy()
a["group"], controls["group"] = "cohort_a", "control"
work = pd.concat([a[["ticker", "date", "group", "cohort_b", "liq_decile"]],
                    controls[["ticker", "date", "group", "cohort_b", "liq_decile"]]], ignore_index=True)
print(f"Cohort A: {len(a):,}  Controls: {len(controls):,}")

print("\nComputing the 3 pre-declared compression features (per-ticker, decision-time-safe)...", flush=True)
cache = {}
rows_out = []
for n, r in enumerate(work.itertuples()):
    if n % 20000 == 0:
        print(f"  {n}/{len(work)}", flush=True)
    if r.ticker not in cache:
        try:
            idf = load(r.ticker, daily_pivots)
            idf["atr5"] = atr(idf, 5)
            idf["atr20"] = atr(idf, 20)
            idf["range5"] = idf.High.rolling(5).max() - idf.Low.rolling(5).min()
            idf["range20"] = idf.High.rolling(20).max() - idf.Low.rolling(20).min()
            sma20, std20 = idf.Close.rolling(20).mean(), idf.Close.rolling(20).std()
            idf["bbw"] = (4 * std20) / sma20 * 100
            cache[r.ticker] = idf
        except FileNotFoundError:
            cache[r.ticker] = None
    idf = cache[r.ticker]
    if idf is None or r.date not in idf.index:
        continue
    pos = idf.index.get_loc(r.date)
    row = idf.iloc[pos]
    atr_ratio = row.atr5 / row.atr20 if pd.notna(row.atr5) and pd.notna(row.atr20) and row.atr20 else np.nan
    range_ratio = row.range5 / row.range20 if pd.notna(row.range5) and pd.notna(row.range20) and row.range20 else np.nan
    bbw_today = row.bbw
    if pd.notna(bbw_today) and pos >= 251:
        bbw_hist = idf.bbw.iloc[pos - 251:pos + 1].dropna().values
        if len(bbw_hist) >= 60:
            bbw_pctile = float((np.searchsorted(np.sort(bbw_hist), bbw_today, side="left")
                                  + np.searchsorted(np.sort(bbw_hist), bbw_today, side="right") + 1)
                                 / 2.0 / len(bbw_hist) * 100)
        else:
            bbw_pctile = np.nan
    else:
        bbw_pctile = np.nan
    rows_out.append(dict(ticker=r.ticker, date=r.date, group=r.group, cohort_b=r.cohort_b, liq_decile=r.liq_decile,
                            atr_ratio=atr_ratio, range_ratio=range_ratio, bbw_percentile=bbw_pctile))

feats = pd.DataFrame(rows_out)
feats.to_csv(f"{OUT_DIR}/compression_expansion_features.csv", index=False)
print(f"\n{len(feats):,} rows, saved compression_expansion_features.csv")


def pstack(s):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        return "n=0"
    return f"P25={np.percentile(s,25):.3f} P50={np.percentile(s,50):.3f} P75={np.percentile(s,75):.3f} (n={len(s):,})"


print(f"\n{'='*110}\nCOMPRESSION FEATURES -- Cohort A vs matched control\n{'='*110}")
ca, ct = feats[feats.group == "cohort_a"], feats[feats.group == "control"]
for f in ["atr_ratio", "range_ratio", "bbw_percentile"]:
    ca_med, ct_med = ca[f].median(), ct[f].median()
    print(f"  {f:18s} cohort_a: {pstack(ca[f]):40s}  control: {pstack(ct[f]):40s}  gap={ca_med-ct_med:+.3f}")

print(f"\n{'='*110}\nCohort B context (within the same Cohort A sample, since B is a heavily-overlapping -- 73.4% --\n"
      f"population per 07A-2B; full independent B-vs-control symmetry deferred to a follow-up if A shows signal,\n"
      f"same precedent as 07A-3 -> 07A-2B)\n{'='*110}")
cb_within_a = feats[(feats.group == "cohort_a") & feats.cohort_b]
a_not_b = feats[(feats.group == "cohort_a") & ~feats.cohort_b]
for f in ["atr_ratio", "range_ratio", "bbw_percentile"]:
    print(f"  {f:18s} A-and-B overlap: {pstack(cb_within_a[f])}   A-only: {pstack(a_not_b[f])}")

print("\nDONE")
