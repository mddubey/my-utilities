# EMAPB Stage 0 — Final Specification (Revision 3, adversarially validated)

**Status: proposed for final sign-off. Not yet implemented.**

## Root cause of the Revision 2 defect, fixed at the source

Revision 2 conflated two genuinely different concepts under one word, "locked": (a) *a pivot is
committed enough to be used as one of the fixed points that establishes Stage 0*, and (b) *a
pivot's value is known and can be compared against the running references for invalidation
tracking*. These do not need the same timing. (b) is knowable the instant a pivot **confirms** —
nothing about comparing a freshly confirmed High's price to `reference_high` requires waiting to
see whether an even-later High might eventually replace it in the list. (a) genuinely does need
the wait, because establishing Stage 0 is a one-time, permanent decision that must not be able to
later disagree with the pivot list.

**Resolution: split the concept.** "Locking" (append of an opposite-type pivot makes the previous
tail permanent) is now used **only** for (1) the Stage 0 establishment rule, and (2) the fresh-cycle
eligibility boundary. **Every ongoing reference update and warning, once Stage 0 is established,
triggers on a pivot's own CONFIRMATION date — never on a later lock date.** This removes the whole
class of confirm-vs-lock timing ambiguity from the part of the machine where it was causing
contradictions.

## 1. Pivot construction and chronological integrity (unchanged, still holds)

Same-type pivot -> replace tail. Different-type pivot -> append, which locks the previous tail.
`confirmation_index = pivot_index + 2` for both swing types under symmetric K=2, so confirmation
order and pivot-date order are always identical for two different bars.

**Dual-pivot bars**: a bar satisfying both swing conditions simultaneously contributes **neither**
event to the pivot list, and cannot update any reference or warning under any rule in this
specification. Logged as `dual_pivot_excluded`.

## 2. Stage 0 establishment (unchanged from Revision 2 — "locking" applies here)

`L1 -> H1 -> L2 -> H2`, strict `L2 > L1` and `H2 > H1`. Establishment requires H2 to be **locked**
by a 5th pivot (the next opposite-type confirmation) before Stage 0 is declared active — this is
the one place in the spec where lock, not confirmation, is the correct trigger, because
establishment is a permanent, one-time decision about which pivots to trust forever. Effective
date = the locking pivot's confirmation date.

## 3. Post-establishment reference tracking and invalidation — CONFIRMATION-triggered (revised)

**State**: `defended_low`, `reference_high` (initialized from the established L2/H2),
`pending_warning` (None, or a snapshot).

**Per-bar processing order, unchanged and now the single source of all timing correctness**:
1. **First**: if `pending_warning` is active and today's Close < the snapshotted level ->
   invalidation fires, effective today. (Uses only warnings that existed *before* today's own new
   confirmations are processed — see the worked cases below for why this matters.)
2. **Then**: process every pivot that **confirms today** (whether it replaces the current tail or
   appends, locking something else — irrelevant for this step) and apply:
   - New Low confirms, no warning pending, price > `defended_low` -> `defended_low` updates.
   - New Low confirms, warning pending -> no change (frozen, per the existing freeze rule).
   - New Low confirms, price <= `defended_low` -> no change.
   - New High confirms, price > `reference_high` -> `reference_high` updates; clears
     `pending_warning` if one exists.
   - New High confirms, price < `reference_high` -> **this is the lower-high event.** If no warning
     is currently pending, set `pending_warning` = (today, current `defended_low`). **If a warning
     is already pending, this repeated lower-high has no additional effect** — the original
     warning's date and snapshot stand (documented choice: the first lower-high after
     establishment/clearance is what matters; a second, even-lower high while already pending adds
     no new information worth tracking).
   - New High confirms, price == `reference_high` -> no change.

Because step 1 always runs before step 2 on the same bar, **a brand-new warning or a brand-new
clearance created today can never affect today's own close-check** — both only take effect starting
from the next day's step 1.

## Adversarial validation — all 10 cases

**1. Pivot replacement before establishment.** A same-type pivot replacing the tail never touches
anything earlier in the list (those entries are already locked, in the establishment sense, from
when the current tail was appended). **PASS.**

**2. Dual-pivot bar.** Excluded from the list, from establishment, from reference updates, and from
warnings — all four mechanisms check pivot-list membership, and an excluded event never enters the
list. **PASS.**

**3. Stage 0 activation, L1->H1->L2->H2->L3.** H2 locks exactly when L3 confirms; establishment
fires at that moment using the now-permanent L1/H1/L2/H2; Stage A eligible from L3's confirmation
date onward, never earlier. **PASS** (per Revision 2's fix, unchanged here).

**4. Lower-high warning timing — confirmation vs. lock.** **Resolved by the root-cause fix above:
warnings trigger on the High's own confirmation date, full stop.** Locking is irrelevant to this
mechanism. This directly fixes the Revision 2 defect: in the worked example below, the warning is
now correctly dated to H3's confirmation (the day it actually happened), not deferred to whenever a
subsequent Low happens to confirm afterward.

**5. Same-day invalidation vs. a same-day new warning.** A warning created today cannot invalidate
off today's own close — step 1 (close-check) runs before step 2 (today's new confirmations,
including the one that would create this warning). The earliest a brand-new warning can trigger
invalidation is tomorrow's close-check. **No defect — this is the correct, intended behavior**,
directly answering critic's question 3.

