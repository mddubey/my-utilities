# EMAPB — Theory-First Specification v1.0

**Status: Draft for conceptual agreement. Not yet implemented, not yet backtested.**

This document exists because the project's prior approach built its own ad hoc definitions of
"advance," "pullback," and "base," tested them with data, and patched them whenever a chart
exposed a problem. That put the conceptual burden on manual chart review and produced a sequence
of retroactive fixes (same-day-peak bug, position-blocking, wick-vs-close, no-bullish-candle,
box_high vs peak_high, and now the A-day-Low-as-base-floor issue) rather than a setup defined
correctly from the start. This spec reverses the order: agree on the theory, write it down
precisely, implement it once, and only then test it.

**Governing framework**: classical continuation-base theory (O'Neil-style completed base + pivot
breakout) as the primary structural model, with VCP's contraction principle used as a QUALITY
signal (evidence a base is maturing well) rather than a mandatory condition every base must meet.
Wyckoff's supply/demand framing is kept as interpretive context, not a source of additional
mechanical rules.

**Track A vs Track B, and why they're kept separate**: Track A (this document) determines whether
the mechanical implementation correctly identifies a meaningful advance, a constructive pullback,
and a genuine base. Track B (current-day EOD to next-trading-day EOD return, once a base breaks)
is retained as a descriptive outcome measure, but it is NOT evidence that Track A's definitions are
correct. A positive Track B return does not validate a structural label; a negative one does not
condemn it. Track A is judged by chart-level semantic fidelity, not by Track B's numbers.

---

## Stage A — Prior Advance

**Definition**: a material, directional upward move that establishes both (a) the context for a
continuation setup and (b) a recognizable swing-high reference level, as distinct from an arbitrary
single green candle that happens to be large.

**Rationale**: continuation-base theory requires something to continue FROM. A base without a real
prior advance in front of it is not a continuation setup under any of the three frameworks
reviewed (O'Neil, Minervini, Wyckoff) — it's just a range.

**Proposed operational test** (explicitly flagged as our own choice, not an imported number):
- The advance must produce a move that is large relative to the stock's OWN recent volatility (not
  an absolute % cutoff that's the same for a Rs50 stock and a Rs5,000 stock) — e.g., expressed as a
  multiple of the stock's own trailing ATR, not a flat percentage.
- The advance must have some persistence — more than one bar's worth of net progress — not a
  single-candle spike surrounded by flat/declining price action on both sides. A one-day move that
  immediately reverses is a candidate for Stage-A disqualification, not an automatic pass.
- Context check (descriptive, not yet a hard filter): is this a sustained multi-day move, or a
  single-day spike that an otherwise flat chart surrounds? Both may turn out to be valid, but they
  should be distinguishable in the data, not silently merged into one "A-day" concept.

**Disqualifiers**:
- A routine positive candle with no preceding or concurrent evidence of a meaningful move.
- (Open question, not yet resolved) Whether a pure one-day news-style spike with no multi-day
  follow-through should count as the SAME category of "prior advance" as a sustained move, or
  whether these need to be tracked as separate sub-populations from the start.

**Information available at decision time**: only price/volume data up to and including the
candidate advance day itself. No future peak, no future base, no future resolution.

**Explicitly NOT yet defined (do not fit this to data)**: the exact ATR-multiple or persistence
threshold. This gets decided from a principled, pre-declared choice, then frozen before any
population test — not tuned until the population looks attractive.

---

## Stage B — Pullback

**Definition**: the retracement following the prior advance, evaluated for whether it remains
consistent with continuation (constructive) or undermines the advance's own structure (invalid) —
judged against the ADVANCE and the pullback's OWN developing shape, never against a single
reference candle.

**Rationale, and the specific correction this makes**: the project's prior work treated the
A-day's own Low as a meaningful reference (clean-win vs round-trip-win was defined by whether price
closed below it) and, separately, treated a breach of the A-day's Low during base formation as
something to investigate as an exclusion rule. Both of those made the same category error: the
A-day Low is a byproduct of where the advance happened to end one particular day, not a structural
floor of the base that forms afterward. A pullback can legitimately breach it and still build a
legitimate, lower base. Conversely, a pullback that erases nearly the entire advance should not
automatically qualify just because it goes sideways for a few days afterward.

