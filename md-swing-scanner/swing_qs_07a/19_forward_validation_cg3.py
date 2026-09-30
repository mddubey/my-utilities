"""RQ-QS-07A-CG3 -- Forward/Out-of-Sample Candidate Validation (started
2026-09-30, critic-specified; hardened 2026-09-30 per critic's follow-up
review). The line crossed here, per critic: from "can we discover another
precursor?" to "when we freeze what we discovered and let it run forward,
does it actually surface the phenomenon?"

STATUS (critic's exact words): RUNNING / PARKED. No new RQ right now. This
script's only job is to accumulate genuinely unseen candidate dates until
enough D3-resolved observations exist for a real checkpoint review (critic's
guidance: ~20-30 D3-resolved OOS trading dates, several hundred W events,
several thousand S events). Re-run this script each time `fetch_prices.py`
brings in fresh trading days. Do NOT: optimize on partial D1/D2 numbers,
compare W vs S on a handful of observations, promote D1/D2 to alternative
success labels, investigate day-to-day candidate-count variation, add
market-regime/freshness/liquidity/F&O/circuit filters, alter the W/S
definitions, or backfill/recalibrate the frozen constants. The candidate
engine is frozen.

STRICT REQUIREMENT (unchanged): reuses `frozen_candidate_spec.json` +
`frozen_sorted_arrays.npz` exactly as produced by `17_boundary_flip_audit.py`.
No recalculation, no re-estimation, no new percentile boundaries, no adding
recent data to the reference population.

APPEND-ONLY DESIGN (critic's explicit hardening requirement, implemented
here): a candidate DECISION (composite, decline_from_high10d_pct, ret_1d,
is_W, is_S, persistence, run_date) is computed ONCE, the first time a given
(ticker, date) is ever seen, and is then IMMUTABLE -- never silently
overwritten on a later re-run. On every re-run, this script:
  1. Recomputes the decision fields for already-recorded (ticker, date) rows
     ONLY as an integrity check -- if the recomputed value differs from what
     was already stored (e.g. an upstream price-cache correction), this is
     flagged LOUDLY, not silently replaced.
  2. Updates the OUTCOME fields (max_return/adverse/close_ret for d1/d2/d3,
     plus `d3_resolution_date`) for already-recorded rows -- this IS meant to
     change over time as more days resolve, that's the whole point.
  3. Adds brand-new rows for any (ticker, date) never seen before, stamped
     with `run_date` = today (the date this candidate was actually decided).

THREE TIMESTAMPS PER ROW (critic's explicit requirement): `date` (the
candidate/observation date T), `run_date` (when this candidate decision was
first computed -- should equal or closely follow T in normal operation),
`d3_resolution_date` (the calendar date D3 became resolved, NaN while
pending). Together these let us later demonstrate: "this candidate was
generated on T using only information available then; its outcome was
resolved on T+3" -- stronger evidence than an OOS CSV alone.

D1/D2 ARE PARTIAL/NOT-FOR-EVALUATION TELEMETRY (critic's explicit
instruction): retained because they're already being produced and can help
catch future data/logic failures, but never treated as a success label and
never used for any comparison. Labeled as such in every printout.

CLUSTERING WARNING (critic's explicit statistical guardrail, for whenever
this is eventually reviewed at the ~20-30-date checkpoint): S's candidate-
events are NOT independent observations -- the same ticker can appear on
many consecutive dates (CG2: 91.9% of S events in a 4+-day run). A raw
event-level incidence rate must never be reported with an unclustered
confidence interval or treated as N independent trials. Not implemented
here (nothing to evaluate yet) -- noted for whoever runs the eventual
checkpoint review.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import json
import datetime
import numpy as np
import pandas as pd
from backtest import load, daily_pivots

OUT_DIR = "swing_qs_07a"
PRIMARY = ["dist_sma200_pct", "ret_20d", "dist_low252_pct", "dist_ema34_pct", "rsi14"]
CANDIDATES_FILE = f"{OUT_DIR}/cg3_forward_candidates.csv"
TODAY = pd.Timestamp(datetime.date.today())

print("Loading FROZEN spec (CG1 integrity-patched version -- no recalculation)...", flush=True)
with open(f"{OUT_DIR}/frozen_candidate_spec.json") as f:
    spec = json.load(f)
P10, P90 = spec["composite_p10_weak_state_cutoff"], spec["composite_p90_strong_state_cutoff"]
DECLINE_MEDIAN = spec["decline_from_high10d_pct_median_weak_state"]
SORTED_ARRAYS = dict(np.load(f"{OUT_DIR}/frozen_sorted_arrays.npz"))
FREEZE_CUTOFF = pd.Timestamp(spec["reference_population_dates"][1])
print(f"Frozen: P10={P10:.3f}  P90={P90:.3f}  decline_median={DECLINE_MEDIAN:.3f}  freeze_cutoff={FREEZE_CUTOFF.date()}")


def exact_percentile_rank(value, sorted_arr):
    left = np.searchsorted(sorted_arr, value, side="left")
    right = np.searchsorted(sorted_arr, value, side="right")
    return (left + right + 1) / 2.0 / len(sorted_arr) * 100.0


def compute_composite(vals):
    ranks = [exact_percentile_rank(vals[f], SORTED_ARRAYS[f]) for f in PRIMARY]
    return float(np.mean(ranks))


def compute_decision(idf, idx, pos):
    """Returns None if not eligible (insufficient history). Otherwise the
    candidate decision fields -- computed identically regardless of whether
    this (ticker, date) is brand new or already recorded (used both to
    create new rows and to integrity-check existing ones)."""
    if pos < 252:
        return None
    row = idf.iloc[pos]
    close = row.Close
    close_1ago = idf.Close.iloc[pos - 1]
    close_20ago = idf.Close.iloc[pos - 20] if pos >= 20 else np.nan
    high10 = idf.High.iloc[max(0, pos - 9):pos + 1].max() if pos >= 9 else np.nan
    vals = dict(
        dist_sma200_pct=(close / row.sma200 - 1) * 100 if pd.notna(row.sma200) else np.nan,
        ret_20d=(close / close_20ago - 1) * 100 if pd.notna(close_20ago) and close_20ago else np.nan,
        dist_low252_pct=(close / row.low_252 - 1) * 100 if pd.notna(row.low_252) and row.low_252 else np.nan,
        dist_ema34_pct=(close / row.ema34 - 1) * 100 if pd.notna(row.ema34) else np.nan,
        rsi14=row.rsi14,
    )
    if any(pd.isna(v) for v in vals.values()):
        return None
    composite = compute_composite(vals)
    decline_from_high10d_pct = (close / high10 - 1) * 100 if pd.notna(high10) and high10 else np.nan
    ret_1d = (close / close_1ago - 1) * 100 if pd.notna(close_1ago) and close_1ago else np.nan
    is_D0 = composite <= P10
    is_S = composite >= P90
    is_W = is_D0 and pd.notna(decline_from_high10d_pct) and decline_from_high10d_pct <= DECLINE_MEDIAN and ret_1d >= 0
    return dict(composite=composite, decline_from_high10d_pct=decline_from_high10d_pct, ret_1d=ret_1d,
                 is_W=bool(is_W), is_S=bool(is_S))


def compute_outcome(idf, idx, pos, candidate_date):
    """PARTIAL/NOT-FOR-EVALUATION telemetry (d1/d2) plus the real outcome
    (d3). Returns whichever of d1/d2/d3 are actually resolvable right now,
    NaN otherwise, plus d3_resolution_date (the real calendar date D3's
    close was cached) once resolved."""
    close = idf.Close.iloc[pos]
    out = {}
    d3_resolution_date = np.nan
    for k, label in [(1, "d1"), (2, "d2"), (3, "d3")]:
        if pos + k < len(idx):
            fut_close = idf.Close.iloc[pos + k]
            fut_high = idf.High.iloc[pos + 1:pos + k + 1].max()
            fut_low = idf.Low.iloc[pos + 1:pos + k + 1].min()
            out[f"max_return_{label}"] = (fut_high / close - 1) * 100
            out[f"adverse_{label}"] = (fut_low / close - 1) * 100
            out[f"close_ret_{label}"] = (fut_close / close - 1) * 100
            if label == "d3":
                d3_resolution_date = idx[pos + k]
        else:
            out[f"max_return_{label}"] = np.nan
            out[f"adverse_{label}"] = np.nan
            out[f"close_ret_{label}"] = np.nan
    out["d3_resolution_date"] = d3_resolution_date
    return out


print("\nDetermining the OOS window (checked directly against the real cache, not assumed)...", flush=True)
ref_ticker = pd.read_csv("data_cache/RELIANCE.csv", index_col="Date", parse_dates=True)
oos_dates = sorted(d for d in ref_ticker.index if d > FREEZE_CUTOFF)
print(f"OOS trading dates available right now: {[d.date() for d in oos_dates]}")

if os.path.exists(CANDIDATES_FILE):
    _probe = pd.read_csv(CANDIDATES_FILE, nrows=1)
    if "run_date" not in _probe.columns:
        print(f"NOTE: {CANDIDATES_FILE} exists but predates the run_date/d3_resolution_date/persistence schema "
              f"(it was written earlier THIS SAME SESSION, before the append-only hardening). One-time schema "
              f"migration: treated as if no prior file exists -- every decision will be recomputed identically "
              f"(fully deterministic from the frozen spec + cached prices, already proven bit-for-bit "
              f"reproducible) and re-saved under the new schema with run_date backfilled to today, since today "
              f"is genuinely when these decisions were first computed. From THIS run forward, the file is truly "
              f"append-only.")
        existing = pd.DataFrame(columns=["ticker", "date"])
    else:
        existing = pd.read_csv(CANDIDATES_FILE, parse_dates=["date", "run_date", "d3_resolution_date"])
else:
    existing = pd.DataFrame(columns=["ticker", "date"])
existing_keys = set(zip(existing.ticker, existing.date)) if len(existing) else set()
print(f"Existing living artifact: {len(existing)} rows already recorded ({existing.date.nunique() if len(existing) else 0} distinct dates)")

print("\nLoading last-in-sample-day full W/S status for persistence labeling of any brand-new rows...", flush=True)
last_insample = pd.read_csv(f"{OUT_DIR}/trend_state_anatomy.csv", parse_dates=["date"])
last_insample = last_insample[last_insample.date == FREEZE_CUTOFF][["ticker", "decile"]]
mech_hist = pd.read_csv(f"{OUT_DIR}/weak_state_mechanism_features.csv", parse_dates=["date"])[
    ["ticker", "date", "ret_1d", "decline_from_high10d_pct"]]
prev_day_full = last_insample[last_insample.decile == 0].merge(
    mech_hist[mech_hist.date == FREEZE_CUTOFF][["ticker", "ret_1d", "decline_from_high10d_pct"]], on="ticker", how="inner")
seed_S = set(last_insample[last_insample.decile == 9].ticker)
seed_W = set(prev_day_full[(prev_day_full.decline_from_high10d_pct <= DECLINE_MEDIAN) & (prev_day_full.ret_1d >= 0)].ticker)

universe = pd.read_csv("nse_equity_universe.csv").ticker.tolist()
print(f"\nProcessing {len(universe)} universe tickers across {len(oos_dates)} OOS dates "
      f"(new rows created, existing rows integrity-checked + outcome-refreshed)...", flush=True)

new_rows = []
updated_outcomes = {}  # (ticker, date) -> outcome dict, for rows already in `existing`
mismatch_warnings = []
day_membership = {}  # date -> {ticker: (is_W, is_S)}, built as we go, for persistence labeling of new rows

for n, t in enumerate(universe):
    if n % 300 == 0:
        print(f"  {n}/{len(universe)}", flush=True)
    try:
        idf = load(t, daily_pivots)
    except FileNotFoundError:
        continue
    idx = idf.index
    for d in oos_dates:
        if d not in idx:
            continue
        pos = idx.get_loc(d)
        decision = compute_decision(idf, idx, pos)
        if decision is None:
            continue
        day_membership.setdefault(d, {})[t] = (decision["is_W"], decision["is_S"])
        if not (decision["is_W"] or decision["is_S"]):
            continue
        outcome = compute_outcome(idf, idx, pos, d)
        key = (t, d)
        if key in existing_keys:
            stored = existing[(existing.ticker == t) & (existing.date == d)].iloc[0]
            for f in ["composite", "decline_from_high10d_pct", "ret_1d"]:
                if abs(stored[f] - decision[f]) > 1e-6:
                    mismatch_warnings.append(f"MISMATCH {t} {d.date()} field={f} stored={stored[f]:.6f} "
                                                f"recomputed={decision[f]:.6f} -- NOT overwritten, investigate")
            for f in ["is_W", "is_S"]:
                if bool(stored[f]) != decision[f]:
                    mismatch_warnings.append(f"MISMATCH {t} {d.date()} field={f} stored={stored[f]} "
                                                f"recomputed={decision[f]} -- NOT overwritten, investigate")
            updated_outcomes[key] = outcome
        else:
            prev_date_membership = day_membership.get(oos_dates[oos_dates.index(d) - 1], {}) if oos_dates.index(d) > 0 else None
            if prev_date_membership is not None:
                was_w, was_s = prev_date_membership.get(t, (False, False))
            else:
                was_w, was_s = (t in seed_W), (t in seed_S)
            persistence = "persistent" if ((decision["is_W"] and was_w) or (decision["is_S"] and was_s)) else "new"
            new_rows.append(dict(ticker=t, date=d, run_date=TODAY, persistence=persistence, **decision, **outcome))

if mismatch_warnings:
    print(f"\n{'!'*100}\n{len(mismatch_warnings)} DECISION-FIELD MISMATCH(ES) DETECTED -- stored values NOT "
          f"overwritten, per the append-only design. Investigate before trusting either the old or new value:")
    for w in mismatch_warnings[:20]:
        print("  " + w)
    print("!" * 100)
else:
    print("\nIntegrity check on all pre-existing rows: 0 mismatches (decision fields perfectly reproducible).")

# Apply outcome updates to existing rows (this IS supposed to change as more days resolve)
if len(existing) and updated_outcomes:
    for (t, d), outcome in updated_outcomes.items():
        mask = (existing.ticker == t) & (existing.date == d)
        for f, v in outcome.items():
            existing.loc[mask, f] = v

if len(existing):
    candidates = pd.concat([existing, pd.DataFrame(new_rows)], ignore_index=True) if new_rows else existing
else:
    candidates = pd.DataFrame(new_rows)
candidates.to_csv(CANDIDATES_FILE, index=False)
print(f"\nSaved {CANDIDATES_FILE}: {len(candidates)} total rows ({len(new_rows)} newly added this run, "
      f"{len(updated_outcomes)} existing rows had outcome fields refreshed)")

# ---------------------------------------------------------------------------
# REPORTING (D1/D2 explicitly labeled PARTIAL/NOT-FOR-EVALUATION throughout)
# ---------------------------------------------------------------------------
print(f"\n{'='*115}\nCG3 STATUS -- accumulating, not yet at a checkpoint (target: ~20-30 D3-resolved OOS dates)\n{'='*115}")
for d in oos_dates:
    day = candidates[candidates.date == d]
    w_day, s_day = day[day.is_W], day[day.is_S]
    d3_n = day.max_return_d3.notna().sum()
    print(f"\n{d.date()}: W={len(w_day)} ({(w_day.persistence=='new').sum()} new/{(w_day.persistence=='persistent').sum()} persistent)  "
          f"S={len(s_day)} ({(s_day.persistence=='new').sum()} new/{(s_day.persistence=='persistent').sum()} persistent)  "
          f"D3-resolved candidates on this date: {d3_n}")
    for label, df in [("W", w_day), ("S", s_day)]:
        for k in ["d1", "d2"]:
            col = f"max_return_{k}"
            resolved = df[col].notna()
            if resolved.any():
                print(f"    [PARTIAL/NOT-FOR-EVALUATION] {label} {k.upper()} MFE (n={resolved.sum()}): "
                      f"median={df.loc[resolved, col].median():+.2f}")
        d3col = df.max_return_d3
        if d3col.notna().any():
            print(f"    [D3 -- THE REAL OUTCOME METRIC] {label} D3 MFE (n={d3col.notna().sum()}): "
                  f"median={d3col.dropna().median():+.2f}")
        else:
            print(f"    {label} D3: still PENDING")

n_d3_resolved_dates = candidates[candidates.max_return_d3.notna()].date.nunique()
print(f"\n{'='*115}\nCHECKPOINT PROGRESS: {n_d3_resolved_dates} of {len(oos_dates)} OOS dates have >=1 D3-resolved "
      f"candidate. Critic's target for a real review: ~20-30 D3-resolved dates, several hundred W events, "
      f"several thousand S events. NOT THERE YET -- keep accumulating, re-run after each fetch_prices.py update, "
      f"do not act on partial numbers.\n{'='*115}")

print("\nDONE")
