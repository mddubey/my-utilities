# EMAPB Stage 0 — Final Consolidated Specification (Revision 2)

**Status: proposed for final sign-off. Not yet implemented.** This revision resolves the two
contradictions found in the prior draft: the same-bar dual-pivot tie-break, and establishment
depending on a still-replaceable pivot.

## 1. Pivot construction and chronological integrity

**Key fact**: with symmetric K=2 confirmation applied uniformly to both swing types,
`confirmation_index = pivot_index + 2` for every pivot, regardless of type — a fixed, strictly
order-preserving shift. Therefore **confirmation order and pivot-date order are always identical**
for any two pivots of *different* underlying bars. This proof is unchanged from the prior revision
and still holds.

**Defect found and fixed — the same-bar dual-pivot case**: if a single bar satisfies both the
swing-low and swing-high conditions simultaneously, it has identical pivot date AND confirmation
date for both events. No processing order (Low-first, High-first, or any other) can make these
two events "strictly increasing" relative to each other, because they are not increasing at all —
they are the same instant. Inventing an order between them was the error.

**Resolution: dual-pivot bars are excluded entirely from Stage 0 structural sequence
construction.** Concretely: if bar `i` independently satisfies both the swing-low and swing-high
conditions, **neither event is added to the pivot list, and neither can update `defended_low` or
`reference_high`.** The bar is logged in the audit trail as `dual_pivot_excluded` with its date, for
transparency — but it has zero effect on Stage 0 state. Because excluded events never enter the
pivot list, the "strictly increasing pivot dates" requirement is never violated — there is nothing
to order, because there is nothing in the list to order.

## 2. Stage 0 establishment

**Defect found**: the prior draft declared Stage 0 established at the moment H2 (the 4th pivot)
*appends* — but an appended pivot is the new list tail, which remains replaceable by a later
same-type pivot (per the construction rule in the original spec). This created a real
contradiction: an immutable "established" record whose defining pivot (H2) could still change
underneath it.

**Resolution (Option A — committed structure, chosen because it requires no new concept, just a
later, correctly-timed trigger)**: **Stage 0 establishes only when H2 itself becomes LOCKED** — i.e.,
when the *next* opposite-type pivot (a new Low) is appended after H2, which is the same lock
mechanism already used everywhere else in this spec. At that point H2 can never change again, so
there is no possibility of the established record later disagreeing with the pivot list.

This means establishment requires **five** confirmed pivots in total: `L1 → H1 → L2 → H2 → (L3
locks H2)`. This is not a new waiting period invented for convenience — it is the minimum
additional evidence required for H2 to be trustworthy at all, a direct and unavoidable consequence
of the existing lock rule, not an extra filter layered on top of it.

**Exact establishment timestamp**: the confirmation date of the pivot that locks H2 (i.e., L3's
confirmation date), not H2's own confirmation date.

