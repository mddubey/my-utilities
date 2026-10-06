# RQ-EMAPB-03 — Visual Base Audit (critic-specified, 2026-10-04)

Full critic design kept verbatim in the session log. Core ask: before closing the broader
impulse -> pullback -> base -> continuation hypothesis (three mechanical confirmation
definitions have now failed — pin bar, hold+expand, "contained"), build a blinded, 30-episode
chart audit so the user can manually judge whether a recognizable base actually forms,
independent of any mechanical rule, and whether EMA8 appears meaningfully involved without
forcing it into the definition. This is discovery/audit, not strategy optimization — no
parameter sweep, no new indicators, no threshold tuning.

## Implementation choices (surfaced explicitly, not silent)

- **Population**: same volume-confirmed A (10-day lookback, >=1.5x `vol_avg10_prior`, 1H bars,
  2023-10-23 onward) — unchanged from EMAPB-01/02. No new filter.
- **Outcome label, zero new parameters**: CONTINUATION = price makes a new high above the
  original impulse peak (`swing_high`) at any point after the pullback starts, within the
  70-bar window. NON-CONTINUATION = it never does. Reuses only fields already computed
  (`swing_high`, `pullback_start`), no invented threshold.
- **Sample**: 15 continuation + 15 non-continuation, drawn uniformly at random (seed 2026,
  reproducible) from all eligible A's, then shuffled together so episode order doesn't reveal
  the outcome group.
- **Blind stopping point, fixed and predeclared (not hindsight-chosen)**: `peak_i + 14 bars`
  (~2 trading days past the peak) — the same rule applied identically to every episode
  regardless of its eventual outcome.
- **Chart contents**: real 1H candles (`data/intraday_60m/`), volume subplot, EMA8 (solid) and
  EMA21 (dashed, context only, not a candidate rule), Fib 38.2/50/61.8% + retest levels as
  reference lines only, A and peak marked with vertical guides.
- **Two versions per episode**: blinded (stops at the predeclared cutoff) for the initial
  review, and full (extended through the end of the window) held back separately for reveal
  after the visual classification is complete.
- **Metadata** (ticker, A date/price, peak date/price, blind-stop date) kept separate from
  **outcomes** (D1 open/peak/close %, continuation label) — two different files, so the
  initial review stays genuinely blinded.

## Deliverables

`swing_qs_emapb/visual_audit/`: `ep01_blinded.png` .. `ep30_blinded.png` (for review now),
`ep01_full.png` .. `ep30_full.png` (held back), `episode_metadata.csv` (no outcome),
`episode_outcomes_DO_NOT_OPEN_YET.csv` (separate, for after review).