**Proposed operational test**:
- Measure retracement as a fraction of the ADVANCE's total size (peak minus the advance's own
  starting point), not as a fixed level breach.
- Track the pullback's own internal shape: is it a controlled, narrowing retracement (VCP-style
  contraction, a positive quality signal) or an erratic, still-widening decline (a negative quality
  signal) — descriptive fields, not yet hard gates.
- A pullback that retraces nearly 100% of the advance is a candidate disqualifier regardless of
  what it does afterward; a pullback that stays within a smaller fraction of the advance, even if it
  dips below the A-day's own Low, is not automatically disqualified.

**Disqualifiers**:
- Retracement that erases substantially all of the measured advance (exact fraction: open,
  pre-declare before testing, do not fit to data).
- Repeated failure to stabilize (an open-ended decline with no base ever forming) — this is really
  the boundary between Stage B and "no base forms at all," handled by Stage C's own completion
  test, not invented here as a separate rule.

**Information available at decision time**: price/volume data up to and including each day of the
pullback as it unfolds. The pullback's eventual full depth is NOT knowable until it's over —
descriptive fields that use the full pullback (e.g., max retracement) are outcome-only, never
inputs to a live decision at the time.

**Explicitly NOT yet defined**: the exact retracement-fraction disqualifier, and the precise
quantitative shape of "controlled narrowing" vs "erratic decline." Both are open, to be set from
logic before any test.

---

## Stage C — Base

**Definition**: a coherent price range that forms after the pullback stabilizes, with an
identifiable upper boundary (resistance/pivot) and lower boundary (support), showing enough price
development to be distinguished from a single pause — not a box drawn around whatever candles
happen to precede a later breakout.

**Rationale**: this is the stage prior work got least rigorous about — "3 days of not making a new
low" was treated as sufficient confirmation. Classical base theory requires an actual, bounded
range with real structure, and VCP treats narrowing/contracting ranges as a specific quality signal
(not a requirement every base must meet, per the earlier design choice to use the classical model
as primary and VCP's contraction idea as a secondary quality signal, not a strict filter).

**Proposed operational test**:
- Upper boundary = the base's own confirmed High across its formation window (this part survives
  from the existing box_high fix — already correctly anchored to the base's own range, not the
  episode's original peak).
- Lower boundary = the base's own confirmed Low across the SAME formation window, computed
  consistently with the upper boundary (same window, same candle-attribute convention) — this is
  the piece that needs rebuilding, since the current `box_low` is actually a closing-price
  stabilization reference computed from a day BEFORE the base window even starts, not the base's
  own range floor. Needs to be redefined so `box_high` and `box_low` are symmetric: both computed
  from the same window, on the same price convention (wick-based range boundary, consistent with
  `box_high` already being `box_slice.High.max()`).
- Minimum duration and maximum width: open (per O'Neil/Minervini, bases need "enough price
  development" but the exact day-count and width aren't a universal law — pre-declare a specific
  choice before testing, don't fit it).
- Contraction (narrowing range/volume as the base matures) recorded as a descriptive quality
  signal, not a pass/fail gate, consistent with using the classical model as primary.

**Disqualifiers**:
- A "base" that's really just an open-ended decline with no real range ever forming (no stable
  boundary visible).
- (Open question) How many instances of testing-and-holding the lower boundary should be required
  before calling it a real support level, vs. accepting a base that's only been tested once.

**Information available at decision time**: the base's boundaries can only be stated once the base
is actually confirmed (i.e., after some minimum stabilization period) — this matches the existing
`BOX_CONFIRM_DAYS` discipline (no claiming a base exists before it's survived its own confirmation
window). Still fully decision-time-safe: nothing from after the base's own window is used.

**Explicitly NOT yet defined**: exact minimum/maximum duration, maximum acceptable range width, and
how many lower-boundary tests count as real support. Pre-declare before testing.

---

## Stage D — Breakout / Resumption

**Definition**: price resolves the base by closing beyond the base's own upper boundary
(resistance/pivot) — a completed candle close beyond the level, never an intrabar wick that closes
back inside.

**Rationale**: this part is already correctly specified in the existing pipeline (the
`Close > box_high` convention, fixed from the earlier `peak_high` bug, and the close-over-wick
discipline from the TCS catch) — retained as-is, not reopened.

**What changes**: the pivot must be the FRESHLY-confirmed base's own resistance (Stage C's output),
not a stale level from an earlier, already-resolved episode. This is where the "fresh vs.
continuation/re-trigger" distinction from the chart audit (LLOYDSENGG, FORCEMOT) actually belongs —
not as a population-exclusion afterthought (RQ-18, tested narrowly and closed), but as a direct
consequence of correctly re-deriving Stage A/B/C for each candidate: if Stage A's "prior advance"
test is done properly, a stale re-trigger of an already-resolved move should either (a) fail to
register as a fresh Stage A advance at all, or (b) register as its own, separate, later episode with
its own base — not silently inherit an earlier, unrelated breakout's characteristics.

