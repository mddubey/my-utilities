# swing_qs_postbreakout — Novel Breakout -> Post-Breakout Decay -> Renewed Expansion

New sibling research line, opened 2026-09-29 per critic's explicit disposition after
reviewing the 04A-04C arc and the user's own JUSTDIAL/GOCLCORP chart hand-checks:
"not inside swing_qs_bpc/... the mechanism is now clearly different... I would create
a new sibling research folder." Named neutrally (not `..._vcp` or `..._decay`) on
purpose, per critic: "I'd prefer swing_qs_postbreakout/ because it doesn't prematurely
encode the hypothesis."

## What this is NOT (do not conflate)

- **Not BPC** (`swing_qs_bpc/`): BPC = breakout -> pullback BELOW the original level ->
  reclaim. That branch's D3 replay closed negative and stays frozen/untouched.
- **Not the 04A-04C "holds-above-A, first-fail-to-extend-the-running-high" pause**:
  that population was hand-tested (n=8,391) and found to be predominantly a 1-2 bar
  "impulse rest," NOT a base — no volume dry-up, longer pauses wider not tighter, B
  closes above the range only 45.6% of the time. Per the pre-declared decision tree
  that branch should close. Do not retrofit this folder's findings onto that one or
  vice versa — different trigger definition, different question.
- **Not VCP** (yet): Minervini's VCP requires successive contractions each SMALLER
  than the last. Nothing here should use VCP terminology or claim VCP support unless
  a population is found that actually exhibits that specific shape (tightening, not
  widening) — the 04B population did the opposite, and this line starts from that
  same real risk, not from an assumption it's fixed.

## The actual hypothesis (critic's framing, adopted verbatim)

```
ESTABLISHED BASE / RANGE
        v
NOVEL BREAKOUT FROM THAT RANGE          <- Layer A (this session's work)
        v
ABNORMAL VOLUME / PRICE EXPANSION
        v
POST-BREAKOUT COOLDOWN                  <- Layer B (gated on Layer A holding up)
        v
VOLUME + RANGE DECAY
        v
NEW EXPANSION / CONTINUATION
```

Origin: the user's own years-old manual Chartink practice (a screener checking 5 days
of strictly decreasing Volume), sharpened by two real hand-checks — JUSTDIAL (2026-07-
13/14, a genuinely novel breakout, decay followed, messily, with a secondary pop in
late August) vs GOCLCORP (2026-09-03, looked identical on the surface but was NOT a
first-ever institutional event — the same ticker already had 6.7M/8.6M volume days in
March, 21/128 days over 200K shares in the 6 months before). That contrast is the
whole reason Layer A exists as a SEPARATE, sequential gate before Layer B — GOCLCORP-
type re-accelerations must not contaminate the decay-characterization population.

Literature grounding (verified against primary/authoritative sources before building,
per this project's standing discipline — see `FINDINGS.md`'s first entry for the exact
quotes and corrections already caught):
- Flag/Pennant (Bulkowski, thepatternsite.com, direct page fetch): sharp move -> short
  consolidation, volume trends down 86% of the time -> breakout. BUT the pattern
  itself is weak: 54% break-even failure rate on upward breakouts, only 35% reach the
  full price target, average rise just 7% (n=1,600+ perfect trades). CORRECTED from an
  earlier wrong "68% success rate" claim caught by the critic and re-verified directly
  against Bulkowski's own page — carry the corrected numbers, not the retracted ones.
- Minervini VCP: successive contractions each SMALLER than the last, volume drying
  into the tightest/final leg. Demoted to a SECONDARY candidate here (not the primary
  rule) because the already-closed 04B population did the OPPOSITE of this (widening,
  not tightening) — don't assume this line's population will behave differently
  without checking.
- Inside days: mechanical candidate for "compression," NOT a validated literature
  finding that more consecutive inside days predicts a bigger breakout — that specific
  claim didn't survive a primary-source check and must be tested here, not inherited.
- Wyckoff Sign of Strength / Weinstein Stage 2: the source of Layer A's actual logic —
  a valid institutional breakout is a stock's FIRST qualifying escape from an
  established prior range, not merely a big-volume day. Critic's correction, adopted:
  "first qualifying breakout from a sufficiently established prior base/range," NOT
  "first breakout ever" — and the lookback/threshold that defines "sufficiently
  established" is OUR parameter to test, not an inherited number.

## Standing guardrails (same discipline as every other line in this project)

- Rule #22 (Hand-Verification of Surprises): every aggregate result here gets checked
  against JUSTDIAL 2026-07-14 and GOCLCORP 2026-09-03 first, since we already know by
  hand which bucket each should land in.
- Rule #19 (Robustness Before Finding) + its Parameterized Feature corollary: the
  "novelty lookback" has no single canonical value in the literature — pre-declare 3
  materially distinct horizons (3/6/12 months) before looking at results, per that
  corollary, not picked after seeing which one looks best.
- Research Preflight (5 questions) answered in `FINDINGS.md`'s first entry, before any
  code was written for RQ-QS-05A.
- Layer sequencing is NOT optional: Layer B (decay characterization) does not start
  until Layer A's novelty split is itself established as real/discriminating — no
  jumping ahead, per critic's explicit instruction.

## Open reconciliation item, not yet resolved (flag before trusting any external "verification" again)

The critic's own independent JUSTDIAL numbers (July 14: high ~770, volume ~1.03 crore)
disagree with our own `data_cache` (high 809.00, volume 42,569,366) — open ~712 and
July 13 close ~676.85 matched almost exactly, but High/Volume did not, even though the
critic had already been told our own 42.5M figure. GOCLCORP's critic-reported numbers,
by contrast, matched our cache almost to the decimal. Unresolved which side (our cache
vs. critic's source) is right for JUSTDIAL specifically — flagged, not chased down yet
(explicit user call: "let's continue first").
