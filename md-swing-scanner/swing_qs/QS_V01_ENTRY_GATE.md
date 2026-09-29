# QS v0.1 — Entry Gate + Readiness Report (2026-09-27)

**Status: READY FOR CONTROLLED LIVE VALIDATION.** Explicitly NOT "validated strategy"
and NOT "production-ready complete system" — entry is ready; the product is not fully
solved. Exit remains deliberately provisional (see "Exit" section below). Critic-
confirmed closing status for this research arc, 2026-09-27.

**Tomorrow's purpose, stated explicitly so it doesn't drift into another research
session**: NOT another optimization pass. The question is "does the thing we built
actually behave like the quick-continuation population we designed it to capture?" —
capture live events and their full telemetry (base quality, extension, breach timing,
RVOL at breach, immediate continuation, subsequent trajectory, options availability)
without changing the gate mid-session. If a live trade behaves badly, that becomes
validation data for the next research cycle — not a reason to patch the rule same-day.

This is the deployable output of the entire Entry Discovery phase (literature audit →
individual candidates → RVOL mechanism → bounded combination audit → this gate). It
turns the research survivors into a reproducible entry definition with explicit,
disclosed parameters — not another statistical search. Per critic's exact final
instruction: build toward readiness, not more discovery.

## What this is, and is not

- **Is**: a real, decision-time-safe entry gate (raw breakout + two filters), with
  everything else attached as telemetry, ready to observe live trades against.
- **Is not**: a finished, optimized, or backtested-to-death production system. The gate
  uses one config value (`GAP_BAD_THRESHOLD_PCT`) taken directly from the research
  population's own median — genuinely provisional, exposed as config, not claimed to be
  independently calibrated. The exit is explicitly **not** decided — see "Exit" below.

## Gate definition

```
Raw opportunity (10D/20D/40D breakout, ungated, T-1 gate, ungated_recipe)
  → base_duration computed (T-1, generalized live_checkpoint.py's _consolidation_days)
  → gap_to_trigger_pct computed (T-1, entry_price vs prior day's Close)
  → REJECT only if: base_duration == 0  AND  gap_to_trigger_pct > GAP_BAD_THRESHOLD_PCT
  → else: QS v0.1 candidate
```

**Why this specific logic, not two independent cutoffs**: the combination audit's
interaction table showed exactly ONE uniquely bad cell (no base + extended); every other
cell — including no-base-but-not-extended, and any-base-regardless-of-extension —
performed similarly well. This directly encodes the audit's own finding ("a good base
compensates for extension," "don't reject on gap alone") rather than inventing a new
rule. It is not a blanket AND of two independent thresholds.

**Config values, disclosed, not hidden**:
- `MIN_BASE_DURATION = 1` — from `base_duration`'s own research: the "0" bucket (zero
  quiet days before breakout) was categorically worse than every other bucket (1-2,
  3-5, 6+ all performed similarly to each other).
- `GAP_BAD_THRESHOLD_PCT = 2.343` (the research population's own median
  `gap_to_trigger_pct`) — reuses the exact split already validated in the interaction
  audit. **Not independently calibrated** — a placeholder pending real calibration work,
  not a claimed-optimal number.

**RVOL, breach time, R1/R2 rejection, and trajectory milestones are TELEMETRY ONLY** —
computed and attached to every candidate, never used to filter. Per critic: RVOL adds
real information but is based on only ~3.5 months of intraday data, its mechanism is
only partially understood (dominant driver is pre-breach volume buildup, entangled with
an early/mid-session timing effect), and its measured effect is mostly on tail-risk
within already-good setups rather than a clean go/no-go signal. Collect more data before
promoting it to a gate condition.

## No leakage — confirmed for every gate component

- `base_duration`: T-1 only, generalized from `live_checkpoint.py`'s
  `_consolidation_days` (same 3% tolerance constant), independently reviewed.