**Values used**: `defended_low` = L2's price, `reference_high` = H2's price — both already
permanently locked by this point (L2 was locked back when H2 originally appended; H2 is locked now
by L3's append). Neither can ever be superseded after this.

**L3 itself** is simply the new tail at this moment — provisional, not yet locked, and does not
itself update any reference until *it* is later locked by the next opposite-type pivot, following
the same rule uniformly applied throughout.

**Strict inequality, equality, missing/duplicate pivots**: unchanged from the prior revision — L2
> L1 and H2 > H1 strictly; a tie does not establish; duplicate/missing pivot confirmations cannot
arise given the deterministic, single-pass construction.

## 3. Invalidation and defended-low semantics — full state machine (unchanged mechanics, updated timing)

State variables, freeze rule, per-bar processing order (close-check before pivot-lock processing),
and all five lock-event rules are **unchanged** from the prior revision — none of that was in
question. Only the establishment trigger (section 2) changed; everything downstream of
establishment is identical.

**Worked example — corrected for the 5-pivot establishment, dual-pivot exclusion shown**:

| event | type | price | effect |
|---|---|---|---|
| t1 | L1 confirms | 100 | append (list empty); list=[L1] |
| t2 | H1 confirms | 120 | different type -> append, locks L1; list=[L1,H1] |
| t2a | (bar also qualifies as a swing low) | — | **dual-pivot bar -- excluded entirely, logged, no effect** |
| t3 | L2 confirms | 110 | different type -> append, locks H1; list=[L1,H1,L2] |
| t4 | H2 confirms | 130 (>120) | different type -> append, locks L2; list=[L1,H1,L2,H2]. **H2 is the tail -- still provisional, NOT yet established** |
| t5 | L3 confirms | 115 | different type -> append, **locks H2**; list=[...,L3]. Check the four locked pivots ending at H2: L1=100,H1=120,L2=110,H2=130 -> L2>L1 and H2>H1 both hold -> **STAGE 0 ESTABLISHED, effective date = t5**. defended_low=110, reference_high=130 |
| t6 | H3 confirms | 125 | different type -> append, locks L3 (115). Since L3 is now locked and 115>110: **defended_low -> 115**. H3 is the new tail, provisional |
| t7 | L4 confirms | 112 | different type -> append, locks H3 (125). Since H3 is now locked and 125<130 (reference_high): **lower high -> pending_warning = (t7, 115)** |
| t8 | Close = 112 | — | 112 < snapshot (115) -> **INVALIDATION fires at t8** |
| t9 | a new High would later confirm at 140 | — | **irrelevant** -- the cycle already ended at t8; there is nothing left to clear |

**Clearing variant**: identical through t7's warning. If instead, before any close below 115, a
subsequent High locks at a price above 130, `pending_warning` clears and `reference_high` updates
— the cycle continues, exactly as specified in the prior revision.

## 4. Setup lifecycle when Stage 0 invalidates

Unchanged from the prior revision (preserve all historical records; terminate/disqualify
unbroken, in-flight setups going forward only; completed breakouts and their Track B outcomes are
immutable).

## 5. Fresh-cycle eligibility — explicit boundary

Unchanged from the prior revision: on invalidation, the entire pivot list is discarded, and a
pivot is eligible for the new cycle only if its pivot date (not confirmation date) is strictly
after the invalidation date. This is independent of the establishment-timing fix in section 2 and
requires no modification — the new cycle's L1→H1→L2→H2→(lock) sequence is built from scratch using
only post-invalidation pivots, under the same (now 5-pivot) establishment rule.

## 6. State-transition table (revised)

| From | Trigger | To | Effective date | Setup impact |
|---|---|---|---|---|
| NO_TREND | the 4th alternating, strictly-ascending pivot (H2) is itself LOCKED by a 5th pivot | ESTABLISHED | confirmation date of the 5th (locking) pivot | Stage A eligible from here |
| ESTABLISHED | locked Low > defended_low | ESTABLISHED | lock date | defended_low updates |
| ESTABLISHED | locked High > reference_high | ESTABLISHED | lock date | reference_high updates |
| ESTABLISHED | locked High < reference_high | PENDING_WARNING | lock date | snapshot taken, no setup impact yet |
| PENDING_WARNING | locked High > reference_high (no prior close breach) | ESTABLISHED | lock date | warning cleared, reference_high updates |
| PENDING_WARNING | Close < snapshot | NO_TREND (via INVALIDATED) | close date | per section 4; pivot list reset per section 5 |
| (any state) | a bar independently satisfies both swing-low and swing-high conditions | unchanged | — | event logged as `dual_pivot_excluded`, no state effect |

## Explicit remaining questions: none.

Both contradictions are resolved by (a) excluding same-instant dual pivots from the structural
sequence entirely rather than inventing an order between them, and (b) delaying establishment by
exactly one pivot so that the defining high is always already locked before the trend is declared
established. Neither fix introduces new concepts beyond what the spec already uses elsewhere (the
same lock mechanism, the same audit-logging principle). Requesting sign-off to implement once,
followed by the single agreed chart audit for semantic fidelity.
