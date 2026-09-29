# RQ-QS Exit Philosophy Benchmark (Stage QS-E0, 2026-09-27)

Per critic's explicit instruction after the user caught a real methodological slip
("we slipped back into letting the dataset tell us what exit to build"): this document
states expectations **derived from breakout-trading literature, before running any new
exit-side test on our own data**. It exists specifically so we can later say "the data
agrees with X" or "the data contradicts Y" — not so we can retroactively describe
whatever pattern the data happens to show. Entry candidates (10D/20D/40D raw, BC v2)
stay fixed throughout this stage — this document is about the EXIT/management
philosophy, not about picking a winning entry.

## Standing rule adopted alongside this document: Expectation Disagreement Rule

Every exit hypothesis below has a pre-stated, falsifiable expectation. When an observed
result disagrees with it, the correct response is NOT to immediately retune the
hypothesis or the definition. First classify the disagreement as one of:
(a) the literature hypothesis is simply wrong for this market/product,
(b) a measurement/definition problem (e.g. the threshold or window chosen doesn't
    capture what the hypothesis actually means),
(c) an entry-definition mismatch (the entry candidates tested don't produce the kind of
    setup the hypothesis assumes),
(d) a market/universe difference (NIFTY 500 behaves differently from whatever market the
    literature reference actually traded),
(e) the hypothesis is genuinely supported.
Any change to an exit or entry definition in response to a disagreement requires an
explicit stated reason from this list — never a silent re-tune.

## Literature archetypes (established BEFORE testing, not fitted after)

| Philosophy | Reference | Expected behavior |
|---|---|---|
| Fast momentum | Kullamägi | **Corrected after independent verification (2026-09-27) — this is one staged mechanism, not two alternative styles**: take partial profit (roughly 1/3-1/2 of the position) after 3-5 sessions OR at 2-3R profit, whichever comes first; move the stop to breakeven; trail the remainder with a moving average (10-EMA if the stock's ADR>10%, 20-EMA otherwise) with no calendar exit — it runs until a close below the trail. Whether a trade ends up "fast" (3-5 days) or long (weeks) is an OUTCOME of this mechanism, not a fork chosen upfront. Entry setup: a strong prior move (30-100%+ over the prior 1-3 months), a real consolidation with tightening range and higher lows (duration is genuinely disputed across sources, roughly 1-8 weeks), then decisive expansion — not a bare N-day-high touch alone. Execution: opening-range entry, stop at the breakout day's low, never wider than ~1 ADR. |
| Structural staircase | Darvas | Exit is structural (box-floor failure), not calendar-based. Advance → consolidation (new box) → next breakout → higher floor. A stall (no new box forming within a reasonable window) is itself a warning sign. |
| Failure-vs-winner asymmetry | O'Neil (framework, not the whole product) | Failure and success should be managed with different logic: a hard, fast loss limit for breakouts that don't work (~7-8% from entry), versus real room for winners to develop, with an explicit exception for unusually fast/strong movers to be held even longer. |
| Digestion tolerance | Minervini | Ordinary post-entry weakness (a red day, a shallow pullback) should not trigger an exit — only a large-enough reversal should. Normal digestion must be distinguished from real failure. |
| Give-back-after-impulse | This project's own HH/LH work + O'Neil/Darvas structural-failure concept | Once a trade has produced a real, meaningful favorable move, the operative question changes from "will this work" to "is the move now deteriorating" — give-back/structural-failure signals are relevant AFTER a real impulse, not as entry filters and not as a flat, always-on trailing stop from day one. |

**Note on scope, per direct user challenge**: O'Neil and Minervini are NOT treated as
primary references for this new product — their style (multi-week base, tolerate large
digestion, ride to 20-25%+ gains) is much closer to BC's *existing*, already-built
positional-leaning product than to a genuine 3-5 day quick swing. They inform the
general failure-vs-winner and digestion-tolerance CONCEPTS above, not the specific
timing. Kullamägi is the primary reference for timing, specifically for his shorter,
3-5-day-burst approach (his own separate longer/trailed approach is explicitly NOT what
we're building here either).

## Pre-data hypotheses (QS-H1 through QS-H6) — falsifiable, stated before testing

- **QS-H1 (Early evidence)**: a genuine quick-swing breakout should show meaningful
  positive excursion early — within roughly the first several sessions. If most eventual
  winners are still negative through day 5 and only become good trades around days
  10-15, that's a real, direct challenge to whether the QS product exists in this
  universe at all — not necessarily evidence the trades are bad, evidence they aren't
  behaving like the product we're trying to build.
- **QS-H2 (Early failure)**: a breakout that is going to fail should disproportionately
  reveal weakness early — some combination of failure to extend, inability to hold the
  breakout, adverse excursion, weak closes, reversion toward the base. Connects directly
  to this project's own Type-A research question.
- **QS-H3 (Don't kill healthy consolidation)**: advance → consolidation → expansion is
  the literature's normal pattern, not uninterrupted vertical movement. A day-2/3 pause
  or shallow pullback should NOT be treated as automatic failure — some real winners
  should show temporary stagnation before their eventual move.
- **QS-H4 (State change after impulse)**: the right exit philosophy should differ before
  vs. after a trade proves itself. Before proof: failure management (cut it if it's not
  working). After a real impulse: profit-preservation / continuation management (give it
  room, watch for structural deterioration instead of a flat rule). The exit
  architecture should plausibly have STATES (Entry → Prove/Disprove → Expansion → Manage
  give-back/structural failure), not one universal rule applied identically throughout.
- **QS-H5 (No 15-day rescue mission)**: a large proportion of successful QS trades
  should demonstrate meaningful continuation substantially earlier than the current
  15-day framework requires. If this fails — if reaching a real result routinely takes
  the full window regardless of entry definition — we have to seriously question whether
  the proposed QS product is actually present in this breakout universe, not just retune
  a threshold.
- **QS-H6 (Give-back matters after meaningful MFE, not before)**: once a trade has
  already shown a real move, structural deterioration (failure to make another high, a
  confirmed lower high, a break of recent support, substantial give-back) becomes
  conceptually relevant. This is NOT proposed as an entry filter, and NOT as an
  always-on trailing stop from day one — only as a post-impulse management concept.

## What this stage does NOT do

No new exit code. No entry filters. No threshold optimization. No picking a "best"
lookback among 10D/20D/40D — those stay fixed as reference entry candidates throughout,
per the explicit sequencing agreed: **entry candidates fixed → exit philosophy
established independently → each entry tested against the exit expectations → any
disagreement diagnosed via the Expectation Disagreement Rule before anything changes.**

## Test results — logged in `FINDINGS.md`, not here

This document stays static as the benchmark; test outcomes (expectation vs. observed,
agrees/partially/contradicts, implication) are logged in `swing_qs/FINDINGS.md` as they
run, so the expectation record itself is never edited after the fact.