- `gap_to_trigger_pct`: T-1 only (`entry_price` vs prior day's Close), independently
  reviewed.
- RVOL/breach-time telemetry fields: use only information up to and including the actual
  breach bar, independently reviewed against this project's own trusted production
  breach-reconstruction code before being trusted.

## Population

| | n | % |
|---|---|---|
| Raw opportunity population (all raw 10D/20D/40D breakouts, full 5yr) | 47,458 | 100% |
| Feature-eligible (252+ days history for base_duration/gap_to_trigger) | 37,802 | 79.7% |
| **QS v0.1 candidates** (passes the gate) | **26,541** | **70.2% of feature-eligible** |
| Rejected by the gate | 11,261 | 29.8% of feature-eligible |
| — of which base_duration=0 alone (before combining with gap) | 14,030 | 37.1% |
| — of which gap>median alone (before combining with base) | 18,901 | 50.0% |

The feature-eligibility gap (47,458 → 37,802) is a **data-availability constraint**
(the earliest ~14 months of the 5-year window don't have enough prior history for
`base_duration`/`gap_to_trigger`), not a product decision — irrelevant going forward
once live, since there will always be ample history.

## Tradeability

**QS v0.1 candidates (n=26,541) vs. unfiltered feature-eligible baseline (n=37,802)**:

| | Baseline (unfiltered) | QS v0.1 (gated) |
|---|---|---|
| ≥0.25R by D5 | 75.9% | 77.4% |
| ≥0.5R by D5 | 62.5% | 65.1% |
| ≥1R by D5 | 40.3% | **43.5%** |
| ≥1R by D10 | 53.1% | **56.6%** |
| Net negative @ D10 | 49.5% | 49.6% |

**Honest read**: the gate meaningfully improves *reachability* (+3.2-3.5pp on ≥1R at
both D5 and D10) while removing 29.8% of the population — but does **not** improve
loss-avoidance (net-negative @ D10 is essentially unchanged, 49.5%→49.6%). This matches
everything found this session: the gate filters out weaker-opportunity setups, it does
not somehow avoid losses that would otherwise happen. Do not oversell this as "safer" —
it is "more likely to work," which is a different claim.

- Median days-to-1R (among reachers): 3
- Win composition by D10 (of the whole gated population, not just reachers): **56.6%
  real win (≥1R)**, 27.1% tiny win (0.25-1R), 16.2% no meaningful win yet
- S1b initial risk distribution: median 3.60%, mean 3.94%, p90 6.03%, p99 9.91%
- Pathological-risk count (>p99, i.e. >9.91% initial risk): 266 events (1.00%) — a small,
  expected tail, not a red flag requiring a new filter

## Robustness — annual split (QS v0.1 candidates)

| Year | n | ≥1R by D5 | ≥1R by D10 | Net negative @ D10 |
|---|---|---|---|---|
| 2022 | 1,901 | 41.4% | 53.7% | 56.1% |
| 2023 | 7,448 | 46.9% | 62.2% | 40.5% |
| 2024 | 6,494 | 45.0% | 58.1% | 50.0% |
| 2025 | 6,346 | 40.2% | 52.4% | 54.6% |
| 2026 (partial) | 4,352 | 41.4% | 52.3% | 54.4% |

**Real, disclosed regime effect**: 2023 was the strongest year on every metric; 2025-26
show a real, consistent step-down (lower reach-rate, higher net-negative) — consistent
with the "something changed after 2024" concern raised earlier this weekend. The gate
does not eliminate this — it's a market-regime effect sitting underneath the entry
definition, not a flaw in the gate itself. Worth monitoring, not something this gate is
expected to fix.

**RVOL is explicitly NOT part of this annual split** — it only has data for 2026
(3.5 months), can't be evaluated across years, and is telemetry-only regardless.

## Execution — F&O eligibility (descriptive only, not a filter)

- QS v0.1 candidates that are F&O eligible: 13,960 (52.6%)
- QS v0.1 candidates NOT F&O eligible (stock-only, still a fully valid QS trade):
  12,581 (47.4%)

The underlying stock trade remains valid regardless of options eligibility. Options are
an execution/product layer on top of a valid QS candidate, never a requirement for one
— consistent with the standing "options allowed, not forced" decision from earlier this
session.

## Live telemetry — what to capture for every real QS candidate going forward

For every trade that fires against this gate, capture (not filter on):
- Breach timestamp (exact time of the intraday trigger touch)
- RVOL-at-breach (and its two decomposed components: pre-breach volume, breach-bar-only
  volume)
- Breach price
- S1b initial stop (prior trading day's Low) and `initial_risk_pct`
- `base_duration`, `gap_to_trigger_pct` (the two gate inputs, for post-hoc review)
- R1/R2 context (same-day hold/reject observation, per the earlier post-entry finding —
  telemetry only, no action)
- Subsequent trajectory (day1-15 raw OHLC, matching `qs_stage0`'s existing convention)

**Live trades become validation data, not a reason to modify the gate intraday.**

## Exit — explicitly, deliberately provisional

**No production exit is decided.** Per this session's own Exit Discovery closure: every
tested exit rule (EX1/EX2/EX3, 10 candidates spanning Failure and Momentum families)
underperformed simply holding to the observation window's end. Bolting one of those
rejected rules onto QS v0.1 now, just to make the product look complete, would
contradict that finding. The 15-day trajectory/observation framework remains exactly
that — an observation layer for measuring what happens, not a production exit
mechanism. This is a deliberate, disclosed gap, not an oversight.

## Standing disposition of every candidate tested this weekend

| Status | Items |
|---|---|
| **In the gate** | `base_duration` (≥1), `gap_to_trigger_pct` (conditional on base_duration) |
| **Telemetry, not gate** | RVOL-at-breach (+ decomposition), breach time, R1/R2 same-day rejection, S1b risk/ADR multiple |
| **Interesting, weaker than literature implies, not in gate** | `prior_advance_63d`, `dist_52w_high_t1`, `rs_rating_t1` |
| **Descriptive only (same-day, not live-IOC-safe)** | `close_location_SAMEDAY`, `body_pct_SAMEDAY`, `range_expansion_SAMEDAY`, `eod_volume_ratio_SAMEDAY` |
| **No evidence (proxy issue, not concept falsification)** | `base_tightness`, structural overhead (swing-high proxy), `gap_open_pct_SAMEDAY` |
| **Closed/redundant** | R1/R2 entry proximity (subsumed by `gap_to_trigger_pct`) |
| **Closed (exit discovery)** | E1A (yesterday's-low trail), Immediate Failure, F1+non-reclaim, F1+MA1, Giveback-50%, fixed time caps 5/7/10 — signals valid, exit policies rejected |

## Architecture pivot (2026-09-27, post-readiness) — read before extending this gate further

Tonight's live-trading questions ("is this good enough to trade," "what if I exit at
2R," "are we entering too casually") led to a real architectural correction, agreed
with critic. **Do not extend this document's gate to try to make the whole 47k-event
research population profitable under one exit rule.** Instead:

- **QS is a narrow, short-duration product.** A candidate either shows a genuine
  continuation burst within ~2-3 sessions or it doesn't — trades that take longer are
  not automatically bad, they are potentially **not QS**. Explicit guardrail: QS must
  never earn its way into a longer hold merely because it hasn't failed yet (that
  exact drift — D3 unresolved→wait, D5→wait, D8→wear, D15→BC v2 — is the failure mode
  this guardrail exists to prevent).
- **The 47,458-event research population becomes a permanent EOD shadow population**,
  not something this gate needs to "solve." Track what the gate rejects and what
  happens to it. Only touch the gate when the shadow population shows a *repeatable
  class* of missed quick-blasts — never because some rejected trades eventually made
  money (that's noise, not evidence).
- **The ADR-relative whipsaw finding (stop tight vs. a stock's own ADR → any
  tightening mechanism gets swamped by ordinary noise, 72% whipsaw in the tightest
  quartile vs 37% in the widest) does NOT mean "widen S1b."** It means: a trade where
  the stop is already tight relative to that stock's own noise may not belong in a
  short-duration product at all. Exclusion, not stop-sizing.
- **Labels need to change too** — tiny winners are not the product target. New scheme
  for the next research pass: BLAST (≥2R by day 5), DRIFT (0.25-2R by day 10, not
  Blast), FAILURE (stop first or never clears 0.25R by day 5). Today's "43.5% reach 1R
  by day 5" headline conflates real Blasts with Drift — needs to be re-cut this way
  before it's trusted as a QS-relevant number.

**Next session's exact, bounded scope (per critic, do not expand)**: one Feature
Battle pass — Blast vs Drift vs Failure, across base_duration, gap_to_trigger,
EMA34 persistence (already have data) plus EMA21 distance, prior 20-day advance,
RS rating, volume dry-up (T-1), and one PROPER base-tightness/contraction proxy (the
earlier ATR-ratio version failed — try consecutive-days-inside-range instead,
literature-grounded, not another arbitrary formula). One output table, no thresholds,
no filtering, no promotion — just identify which features separate Blast from BOTH
Drift and Failure. Five falsifiable predictions were written down in advance (see
FINDINGS.md's "Exit Discovery reopened" section and the critic thread) — check the
result against them explicitly, don't just report numbers.

**The eventual daily deliverable is a running dashboard (`qs_dashboard.py`), not
another report** — morning candidate list (top 4-8 names by priority score, not a
binary pass list) + EOD shadow report + D1-D3 trajectory log per live candidate.
RVOL/breach-timing/R1-R2/ADR-compatibility become a priority SCORE, never a hard
filter, until ~20-30 real live trades exist to evaluate them against.

## Next steps, explicitly not started here

- Calibrate `GAP_BAD_THRESHOLD_PCT` properly (currently a placeholder = research median).
- Collect more intraday history before any RVOL promotion decision.
- Live observation of real QS v0.1 candidates — the actual next action.
- No exit engineering reopened without new evidence.