**Volume at resolution**: contextual evidence (is there real participation at the moment of
resolution), assessed across the base-to-resolution transition — not a single inherited ratio gate.
Exact formalization: open, not yet defined, not to be invented just to replace the old 1.5x gate
with a different arbitrary number.

**Information available at decision time**: the resolution event (Close > confirmed base's High) is
knowable the moment that candle closes — same discipline as the existing pipeline.

---

## Stage E — Entry and Risk (FROZEN PLACEHOLDER, OUT OF SCOPE FOR THIS PHASE)

Per explicit instruction: entry/exit/stop/sizing are personal decisions (schedule, risk appetite)
to be made LAST, after Stages A-D are trusted. For this phase:

- **Entry**: 3pm on the qualifying resumption day (unchanged from existing RQ-EMAPB-3PM-01
  convention).
- **Exit**: 3pm the next trading day (D1).
- **Stop / position sizing / profit target / performance-based filtering of Stages A-D**: explicitly
  OUT OF SCOPE. Win rate, returns, and MFE/MAE are NOT used to decide which chart structures
  qualify as a valid advance/pullback/base. This is Track B, descriptive only.

---

## What this specification explicitly rejects (carried over, still binding)

| Shortcut | Why it's inadequate |
|---|---|
| Any green bar above a volume threshold | Doesn't establish a meaningful prior advance |
| Any 3-day sideways patch | Duration alone doesn't establish a valid base |
| Original breakout-day Low as the universal base floor | Confuses a reference candle with the base's actual support |
| A wick above resistance | Doesn't confirm price accepted the higher level |
| A fixed volume multiple inherited without re-justification | Hasn't earned that status; needs its own grounding |
| Drawing the base after seeing the outcome | Introduces hindsight into the setup definition |
| Adding a filter because one chart looked wrong | Overfitting; conceptual defects go back to the spec, not a patch |

## Process from here

1. This document gets reviewed (critic: ambiguity questions and spec-violation verdicts only, no
   performance judgments; user: does this match the trade you actually mean).
2. Resolve the "explicitly NOT yet defined" items in each stage from logic, pre-declared, before
   any implementation.
3. Implement the complete spec ONCE as a single coherent population builder.
4. One representative chart audit — semantic fidelity only (does the code identify the intended
   structure). Conceptual defects revise this document, not ad hoc code exceptions.
5. Freeze the population. Only then compute Track B (EOD-to-next-EOD return) as a descriptive
   number, not a validation of Stages A-D.
