"""RQ-QS-07A-P3 -- W/S State Overlay on QS-A's Real Trade Population (2026-09-30,
critic-specified). First Phase-3 experiment: does knowing the frozen W or S
state at T-1 materially change the subsequent QS-A trajectory distribution,
relative to QS-A entries that were not in that state? Purely OBSERVATIONAL --
does NOT establish that adding the state to the product improves performance
(no intervention on the entry population), and does NOT modify QS-A's entry
gate, stop, or exit in any way.

FROZEN, per critic's exact instruction:
  - Population: the ORIGINAL 46,613 QS-A positions (10D/20D/40D, real
    intraday breach, frozen v0.1 gate, S1b stop) -- no rebuild. (The D15
    extension script incidentally picked up 40 additional entries from
    trading days added to the cache after the original envelope was built --
    excluded here to stay exactly on the critic's named population.)
  - W(T) and S(T) evaluated using information through T-1 ONLY -- QS-A
    enters on a real intraday breach during day T, so T's own completed
    candle is not actually available at the entry moment. Using T's close
    (the convention every other 07A script used, since those were EOD-
    observed phenomena, not intraday entries) would be exactly the decision-
    time leakage this project's own CLAUDE.md Rule #18 exists to prevent.
  - No re-estimation of P10/P90/decline-median/percentile lookup/feature
    definitions -- the frozen CG1 artifacts are reused via the ALREADY-
    VERIFIED-EQUIVALENT decile/decline/ret_1d columns (17_'s audit proved 0
    boundary flips between the exact lookup and trend_state_anatomy.csv's
    own rank-based decile column, so decile==0/decile==9 there IS the frozen
    W/S precursor gate, not an approximation).
  - Two separate analyses (P3-W, P3-S) -- never combined into a joint
    filter. W∩S overlap verified empirically, not assumed.
  - Primary: close_r at D3/D5/D10/D15, giveback_from_mfe_pct.
  - Secondary: D1/D3/D5 MFE, MAE, first_hit_day (time to 0.5R/1R), full
    trajectory shape (median close_r across D1..D15).
  - Concentration/persistence guardrail (critical for S specifically): every
    comparison reports n positions, n distinct tickers, n distinct episodes
    -- a single ticker staying S for 30 days must not be read as 30
    independent confirmations.

No intervention, no threshold change, no entry change, no exit change, no
new predictor. Observational overlay only.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots

OUT_DIR = "swing_qs_07a"

print("Loading QS-A's D15-extended envelope (restricted to the ORIGINAL 46,613-position population)...", flush=True)
envelope = pd.read_csv(f"{OUT_DIR}/qsa_envelope_d15.csv", parse_dates=["entry_date"])
original_keys = pd.read_csv("swing_qs/trajectory_replay/rq_qs_06_envelope.csv", parse_dates=["entry_date"])[
    ["ticker", "entry_definition", "entry_date"]]
envelope = envelope.merge(original_keys, on=["ticker", "entry_definition", "entry_date"], how="inner")
print(f"QS-A population (original, no rebuild): {len(envelope):,} positions")

print("\nComputing T-1 (the real prior trading day per ticker) for each entry...", flush=True)
cache = {}
t_minus_1 = []
for r in envelope.itertuples():
    if r.ticker not in cache:
        try:
            cache[r.ticker] = load(r.ticker, daily_pivots).index
        except FileNotFoundError:
            cache[r.ticker] = None
    idx = cache[r.ticker]
    if idx is None or r.entry_date not in idx:
        t_minus_1.append(pd.NaT)
        continue
    pos = idx.get_loc(r.entry_date)
    t_minus_1.append(idx[pos - 1] if pos >= 1 else pd.NaT)
envelope["t_minus_1"] = t_minus_1
print(f"T-1 resolved for {envelope.t_minus_1.notna().sum():,} of {len(envelope):,} positions")

print("\nLooking up W(T-1)/S(T-1) from the already-verified-equivalent frozen classification "
      "(trend_state_anatomy.csv's decile column + full_population_decline_ret1d.csv)...", flush=True)
state = pd.read_csv(f"{OUT_DIR}/trend_state_anatomy.csv", parse_dates=["date"])[["ticker", "date", "decile"]]
extra = pd.read_csv(f"{OUT_DIR}/full_population_decline_ret1d.csv", parse_dates=["date"])
with open(f"{OUT_DIR}/frozen_candidate_spec.json") as f:
    import json
    DECLINE_MEDIAN = json.load(f)["decline_from_high10d_pct_median_weak_state"]

lookup = state.merge(extra, on=["ticker", "date"], how="inner")
lookup["is_D0"] = lookup.decile == 0
lookup["is_S_lookup"] = lookup.decile == 9
lookup["is_W_lookup"] = lookup.is_D0 & (lookup.decline_from_high10d_pct <= DECLINE_MEDIAN) & (lookup.ret_1d >= 0)
lookup = lookup.rename(columns={"date": "t_minus_1"})[["ticker", "t_minus_1", "is_W_lookup", "is_S_lookup"]]

envelope = envelope.merge(lookup, on=["ticker", "t_minus_1"], how="left")
envelope["is_W"] = envelope.is_W_lookup.fillna(False)
envelope["is_S"] = envelope.is_S_lookup.fillna(False)
n_classifiable = envelope.is_W_lookup.notna().sum()
print(f"T-1 classifiable against the frozen artifacts: {n_classifiable:,} of {len(envelope):,} "
      f"({n_classifiable/len(envelope)*100:.1f}%) -- the rest (missing ticker/date in the reference population, "
      f"e.g. outside 2022-09-02 to 2026-09-24, or insufficient 252d history) are treated as NOT W/NOT S, "
      f"not silently dropped from the denominator.")

overlap = envelope[envelope.is_W & envelope.is_S]
print(f"\nW ∩ S overlap: {len(overlap)} positions (verified, not assumed -- expected 0, opposite composite tails)")
print(f"W-tagged: {envelope.is_W.sum():,} positions   S-tagged: {envelope.is_S.sum():,} positions   "
      f"Neither: {(~envelope.is_W & ~envelope.is_S).sum():,} positions")

envelope.to_csv(f"{OUT_DIR}/p3_qsa_wstate_overlay.csv", index=False)

PRIMARY_DAYS = [3, 5, 10, 15]


def describe_group(df, label):
    n = len(df)
    n_tickers = df.ticker.nunique()

    def episodes(sub):
        count = 0
        for t, g in sub.sort_values("entry_date").groupby("ticker"):
            dates = g.entry_date.tolist()
            if not dates:
                continue
            count += 1
            for i in range(1, len(dates)):
                if (dates[i] - dates[i - 1]).days > 10:
                    count += 1
        return count

    n_episodes = episodes(df)
    print(f"\n-- {label} -- n={n:,}  distinct tickers={n_tickers:,}  distinct episodes(~10d gap rule)={n_episodes:,}")
    if n == 0:
        return
    top10_share = df.ticker.value_counts().head(10).sum() / n * 100
    print(f"   top-10-ticker share of positions: {top10_share:.2f}%")
    for d in PRIMARY_DAYS:
        col = f"close_r_D{d}"
        s = df[col].dropna()
        print(f"   close_r D{d}: median={s.median():+.3f}R  P25={np.percentile(s,25):+.3f}R  "
              f"P75={np.percentile(s,75):+.3f}R  (resolved n={len(s):,})")
    gb = df.giveback_from_mfe_pct.dropna()
    print(f"   giveback_from_mfe_pct (D15, where >=0.5R touched): median={gb.median():.1f}%  "
          f"(n={len(gb):,})  %>=100% (gave back the whole move): {(gb>=100).mean()*100:.1f}%")
    for d in [1, 3, 5]:
        s = df[f"mfe_D{d}"].dropna()
        print(f"   mfe D{d} (secondary): median={s.median():+.3f}R  (n={len(s):,})")
    mae15 = df.mae_D15.dropna()
    print(f"   mae D15 (secondary): median={mae15.median():+.3f}R  (n={len(mae15):,})")
    for r in [0.5, 1.0]:
        col = f"first_hit_day_{r}R"
        reached = df[col].notna()
        print(f"   first_hit_day_{r}R (secondary): reached by D15 = {reached.mean()*100:.1f}%  "
              f"median day = {df[col].median():.1f}" if reached.any() else f"   first_hit_day_{r}R: 0 reached")
    print(f"   stopped_by_D15 rate: {df.stopped_by_D15.notna().mean()*100:.1f}%")
    print(f"   full trajectory (median close_r, D1..D15): " +
          "  ".join(f"D{d}={df[f'close_r_D{d}'].median():+.2f}" for d in range(1, 16)))


print(f"\n{'='*115}\nP3-W -- W-tagged QS-A entries vs. non-W\n{'='*115}")
describe_group(envelope[envelope.is_W], "W-tagged")
describe_group(envelope[~envelope.is_W], "non-W")

print(f"\n{'='*115}\nP3-S -- S-tagged QS-A entries vs. non-S\n{'='*115}")
describe_group(envelope[envelope.is_S], "S-tagged")
describe_group(envelope[~envelope.is_S], "non-S")

print("\nDONE")
