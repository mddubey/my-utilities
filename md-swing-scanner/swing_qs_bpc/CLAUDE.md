# swing_qs_bpc — Breakout-Pullback-Continuation, a SIBLING entry family to swing_qs/

This is a SEPARATE research line from `swing_qs/` (first-breakout QS), per critic's
explicit architectural decision (2026-09-29): "we've accumulated too many findings
that are specific to first-breakout QS. BPC has different assumptions, different
anatomy, and potentially different exits. Mixing them into the same folder will
recreate the BC v2 vs QS confusion you deliberately avoided with swing_qs/."

**Frozen, do not touch from here**: QS v0.1 (first-breakout continuation) stays the
frozen baseline in `swing_qs/`. Exit discovery there stays frozen. The 1H hypothesis
is closed negative. R1/R2 stays descriptive-only. Nothing in this folder modifies any
of that.

## What BPC is, precisely (do not conflate with what RQ-QS-03 actually tested)

**Real, independently-documented, named strategy**: Breakout-Pullback-Continuation.
Verified against multiple independent sources (not just one), including a Nifty-
options-specific writeup. Core structure: (1) a breakout past resistance, (2) a
CONTROLLED pullback/contraction, (3) a second breakout FROM that contraction, at or
near the original level.

**Critical correction, already made once — do not repeat**: RQ-QS-03's first pass
implemented "first fresh v0.1-gate-passing trigger on the same ticker within 10
days" — NOT literature BPC. That is a mechanically different thing (a mechanical
re-entry, which fires 51.6% of the time literally the next day — almost impossible
under a genuine breakout-pullback-continuation reading). **Renamed to RQ-QS-03A —
Mechanical Re-entry** in the findings, specifically so it never gets cited as "BPC"
later. The properly-verified subset (gap≥2 days AND a confirmed pullback below A's
entry price, further confirmed to resume within ~1-3% of A's original level, not a
disconnected later move) is the real BPC-adjacent population — still not the full
literature definition, but a much closer approximation.

## Standing guardrail for everything built here

Rule #22 (parent `../CLAUDE.md`): any surprising aggregate result gets hand-verified
against 3-5 concrete real examples before being trusted, not just re-aggregated or
re-run at a bigger sample. This folder's own history already produced the exact case
that rule is named after (a pullback-detection aggregation bug: reported 0.1%, real
answer was 72.3% — caught by hand-checking 5 real A/B pairs, not by re-running the
same buggy aggregation on more data).

## Product architecture insight (critic, 2026-09-29) — QS-A vs QS-B, an entry-side split

Not an exit-side fix (everything tried there this weekend underperformed or made
things worse). A genuine product split at the ENTRY: **QS-A** (first-breakout, in
`swing_qs/`) enters during the expansion itself — highest upside, most psychological
pain, probably better suited to stock swing. **QS-B** (BPC, here) enters after
pullback confirmation — smaller upside, faster proof, a real structural stop (the
pullback low / retested level), potentially better suited to options specifically
(the standing "options can't sit for 10-15 days" complaint). These don't compete —
they answer different questions about the same breakout event. Deployment status as
of 2026-09-29: QS-A is 🟡 ready for trajectory replay / paper trades, not options.
QS-B is 🟢 ready for anatomy and replay, not live trades yet — earlier than QS-A in
its own validation arc, but on a real, separately-evidenced track.

## Read `FINDINGS.md` before extending this line further

Full RQ-QS-03A result, the volume dry-up proxy-mismatch correction, and RQ-QS-03B's
scope (Quality Pullback Audit — descriptive only, five fields, no thresholds, no
pass/fail, no expectancy) are there.