**6. Warning clearance vs. a same-day breach.** If a warning has been pending since a prior day,
and TODAY both (a) the close breaches the old snapshot, and (b) a new higher High confirms that
would clear the warning: step 1 runs first, using the warning as it stood *before* today's
confirmations are processed -> **invalidation fires on today's close-check**, before step 2 would
otherwise have cleared it. The later clearing event is simply never reached, because the state
machine has already exited to NO_TREND. **A later event never reverses an already-fired
invalidation — PASS, consistent with the standing requirement.**

**7. Rolling defended low — higher low / lower low / lower high in varied order.** A lower low
confirming does nothing by itself (no rule reacts to it alone); a higher low updates `defended_low`
immediately (if no warning pending); a lower high sets a warning as in case 4. No path produces a
stale or silently-drifting value — every update is a direct, immediate consequence of a specific
confirmation event. **PASS.**

**8. Invalidation and reset — pivots confirming after invalidation but dated before it.**
Unaffected by this revision; Section 5's boundary rule (pivot DATE, not confirmation date, must be
strictly after the invalidation date) already excludes these regardless of confirmation timing.
**PASS.**

**9. Same-date multiple events, historical integrity.** The fixed per-bar order plus dual-pivot
exclusion (case 2) plus immutable completed-breakout records (Section 4, unchanged) together cover
every same-date collision this specification can produce. **PASS.**

**10. Lifecycle completeness, including repeated warnings.** A second lower-high while a warning is
already pending is explicitly a no-op (documented above, not left undefined). Equality (new High ==
reference_high, new Low == defended_low) is a no-op in both directions, already specified.
"Missing qualifying pivots" is simply the ongoing NO_TREND/searching state, not an error. Every
state in the table below has a defined next action for every input. **PASS.**

## Worked example — corrected timing (dual-pivot exclusion + confirmation-based warning)

| event | type | price | effect |
|---|---|---|---|
| t1 | L1 confirms | 100 | list=[L1] |
| t2 | H1 confirms | 120 | append, locks L1; list=[L1,H1] |
| t2a | (same bar also satisfies swing-low) | — | **dual-pivot excluded, logged, no effect** |
| t3 | L2 confirms | 110 | append, locks H1; list=[L1,H1,L2] |
| t4 | H2 confirms | 130 (>120) | append, locks L2; list=[...,H2]. H2 still provisional — **not yet established** |
| t5 | L3 confirms | 115 | append, **locks H2**. Check L1,H1,L2,H2 = 100,120,110,130: ascending holds -> **STAGE 0 ESTABLISHED at t5**. defended_low=110, reference_high=130 |
| t6 | H3 **confirms** | 125 | 125 < reference_high(130) -> **lower-high warning set AT t6** (its own confirmation date, not deferred) |
| t7 | L4 **confirms** | 112 | 112 vs defended_low(110): warning is pending, so **frozen — no update**, consistent with the freeze rule |
| t8 | Close = 108 | — | 108 < snapshot (110, the defended_low value at the moment the t6 warning was set) -> **INVALIDATION fires at t8** |
| t9 | a new High later confirms at 140 | — | irrelevant; cycle already ended at t8 |

**Clearance variant**: identical through t5. At t6, instead of 125, a High confirms at 135 (>130)
-> `reference_high` updates to 135 immediately, no warning ever created. Trend continues.

**Same-day collision variant (case 6)**: warning pending since t6 (snapshot=110). At t8, today's
Close = 105 (< 110) AND a new High also confirms today at 140 (which would otherwise clear the
warning). Step 1 (close-check, using yesterday's state) fires invalidation first; step 2's
would-be clearance never executes because the cycle has already exited. The 140 high is logged as
occurring on an already-invalidated bar, with no effect on this cycle.

## 4. Setup lifecycle when Stage 0 invalidates (unchanged)

Historical records preserved in every case; unbroken in-flight setups terminate/disqualify going
forward only; completed breakouts and Track B outcomes are immutable.

## 5. Fresh-cycle eligibility (unchanged)

Full pivot-list reset on invalidation; a pivot is eligible for the new cycle only if its pivot date
is strictly after the invalidation date, regardless of confirmation timing.

## 6. State-transition table (final)

| From | Trigger | To | Effective date | Setup impact |
|---|---|---|---|---|
| NO_TREND | H2 (4th ascending pivot) is locked by a 5th pivot | ESTABLISHED | 5th pivot's confirmation date | Stage A eligible from here |
| ESTABLISHED | a Low confirms, price > defended_low | ESTABLISHED | that pivot's confirmation date | defended_low updates |
| ESTABLISHED | a High confirms, price > reference_high | ESTABLISHED | that pivot's confirmation date | reference_high updates |
| ESTABLISHED | a High confirms, price < reference_high | PENDING_WARNING | that pivot's confirmation date | snapshot taken |
| PENDING_WARNING | a High confirms, price > reference_high | ESTABLISHED | that pivot's confirmation date | warning cleared, reference_high updates |
| PENDING_WARNING | a second lower High confirms | PENDING_WARNING | — | no-op, original snapshot/date stand |
| PENDING_WARNING | Close < snapshot (checked before today's new confirmations) | NO_TREND (via INVALIDATED) | close date | setups per Section 4; pivot list reset per Section 5 |
| (any state) | a bar satisfies both swing conditions | unchanged | — | logged `dual_pivot_excluded`, zero effect |

## Explicit remaining questions: none.

Every adversarial case above resolves to a defined, consistent outcome. The root-cause fix
(confirmation-triggers-tracking, lock-triggers-establishment-only) removes the specific ambiguity
Revision 2 had, and the audit found no further contradictions. Requesting sign-off to implement
once, followed by the single agreed chart audit for semantic fidelity.
