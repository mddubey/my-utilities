# EMAPB Stage 0 — Final Specification (Revision 4, two structures made explicit)

**Status: proposed for final sign-off. Not yet implemented.**

## Root cause of the Revision 2 defect, fixed at the source

Revision 2 conflated two genuinely different concepts under one word, "locked": (a) *a pivot is
committed enough to be used as one of the fixed points that establishes Stage 0*, and (b) *a
pivot's value is known and can be compared against the running references for invalidation
tracking*. These do not need the same timing. (b) is knowable the instant a pivot confirms; (a)
needs to wait, because establishing Stage 0 is a one-time, permanent decision.

## Answering the Revision 3 question directly: yes, intentional — made explicit as two structures

Critic's question was precise: does a High that gets replaced in the pivot list still legitimately
affect invalidation tracking? **Yes — and the reason it's not a contradiction is that "the pivot
list" and "the tracking mechanism" were never the same data structure. Revision 3 left that
implicit; this revision names them separately so nothing looks silently inconsistent.**

**Structure 1 — `pivot_list`** (replace-tail / append / lock semantics, exactly as before). Used
**only** for two purposes: (1) detecting Stage 0 establishment (Section 2), and (2) the fresh-cycle
eligibility boundary after an invalidation (Section 5). It is dormant — not consulted at all — while
Stage 0 is already ESTABLISHED.

**Structure 2 — the confirmed-swing event stream**: a plain, **append-only** log of every
swing-low and swing-high confirmation, in confirmation order, with nothing ever replaced or
removed. Once Stage 0 is established, **all of Section 3's tracking rules read from this stream,
never from `pivot_list`.**

Why this resolves the concern rather than hiding it: a High confirming at 125 is a real,
already-happened market event the moment it confirms — the fact that `pivot_list` may later replace
its *bookkeeping slot* with a 135 High (because no Low confirmed in between) has no bearing on
whether 125 actually printed below `reference_high` at the time. The warning it created reflects
true, decision-time-knowable information. The 135 High that follows is a *separate*, later, equally
real event, and it legitimately clears the warning on its own merits — not because it overwrote the
125 entry in `pivot_list` (it does do that, in Structure 1, but Structure 2 never cared about that
replacement in the first place).

**Audit trail guarantee**: the event stream (Structure 2) is immutable and append-only by
definition — the 125 confirmation and the warning it created are permanently recorded, exactly as
they happened, regardless of anything `pivot_list` does afterward. Nothing is ever silently treated
as "committed structure" by the tracking mechanism, because the tracking mechanism never makes
structural-commitment claims — only `pivot_list` does, and only for establishment/fresh-cycle
purposes, which are explicitly walled off from Section 3.

## 1. Pivot construction and chronological integrity (Structure 1 — unchanged)

Same-type pivot -> replace tail. Different-type pivot -> append, locking the previous tail.
`confirmation_index = pivot_index + 2` for both swing types under symmetric K=2, so confirmation
order and pivot-date order are always identical for two different bars.

**Dual-pivot bars**: a bar satisfying both swing conditions simultaneously contributes **neither**
event to `pivot_list` **nor to the event stream** — excluded from both structures entirely, logged
as `dual_pivot_excluded`.

## 2. Stage 0 establishment (Structure 1 only)

`L1 -> H1 -> L2 -> H2`, strict `L2 > L1` and `H2 > H1`. Establishment requires H2 to be locked by a
5th pivot in `pivot_list` before Stage 0 activates. Effective date = the locking pivot's
confirmation date. Unchanged from Revision 3.

## 3. Post-establishment reference tracking and invalidation (Structure 2 only)

**State**: `defended_low`, `reference_high` (initialized from the established L2/H2),
`pending_warning` (None, or a snapshot). From this point forward these are driven **exclusively**
by the append-only event stream — `pivot_list`'s replace/lock mechanics are not consulted again
unless/until an invalidation occurs and a fresh Stage 0 search restarts (Section 5).

**Per-bar processing order** (unchanged, this is still what makes every timing question resolve
cleanly):
1. **First**: if `pending_warning` is active and today's Close < the snapshotted level ->
   invalidation fires, effective today, using only state that existed before today's own stream
   entries are processed.
