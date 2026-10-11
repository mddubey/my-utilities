# EMAPB Stage 0 — Final Consolidated Specification

**Status: proposed for final sign-off. Not yet implemented.**

## 1. Pivot construction and chronological integrity

**Key fact that resolves this entire section**: with symmetric K=2 confirmation applied
uniformly to both swing types, `confirmation_index = pivot_index + 2` for every pivot,
regardless of type. This is a fixed additive shift, which is a strictly order-preserving
transformation. Therefore **confirmation order and pivot-date order are always identical** — a
later-pivot-dated swing can never confirm before an earlier-pivot-dated swing, of either type.
This is not an assumption; it follows directly from using the same K for both swing types.

Consequences, answering each sub-question directly:
- The list is built by processing pivots in confirmation order (the natural order they become
  knowable during a forward scan). Because confirmation order ≡ pivot-date order, this is
  simultaneously pivot-date order — there is no case where these two orderings could conflict.
- A same-type replacement never creates a chronology conflict: any new confirmation necessarily
  has a later pivot date AND later confirmation date than everything already in the list, because
  we only ever process events in increasing confirmation order.
- The four pivots establishing Stage 0 have strictly increasing pivot dates and strictly
  increasing confirmation dates automatically — this is not separately enforced, it falls out of
  the construction.
- A pivot confirming after another pivot's confirmation despite an earlier swing date **cannot
  occur** under fixed, equal K — proven above.
- A previously established Stage 0 state is never rewritten by later confirmations: establishment
  is evaluated and recorded exactly once, at the moment the 4th alternating pivot is appended.
  Nothing afterward re-examines or recomputes that decision.

**Edge case, stated explicitly**: if a single bar confirms as both a swing low and swing high
simultaneously (a wide-range reversal day satisfying both the K=2 low and high conditions), the
Low event is processed first, then the High event, as a fixed, documented tie-break. This never
causes ambiguity since both still occupy the same confirmation index and the choice only affects
which becomes the tail first within that single bar's processing.

## 2. Stage 0 establishment

Retained: `L1 → H1 → L2 → H2` with **L2 > L1 and H2 > H1, strict inequality**. An exact tie
(L2 == L1 or H2 == H1) does not establish — the candidate simply fails to qualify at that append;
scanning continues and the tail remains eligible for further replacement or extension.

**Exact establishment timestamp**: the confirmation date of H2 — the moment the 4th alternating,
strictly-ascending pivot is appended. Stage 0 cannot be active before this date under any
circumstance.

**Missing/duplicate pivots**: cannot arise. Each bar index is evaluated for swing-low and
swing-high status exactly once in the scan (deterministic boolean per index), so there is no
mechanism for a duplicate confirmation event. "Missing" pivots simply mean Stage 0 has not yet
accumulated 4 qualifying points — not an error state, just "not yet established."

## 3. Invalidation and defended-low semantics — full state machine

**State variables**: `defended_low`, `reference_high` (both initialized from L2/H2 at
establishment), `pending_warning` (None, or a snapshot taken at the moment a lower high locks).

**IMPLEMENTATION CHOICE, stated explicitly**: once `pending_warning` is active, `defended_low`
stops updating entirely (frozen at whatever value was true when the warning was created) until the
warning resolves (cleared by a fresh higher high, or fired as invalidation). This keeps the pending
state's trigger level unambiguous — it is always exactly the snapshot, with no possibility of the
live reference silently drifting away from what's being watched.

**Per-bar processing order** (critical for the temporal-integrity requirement): on each bar, in
this fixed order:
1. **First**, if `pending_warning` is active and today's Close < the snapshotted level: fire
   invalidation. Effective date = today. This check always runs before anything else on the bar.
2. **Then**, process any pivot-lock events completing on this bar (a pivot 2 bars prior becoming
   non-tail): update `defended_low`/`reference_high`/`pending_warning` per the rules below.

This ordering guarantees a same-day pivot lock can never retroactively rescue a close-based
invalidation that the same bar's own close already triggered.

**Lock-event rules** (a pivot locks when an opposite-type pivot is appended after it):
- Locked Low, price > `defended_low` (strict): `defended_low` updates to this value. (Only while
  no warning is pending — see freeze rule above.)
- Locked Low, price ≤ `defended_low`: no change. Does not itself trigger anything.
- Locked High, price > `reference_high` (strict): `reference_high` updates; if `pending_warning`
  was active, it is cleared (set to None) — a genuine new higher high supersedes an earlier
  lower-high warning.
