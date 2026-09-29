"""RQ-QS-07A-3 -- Broad Pre-Event State Search (2026-09-29, critic+user corrected
sequencing, pre-registered before running).

QUESTION: among the FULL Cohort A population (D3 MFE >= P95, n=102,837) and their
matched controls -- NOT restricted to F&O/liquid names, per the explicit
correction ("why restrict to F&O before we've found what's actually causing
these outcomes") -- what pre-event, decision-time-safe state distinguishes a
future fast mover from a comparable non-event?

INFORMATION CUTOFF: every feature below is computed using ONLY data through day
T's own close (the day the forward D1-D3 window is measured FROM) -- reuses this
project's existing, already-validated production indicator columns
(`signals.py`'s `build_indicators()`), not re-derived. F&O eligibility, NIFTY-500
membership, circuit involvement, and liquidity decile are recorded as
STRATIFICATION/ANNOTATION on every row -- NOT included as candidate precursor
features (they are market-quality labels by construction, not the kind of
price/volume/volatility state being searched for here), and NOT used to filter
the population.

FEATURE FAMILIES, pre-declared (deliberately primitive first pass, per this
project's own standing discipline -- relative-strength/sector explicitly
DEFERRED, same known limitation as RQ-QS-07U: the existing RS/sector modules are
live single-lookup tools, not vectorized for this scale):

  Price structure:
    dist_ema8/21/34_pct, dist_sma50/150/200_pct  -- % distance from Close to each MA
    dist_high252_pct   -- % below the 52-week high (0 = at the high)
    dist_low252_pct    -- % above the 52-week low
    ret_5d/10d/20d      -- trailing % return
    range5_width_over_atr -- prior-5-day High-Low range / atr14 (compression measure,
                            reuses signals.py's own range5_high/range5_low, NOT
                            re-derived)
    rsi14
  Volume:
    vol_zscore          -- reuses signals.py's own prior-window z-score
    vol_ratio_10d        -- Volume / vol_avg10_prior
    vol_declining5        -- reuses production's own 5-day-declining flag
    ad_fraction          -- O'Neil accumulation/distribution (reused, not re-derived)
  Volatility:
    atr_expansion         -- atr14 / atr14_60ago
    body_atr              -- today's own candle body / atr14

No model, no score, no threshold chosen, no filter applied. Report the
distribution comparison (median/IQR, cohort vs control) for every feature, and
stop there -- deciding which (if any) feature is worth carrying into a real
candidate signal is a separate, later step.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots

OUT_DIR = "swing_qs_07a"
SEED = 42

FEATURES = [
    "dist_ema8_pct", "dist_ema21_pct", "dist_ema34_pct", "dist_sma50_pct",
    "dist_sma150_pct", "dist_sma200_pct", "dist_high252_pct", "dist_low252_pct",
    "ret_5d", "ret_10d", "ret_20d", "range5_width_over_atr", "rsi14",
    "vol_zscore", "vol_ratio_10d", "vol_declining5", "ad_fraction",
    "atr_expansion", "body_atr",
]

print("Loading event matrix and reconstructing Cohort A + matched controls "
      "(identical method/seed to 03_, reproducible)...", flush=True)
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
print(f"Cohort A: {len(a):,}  Controls: {len(controls):,}")

a["group"] = "cohort_a"
controls["group"] = "control"
work = pd.concat([a, controls], ignore_index=True)[["ticker", "date", "group",
    "nifty500_member", "fo_eligible", "circuit_days_in_window", "liq_decile"]]

print("Computing pre-event features from cached indicators (per-ticker, decision-time-safe)...", flush=True)
cache = {}
feat_rows = []
for n, r in enumerate(work.itertuples()):
    if n % 20000 == 0:
        print(f"  {n}/{len(work)}", flush=True)
    if r.ticker not in cache:
        try:
            cache[r.ticker] = load(r.ticker, daily_pivots)
        except FileNotFoundError:
            cache[r.ticker] = None
    idf = cache[r.ticker]
    if idf is None or r.date not in idf.index:
        continue
    row = idf.loc[r.date]
    close = row.Close
    ema8, ema21, ema34 = row.ema8, row.ema21, row.ema34
    sma50, sma150, sma200 = row.sma50, row.sma150, row.sma200
    high252, low252 = row.high_252, row.low_252
    atr14, atr60ago = row.atr14, row.atr14_60ago
    close_20ago = row.close_20ago
    # 5d/10d trailing returns: locate by integer position, not a stored column
    pos = idf.index.get_loc(r.date)
    close_5ago = idf.Close.iloc[pos - 5] if pos >= 5 else np.nan
    close_10ago = idf.Close.iloc[pos - 10] if pos >= 10 else np.nan

    feat = dict(
        ticker=r.ticker, date=r.date, group=r.group,
        dist_ema8_pct=(close / ema8 - 1) * 100 if pd.notna(ema8) else np.nan,
        dist_ema21_pct=(close / ema21 - 1) * 100 if pd.notna(ema21) else np.nan,
        dist_ema34_pct=(close / ema34 - 1) * 100 if pd.notna(ema34) else np.nan,
        dist_sma50_pct=(close / sma50 - 1) * 100 if pd.notna(sma50) else np.nan,
        dist_sma150_pct=(close / sma150 - 1) * 100 if pd.notna(sma150) else np.nan,
        dist_sma200_pct=(close / sma200 - 1) * 100 if pd.notna(sma200) else np.nan,
        dist_high252_pct=(close / high252 - 1) * 100 if pd.notna(high252) and high252 else np.nan,
        dist_low252_pct=(close / low252 - 1) * 100 if pd.notna(low252) and low252 else np.nan,
        ret_5d=(close / close_5ago - 1) * 100 if pd.notna(close_5ago) else np.nan,
        ret_10d=(close / close_10ago - 1) * 100 if pd.notna(close_10ago) else np.nan,
        ret_20d=(close / close_20ago - 1) * 100 if pd.notna(close_20ago) and close_20ago else np.nan,
        range5_width_over_atr=((row.range5_high - row.range5_low) / atr14) if pd.notna(atr14) and atr14 and pd.notna(row.range5_high) else np.nan,
        rsi14=row.rsi14,
        vol_zscore=row.vol_zscore,
        vol_ratio_10d=(row.Volume / row.vol_avg10_prior) if pd.notna(row.vol_avg10_prior) and row.vol_avg10_prior else np.nan,
        vol_declining5=bool(row.vol_declining5) if pd.notna(row.vol_declining5) else np.nan,
        ad_fraction=row.ad_fraction,
        atr_expansion=(atr14 / atr60ago) if pd.notna(atr60ago) and atr60ago else np.nan,
        body_atr=row.body_atr,
    )
    feat_rows.append(feat)

feats = pd.DataFrame(feat_rows)
feats.to_csv(f"{OUT_DIR}/precursor_features.csv", index=False)
print(f"\n{len(feats):,} rows with features computed, saved precursor_features.csv")


def pstack(s, fmt="{:.2f}"):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        return "n=0"
    return f"P25={fmt.format(np.percentile(s,25))} P50={fmt.format(np.percentile(s,50))} P75={fmt.format(np.percentile(s,75))} (n={len(s):,})"


print("\n" + "=" * 100 + "\nPRECURSOR FEATURE DISTRIBUTIONS -- Cohort A vs matched control\n" + "=" * 100)
ca = feats[feats.group == "cohort_a"]
ct = feats[feats.group == "control"]
for f in FEATURES:
    if f == "vol_declining5":
        print(f"  {f:24s} cohort_a: {ca[f].mean()*100:.1f}%   control: {ct[f].mean()*100:.1f}%")
        continue
    ca_med, ct_med = ca[f].median(), ct[f].median()
    print(f"  {f:24s} cohort_a: {pstack(ca[f])}   control: {pstack(ct[f])}   gap={ca_med-ct_med:+.2f}")