2. **Then**: process every swing event that **confirms today** (append to the stream — nothing is
   ever replaced here) and apply:
   - New Low confirms, no warning pending, price > `defended_low` -> `defended_low` updates.
   - New Low confirms, warning pending -> no change (frozen).
   - New Low confirms, price <= `defended_low` -> no change.
   - New High confirms, price > `reference_high` -> `reference_high` updates; clears
     `pending_warning` if one exists.
   - New High confirms, price < `reference_high` -> lower-high event. If no warning pending, set
     `pending_warning` = (today, current `defended_low`). If already pending, no-op (original
     snapshot/date stand).
   - New High confirms, price == `reference_high` -> no change.

## Adversarial validation — all 10 cases, plus the new one

**1-3, 7-10**: unchanged from Revision 3's validation; none of them depend on the Structure 1/2
distinction in a way that changes their outcome — restating PASS for each (pivot replacement before
establishment; dual-pivot bars; establishment timing; rolling defended-low; fresh-cycle reset;
same-date collisions; full lifecycle including repeated warnings).

**4-6 (timing)**: unchanged conclusions, now additionally justified by the Structure 2 append-only
model — a warning/clearance event is simply an entry in the stream, processed once, in order,
exactly where it falls; nothing about `pivot_list` replacing its own bookkeeping slot afterward
touches the stream.

**11 (new — the Revision 3 question itself). A High that is later replaced in `pivot_list` still
created a valid warning/clearance.** Worked below. **Resolved, not a defect**: Structure 2 never
treats the replaced pivot as "committed structure" — it never claimed structural commitment at all,
only `pivot_list` does, for an unrelated purpose. **PASS.**

## Worked example — the exact Revision-3 sequence, now shown against both structures

| event | type | price | `pivot_list` (Structure 1) | event stream / tracking (Structure 2) |
|---|---|---|---|---|
| ... | (Stage 0 already established per Section 2, as in the prior worked example) | | | defended_low=110, reference_high=130 |
| t6 | H confirms | 125 | replaces current tail in `pivot_list` (irrelevant to tracking) | 125 < 130 -> **pending_warning = (t6, 110)** |
| t7 | H confirms | 135 | replaces the 125 entry in `pivot_list` | 135 > 130 -> **reference_high -> 135, warning cleared** |

Both t6 and t7 are permanent entries in the event stream (Structure 2), regardless of what happened
in `pivot_list`. Nothing is silently overwritten; the audit log shows exactly: a warning created at
t6, cleared at t7, both real, both timestamped, neither retroactively altered.

## 4. Setup lifecycle when Stage 0 invalidates (unchanged)

Historical records preserved in every case; unbroken in-flight setups terminate/disqualify going
forward only; completed breakouts and Track B outcomes are immutable.

## 5. Fresh-cycle eligibility (unchanged, Structure 1 only)

Full `pivot_list` reset on invalidation; a pivot is eligible for the new cycle only if its pivot
date is strictly after the invalidation date, regardless of confirmation timing. The event stream
(Structure 2) is not reset — it is a historical record and remains intact — but tracking (Section 3)
does not resume until a new Stage 0 establishes, per Section 2, from the reset `pivot_list`.

## 6. State-transition table (final, unchanged from Revision 3)

| From | Trigger | To | Effective date | Setup impact |
|---|---|---|---|---|
| NO_TREND | H2 (4th ascending pivot) is locked by a 5th pivot | ESTABLISHED | 5th pivot's confirmation date | Stage A eligible from here |
| ESTABLISHED | a Low confirms, price > defended_low | ESTABLISHED | that pivot's confirmation date | defended_low updates |
| ESTABLISHED | a High confirms, price > reference_high | ESTABLISHED | that pivot's confirmation date | reference_high updates |
| ESTABLISHED | a High confirms, price < reference_high | PENDING_WARNING | that pivot's confirmation date | snapshot taken |
| PENDING_WARNING | a High confirms, price > reference_high | ESTABLISHED | that pivot's confirmation date | warning cleared, reference_high updates |
| PENDING_WARNING | a second lower High confirms | PENDING_WARNING | — | no-op |
| PENDING_WARNING | Close < snapshot | NO_TREND (via INVALIDATED) | close date | setups per Section 4; `pivot_list` reset per Section 5 |
| (any state) | a bar satisfies both swing conditions | unchanged | — | excluded from both structures, logged |

## Explicit remaining questions: none.

The two structures (establishment bookkeeping vs. ongoing tracking) were always functionally
separate in the rules as written; this revision names them explicitly so that separation is
auditable rather than implicit. No behavior changes from Revision 3 — only the explanation and
the audit-trail guarantee are made concrete. Requesting sign-off to implement once, followed by the
single agreed chart audit for semantic fidelity.