- Locked High, price < `reference_high` (strict): this **is** the lower-high event. Set
  `pending_warning` = (this confirmation date, current `defended_low` value). `reference_high`
  unchanged.
- Locked High, price == `reference_high`: no change (exact retest, neither a new high nor a lower
  high).

**Worked example — warning that resolves into invalidation (later high does NOT reverse it)**:

| event | type | price | effect |
|---|---|---|---|
| t1 | L1 confirms | 100 | list=[L1] |
| t2 | H1 confirms | 120 | locks L1; list=[L1,H1] |
| t3 | L2 confirms | 110 (>100) | locks H1; list=[...,L2] |
| t4 | H2 confirms | 130 (>120) | **Stage 0 ESTABLISHED**, defended_low=110, reference_high=130 |
| t5 | new Low locks | 115 (>110) | defended_low -> 115 |
| t6 | new High locks | 125 (<130) | **lower high** -> pending_warning=(t6, 115) |
| t7 | Close = 112 (<115) | — | **INVALIDATION fires at t7** |
| t8 | new High would confirm | 140 (>130) | **irrelevant** — cycle already ended at t7, nothing to clear |

**Worked example — warning that clears (trend continues)**: identical through t6. Instead of a
close breach, at t7' a new High locks at 135 (> reference_high 130) **before** any close below 115
occurs. `pending_warning` clears, `reference_high` -> 135, trend continues uninvalidated.

## 4. Setup lifecycle when Stage 0 invalidates

| Setup state at invalidation | Effect |
|---|---|
| Active advance/pullback, no base yet | Historical advance record preserved; this candidate is terminated, cannot proceed to a base |
| Candidate base still forming | Preserved on record; this candidate cannot proceed to confirmation |
| Confirmed base, not yet broken | Preserved on record; disqualified from producing a qualifying breakout going forward |
| Completed breakout + Track B outcome | Immutable — never touched, never retroactively erased |

Invalidated, unbroken setups can never later produce a qualifying breakout under the old trend
state, by construction — the state machine has already moved past Stage 0 ESTABLISHED for that
cycle.

## 5. Fresh-cycle eligibility — explicit boundary (the one genuinely open problem, now resolved)

The earlier claim ("old pivots are just further back in the list") was insufficient, and the
critic's concern is concretely real: a post-invalidation recovery low that happens to land above
an *old*, pre-invalidation low (without that old low itself having been the one broken) could
combine with a subsequent new high to falsely re-establish Stage 0 using one pre-invalidation
pivot and one post-invalidation pivot.

**Resolution: upon invalidation, the entire pivot list is discarded.** A pivot is eligible to enter
the fresh list **only if its pivot date (the swing's own bar index, not its confirmation date) is
strictly after the invalidation date.** Any pivot whose swing bar occurred at or before
invalidation is permanently ineligible for the new cycle, even if its confirmation lands after
invalidation (it belongs temporally to the old regime's price action, even though it wasn't known
to be a pivot until later) — it may still be logged for audit purposes, but never used to build the
new L1/H1/L2/H2 chain.

This guarantees no mixing of old-cycle and new-cycle structure, requires zero arbitrary waiting
period (the very next eligible pivot after the boundary can start accumulating immediately), and
is fully auditable (every discarded pivot is logged with a reason).

## 6. State-transition table

| From | Trigger | To | Effective date | Setup impact |
|---|---|---|---|---|
| NO_TREND | 4th alternating pivot confirms, strictly ascending | ESTABLISHED | H2 confirmation date | Stage A eligible from here |
| ESTABLISHED | locked Low > defended_low | ESTABLISHED | lock date | defended_low updates |
| ESTABLISHED | locked High > reference_high | ESTABLISHED | lock date | reference_high updates |
| ESTABLISHED | locked High < reference_high | PENDING_WARNING | lock date | snapshot taken, no setup impact yet |
| PENDING_WARNING | locked High > reference_high (no prior close breach) | ESTABLISHED | lock date | warning cleared, reference_high updates |
| PENDING_WARNING | Close < snapshot | NO_TREND (via INVALIDATED) | close date | per section 4 table; pivot list reset per section 5 |

Every transition is logged with: trigger event, evidence used, effective date, and resulting
impact on any in-flight setup — nothing is silently overwritten.

## Explicit unresolved questions: none remaining that block implementation.

This specification is internally consistent, uses only information knowable at each stated
effective date, and contains no lookahead. Requesting sign-off to implement once, followed by the
single agreed chart audit for semantic fidelity.
