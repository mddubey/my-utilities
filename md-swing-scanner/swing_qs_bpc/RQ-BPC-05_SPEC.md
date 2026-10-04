# RQ-BPC-05 — Volume-Confirmed A Population Audit

Frozen from the critic's pre-registration, 2026-10-04 (verdict on the reopen request for
PARKING_LOT #9). Paraphrased from the critic's own wording; nothing here is improvised.

## Objective

Determine whether the BPC holds-above-A population (RQ-QS-04A/04B/04C) behaves differently
when A is restricted to a genuine, volume-confirmed breakout, instead of any ordinary
swing-high clear.

## Status of the prior work (critic's framing, adopted)

04B/04C's "close the branch" verdict is **superseded / population-invalidated**, not erased.
It remains a valid, correct result for the population it actually tested (unconfirmed
price-clears) — it is not valid evidence against the population BPC's theory is actually
about (volume-confirmed breakouts). This was not a deliberate, reasoned exclusion of volume
— the record shows "breakout volume 40-50%+ above average" was already on the critic's own
2026-09-29 literature checklist, marked "later," and the branch moved to 04A/04B/04C without
it. That is a legitimate reason to reopen, independent of whatever the literature says.

## Population — change ONLY the A qualification

Same `03A -> 04A -> 04B -> 04C` pipeline, same universe (`nifty500_universe.csv`), same
lookbacks (10/20/40), same everything else. A must clear the existing v0.1 gate **and**
satisfy a predeclared breakout-day volume requirement.

**Primary volume condition (pre-registered, literature-informed — NOT the 3x the hand-
inspected examples suggested):**
  A breakout-day volume >= **1.5x** trailing 10-day average volume (`vol_avg10_prior`,
  the same production field `signals.py` already defines — `Volume.shift(3).rolling(10).mean()`
  — reused as-is, not redefined).

**Diagnostic volume buckets (reported, not optimized over):** <1x, 1-1.5x, 1.5-2x, 2-3x,
>=3x. 3x is reported as a separate high-volume subgroup, never used as the gate.

## B — no volume requirement, by design

B is NOT required to have elevated volume. The hypothesis under test is "genuine demand
thrust -> controlled digestion -> continuation" — a quiet B (reduced selling pressure after
the initial event) is plausible and consistent with the theory, not a disqualifier.
B's own volume is reported observationally (vs A, vs its own 10-day average) but never
filtered on.

## New diagnostic fields (critic's addition — confirm A's volume and price event are the
SAME event, not just "some volume nearby")

For every A (corrected population, and the full unfiltered population for context):
- breakout-day volume / `vol_avg10_prior`
- preceding day's volume ratio
- subsequent day's volume ratio
- price displacement on A's own day (Close vs prior Close, %)
- distance from the most recent meaningful (60-trading-day) prior high, before A
- whether a bigger volume thrust exists in the preceding 10 trading days (catches exactly
  the failure mode found by hand: A firing on a late, secondary pop while the real
  volume-origin day sits a few days earlier)

## Re-run, same 04A/04B/04C outputs, corrected-A vs old-A side by side

Anatomy (04A: consolidation detection, holds-above-A subset), shape of the pause (04B:
duration, range width, volume during pause, duration x width matrix, B-close-above-
consolidation-high rate), and the 20-pair trajectory replay (04C) if the corrected
population is large enough to stratify meaningfully.

## Decision rule, pre-declared before any result is seen

**Reopen succeeds** (continuation hypothesis survives) if the corrected-A population shows,
materially and not from a tiny/concentrated subgroup: a recognizable pause/digestion
structure, B behaviour more consistent with controlled pullback than random poke-and-fade,
and improved B-continuation — directionally consistent with the intended BPC hypothesis.

**Reopen fails** (closes with MORE confidence than before) if the same poke-and-fade /
non-base behaviour persists even after volume-confirming A. That would be a stronger
negative than 04B/04C's original result, because it rules out the "we tested the wrong
population" explanation.

## What this does NOT do

No threshold optimization (1.5x is literature-pre-registered, not fit to the hand-inspected
examples; 3x is diagnostic only). No B volume filter. No new indicators, no stop-rule
changes, no exit optimization, no expectancy/returns until the anatomy question is answered
first (same gating discipline as the original 04 arc).
