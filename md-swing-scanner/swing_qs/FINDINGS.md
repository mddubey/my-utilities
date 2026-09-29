# swing_qs research log

Separate from the parent `FINDINGS.md` — see `CLAUDE.md` and `PRODUCT_DEFINITION.md` in
this folder for why. Same append-only convention as the parent log: never edit past
entries, only add new ones.

## Stage 0, Deliverable 1 — Trajectory Labeler (2026-09-26)

Population: BC v2, honest T-1-gated (`rule18_yesterday_gate_full.csv`, n=9,430,
entry_date>=2022-07-04 — reused as-is from the parent project, not rebuilt). Labels per
`PRODUCT_DEFINITION.md`: FAST = reaches >=0.25R (High-based) by day_idx<=5; SLOW =
reaches it later; FAKE = never reaches it before the real exit.

**Population sizes (no performance conclusions expected at this stage):**

| Label | n | % |
|---|---|---|
| FAST | 4,644 | 49.2% |
| FAKE | 2,850 | 30.2% |
| SLOW | 1,936 | 20.5% |

Context only, not a promotion signal: mean r_multiple — FAKE -0.470, FAST +0.369, SLOW
+0.285. Exit-reason composition: FAKE is 79.2% max_hold_cap / 20.8% stop (no
target/climax at all, consistent with never reaching 0.25R); FAST is 81.1% max_hold_cap
/ 17.3% stop; SLOW is 94.7% max_hold_cap / 4.2% stop (fewest stops — once a trade
reaches 0.25R even late, it rarely reverses all the way to a stop-out afterward).

## Stage 0, Deliverable 2 — Trigger Timing Dataset (2026-09-26)

For every real 10-day BC v2 trigger, searched forward (same T-1 gate applied, same
`base_filters_pass` recipe, capped at 60 days) for the first day a 20-day-high and,
separately, a 40-day-high trigger would also fire for the same ticker. Descriptive only,
no gate change, no optimization.

**Coverage**: found a 20d trigger for 98.3% of episodes, a 40d trigger for 94.2% (the
rest never clear that lookback within 60 days in this sample).

**Timing gap (days after the 10-day trigger):**

| | median | 75th pct | 90th pct |
|---|---|---|---|
| 20-day trigger | 0 | 0 | 1 |
| 40-day trigger | 0 | 1 | 11 |

Most of the time all three thresholds clear on the exact same day (20d: 88.4% same-day,
40d: 68.0% same-day) — the stock hasn't made a meaningful new high at any horizon in a
while, so a real breakout clears all of them at once. Price paid for waiting (versus the
10-day trigger price): median 0% for both, but the 90th-percentile tail costs 1.6% (20d)
/ 5.2% (40d) — a real, if occasional, gap cost to waiting for a longer confirmation.

**The one genuinely striking result — timing of the 40-day trigger relative to the
10-day one predicts the trajectory label, and not monotonically:**

| 40d trigger timing | n | FAKE | FAST | SLOW |
|---|---|---|---|---|
| Same day as 10d | 6,408 | 30.2% | 50.2% | 19.6% |
| **Within 5 days (but not same-day)** | **1,077** | **6.8%** | **84.3%** | **8.9%** |
| Later than 5 days | 1,394 | 32.9% | 29.1% | 38.0% |
| Never found within 60d | 551 | 69.7% | 20.7% | 9.6% |

Episodes where the 40-day high clears shortly *after* the 10-day high (1-5 days later,
not the same day) show a raw FAST rate of 84.3%, vs 50.2% for simultaneous clears and
20.7% for episodes that never clear the 40-day high within 60 days.

**Caught a real circularity risk before trusting the 84.3% number, per direct user
challenge ("isn't this just saying a bigger move is a good trade — obvious").** Checked:
at the median, the price gap needed to clear the 40-day high already represents ~91% of
the entire 0.25R FAST bar itself (since both the label and this feature are High-based,
measured off the same trigger price) — for 45.3% of the "within 5 days" bucket, clearing
that level ALONE is already enough to be at 0.25R, making "cleared it" and "is FAST"
close to the same event by construction for nearly half these cases. The raw 84.3%
number is genuinely inflated by this overlap.

**Decontaminated re-check — excluding every case where clearing the 40-day high alone
already reached 0.25R** (n=589, the cases where the label and the feature are NOT
mechanically the same event):

| Group | n | FAST rate |
|---|---|---|
| Cleared 40d high within 5 days, NOT already at 0.25R from that alone | 589 | **71.3%** |
| Same-day clear (baseline) | 6,408 | 50.2% |
| Never clears 40d high within 60d | 551 | 20.7% |

**A real, non-circular signal survives** (71.3% vs 50.2%/20.7% baselines), just smaller
and more honest than the raw number suggested. Plausible mechanism (hypothesis, not yet
robustness-tested): clearing a genuine overhead resistance level within a few days —
not instantly (which mostly reflects a quiet stock with no real ceiling to begin with),
not never (weak, non-accelerating, 69.7% FAKE) — predicts continued follow-through even
among trades that hadn't already technically qualified as FAST at that point.

**Disposition**: real, descriptive result, now correctly decontaminated. Per
`PRODUCT_DEFINITION.md`'s Stage 0 guardrails, NOT promoted, NOT gated, NOT
threshold-optimized — a Stage 2 candidate once Stage 0/1 are fully built out. Per Rule
#19 it will need a robustness check (does this survive a different "within N days"
window before 5, e.g. 3 or 7) before being treated as more than an exploratory
observation. **Standing lesson for the rest of this research line**: any feature built
from the same High-based price series as the FAST/SLOW/FAKE label itself must be
checked for this exact overlap before its raw separation rate is trusted — a feature
and a label sharing the same underlying measurement (price vs. entry, in R units) can
look like a strong predictor while partly just restating the outcome.

**Second round of the same challenge, per direct user follow-up ("is this generally
because both highs are so very close, and if so isn't that itself the signal") — checked
directly, and it goes deeper than expected.** Re-bucketed the full population purely by
the SIZE of the 10d-to-40d-high price gap (ignoring clearing timing entirely):

| Gap size | n | FAST (raw) | % of bucket already contaminated (gap alone >=0.25R) |
|---|---|---|---|
| 0% (same day) | 5,061 | 45.8% | 0.0% |
| 0-2% | 1,596 | 53.5% | 0.4% |
| 2-5% | 1,287 | 59.4% | 47.6% |
| 5-10% | 740 | 63.0% | 98.0% |
| >10% | 195 | 64.1% | 100.0% |
| Never clears | 551 | 20.7% | n/a |

The raw version looked like a clean monotonic "bigger gap = better" story — but it is
**almost entirely the same circularity, and worse**: 98-100% of the 5%+ gap buckets are
mechanically already at 0.25R purely from the gap size itself, leaving almost no
uncontaminated data at the larger sizes (n=15 left at 5-10%, effectively none above 10%).

**Fully decontaminated (gap alone did NOT already reach 0.25R):**

| Gap size | n (decontaminated) | FAST |
|---|---|---|
| 0% (same day) | 5,061 | 45.8% |
| 0-2% | 1,590 | 53.5% |
| 2-5% | 674 | 53.6% |
| 5-10% | 15 (too thin to trust) | 40.0% |
| Never clears | 551 | 20.7% |

The honest picture is much flatter than the raw table suggested: a real, modest step
from "no gap at all" (45.8%) to "some real gap exists" (53-54%, plateauing rather than
continuing to climb) — the apparent continued rise at 5%+ gaps in the raw table was
essentially all circularity, not signal.

**Reconciling this against the earlier "within 5 days" result (71.3% decontaminated) —
why is it higher than the comparable gap-size buckets (53-54%)?** Checked directly: the
"within 5 days" decontaminated subset draws from bigger real gaps (median 0.144R) than
the plain "0-2%" bucket (median 0.068R) — requiring the gap to close within a bounded
number of days implicitly selects for gaps that were closed at a real pace, not just
gaps that happened to be small. So the timing-based cut is not simply a noisier version
of the gap-size cut — it carries genuine extra information (how fast the distance was
covered, not just how far), which is likely the real, non-circular content of the
original finding.

**Corrected disposition**: the real, decontaminated, non-circular signal here is modest
— roughly a 45.8%-to-54% step for having any real gap that isn't instantly closed, and a
sharper, uncontaminated, and much more trustworthy 20.7% floor for "never clears at
all." The dramatic-looking large-gap numbers (63-84% FAST) were mostly or entirely
circularity. This is a smaller, more honest finding than first reported.

**Third round, per a further direct user challenge — a much sharper distinction than
circularity: is this even a PRE-ENTRY-usable feature at all?** Everything above (gap
size bucketed by "0-2%/2-5%/etc.") still secretly used the FUTURE to decide which bucket
a trade belonged to — a trade only landed in "0-2%" if the future price happened to
reach that level within 60 days; otherwise it fell into "never clears" regardless of
what its actual pre-known gap size was. That makes every version above a POST-ENTRY
observation ("did it clear, and how far/fast"), not something usable to decide whether
to take the trade in the first place — a genuine entry filter can only use information
that exists the instant the trigger fires, never "what happened afterward."

**Rebuilt correctly as a purely pre-entry, zero-future-information feature**: at the
exact moment of entry, both the 10-day high and 40-day high are already fixed numbers
from history — `static_gap_pct = (high40_prior / high10_prior - 1) * 100`, computed
directly, no forward search, defined for every trade regardless of what happens next
(n=9,387 of 9,430; the small remainder lack enough history for a 40-day window).

| Static pre-entry gap | n | FAST | FAKE |
|---|---|---|---|
| 0% (no gap) | 5,060 | 45.8% | 32.7% |
| **0-2%** | 1,646 | **55.0%** | 27.0% |
| 2-5% | 1,471 | 54.4% | 25.9% |
| 5-10% | 946 | 49.7% | 28.4% |
| >10% | 264 | 46.2% | 34.5% |

**This is a genuinely different shape from both earlier (post-entry-contaminated)
versions — a real, modest, PEAKED pattern** (best at a small-to-moderate gap, worse both
at zero gap and at a large gap), with zero circularity risk and zero future-information
leakage, since every value is knowable the instant the 10-day trigger fires. This is the
one version of this idea that is actually usable as a pre-entry filter candidate — the
"days to clear"/"observed gap size at time of clearing" versions from earlier in this
section are, at best, a post-entry early-warning signal, never an entry decision.

**Disposition, final for this sub-thread**: the purely pre-entry `static_gap_pct` (peaked
0-5%) is the one form of this idea worth carrying to Stage 2 as a real filter candidate.
The timing/observed-clearing versions stay logged above for the record (real
early-warning content, once decontaminated) but are explicitly NOT entry-filter
candidates — they answer a different question (what does the price path look like after
you're already in) and should not be confused with this one going forward.

**Not yet done**: Deliverable 3 (base descriptor dataset — pre-entry range/volume/ATR
contraction, tight-close statistics, pullback-depth sequence, time spent near highs,
base duration via the existing `_consolidation_days` from `live_checkpoint.py`).

## Stage 0 REBUILD — raw population as primary, BC v2 as secondary, 10D/20D/40D as independent alternative entries (2026-09-27)

Per critic's explicit final decision after the four corrections caught in the first pass
(recapped in the critic thread, not re-derived here): rebuilt Deliverable 1 and a
corrected Deliverable 2 on the RAW, ungated trigger population as primary, keeping BC v2
as a secondary comparison, and rebuilt the trigger-timing question correctly as three
INDEPENDENT alternative entry definitions (10D/20D/40D breach, each its own population),
not a side-feature layered on the existing 10D entry. Explicitly NOT a parameter sweep —
the question is whether the lookbacks represent different KINDS of trades, not which one
scores highest.

**Data source, per critic's explicit clarification**: no intraday data needed or used —
"N-day breakout" = `High[T] > prior N trading days' highest High`, purely from daily
OHLC (the same mechanism `detect_primed_entry` already uses). Full 5-year daily history
(2021-2026, no 2022-07-04 restriction — that cutoff was specific to BC v2's own canonical
dataset, not a data-availability limit here). Full NIFTY 500 universe. `ungated_recipe`
(no Trend/EMA34/Momentum/Fragility gate at all) via `population_builder.py` — same real
exit mechanics, same Gate/Exit Engine Integrity as every other population this weekend.

**Raw population sizes and outcome mix, three independent lookback definitions:**

| Lookback | n events | FAST | SLOW | FAKE | meanR | medianR | Meaningful Win |
|---|---|---|---|---|---|---|---|
| **10D** | 21,279 | **58.6%** | 16.2% | 25.1% | 0.056 | -0.001 | **37.5%** |
| 20D | 15,250 | 54.0% | 17.7% | 28.3% | 0.066 | 0.025 | 36.9% |
| 40D | 10,929 | 51.0% | 18.0% | 31.1% | 0.070 | 0.035 | 35.6% |

**The surprising, real answer to "did we tune ourselves to catch stalls by using a
10-day lookback": no — the opposite.** Event count decreases with lookback (as
expected — a longer high is harder to clear), but FAST rate DECREASES (58.6%→51.0%) and
FAKE rate INCREASES (25.1%→31.1%) as the lookback gets longer, not the reverse. The
10-day trigger is not the noisier, weaker, more stall-prone definition — on the specific
question of "does this reach meaningful continuation quickly," it is the best of the
three. What DOES improve with a longer lookback is the average magnitude (meanR
0.056→0.070, medianR -0.001→0.035) — a real, opposite-direction tradeoff: 10D gives more
opportunities with a higher hit-rate on quick continuation but slightly smaller average
size; 40D gives fewer, slower-to-confirm opportunities that are on average a bit bigger
when they do work. This is a real difference in trade KIND, not one lookback simply
being "better" — exactly the kind of finding critic said to look for, not chase as an
optimization target.

**Secondary comparison — what has BC v2's existing filter stack (Trend + EMA34 + Momentum
+ Fragility, T-1 gated) done to the raw 10-day opportunity set:**

| | n | FAST | SLOW | FAKE | meanR | Meaningful Win |
|---|---|---|---|---|---|---|
| RAW 10D (no filters) | 21,279 | 58.6% | 16.2% | 25.1% | 0.056 | 37.5% |
| BC v2 (filtered, T-1 gated) | 9,430 | 49.2% | 20.5% | 30.2% | 0.098 | 36.9% |

**BC v2's filters cut the population by more than half (21,279 -> 9,430) and, on this
specific FAST/SLOW/FAKE lens, make it WORSE, not better** — lower FAST rate (49.2% vs
58.6%), higher FAKE rate (30.2% vs 25.1%). What they DO improve is raw meanR (0.098 vs
0.056) — nearly double. Read plainly: BC v2's filter stack is selecting for bigger,
slower-to-confirm trades (more like the 40D-lookback character above) at the cost of
hit-rate on quick continuation, even though it was built around a 10-day trigger. This is
a real, measurable sign that BC v2's existing recipe (largely inherited from — and mostly
invalidated for — the old 15-day-hold framing) may be pulling the 10-day trigger's
naturally fast character toward something slower and more positional, exactly the
tension the user has been describing all weekend. Not yet a conclusion about causation
(which specific filter drives this needs its own check) — a clean, descriptive
observation, nothing promoted or gated.

**Not yet done**: MAE/MFE comparison across the three lookbacks, overlap analysis
between populations, and isolating which of BC v2's four filter conditions specifically
drives the FAST-rate degradation (candidate for a Stage 2 question, not Stage 0).

## Stage QS-E0 — Exit Philosophy Benchmark, first hypothesis tests (2026-09-27)

Per critic's explicit sequencing (literature expectations first, logged in
`EXIT_PHILOSOPHY_BENCHMARK.md`, before touching new data): testing QS-H1/H2/H3/H5
against data we already had (the raw 10D/20D/40D trajectory files built for the entry
comparison) — no new exit code, entry candidates unchanged, format is
Expectation -> Observed -> Verdict -> Implication throughout.

**QS-H1/H5 (early evidence / no 15-day rescue needed).**
Expectation: a genuine quick-swing breakout should show meaningful continuation within
roughly the first several sessions; if it routinely takes 10-15 days, the QS thesis is
in real doubt.
Observed, day of first 0.25R among trades that EVENTUALLY become winners:

| Lookback | median day | by D3 | by D5 | by D7 | by D10 |
|---|---|---|---|---|---|
| 10D | 2 | 69.9% | 80.8% | 88.0% | 94.2% |
| 20D | 2 | 64.7% | 76.9% | 84.8% | 91.9% |
| 40D | 2 | 63.5% | 76.1% | 83.5% | 92.2% |

**Verdict: AGREES, strongly.** Median time to real continuation is 2 days across all
three lookbacks; 76-81% of eventual winners show it within 5 days. **Implication**: this
directly reconciles what looked like a contradiction in yesterday's BC v2 work (the
`max_hold_cap` aggregate trajectory showed slow, continuous growth with a negative
median through day 6). That aggregate mixed FAKE trades (30%+ of the population, which
sit flat/negative the entire hold) in with real winners — once isolated to winners only,
continuation is fast, not slow. **The earlier "this looks positional" read was partly an
artifact of not separating winners from fakes before looking at the average trajectory**
— exactly the mixing problem labeling was built to solve.

**QS-H2 (early failure signature).**
Expectation: a failing breakout should reveal weakness early via weak closes and/or
adverse excursion, not just eventually.
Observed, median close_R and mae_so_far by day, eventual FAKE vs eventual WINNER:

| Lookback | Day | FAKE close_R | FAKE mae | WINNER close_R | WINNER mae |
|---|---|---|---|---|---|
| 10D | 1 | -0.055 | -0.168 | +0.093 | -0.072 |
| 10D | 3 | -0.115 | -0.293 | +0.206 | -0.125 |
| 20D | 1 | -0.053 | -0.152 | +0.081 | -0.062 |
| 40D | 1 | -0.050 | -0.142 | +0.084 | -0.052 |

**Verdict: AGREES, cleanly, from day 1.** FAKE and WINNER populations are already
separated on day 1 (opposite sign on median close_R, 2-3x deeper MAE for FAKE), and the
gap widens through day 3. **Implication**: this is a genuinely promising signal for
Type-A / momentum-absence detection — the separation is visible far earlier than the
5-day FAST cutoff itself, meaning an early-warning signal built on day-1/2/3 behavior is
plausible in principle. Not yet a rule — this is a population-level median comparison,
not a validated per-trade classifier, and it still needs the same rigor (decontamination,
robustness, capacity-constrained check) everything else this weekend has gone through.

**QS-H3 (healthy consolidation, don't kill a normal pause).**
Expectation: some real winners should show a temporary dip/pause before their eventual
move — advance/consolidation/expansion, not uninterrupted vertical movement.
Observed, among eventual winners, whether close_R ever goes negative in days 1-5:

| Lookback | % of winners with a dip in D1-5 | median depth of that dip |
|---|---|---|
| 10D | 50.4% | -0.0027 (negligible) |
| 20D | 50.8% | -0.0038 (negligible) |
| 40D | 49.5% | +0.0027 (essentially flat, not even negative at the median) |

**Verdict: PARTIALLY AGREES.** About half of eventual winners do show some early
wobble, consistent with normal digestion being real and not rare — but the typical dip
is tiny, not a real pullback. **Implication**: a management rule needs to tolerate
*shallow* early weakness without needing to tolerate *deep* early weakness — this data
doesn't yet tell us how a genuinely deep early drawdown among eventual winners behaves
(the tail of that dip distribution, not just the median), which is the more decision-
relevant question and isn't answered here yet.

**QS-H4 and QS-H6 (state-based exit, give-back after meaningful MFE) — not yet tested.**
These require conditioning on whether/when a trade has already produced a real impulse
(MFE crossing some threshold) and then looking at post-impulse behavior specifically —
a different cut of the data than the population-level day-by-day comparisons above.
Queued as the next test, not yet run.

**Disposition**: three of four testable hypotheses (H1/H5, H2, H3) show real, encouraging
agreement with the literature-derived expectations — the "fast momentum" quick-swing
thesis looks genuinely present in this breakout universe once winners and fakes are
separated, and early-day behavior carries real, visible signal. No exit rule has been
built from any of this yet, per the explicit Stage QS-E0 scope.

## Stop Definition Audit, complete — the earlier 10D/20D/40D "trade character gradient" was substantially a stop-width artifact (2026-09-27)

Per critic's explicit damage-assessment spec: computed three candidate initial-risk
definitions on the already-built raw 10D/20D/40D event populations, no new exit logic,
no optimization.
- **S0** = inherited 20-day structural low (the CONTROL — old/positional risk geometry)
- **S1** = breakout-day low (direct translation of Kullamägi's documented stop)
- **S2** = S1, excluding events where it exceeds ~1x ADR/ATR (per critic: a stop this
  wide may mean the opportunity doesn't belong in the strategy, not that it should be
  artificially tightened)

**Risk-width comparison, all three lookbacks:**

| Lookback | S0 median risk% | S1 median risk% | median S1/S0 ratio | % where S1 > 1xADR | % where S1<=0 (invalid, gap-through-trigger day) |
|---|---|---|---|---|---|
| 10D | 9.99% | 2.57% | 0.258 | 34.5% | 1.7% |
| 20D | 11.92% | 2.84% | 0.238 | 43.4% | 1.4% |
| 40D | 13.43% | 3.04% | 0.229 | 48.8% | 1.3% |

**S1 is roughly 4-5x tighter than S0** — exactly the magnitude critic predicted (the
same +3% move going from ~0.3-0.6R under S0 to ~1.2-1.5R under S1). S0's own risk width
ALSO increases with lookback (9.99%->13.43%), which is itself a real, previously
unexamined confound — a mechanically wider stop for longer-lookback entries would
inflate the apparent "40D produces bigger/slower trades" reading independent of any real
difference in trade behavior.

**FAST/SLOW/FAKE reclassified under S1 and S2 (n=1,995 excluded per lookback for
S1<=0 in the S1 columns; S2 additionally excludes the >1xADR events):**

| Lookback | n (S1) | FAST (S1) | SLOW (S1) | FAKE (S1) | n (S2) | FAST (S2) | FAKE (S2) |
|---|---|---|---|---|---|---|---|
| 10D | 20,917 | 79.9% | 8.1% | 12.0% | 13,573 | 85.5% | 8.0% |
| 20D | 15,030 | 79.8% | 8.2% | 12.0% | 8,408 | 86.4% | 7.3% |
| 40D | 10,788 | 79.6% | 8.3% | 12.1% | 5,453 | 86.6% | 7.6% |

**The gradient reported yesterday under S0 (FAST 58.6%->54.0%->51.0%, FAKE
25.1%->28.3%->31.1% as lookback increased) has LARGELY DISAPPEARED under the corrected
stop.** All three lookbacks now look nearly identical on this dimension (FAST ~80%,
FAKE ~12% under S1; FAST ~85-87%, FAKE ~7-8% under S2) — the differences between 10D,
20D, and 40D that looked like a real, meaningful "trade character" difference were
substantially an artifact of S0's own risk width mechanically varying with lookback,
not a genuine property of the entry definitions themselves.

**Per the Expectation Disagreement Rule**: this is squarely case (b), a measurement/
definition problem — R was being computed with a stop that itself confounded the
comparison, not a genuine finding about entry-definition character. The correct
disposition is NOT "10D/20D/40D are all secretly the same" as a new positive finding
either — it's "our prior comparison of them was measuring the wrong thing, and needs to
be redone honestly before any conclusion about entry-definition character can be
trusted."

**Also surfaced, a real edge case needing an explicit decision, not silently papered
over**: 1.3-1.7% of events have `S1<=0` — the entry price (trigger) sits BELOW that same
day's own Low, meaning the stock gapped through the trigger and traded entirely above it
all session (never touched the trigger level again intraday). "Breakout-day low" is not
a valid stop reference for these — excluded from this audit, but needs its own explicit
rule (e.g. use the trigger price itself, or the prior day's low, or exclude these from
the product entirely) before any real implementation.

**Everything built in yesterday's Stage 0 entry-comparison (the raw 10D/20D/40D FAST/
SLOW/FAKE table, the QS-H1/H2/H3 test verdicts) is QUARANTINED as measured under the
wrong stop convention, per the Risk-Unit Integrity Rule.** The raw event populations
themselves (which tickers/dates triggered, at what price) remain valid and reusable —
only the R-based outcome characterization needs rebuilding. Given the FAST/SLOW/FAKE mix
looks so similar across S1/S2 now, it's plausible (not yet confirmed) that QS-H1/H2/H3's
qualitative verdicts (fast continuation is real, FAKE separates early, some digestion is
normal) survive the correction even though the specific percentages do not — this needs
to be re-run properly, not assumed.

**Not yet resolved**: the exact stop definition to adopt going forward (S1 alone, or S2
with events failing the ADR cap genuinely excluded from the product, per critic's point
that a stop this wide may mean the trade doesn't belong in the strategy at all) — and
what to do about the S1<=0 edge case. Both need an explicit decision before rebuilding
Stage 0 for real.

## S1b — prior-day low, the practical decision-time-safe stop (2026-09-27)

Per direct user objection: S1 (breakout-day's own low) is impractical — the day is still
in progress at the moment of entry, so "today's low" isn't actually knowable when the
trade is taken; you could enter mid-session and the stock could make a fresh, lower low
afterward with no way to know it in real time. **S1b = prior day's Low** (the day BEFORE
the breakout) is fully known before the entry day even begins — genuinely
decision-time-safe, no lookahead of any kind.

**Checked the user's own stated concern first, before adopting this**: does the breakout
day routinely make a fresh lower low than the prior day (which would mean an S1b stop
gets hit constantly, often on the entry day itself)? **No** — only ~10% of the time
(9.7-10.6% across the three lookbacks) does the breakout day's own Low undercut the
prior day's Low. S1b is a workable, non-degenerate stop.

**Risk width, S0 vs S1b:**

| Lookback | S0 median risk% | S1b median risk% | S1b > 1xADR rate |
|---|---|---|---|
| 10D | 9.99% | 4.12% | 78.7% |
| 20D | 11.92% | 4.51% | 85.7% |
| 40D | 13.43% | 4.81% | 89.0% |

S1b is roughly 2.3-2.8x tighter than S0 (less dramatic than S1's 4-5x, but still a real,
substantial tightening). It does not satisfy the literature's "<=1xADR" ideal for the
large majority of trades (79-89%) — a real, disclosed tension between decision-time
validity (favors S1b) and matching the documented Kullamägi stop width exactly (favors
S1, which isn't practically executable from daily bars). Flagged, not yet resolved —
likely reflects a genuine gap between his live intraday execution and our daily-bar
reconstruction, not a bug.

**Correction (2026-09-27, caught by direct user challenge — "does calculating invalid
rate even make sense with the new SL mechanism?")**: an earlier version of this entry
reported "S1b has zero invalid cases (unlike S1's 1.3-1.7%)" as if it were an empirical
validation of S1b. It is not — for S1b, `initial_risk_pct <= 0` is mathematically
impossible, not just empirically rare. `entry_price` is derived from `high_prior`, the
highest High over a lookback window that always includes the prior trading day itself;
so `high_prior >= prior_day's High >= prior_day's Low = initial_stop_price`, and
`entry_price = high_prior * 1.005` is therefore always strictly greater than
`initial_stop_price` by construction. A 0% "invalid rate" for S1b is a tautology, not a
finding, and the comparison to S1's real 1.3-1.7% (which IS meaningful, since the
breakout day's own low is genuinely unconstrained by the trigger-price formula) was a
false equivalence. The check that IS meaningful and stays valid: whether the breakout
day's own Low undercuts the prior day's Low (~10%, reported above) — that's the real
answer to "would this stop constantly get hit same-day," not the invalid-rate number.

**FAST/SLOW/FAKE reclassified under S1b:**

| Lookback | n | FAST | SLOW | FAKE |
|---|---|---|---|---|
| 10D | 21,279 | 75.4-76.4% (76.4) | 9.6% | 13.9% |
| 20D | 15,250 | 76.0% | 9.7% | 14.3% |
| 40D | 10,929 | 75.4% | 9.8% | 14.8% |

**Confirms the S1 finding holds under the practical, decision-time-safe stop too**: FAST
rate is ~75-76% across all three lookbacks, essentially flat — the "10D vs 40D character
gradient" reported under the old S0 stop does not reappear under S1b either. This is now
the standing candidate stop for the QS product going forward (S1 remains logged as a
reference point but is not practically executable from daily-bar data).

## Stage 1 — canonical `qs_stage0` immutable dataset built (2026-09-27)

Per critic's exact spec after the Stop Definition Audit review: one canonical dataset,
storing ONLY immutable fields, becomes the sole source of truth for all future QS
research. No script downstream of this one is allowed to compute its own stop (this is
Rule #20 / Risk Unit Integrity's storage-level enforcement, not just a written rule).

Built via `rq_qs_stage0_build.py` (scratchpad), re-deriving entry_price and the S1b stop
directly from raw daily bars per event (self-contained, no dependency on the earlier
qs_raw_*/qs_s1b_* intermediate files going forward). Output: `qs_stage0_{10,20,40}d.csv`
→ merged `qs_stage0_full.csv`.

**Schema**: `ticker, entry_date, entry_definition (10/20/40), entry_price,
initial_stop_price (S1b = prior trading day's Low), initial_risk_pct, adr_pct,
adr_multiple_of_stop (telemetry only, not a filter), day1_high/low/close ...
day15_high/low/close, days_available`. Deliberately does NOT store FAST/SLOW/FAKE, exit
date, pnl_pct, or r_multiple — those are all either BC's own exit-engine decisions (a
different product, different stop) or derived research views that must never become a
stored, load-bearing artifact again.

**Verification against the pre-audit numbers (sanity check, not new research)**:

| Lookback | n | median initial_risk_pct | >1xADR | trajectory <15 sessions |
|---|---|---|---|---|
| 10D | 21,279 | 4.12% | 78.7% | 0.2% |
| 20D | 15,250 | 4.51% | 85.7% | 0.1% |
| 40D | 10,929 | 4.81% | 89.0% | 0.1% |

Every number matches the earlier S1b audit exactly (population sizes, median risk,
>1xADR rate) — confirms the rebuild is consistent with what was already reported, not a
new/different result. No nulls in any immutable field. The <0.2% "short trajectory"
cases are corp-action breaks or genuinely running out of history near the end of the
5-year window — expected, not a bug.

**Note**: the earlier "invalid rate (risk<=0)" column has been dropped from this table —
it was 0.00% for every lookback, but that is guaranteed by construction under S1b (see
the correction note in the S1b section above), not a result worth verifying or citing
again. No new check has replaced it; the earlier "~10% of breakout days undercut the
prior day's low" check (S1b section above) remains the real, meaningful safety check for
this stop, and is unaffected by this correction.

**Disposition**: Stage 1 complete. `qs_stage0_full.csv` (scratchpad) is now the canonical
QS dataset. Stage 2 (exit philosophy — Impulse/Failure branches, Breakout Exhaustion
Audit, per critic's roadmap) has NOT been started — this stage was purely the immutable-
dataset build, per the "freeze the layer below before researching above it" discipline
this whole weekend's integrity bugs have been teaching.

## Stage 1 (Breakout Exhaustion Audit) — anatomy timestamps built, no exits yet (2026-09-27)

Per critic's exact spec: `qs_anatomy_full.csv` (n=47,458, matches `qs_stage0` exactly)
computes, for every event, WHEN (not whether-to-exit) each candidate anatomy signal
first occurs. No expectancy, no exit rule, purely descriptive.

| Event | Present | Median day (10D/20D/40D) |
|---|---|---|
| Peak close (hindsight only, not decision-time) | 100% | 8/8/8 |
| Peak high (hindsight only, not decision-time) | 100% | 7/8/8 |
| First close below EMA8 | 89-91% | 5/5/6 |
| First inside day | 93.5-93.8% | 3/3/3 |
| First bearish outside day (range expands both sides, closes down) | 56.2-56.5% | 7/7/7 |
| First confirmed lower high (K=2 symmetric, mirrors the existing swing-low trail lag exactly) | only 30.6-30.7% | peak day 10, confirm day 12 |

`n_confirmed_swing_highs` (10D): 0 swings 5.0%, 1 swing 38.0%, 2 swings 45.0%, 3+ 12.0%.

**Decision, flagged rather than made silently**: only ~31% of events produce a confirmed
lower high within the 15-day window, and even then it clusters right at the boundary
(day 10-12) — plausibly a window-truncation effect, not evidence lower highs are rare.
Decided NOT to extend the window (stays at 15 days, matching the product's own 10-day
absolute ceiling) — sent to critic for review rather than assumed correct.

## QS-E1 / QS-E1A — Yesterday's-Low Trail, anatomy audit (2026-09-27)

New candidate exit mechanism, proposed directly by the user: extend the S1b entry-stop
logic (prior trading day's Low) into an ongoing trail for the whole trade — each day's
operative stop = max(previous stop, prior day's own Low), ratcheting up only, active from
day 1 with no delay (Version A, the required control per Rule #19 before any buffered/
delayed variant is tested). Critic promoted this to QS-E1 immediately as "the first exit
idea in weeks worth building before looking at results" — parameter-free, fully
decision-time-safe (today's stop is fixed by yesterday's already-completed Low), and
taxonomically a **Trend-family** exit (ride until structure breaks), not a Failure-family
one — to be judged on winners-preserved/drawdown-reduced, not on catching fakes.

Per critic's explicit instruction: anatomy audit ONLY first (`qs_e1a_full.csv`,
n=47,458, matches exactly) — no expectancy, no backtest, just when this mechanism would
first fire relative to the trade proving itself (+0.25R) and its own eventual peak.

**Results, all three lookbacks — again nearly identical:**

| Metric | 10D | 20D | 40D |
|---|---|---|---|
| Median hit day | 2 | 2 | 2 |
| Day-1 whipsaw rate | 27.4% | 26.6% | 25.8% |
| Never hit within 15 days | ~0.02% | ~0.01% | ~0.01% |
| Stopped before ever reaching +0.25R | 42.1% | 42.5% | 42.3% |
| Stopped before eventual peak high | 68.1% | 68.4% | 68.0% |
| Among eventual +0.25R reachers, stopped on/before that day anyway | 32.7% | 32.9% | 32.3% |

**Verdict: Version A, as specified, is not usable as-is.** This is the correct, necessary
control result, not a wasted test — critic explicitly required Version A be tested before
any buffered/delayed variant (Rule #19 discipline). Median exit is day 2; essentially
every trade (99.98%+) gets stopped within the 15-day window; a quarter are killed on the
very first day; roughly a third of trades that would have gone on to prove themselves get
killed first. This directly confirms the risk flagged before running it: the anatomy
audit's own 93.7%-by-day-3 inside-day rate (mostly harmless digestion, per QS-H3) is more
than enough to trip a zero-buffer, zero-lag daily ratchet. Sent to critic with this
baseline for the next decision: buffer the level, delay activation, or treat this
specific mechanism as falsified and look to a smoothed/confirmed version instead (e.g.
BC's existing K=2 swing-low convention, at QS's own tighter horizon).

## QS-E1A Failure-Information Audit — decisive result (2026-09-27)

Per critic's exact spec: does the yesterday's-low break carry genuine early-failure
information, or is it noise? Counterfactual test — for every E1A stop, using the
trade's real, unconstrained trajectory (ignoring the stop) to see what actually happened
afterward. `qs_e1a_failure_info_audit_full.csv` (n=47,458, merged from qs_stage0 + qs_e1a
+ qs_anatomy, matches exactly).

**The decisive cut**: split every stop by whether the trade had ALREADY reached 0.25R
before the stop fired (removing the "this is just profit-taking on an already-proven
winner" confound). Among trades that had NOT yet proven themselves at the moment of the
stop — the real candidates for "did we catch a genuine failure":

| Stop day | 10D eventual ≥0.25R | ≥0.5R | ≥1R |
|---|---|---|---|
| 1 | 60.5% | 52.3% | 39.0% |
| 2 | 58.4% | 49.3% | 32.7% |
| 3 | 60.4% | 50.0% | 31.9% |
| 4 | 56.0% | 46.2% | 24.2% |
| 5 | 48.3% | 41.4% | 31.0% |

20D and 40D show the same magnitude (55-60% at every stop-day bucket) — flat, no
lookback-specific difference, consistent with everything since the stop correction.

**Verdict: Case B — noise, not a useful failure signal, per critic's own pre-declared
framework.** Roughly 55-60% of trades cut before proving themselves would have gone on
to reach the meaningful-win threshold anyway if left alone, essentially unchanged
whether the stop fires day 1 or day 5 — there is no day where this signal becomes
trustworthy. A rule whose typical "you got stopped" outcome is "you were probably fine"
is not detecting genuine structural failure.

**Supporting evidence, same direction**: the at-stop snapshot shows later stop-day
buckets are increasingly just profit-taking on already-proven winners
(`pct_had_hit_025_before_stop`: 21.4% at day 1 -> 97.5%+ by day 5), not failure
detection — shrinking the genuinely-informative-early-stop pool further. The inside-day
interaction shows the OPPOSITE of the "harmless digestion" hypothesis (stops preceded by
an inside day have a slightly LOWER eventual win rate, 84.2% vs 86.6% for 10D) though the
gap is small and not decomposed by stop-day bucket, so not leaned on heavily here.

**Disposition, per critic's pre-declared decision tree**: Outcome 1 — kill this specific
mechanism (raw 1-day-lag yesterday's-low ratchet). Do NOT buffer it, do NOT delay its
activation — both would just be tuning a mechanism already shown to carry little
information, not learning anything new (per critic's explicit warning against this).
QS-E1/QS-E1A closed as a real, useful negative result (Rule #17 — log as closed, don't
reopen under a new name later) — the underlying "loss of yesterday's low, 1-day lag, no
context" event does not distinguish genuine breakout failure from ordinary noise in this
universe. Does not (yet) rule out a smoothed/confirmed version (e.g. K=2-style) or a
context-conditioned version (e.g. only meaningful after a prior real impulse, closer to
QS-H4/H6's state-based idea) — those are different, untested claims, not resurrections of
this one.

## Time-to-2R/3R audit (2026-09-27) — per direct user question, checking a real gap against Kullamägi's documented mechanism

Not yet computed anywhere this session — user asked directly whether we'd checked how
long it takes to reach 2R/3R, and estimated (from eyeballing the E1A audit's
`mean_eventual_MFE` column) that a majority of trades don't reach 3R even after 10 days.
Checked properly using `qs_stage0`'s stored day1-15 High trajectory (High-based R,
consistent with the FAST/SLOW/FAKE convention), no lookahead — first day_idx where R
crosses 2.0 and 3.0, per event.

| Lookback | Reaches 2R ever (15d) | by day 10 | Reaches 3R ever (15d) | by day 10 | Median day among 3R-reachers |
|---|---|---|---|---|---|
| 10D | 37.0% | 29.1% | 22.1% | 15.6% | 7 |
| 20D | 34.8% | 26.5% | 20.1% | 13.7% | 8 |
| 40D | 33.0% | 24.9% | 18.1% | 12.4% | 8 |

**The user's instinct was right, and the real number is starker than the eyeballed
estimate**: 84-88% of trades do NOT reach 3R within 10 days (only 12.4-15.6% do), and
even given the full 15-day window, still only ~18-22% ever reach 3R at all.

**Why this matters architecturally, not just descriptively**: Kullamägi's documented
partial-profit mechanism triggers at 3-5 sessions OR 2-3R, whichever comes first. Given
the product's own stated horizon (3-5 day target, 10-day absolute ceiling per the draft
v0.2 product definition), this data shows the R-based side of that trigger would rarely
ever fire within the product's realistic window in this universe — the calendar side
(3-5 sessions) is doing nearly all the work. This is a real, disclosed gap between his
literal mechanism and what this specific universe/entry-definition combination actually
produces, not yet resolved (does the product need a lower partial-profit R threshold,
e.g. 1R or 1.5R, to actually be reachable in a realistic window — or does 2-3R only make
sense for the minority of trades that DO run that far, with everything else exiting on a
different rule entirely). Sent to critic for review before building any profit-taking
rule around a 2-3R assumption.

## S1 vs S1b — how much of the 2R/3R reachability gap is stop-width, not weak price action (2026-09-27)

Per direct user question: is the low 2R/3R reachability rate (previous section) largely
an artifact of S1b being a wider risk unit than what Kullamägi's own literal mechanism
uses (S1, breakout day's own low, ~1.6x tighter median)? Checked by rescaling the SAME
day1-15 High trajectory using `s1_risk_pct` (from the earlier Stop Definition Audit's
`qs_stop_audit_{lb}d_full.csv`, merged on ticker+entry_date, excluding the known
~1.3-1.7% S1<=0 invalid cases) instead of `initial_risk_pct` (S1b) as the denominator —
no re-walking of price data, same mechanism as every earlier S0/S1/S1b rescaling.

| | S1b (current, prior-day low) | S1 (Kullamägi's literal stop) |
|---|---|---|
| 2R reached ever (15d) | 33.0-37.0% | **50.0-54.5%** |
| 2R by day 10 | 24.9-29.1% | **42.4-47.1%** |
| 3R reached ever (15d) | 18.1-22.1% | **35.8-40.6%** |
| 3R by day 10 | 12.4-15.6% | **28.7-33.1%** |
| Median day to reach 3R (among reachers) | 7-8 | **5** |

**Confirmed, and substantial**: under S1's tighter denominator, 3R reachability roughly
doubles and the median day to reach it (5) lines up closely with Kullamägi's own stated
3-5 session window — whereas S1b's median day (7-8) sits noticeably past it. A real part
of "2-3R feels rare here" is that S1b is a genuinely wider risk unit than what his
mechanism's round numbers were calibrated against, not that the underlying price moves
are structurally smaller in this universe.

**Does NOT change the stop decision**: S1 remains impractical (not decision-time-safe —
the breakout day is still in progress at the moment of entry). This is a measurement/
translation finding, not a reason to revert S1b. Sent to critic alongside the original
reachability finding. A possible future resolution — an intraday-derived stop, tighter
than S1b but still decision-time-safe using only information available up to the moment
of breach — is explicitly parked, not pursued now (see `PARKING_LOT.md`, item 8): this
needs intraday-data tests to even be meaningful, which is a larger scope decision the
user explicitly did not want to jump into opportunistically mid-thread.

## Milestone → subsequent-trajectory / give-back audit (2026-09-27)

Per critic's exact spec: once a QS trade demonstrates X profit (0.25R/0.5R/1R/2R,
High-based, on the operating S1b risk unit — S1 rescaling deliberately NOT used here,
kept as a separate logged reference per critic's explicit safeguard), what normally
happens next? Purely descriptive, no threshold optimization, no new stop, no intraday
work. `qs_milestone_giveback_full.csv` (n=47,458).

**Note on a bug caught mid-analysis**: the first pass mis-aggregated a boolean flag
column (an `apply(..., result_type='expand')` dtype quirk — mixed True/False/NaN ended
up uncomputable via a naive `.mean()`), which silently produced 0.0% for every
"continues to 2x" cell. Caught before reporting by re-deriving the summary from the
saved CSV with explicit bool coercion — the numbers below are the corrected version.

**10D results (20D/40D nearly identical in shape, logged in the CSV):**

| Milestone | Reached | Median day | Median subseq. MFE | Median max giveback after | % net negative @ day15 | % holds gain @ day15 | % reaches 2x milestone | Median days milestone→peak |
|---|---|---|---|---|---|---|---|---|
| 0.25R | 86.1% | 1 | 1.717R | 1.966R | 39.5% | 54.3% | 91.2% | 5 |
| 0.5R | 78.5% | 1 | 1.882R | 1.951R | 34.6% | 52.9% | 79.8% | 5 |
| 1R | 62.6% | 3 | 2.320R | 1.945R | 25.1% | 51.0% | 59.0% | 4 |
| 2R | 37.0% | 6 | 3.334R | 2.025R | 12.9% | 50.9% | 35.9% | 2 |

**Three real, disclosed observations:**

1. **Early proof strongly predicts further continuation** — 91.2% of trades reaching
0.25R go on to reach 0.5R; even after a full 1R, 59.0% go on to double it. Strong
evidence for "let winners run," not fixed-target profit-taking.

2. **Give-back magnitude is oddly constant across milestones (~1.7-2.0R median), not
proportional to how far the trade has already run.** A trade up only 0.25R and one up
2R show a similar typical worst pullback afterward. Real design implication: a
percentage-of-peak give-back rule would behave very differently by milestone, whereas a
roughly fixed-R give-back cushion may fit better. NOT disentangled from a remaining-
window-length confound (later milestones leave fewer days before the 15-day cutoff,
mechanically capping observable giveback) — flagged, not resolved.

3. **Real early success still frequently gives back to a net loss by the window's end**:
25.1% of trades that reach a full 1R end up net negative by day 15's close — matches the
user's own real Aegis Logistics experience (proven move, given back entirely). Reinforces
give-back protection as a genuine need.

**Caveat on `pct_holds_gain` (~51-54%, oddly flat across all milestones)**: measures
whether Close is still above the milestone AT THE ARBITRARY 15-DAY WINDOW BOUNDARY, not
at any sensible exit point — a blunt snapshot, weighted less than the other columns.

**Disposition**: descriptive only, per critic's explicit "don't optimize a threshold,
understand the trajectory" instruction. Sent to critic; per critic's stated plan, once
reviewed this closes the profit-taking-philosophy question at the concept level (capture
first impulse, let proven winners extend, protect against meaningful giveback — not an
imported fixed 2R/3R target) and the project returns to the Momentum/Failure family
roadmap next.

## QS Profit Management (renamed from "profit-taking philosophy") — closed at the concept level (2026-09-27)

Per critic's review of the milestone/give-back audit. Sharpened conclusion, replacing
the earlier draft wording: **"QS should seek to capture the first continuation impulse,
allow demonstrated winners room to extend, and manage exits around meaningful loss of
accumulated progress rather than impose an imported fixed 2R/3R target. The appropriate
definition of 'meaningful give-back' remains an open exit-design question."**

**Renamed the research area, per critic**: not "profit-taking" (too narrow — implies a
scale-out/target mechanism specifically) but **QS Profit Management / Winner
Management** — the real objective is "don't let a trade that has demonstrated a
meaningful move turn into a large loss, while not strangling the continuation that made
the trade attractive in the first place," which could resolve as no fixed target, a
structural-failure exit, a give-back exit, or some combination — not decided yet.

**Three evidence-backed principles carried forward** (established, not to be re-litigated
without new evidence):
1. Early proof should generally earn a trade more room, not an automatic target exit —
   well-supported descriptively (91.2% of 0.25R-reachers go on to 0.5R; the subsequent-
   MFE progression 1.717R→1.882R→2.320R→3.334R across milestones is coherent).
2. 2R/3R remain literature benchmarks to compare against, not imported QS thresholds —
   the S1-vs-S1b translation gap (this same day) is exactly why importing them literally
   would be a mistake.
3. Meaningful give-back/failure is a legitimate exit problem (25.1% of 1R-reachers still
   net negative at day 15 — the Aegis Logistics pattern, now quantitatively real), but
   its exact implementation is UNRESOLVED, not just uncalibrated.

**Explicitly parked, not resolved**: the constant-~2R-median-giveback observation is
real evidence, not yet a conclusion — it's confounded by remaining-observation-window
length (later milestones have fewer days left before the 15-day cutoff, mechanically
capping observable giveback). Per critic's explicit call: do NOT investigate this now —
"we're currently answering what QS profit-management philosophy should target, not what
exact give-back threshold to use." Revisit only when actually designing the give-back
exit mechanism itself, using a time-normalized/fixed-horizon framework at that point, not
before. Research sequence stays clean: philosophy -> mechanism -> event definition ->
implementation -> calibration — don't skip from a descriptive statistic straight into
threshold tuning.

**Disposition**: QS Profit Management closed at the concept level. Returning to the
Momentum/Failure exit-family roadmap next (Failure: Momentum Absence / Return-to-Breakout
/ Structural Failure; Momentum: Give-back / Confirmed-LH / Major-resistance / Scale-out) —
not yet started.

## F1 — Return-to-Breakout anatomy + Failure-Information Audit (2026-09-27)

Per critic's exact spec: pure event/trajectory audit, not an exit strategy. Trigger level
frozen at `entry_price` (unchanged from every other calculation this line), no
recalculation afterward. Two threshold-free telemetry variants (per critic's explicit
"don't pick a meaningful-penetration threshold yet"): `first_day_touch_trigger` (Low <=
entry_price) and `first_day_close_below_trigger` (Close < entry_price), with continuous
penetration depth recorded, not collapsed into a bucket. `qs_f1_return_to_breakout_full.csv`
(n=47,458). Same bug-guard applied as the milestone audit (explicit bool coercion on the
flag columns before aggregating) — verified correct before reporting.

**Added a proper unconditional baseline first** (missing from the earlier E1A audit,
worth having for comparison): net-negative-at-window-end rate for the WHOLE population,
no event conditioning at all — **~47-48% across all three lookbacks**.

**10D results (20D/40D nearly identical):**

| Event | Occurs | Median day | Median depth | Subgroup | Subseq. eventual >=0.25R | Net negative @ window end |
|---|---|---|---|---|---|---|
| Touch (Low<=trigger) | 91.6% | 1 | 1.78% | NOT yet proven (45.9% of touches) | 66.9% | **59.9%** |
| | | | | ALREADY proven (54.1%) | 99.0% | 45.7% |
| Close below trigger | 81.9% | 1 | 1.36% | NOT yet proven (48.7%) | 65.1% | **61.0%** |
| | | | | ALREADY proven (51.3%) | 92.4% | 56.1% |

**Reading it**: most retests of the breakout level happen (both events, ~92%/~82% of all
trades, almost always by day 1) — but MOST of them (54.1% of touches) occur AFTER the
trade has already proven itself (0.25R), i.e. a normal healthy pullback, and that
subgroup's net-negative rate (45.7%) sits right at/slightly below the ~48% baseline —
nothing concerning there. The genuinely interesting subgroup is the ~46-49% of retests
that happen BEFORE the trade has proven itself: net-negative rate 59.9-61.0%, a real
**12-13 percentage-point elevation above the unconditional baseline**. This is a
meaningfully different result from E1A, whose Failure-Information Audit showed
essentially NO differentiation from baseline regardless of timing (flat 55-60% across
every stop-day bucket, matching a plausible coin-flip-ish base rate — though a proper
unconditional baseline for E1A's exact metric was never explicitly computed either,
flagged as a gap in that earlier audit).

**Disposition**: Case A candidate (genuine information), tentatively, sent to critic
before drawing a firm conclusion — has NOT been checked for a timing confound analogous
to what E1A's stop-day-bucket cut needed (e.g. does the "not yet proven" subgroup skew
toward earlier or later occurrence days in a way that could itself explain part of the
elevation). Not yet an exit rule — purely descriptive, per Stage-1-before-mechanism
discipline.

## F1 timing-normalization audit — survives, decisively (2026-09-27)

Per critic's exact spec: does the pre-proof retest penalty survive an AGE-MATCHED
comparison (not the unconditional baseline), given proof-status is path-dependent and
naturally enriches the pre-proof group for early events? Survival-style matched design —
at each day bucket, compare trades whose (first) touch/close-below event falls in that
bucket against the "at-risk" control (still not-yet-proven, not-yet-touched, but not
touched in this bucket), both measured forward from the same age. `rq_qs_f1_timing_normalized.py`.

**Because incidence is so high (91.6%/81.9%), both events are dominated by Day 1** — 76%
of the entire population touches the trigger level on day 1 alone, leaving almost no data
for D2+ on Touch specifically (5-8 events). Close-below spreads a bit further (D2 n~200-
430, D3 n~17-49) but D1 remains the only well-powered bucket for either.

**D1 comparison, 10D (20D/40D consistent — see CSV for full tables):**

| Event | Group | n | Subseq. eventual ≥0.25R | ≥0.5R | ≥1R | ≥2R | Net negative @ window end |
|---|---|---|---|---|---|---|---|
| Touch | Touched | 16,169 | 81.7% | 71.9% | 54.1% | 29.3% | 53.4% |
| | Control (not touched day1) | 5,110 | 100.0% | 99.4% | 89.5% | 61.1% | 30.2% |
| Close-below | Touched | 10,802 | 73.2% | 61.7% | 44.6% | 23.3% | 59.5% |
| | Control (not touched day1) | 10,477 | 99.4% | 95.8% | 81.1% | 51.0% | 35.9% |

**Verdict: SURVIVES, decisively — and the gap is LARGER (23-25pp net-negative), not
smaller, than the naive unconditional-baseline comparison (12-13pp)**, consistent across
all three lookbacks (40D D1: 59.4% vs 34.0%; 20D: 58.8% vs 35.3%). This is genuine
information (Case A), not an artifact of the pre-proof group simply being younger/
earlier on average — the confound critic flagged does not explain the effect away.

**Winner-preservation check retained, per critic's explicit "this must be first-class,
not an afterthought" instruction**: even in the touched group, 54.1% (touch) / 44.6%
(close-below) still go on to reach a full 1R, and 29.3%/23.3% reach 2R. Real, meaningful
signal, but NOT a clean binary failure marker — a rule that exits every Day-1 touch would
sacrifice roughly half the touched population's eventual winners.

**D2+ buckets**: too thin to trust for Touch (n=5-8). Close-below has slightly more (D2
n~200-430, showing a similar but somewhat smaller gap, e.g. 10D D2 netneg 55.7% touched
vs 38.3% control); D3+ (n<50) not reportable as anything beyond noise.

**Disposition**: F1 (specifically Touch-Day-1 and Close-below-Day-1) is alive and
promoted to the next stage per critic's decision tree — a real Failure-family candidate,
not yet an executable rule. D2+ timing for close-below flagged as a secondary, thinner
signal worth keeping in view but not yet load-bearing. Sent to critic with full numbers
and the winner-preservation stats before any exit-rule design begins.

## QS Momentum/Failure Discovery batch — F2 through F6 (2026-09-27)

Per critic's explicit batch instruction (discovery stage, not tuning — classify
definitions by mechanism first, let performance inform after; no threshold
optimization, no exit simulation, no K=2). All results below computed on the full
`qs_stage0` + `qs_e1a` + `qs_anatomy` + `qs_f1_return_to_breakout` merge (n=47,458).
10D shown throughout; 20D/40D consistent in shape (full numbers in
`batch_f2_f6_output.log`).

### F2 — Momentum Absence: three decision-time-safe candidate definitions

- **MA1** (`close_R <= 0` through day D — hasn't even recovered to entry price):
  incidence stable ~50-51% regardless of D. **Discriminating power GROWS with D**:
  D2 gap (flagged vs control) 39.3% vs 81.2% reach 1R; D3 35.7% vs 82.3%; D5 28.8% vs
  82.9%. Net-negative gap widens from ~29pp (D2) to ~43pp (D5). Clearest, cleanest
  candidate.
- **MA2** (no new high vs day 1's high, through day D): incidence falls with D
  (55.4%→33.4%). Real but weaker separation than MA1, and heavily overlapping it
  (67-77% of MA2-flagged trades are also MA1-flagged) — largely redundant.
- **MA3** (zero up-close-days through day D): incidence collapses with D
  (52.5%→7.4%) — becomes a rare, extreme tail at D5, low overlap with MA1/MA2 there
  (13-17%), and that tail is severe (78.4% net negative at D5). Distinct mechanism from
  MA1/MA2, not just a stricter version of the same thing.

**Disposition**: MA1 ("no positive close yet") is the standout candidate — simplest,
cleanest, and the ONLY one whose signal strengthens the longer it persists. MA2 mostly
redundant with MA1. MA3 real but a rare tail, worth keeping in view as a distinct
extreme marker, not a primary definition.

### F3 — F1 (Touch, Day 1) × Momentum Absence (MA1, Day 3) interaction

The highest-value audit in the batch, per critic. Four states, evaluated as of day 3,
outcome measured from day 4 forward:

| State | n (10D) | % of population | Subseq. ≥1R | Net negative |
|---|---|---|---|---|
| No F1 + momentum present | 4,355 | 20.5% | 88.1% | 25.5% |
| F1 + momentum present (pullback) | 6,100 | 28.7% | 78.2% | 34.1% |
| No F1 + momentum absent (stalled) | 755 | 3.5% | 42.8% | 57.4% |
| F1 + momentum absent (candidate failure) | 10,069 | 47.3% | 35.2% | 65.2% |

**Confirms critic's hypothesis cleanly**: combining both signals produces a materially
worse group than either alone (65.2% net negative vs 34.1% for F1-alone-with-momentum,
vs 57.4% for momentum-absence-alone-without-F1) — real evidence the two signals add
information beyond each other, not just double-counting the same thing. **Important
caveat, not to be glossed over**: this "candidate failure" state is 47.3% of the ENTIRE
population — not a rare tail. Any mechanism built on it would be flagging nearly half of
all breakouts, with 35.2% of that huge group still reaching 1R (real winner-sacrifice
concern, same shape as every prior candidate this weekend).

### F4 — Confirmed Lower High failure-information audit (using confirm day, not peak day)

| Group | n (10D) | % of pop | Subseq. ≥1R | Net negative |
|---|---|---|---|---|
| NOT yet proven before LH-confirm | 912 | 4.3% | **3.4%** | **92.4%** |
| ALREADY proven before LH-confirm | 5,629 | 26.5% | 38.1% | 52.1% |
| No confirmed LH at all in window | 14,738 | 69.3% | 64.5% | 43.5% |

**The "not yet proven" subgroup is close to a deterministic failure marker** — 92.4% net
negative, only 3.4% ever reach 1R. Small population (4.3%), structurally different in
character from F1 (F1 = high-incidence/moderate-precision; this = low-incidence/very-
high-precision). Worth carrying forward as a distinct, high-confidence marker, separate
from F1.

### F5 — Anatomy synthesis matrix (all events, one comparable table)

| Event | Incidence | Median day | Net-negative gap (occurred − control) | Winner sacrifice (occurred group still ≥1R) |
|---|---|---|---|---|
| EMA8 break | 91.2% | 5 | +53.2pp | 45.0% |
| Inside day | 93.5% | 3 | **+0.2pp** | 56.0% |
| Bearish outside day | 56.2% | 7 | +9.3pp | 47.4% |
| Confirmed LH (confirm day) | 30.7% | 12 | +13.4pp | 33.3% |
| F1 Touch | 91.6% | 1 | +52.3pp | 53.6% |
| F1 Close-below | 81.9% | 1 | +58.2pp | 43.1% |

**Inside day is now decisively CLOSED as a failure signal** (+0.2pp, essentially zero) —
matches QS-H3's "harmless digestion" finding exactly, no new evidence needed to reopen
this. **EMA8 break shows a large gap but fires late (day 5) and is likely partly
tautological** — its "never breaks EMA8" control is an extreme, cherry-picked best-case
8.8% tail (near-100% win rate is close to definitional for a trade that never showed ANY
weakness in 15 days) — flagged as real but low-actionability for EARLY failure detection
specifically. Bearish outside day: modest, real, later, secondary signal. F1 Close-below
edges out Touch on raw gap size (+58.2pp vs +52.3pp), supporting the severity-hierarchy
framing (Touch = under pressure, Close-below = under stronger pressure) rather than
picking one over the other.

### F6 — Failure-state trajectory audit (around F1 Touch-Day-1)

At the moment of touch (10D): mean close vs entry -0.97%, mean MFE-so-far 0.238R, mean
adverse excursion -0.593R. Only 36.3% reclaim the trigger level (close > entry) the
very next day.

| Group | n (10D) | Subseq. ≥1R | Net negative |
|---|---|---|---|
| Reclaims next day | 5,863 | 77.9% | 37.1% |
| Does NOT reclaim next day | 10,306 | 39.1% | 62.8% |

**A powerful refinement — this is exactly the "temporary violation vs. genuine
breakdown" distinction that killed E1A, and here it works cleanly.** Reclaiming the
trigger level the next day nearly restores baseline-like outcomes; failing to reclaim
compounds the risk substantially. Worth carrying forward as a near-term confirmation
layer on top of F1, not yet built into any rule.

### Batch disposition summary (critic's requested tags)

- MA1 (Momentum Absence): **survivor**, new finding, strengthens over time.
- MA2: **partially redundant** with MA1.
- MA3: **survivor**, distinct extreme tail, not primary.
- F1 × MA1 interaction: **survivor**, new finding, but the flagged state is huge (47%
  of population) — not a rare tail.
- Confirmed LH (not-yet-proven subgroup): **survivor**, new finding, high-precision/
  low-recall, structurally distinct from F1.
- Inside day: **closed-negative** (confirms QS-H3, no reopening without new evidence).
- EMA8 break: **survivor but flagged** — real gap, late timing, likely partly
  tautological, low early-actionability.
- Bearish outside day: **survivor**, modest, secondary.
- Reclaim-next-day (F6): **survivor**, new finding, powerful confirmation layer on F1.

Nothing built into an exit rule yet — per the batch's explicit scope, this stays
architecture/discovery. Sent to critic as one combined report, per their own request.

## Final discovery check — F1/MA1/reclaim/LH overlap + evidence-ladder audit (2026-09-27)

Per critic's exact spec, the last discovery check before Failure-family exit design.
`rq_qs_overlap_state_transition.py`. 10D shown; 20D/40D consistent.

**Part A — nesting/overlap, answers "is LH new information or just F1+MA1's extreme
tail?"**: 97.9% of "Confirmed LH + not-yet-proven" (n=912, 4.3% of population) is
already inside F1+MA1(D3) (n=10,069, 47.3%). Only 8.9% of F1+MA1 ever escalates that far.
**Verdict: LH is the extreme tail of the same evidence pool, not a separate mechanism.**
Architecturally simpler — no standalone LH-detection system needed; it's a terminal
confirmation state within the same ladder.

**Part B — the evidence ladder, EVENTUAL (whole-window) outcome per state**:

| State | n | % of pop | ≥1R | Net negative |
|---|---|---|---|---|
| No F1 at all | 5,110 | 24.0% | 89.5% | 30.2% |
| F1 → reclaim | 5,863 | 27.6% | 78.7% | 37.1% |
| F1 → no reclaim | 10,306 | 48.4% | 40.1% | 62.8% |
| F1 → no reclaim + MA1@D3 | 8,854 | 41.6% | 34.8% | 66.4% |
| F1 → no reclaim + MA1@D5 | 7,899 | 37.1% | 28.5% | 71.7% |
| F1 → ... → LH before proof | 887 | 4.2% | 3.4% | 92.4% |

**Clean, monotonic escalation** — each additional piece of evidence makes outcomes
progressively worse, consistently across all three lookbacks. Confirms the "evidence
ladder" architecture (Level 0 Normal → Level 1 Pressure → Level 2 Persistent pressure →
Level 3 Momentum absence → Level 4 Structural confirmation) is well-supported, not an
artifact of any single definition.

**Disposition**: Discovery phase for Failure-family exits is closed. Per critic's
explicit conditional ("if the audit shows expected nesting, move directly into exit
design") and the newly-adopted Discovery Budget rule (max 3 batches per subsystem,
Exit is now at its limit), no further Failure-family feature mining without explicit
re-opening. Next: EX1 (Failure Exit state machine), EX2 (Momentum Exit comparison), EX3
(Time Exit comparison) — the bounded final exit batch, then Exit Freeze.

## Project structure decisions adopted this session (2026-09-27)

- **Two-product framing formalized**: Product A (BC, positional, 10-15 day) vs Product B
  (Quick Swing, this line, 3-5 day). Written into `PRODUCT_DEFINITION.md` (retitled from
  "BC Product Definition" — always was about QS, title was a leftover).
- **Frozen stop/risk-unit definition** (S1b) written formally into `PRODUCT_DEFINITION.md`
  per critic's v0.2 structure request.
- **Research roadmap phases** adopted: Exit Discovery → Exit Freeze → Entry Discovery →
  Joint Tuning. Written into `PRODUCT_DEFINITION.md`.
- **Discovery Budget rule**: max 3 discovery batches per subsystem before freezing
  (Exit, Entry, Options, Risk sizing each get this budget independently).
- **External Reading Guardrail** adopted: QS hypotheses must state which literature
  concept (Kullamägi/Darvas/Minervini) they test or challenge before looking at
  historical results. Reading pack with exact URLs written into `swing_qs/CLAUDE.md`.

## EX1/EX2/EX3 — the bounded final exit-discovery batch, and its decisive result (2026-09-27)

Per critic's exact spec: event-based, counterfactual exit-philosophy comparison (not
parameter optimization), same S1b risk unit throughout, baseline = hold to the end of
the 15-day observed window (this project has not yet built a real QS exit engine — this
is the honest, explicit comparison point, not a proposed production exit).
`rq_qs_ex1_failure_exit_design.py` (verified bug-free by independent review before
trusting output — one disclosed, non-bug caveat: `winner_sacrifice_R` compares a
High-based eventual MFE against a Close-based exit price, which mildly inflates that
number; directionally still correct) and `rq_qs_ex2_ex3.py`. 10D shown; 20D/40D
consistent.

**EX1 — Failure-family candidates:**

| Rule | Fires on | Would-be-loser % | Damage avoided (R) | Would-be-winner % | Winner sacrifice (R) | Portfolio mean R |
|---|---|---|---|---|---|---|
| 1. Immediate failure (control) | 91.6% | 52.2% | 1.219 | 59.2% | 2.790 | **0.112** |
| 2. F1 + persistent non-reclaim | 48.4% | 62.8% | 0.927 | 40.1% | 3.174 | **0.211** |
| 3. F1 + non-reclaim + MA1(D3) | 41.6% | 66.4% | 0.765 | 34.8% | 3.248 | **0.220** |
| 4. Escalating (MA1@D5) | 37.1% | 71.7% | 0.539 | 28.5% | 3.128 | **0.242** |
| 5. LH high-confidence override | 4.3% | 92.4% | 0.050 | 3.4% | 2.755 | **0.308** |

Baseline (hold to window end) portfolio mean R: **0.3111**.

**EX2 — Momentum-family candidates** (Major Resistance and Distribution Day NOT tested —
no resistance-level or volume-based data built for QS; flagged rather than faked with an
invented proxy):

| Rule | Fires on | Would-be-loser % | Damage avoided (R) | Would-be-winner % | Winner sacrifice (R) | Portfolio mean R |
|---|---|---|---|---|---|---|
| Give-back to 50% of peak (after ≥0.5R) | 70.1% | 38.8% | 1.474 | 78.3% | 2.371 | **0.158** |
| Confirmed-LH as momentum exit (after ≥0.5R) | 23.4% | 47.9% | 0.317 | 75.0% | 2.294 | **0.280** |

**EX3 — Time-cap candidates:**

| Rule | Portfolio mean R |
|---|---|
| Day 5 | 0.109 |
| Day 7 | 0.131 |
| Day 10 | 0.169 |

**THE DECISIVE RESULT: every single candidate across EX1/EX2/EX3 — 10 rules total,
spanning aggressive to conservative, event-based and time-based, Failure- and Momentum-
family — reduces portfolio-level mean R relative to simply holding to the window's end.
None beat baseline.** Even the most conservative/selective candidates (LH override,
Confirmed-LH-as-momentum-exit) land only slightly below baseline, never above it. Time
caps confirm the same pattern independently — cutting even as late as day 10 is still
worse than running to day 15.

**Why**: every rule's winner-sacrifice cost outweighs its damage-avoided benefit. The
population's own recovery rate from "looks bad early" states is high enough (established
across this whole discovery arc: F1, MA1, milestone/giveback audits) that acting on early
evidence costs more expectancy than it protects. This is the same lesson the whole
session has been circling, now quantified directly at the portfolio level rather than
just per-state.

**Disposition, per the Discovery Budget rule**: Exit discovery is now at its 3-batch
limit and is FROZEN per this result. No new exit features (no F7/F8, no EMA variants, no
ADR buffers, no K=3 swings) without explicit re-opening. This result itself is the
trigger for the project's pivot toward Entry Discovery — if no early-exit mechanism beats
holding to the window's end, the marginal value of further exit engineering here is low;
the more promising direction is finding entries whose natural trajectory better fits a
simple, generous hold, rather than continuing to search for a smarter way to cut losers.
Sent to critic as the closing report of the Exit Discovery phase.

## QS Literature Filter Audit (2026-09-27)

Per critic's exact bounded batch spec: ~15 candidate entry filters, tested individually
(no composites), against `entry_definition` raw 10D/20D/40D populations restricted to
events with 252+ days of prior history (n=37,802 of 47,458 — RS Rating and 52-week-high
both need a year+ of history; not a bug, just a coverage constraint). All decision-time-
safe features computed at T-1 (Rule #18); a smaller "same-day telemetry" group
explicitly labeled non-promotable for the live-IOC entry mechanism. `rq_qs_literature_features.py`
(independently reviewed for lookahead bugs before trusting — one tiny, conservative
off-by-one found and fixed in `dist_52w_high_t1`'s window) + `rq_qs_literature_scorecard.py`.

Every production convention reused, not reimplemented: `trend_bullish` (signals.py),
`sma200`/`sma200_20ago` (signals.py), `rs_rating()` (relative_strength.py — the real
Minervini/IBD percentile-vs-universe function), `r1`/`r2` (pivots.py, already lagged by
construction), `atr14`/`vol_avg10_prior` (signals.py), `CONSOLIDATION_TOLERANCE_PCT`
formula (live_checkpoint.py, generalized to each event's own lookback window).

**Baseline** (n=37,802): reaches ≥0.25R "ever" 85.7%, ≥1R 60.8%, ≥3R 20.4% (eventually,
within 15 days). Direct answer to "how many days to reach a meaningful multiple, not
just does it ever happen" (per direct user question, added after the first pass only
reported "ever" + median-day-among-reachers): **only 32%/40%/53% reach ≥1R by day
3/5/10, and only 4%/7%/14% reach ≥3R by day 3/5/10** — confirms the earlier S1b
reachability finding: big multiples within a realistic swing window are genuinely rare.

**Strong candidates (real, monotonic, mechanism-consistent, HOLD UP under the stricter
"by day 5" test, not just "ever"):**

1. **base_duration** (consolidation days before breakout, generalized from
   `live_checkpoint.py`'s `_consolidation_days` formula): 37.1% of the raw population has
   ZERO consolidation days (an arbitrary spike through resistance) — that group shows
   ≥1R 54.3% "ever" / 35% by day5, vs 3-5 days' base showing 67.0%/26.2%("ever")/46%
   (day5). **Reasoning**: directly tests Darvas/Minervini/Kullamägi's requirement that a
   breakout come from genuine consolidation, not a random spike. Highest-value finding of
   the batch — 37% of the population is in the worst bucket.
2. **gap_to_trigger_pct** (how far price has already run from yesterday's close just to
   reach the trigger — a decision-time-safe "how extended already" proxy): clean,
   monotonic, ~16pp swing in "ever" ≥1R (66.9% Q1 vs 50.9% Q4) AND holds up under day5
   (46% vs 32%). **Independently confirms ON-01 (Extension)**, the "don't chase an
   already-extended move" finding this project already validated on the separate O'Neil
   Benchmark replica — two different metrics, same underlying mechanism, agreeing. The
   standout finding of the whole batch.
3. **prior_advance_63d** (trailing 3-month return as of T-1): real under "ever" (62.8%
   Q4 vs 57.6% Q1) but the gap nearly disappears under the day5 cutoff (42% vs 38%) —
   **matters more for eventual reachability than for fast, QS-relevant delivery**. Real,
   but a different kind of "strong" than base_duration/gap_to_trigger.
4. **dist_52w_high_t1** (Close vs 252-day high, T-1): real under "ever" (64.1% Q4 vs
   57.6% Q1), smaller gap under day5 (43% vs 39%) — same pattern as prior_advance, matters
   more for eventual size than fast delivery. Notably STRONGER here than the earlier BC-
   line research found for the same metric ("weak, tail-only, not promoted") — a real
   contrast between products, not re-investigated further this batch.

**Interesting, real, but needs more thought before promoting:**

5. **r1_proximity_pct / r2_proximity_pct** (distance to nearest pivot resistance) — a
   non-monotonic "Goldilocks" shape, NOT the naive monotonic expectation: entries that
   have ALREADY cleared R1/R2 before triggering do WORST (≥1R 51.3% "ever" / 32% day5),
   a MODERATE amount of room does BEST (≥1R 66.9%/47%), and very FAR resistance reverts
   toward baseline. Holds up under the day5 cutoff too, not just an "ever" artifact.
   **Disagrees with the naive "less overhead supply = better" expectation** — plausible
   mechanism: already-past-R1/R2 entries are likely already-extended (same underlying
   phenomenon as gap_to_trigger); very-far-resistance entries may be directionless movers
   with no nearby technical structure at all, not clean setups. Echoes the earlier
   `static_gap_pct` peaked (non-monotonic) shape from Stage 0 — a second instance of the
   same pattern-type in this data, worth trusting rather than dismissing as noise, but not
   obviously actionable as a simple filter yet.
6. **rs_rating_t1** (real Minervini/IBD percentile function, not approximated): real but
   surprisingly weak (~2.6pp lift Q1→Q4) given how central this metric is to his system.
   **Reasoning**: our raw population is already pre-selected for a genuine breakout, which
   itself correlates with above-average recent strength — compressing the RS spectrum
   before RS Rating even gets a chance to discriminate further. His literal 70+ cutoff
   (not just quartiles) is a natural follow-up, not done this batch.
7. **vol_ratio_t1** (T-1's volume vs its own recent average) — clean, monotonic, but
   INVERSE to the textbook "volume confirms breakout" expectation (high pre-breakout
   volume predicts WORSE outcomes, 54.9% vs 63.6% ≥1R). **Does not test what O'Neil/
   Minervini actually claim** (their claim is about the breakout DAY's own volume, an
   inherently same-day/EOD feature for a live-IOC entry, not the day before) — likely
   proxies for "something already happened a day early / already extended," same family
   as gap_to_trigger and R1/R2, not a genuine contradiction of the literature.
8. **eod_volume_ratio_SAMEDAY** (telemetry only): flat on WHETHER the trade eventually
   works, but real on HOW FAST and how safely (net-negative 49.3%→43.7% low-to-high
   volume) — volume seems to confirm speed/safety, not ultimate ceiling.

**Descriptive only (not decision-time-safe for the live-IOC entry, but real and strong)**:

9. **close_location_SAMEDAY** (where the entry day's Close lands in its own range): the
   single largest effect measured in this whole audit — ≥1R 47.7% (closed near the low)
   vs 70.6% (closed near the high), a 23-point swing. Real, intuitive (conviction holding
   through the session vs. a faded breakout) — but requires the full day's candle,
   unavailable at the live-IOC entry moment. **Raises a genuine, unresolved architecture
   question**: does this argue for reconsidering an EOD-confirmed entry variant for QS
   specifically (RQ-94 found Primed beats Confirmed on BC, a different product/population
   — not necessarily true here)? Flagged for critic, not resolved.
10. **body_pct_SAMEDAY**: similar, slightly smaller effect, same telemetry-only caveat.

**No evidence (proxy failed, concept untested, not falsified):**

11. **base_tightness** (generic 10-day/30-day ATR ratio): flat across quartiles
    (~60-61% ≥1R throughout, no trend). The crude proxy doesn't require contraction to
    happen specifically inside a real base right before the breakout — this is "our
    proxy showed nothing," not "VCP-style tightness doesn't matter."

**Not built — genuine data-coverage limitation, not skipped by choice**: intraday
RVOL-at-breach. Full 5-year population can't support it (intraday history only covers a
few months). Per direct user instruction: run it later on whatever intraday history
actually exists (a few months), scoped as its own narrow follow-up — not blocking this
report, not abandoned either.

**Disposition**: no composite features, no threshold optimization, per explicit batch
scope. Sent to critic for classification (Strong candidate / Interesting / Descriptive /
No evidence / Contradictory, per critic's own requested taxonomy) before deciding what,
if anything, becomes part of a QS v0.1 minimum-tradability gate.

## Correction — R1/R2 proximity is NOT independent of gap_to_trigger (2026-09-27)

Per direct user follow-up ("why not check for R1/R2") — ran the redundancy check
proposed as an open question in the prior critic update, rather than waiting.

**Result: r1_proximity_pct and gap_to_trigger_pct correlate at -0.925** (near-perfect;
sign flips because one measures room-to-resistance, the other measures size-of-run-up —
mechanically these are almost the same underlying quantity). 84.5% of the "already past
R1" group is also in the "most extended" gap group. Combining both conditions shows NO
additive effect (49.8% ≥1R for both-bad vs 50.9-51.3% for either alone) — exactly what
two measurements of the same phenomenon should look like, not two independent signals.

**Correction to the prior entry**: R1/R2 proximity's "Goldilocks" shape is NOT a distinct
finding from `gap_to_trigger_pct` — it's the same "don't chase an extended move"
mechanism seen through a different lens, not a second independent filter. One small
nuance survives: R1/R2's far extreme (very distant resistance) reverts toward baseline
rather than being the best bucket the way gap's smallest-quartile is — a minor secondary
signal about "no nearby technical structure" riding on the same core mechanism, not
worth treating as separate.

**vol_ratio_t1 IS genuinely independent** — correlation with gap_to_trigger is ~0
(0.016), with R1/R2 only weak (0.12-0.24). The inverse-volume finding stays a real,
separate signal, not a restatement of extension.

**Revised standing list of independent mechanisms from this batch**: base_duration
(consolidation quality), gap_to_trigger_pct (extension — subsumes R1/R2 proximity),
vol_ratio_t1 (pre-breakout volume, inverse), rs_rating_t1 (weak), dist_52w_high_t1 /
prior_advance_63d (eventual-reachability, not fast-delivery). R1/R2 proximity retired
as its own candidate — folded into gap_to_trigger.

## R1/R2 resistance-rejection deep dive (2026-09-27) — real, consequential, but not an entry filter

Per direct user challenge, following up on the literature audit's R1/R2 proximity result
(which had already been folded into gap_to_trigger_pct as redundant, not independent).
This thread went through several real corrections, logged in order since each one
mattered.

**1. Daily vs monthly pivot, resolved with hard evidence**: user recalled the pivot as
"likely monthly." Checked against real, already-documented live evidence
(`FINDINGS.md` line ~6719): MAXHEALTH touched R1=1067.10 at 1066.50 and RBLBANK touched
R2=429.20 at 429.50, both rejected, both matching the DAILY floor-trader pivot (prior
day's H/L/C via `pivots.py`) to within 0.1%. Confirmed by recomputing MAXHEALTH's R1 for
2026-09-23 from 09-22's H/L/C directly: exact match. Daily, not monthly.

**2. Prior research history surfaced**: this exact question (R1/R2 overhead-resistance
proximity) was already run to conclusion on BC v2's production population — "real,
theoretically well-motivated... but across every formulation tested..., never rises
above a modest, noisy tilt... do not reopen without a materially larger population or
real intraday data." Initially treated this as a reason to deprioritize further QS-side
testing.

**3. User pushed back, correctly**: the prior closure tested different formulations (next-
day continuation, proximity bands) — none of them tested the SPECIFIC mechanism the user
described (a same-day intraday touch-and-reject). Built that exact test:

- **41.5% of R1-touches and 45.0% of R2-touches close back BELOW the level on the SAME
  day they touch it** — a real, common, decision-time-observable (same-day/EOD) event.
- Splitting by same-day reject vs hold produces a huge gap in subsequent outcome:
  R1 rejected 47.4% eventual ≥1R vs held 77.2%; R2 rejected 57.9% vs held 86.4%.
- **This is a genuinely different, more precise formulation than the four already tested
  on BC v2** — not a reopening of a closed question, a new one that happens to work.

**4. Threshold/overshoot refinement** (per user: "different threshold behaves
differently"): bucketed by how far the day's High overshot the level before closing.
0-0.2% overshoot buckets are near-degenerate (99%+ reject rate is just ordinary daily
noise erasing a trivial poke, not resistance psychology — the "held" comparison group is
too thin, n=2/n=13, to trust). The well-powered, cleanest read is the **2%+ overshoot
bucket**: R1 rejected 52.3% vs held 84.3% (n=321 vs n=2,112); R2 rejected 72.2% vs held
93.2% (n=949 vs n=6,197). A decisive breakthrough that still gets thrown back is a rare
(13%), high-confidence bad sign — a marginal poke-and-fade is not informative on its own.

**5. Speed, not just eventual reachability** (per user: "1R two months later isn't what I
care about"): re-ran using days-since-touch, not "ever." At R1's 2%+ bucket: held reaches
1R at a **median of 0 days since the touch** (70.4% within +3 days) — essentially
"blasted through immediately." Rejected: median **5 days**, only 22.7% within +3 days.
Same shape for R2 (held median 0 days/86.4% by +3d; rejected 52.6% by +3d). **Confirms
the user's live intuition directly: a clean hold through resistance isn't just more
likely to work, it's associated with an almost-immediate move — a rejection costs real
time even among trades that eventually recover.**

**6. The critical, honest correction — "held vs rejected" is NOT an entry-time-actionable
split** (per user: "I will either take the trade or skip it — what predicts who gets
held, using only what I know at entry?"). Checked every established pre-entry feature
(gap_to_trigger_pct, base_duration, trend_bullish_t1, prior_advance_63d, rs_rating_t1,
dist_52w_high_t1, vol_ratio_t1, and R2's own entry-time-known proximity) against held vs
rejected populations at R2. **Every single one is statistically indistinguishable between
the two groups** (e.g. gap_to_trigger median 1.639 held vs 1.620 rejected; RS rating 57.5
vs 56.6; proximity itself 0.765% vs 0.869% — no meaningful separation anywhere).

**Disposition — real finding, wrong use case**: whether a trade holds or rejects at R1/R2
is real, consequential (huge outcome and speed differences), and decision-time-safe to
OBSERVE same-day (EOD-knowable) — but **cannot currently be predicted in advance with
anything in our feature set, so it cannot become an entry filter** (filtering out
"R2-nearby" setups would discard held and rejected trades in equal measure, for no
benefit). Its correct use is as a **post-entry trade-management signal**: once in a
trade, whether it closes above or below R1/R2 by end of day on the day it's tested is
real, actionable information for tightening a stop or protecting gains — structurally
similar to F1/reclaim from the exit-discovery arc, not to the entry-filter literature
audit. Not yet built as a management rule — flagged as a candidate for the (currently
frozen) exit-engineering phase, or for Entry Discovery's EN3/EN5 structural work if it
turns out to interact with entry timing.

## R1/R2 escalation audit — result, and why it doesn't change anything actionable yet (2026-09-27)

Per critic's exact bounded spec (State1: F1 touch->no reclaim; State2: State1+MA1@D3;
State3: State2 + R1/R2 rejection, 2%+ overshoot definition preserved; plus an ordering
test). `rq_qs_r1r2_escalation_audit.py`.

**Result: the hypothesis inverted.** Adding an R1/R2 rejection on top of an already-weak
State2 does NOT escalate failure further — it identifies a BETTER sub-population within
the weak state (eventual ≥1R: 62.3% for the rejection subgroup vs 29.4% for the "never
even attempted a rally" control subgroup, both starting from the same 33.1% State2
baseline). Ordering test: rejection happening AFTER the MA1@D3 weakness is confirmed
(n=1,201) does better (67.1% ≥1R) than rejection happening early (n=590, 52.4%) —
consistent with "a later rally attempt, even a failed one, is a stronger recovery sign
than an early one."

**Mechanism**: to have a 2%+ overshoot rejection event at all, the stock must first rally
hard enough to seriously threaten the level. The "no rejection" control isn't a cleaner
failure state — it's the group that never even attempted a real rally. Rejection is a
byproduct of showing strength, not a cause of weakness.

**Day-by-day Close-R trajectory (day3, the MA1@D3 confirmation point, through day8)
makes this vivid**: the "no rejection" control keeps sinking (median -0.674→-0.789); the
State2 baseline is flat (-0.655→-0.727); the rejection subgroup climbs steadily every
single day (-0.546→-0.485→-0.351→-0.313→-0.233→-0.194) — still underwater at day8, but
visibly and consistently healing.

**Critical correction, per direct user challenge — reachability WITHIN QS's own window,
not "ever," and split by win SIZE, not just "any win":**

| | ≥1R by day5 | ≥1R by day10 | No win/Tiny(0.25-1R)/Real(≥1R) by day10 |
|---|---|---|---|
| State 2 baseline | 7.3% | 21.9% | 41.1% / 37.0% / 21.9% |
| + R1/R2 rejection | 20.9% | 46.8% | 6.4% / 46.8% / 46.8% |
| No rejection (control) | 5.6% | 18.7% | 45.5% / 35.8% / 18.7% |
| **Rest of population** (58.3% — never enters this weak state at all) | **63.9%** | **75.4%** | 0.7% / 23.9% / 75.4% |

**Even the best sub-population here (rejection subgroup) reaches a full 1R within QS's
own 10-day ceiling less than half the time (46.8%), and most of the improvement over
day5's numbers only materializes by day 10-15 — at or past the edge of QS's stated
window, not comfortably inside it.** Compared against the healthy 58.3% majority that
never enters this state at all (63.9%/75.4% real-win rate at the same day cutoffs), even
the "recovering" subgroup remains meaningfully worse — this distinguishes "bad" from
"less bad," not "bad" from "fine."

**Disposition, per user's explicit priority call**: this is a genuine, validated,
POST-ENTRY trade-invalidation/management signal (not a pre-entry filter — nothing
predicts held-vs-rejected in advance, established earlier). Worth keeping documented,
but explicitly NOT the current priority — the user's stated priority going forward is
the PRE-ENTRY R1/R2 question (proximity at entry as a decision-time filter), which was
already found to be ~92.5% correlated with `gap_to_trigger_pct` and folded into it, not
independent. Sent to critic as a full stocktake of the whole R1/R2 thread, with this
priority ordering made explicit.

## R1/R2 — final disposition, formally closed (2026-09-27)

Per critic's review of the full stocktake. Clean separation by clock, closing the
pre-entry question while preserving the post-entry finding as telemetry (not deleted,
not acted on):

| At what time? | R1/R2 information | Disposition |
|---|---|---|
| Before entry | Proximity to R1/R2 | **CLOSED** — represented by `gap_to_trigger_pct`'s extension/geometry (~92.5% correlated, no additive information; adding R1/R2 as a separate entry filter would double-count the same setup geometry, not add independent evidence) |
| After entry, same day | Meaningful (2%+) overshoot + close back below R1/R2 | Real, interesting trajectory information (`r1_r2_rejection_2pct_same_day`) — kept in research telemetry |
| As exit intervention | Automatically exit/reduce on rejection | **Not supported** — the escalation audit inverted the hypothesis (rejection identifies a BETTER sub-population, not worse); no active exit role now |

**Explicitly will NOT chase variants** (R1 within 0.5 ATR, R2 within 1 ATR, R1-but-not-R2,
ATR-normalized distance, R1/R2+gap combinations, etc.) — per critic: "that would be
trying to rescue a feature whose underlying information has already been accounted
for." Per user's own priority call: post-entry trade-management use is secondary, not
the current focus — documented, not pursued further right now.

**Standing rule reinforced**: don't convert a post-entry observation into an entry
filter merely because entry research is the current priority — mixing clocks. R1/R2
proximity (pre-entry) and R1/R2 rejection (post-entry) are different questions with
different, independently-determined dispositions.

**Literature audit — remaining genuinely independent candidates, not yet covered**: per
critic, the productive remaining space is base quality/tightness (partially done —
`base_duration` strong, `base_tightness` proxy failed), prior advance (done), trend/
strength (done), breakout volume/RVOL (T-1 and same-day EOD versions done; true intraday
RVOL-at-breach still parked, data coverage), breakout candle/range quality (body%/close-
location done; range-expansion and gap_open_pct not yet tested), relative strength
(done, weaker than literature implies), **structural overhead beyond what extension
captures** (genuinely new — e.g. actual prior swing-high/chart resistance, distinct from
the R1/R2 pivot formula that's now closed — not yet tested), and intraday breach
characteristics (parked, data coverage).

## Literature audit extension — remaining daily-bar candidates closed out (2026-09-27)

Per critic's list, three genuinely untested items were buildable on daily data alone
(the rest need real intraday data, still parked). All three now tested.

**Structural overhead — nearest confirmed prior swing-high** (`rq_qs_structural_overhead.py`,
independently reviewed for lookahead before running — mirrors `primed_engine.py`'s real
K_SWING=2 confirmation logic exactly, confirmed via direct comparison to the production
source, not assumed). n=43,333 (needs 120+ days history). **Genuinely independent** of
the extension cluster (correlation with `gap_to_trigger_pct`: 0.058; with R1/R2
proximity: -0.036/-0.012) — but a **clean null result**: no overhead found (28.2% of
population, "clear skies") shows 60.1% eventual ≥1R; every proximity quartile (closest
to farthest confirmed peak) sits within ~2pp of that, no monotonic trend anywhere.
**Reasoning**: the K=2 confirmation rule confirms any minor 2-day local peak, not
specifically a chart-significant level (one that held for a while or was tested
multiple times) — likely dilutes whatever real "clear of overhead supply" effect exists,
similar to how the earlier crude `base_tightness` proxy also found nothing while the
more literal `base_duration` found a strong effect. Concept remains untested in a
cleaner form; this specific formulation shows no evidence.

**range_expansion_SAMEDAY** (today's High-Low vs T-1's known ATR — same-day/EOD-only,
not live-IOC-safe): mixed but real. Flat on eventual "ever" reachability (59-63% across
quartiles) but a genuine, real effect on SPEED and SAFETY — widest-range quartile
reaches ≥1R by day5 at 46.3% vs narrowest's 38.6%, net-negative 44.0% vs 47.9%. Same
shape as the earlier `eod_volume_ratio_SAMEDAY` finding: real breakout-day conviction
predicts faster/safer outcomes, not necessarily a higher ceiling. Correlates moderately
(0.53-0.61) with `gap_to_trigger_pct`/`body_pct_SAMEDAY` — related, not redundant.

**gap_open_pct_SAMEDAY** (today's actual Open vs T-1's Close, distinct from
`gap_to_trigger_pct` which measures distance to the trigger price, not the day's actual
open — correlation between them only 0.285, genuinely different quantities): flat, no
signal (60.5%→61.4%→62.2%→59.5% across quartiles, no trend).

**Disposition**: this closes out every daily-bar-buildable candidate from critic's
literature-audit list. Remaining open items (true intraday RVOL-at-breach, general
intraday breach characteristics) are both genuinely blocked on real intraday data
coverage, not skipped by choice — still parked per `PARKING_LOT.md` item 8's scope,
to be picked up if/when that data project happens.

## Intraday RVOL-at-breach — the first real intraday test (2026-09-27)

The one genuinely-blocked candidate, now run on whatever real intraday data actually
exists (`intraday_cache/`, 5-min bars, full 500-ticker universe, confirmed by direct
inspection to cover 2026-06-10 through 2026-09-23 — ~3.5 months, NOT the full 5-year
population). Per direct user instruction: run it now on this real but narrow window,
scoped explicitly, not blocking on a full data rebuild. `rq_qs_intraday_rvol.py` —
independently reviewed before running (confirmed the breach-detection logic exactly
matches this project's own production research pattern in
`breakout_failure_threshold_sweep.py`'s `gather_breaches()`, and that the cross-day
bar-position alignment risk is real but already handled correctly by the existing
guard — short intraday days are truncated at the END, not gapped mid-session, so
early-session bar positions stay aligned).

**Definition**: `rvol_at_breach` = cumulative Volume from session start through the
actual breach bar (the real 5-min bar where High first reached the trigger price), on
the breach day, divided by the average of the same cumulative-volume-by-bar-position
across the nearest 10 prior trading days with intraday coverage for that ticker.
Decision-time-safe (only volume up to and including the breach bar itself, plus fully
completed prior days — this is the literal, real version of "is volume confirming the
breakout AT the moment it happens," not a daily-bar proxy).

**Result, n=2,031 (small-sample caveat — only ~3.5 months of real intraday history,
weight accordingly)**:

| RVOL at breach | Median RVOL | Ever ≥1R | ≥1R by day5 | Mean MFE |
|---|---|---|---|---|
| Q1 (low) | 0.85x (below normal) | 59.3% | 39.0% | 2.011 |
| Q2 | 1.74x | 51.0% | 33.7% | 1.435 |
| Q3 | 3.09x | 52.1% | 34.1% | 1.388 |
| Q4 (high) | 7.64x | 43.7% | 28.1% | 1.178 |

Clean, monotonic — **high RVOL at the moment of breach predicts WORSE outcomes**,
directly inverting the textbook "volume confirms breakout" expectation. Unlike the
earlier `vol_ratio_t1` finding, this can't be dismissed as "measuring the wrong day" —
this is the literal, real moment described in the literature, using genuine intraday
data, and it still inverts.

**Genuinely independent, not a restatement**: correlation with `gap_to_trigger_pct` is
only 0.225 (modest, real, not redundant); with `vol_ratio_t1` (T-1 volume) it's
essentially zero (0.008).

**The coherent three-way volume story, combining all three volume tests this session**:

| Signal | Timing | Direction |
|---|---|---|
| `vol_ratio_t1` (prior day's volume) | Before the breakout day | High volume = worse |
| `rvol_at_breach` (this test) | Early in the breakout day itself | High volume = worse |
| `eod_volume_ratio_SAMEDAY` (full day's final volume) | End of the breakout day | High volume = better (faster, safer) |

**Reasoning**: volume showing up BEFORE the trigger (yesterday, or in the first couple
hours of the trigger day) looks like an already-hot, already-discovered stock —
consistent with the broader "already extended" mechanism found elsewhere this session.
Volume accumulating AFTER the breach, over the rest of that same day, looks like genuine
fresh participation drawn in BY the breakout itself. Not all high volume is equal —
pre-breach volume is a bad sign, post-breach volume is a good one. This is the first
result all session that tests the literal literature claim with real intraday data
rather than a daily-bar proxy, and it does not validate the naive story.

**Disposition**: real, coherent, mechanism-consistent finding, but explicitly caveated
by small sample size (3.5 months only) — treat as directionally suggestive, not
equal-confidence to the 5-year daily-bar findings. This closes out the literature audit's
list completely, including the previously-blocked intraday item. Sent to critic with the
full three-way volume picture.

## RVOL-at-breach mechanism decomposition (2026-09-27)

Per critic's exact spec — not a new filter, not a composite, pure diagnosis of what
high breach-RVOL actually represents. `rq_qs_rvol_mechanism.py` (extends the already-
reviewed `rq_qs_intraday_rvol.py` reconstruction; self-consistency verified —
reconstructed RVOL from the two decomposed components matches the original to
floating-point precision, confirming both scripts agree). n=2,031 (same population as
the original intraday RVOL test).

**A vs B**: `rvol_before_breach` (volume already accumulated before the breach bar)
correlates **0.926** with the overall rvol_at_breach signal; `rvol_breach_bar_only`
(just the single breach bar's own volume) correlates only **0.741**. **Hypothesis A
dominates — the "badness" is primarily about pre-existing volume buildup, not a violent
single-bar breach.** Both rise together across quartiles (so B contributes something
real too), but A is the clearly bigger driver.

**Confound surfaced, not asked for but important**: breach timing collapses
monotonically as RVOL rises — Q1 (low RVOL, median 0.85x) breaches at a median 120
minutes after open (~11:15 IST); Q4 (high RVOL, median 7.64x) breaches at a median of
just 35 minutes after open (~09:50 IST). Mechanically, RVOL is a cumulative ratio and is
inherently noisier/more extreme early in the session (small denominator) — part of
"high RVOL" may be a timing artifact rather than a genuine participation signal. Could
also represent a real, different phenomenon (gap-and-go immediate triggers vs. slower
mid-session organic breakouts) — not yet disentangled, flagged as an open question.

**Supporting, modest, not dominant**: `price_move_before_breach_pct` rises monotonically
(1.47%→3.40%) and `gap_to_trigger_pct` rises too (1.68→4.08) — consistent with, but not
a rediscovery of, the extension mechanism found elsewhere (correlation was only 0.225,
confirmed still modest here).

**Disposition**: real, coherent, but nuanced — high breach-RVOL mostly reflects genuine
pre-existing volume buildup, entangled with an early-breach-timing effect not yet
disentangled. Per critic's own framing, this stays "strong research signal / provisional
direction, not production filter" given the 3.5-month sample. Sent to critic before the
small combination audit (base_duration × gap_to_trigger × RVOL) and gate design.

## Bounded combination audit — base_duration × gap_to_trigger × RVOL (2026-09-27)

Per critic's exact scope (A/B/C/D, broad buckets only, no threshold optimization).
`rq_qs_combination_audit.py`. Part A on the large litfeat population (n=37,802); B/C/D
on the small intraday-RVOL population (n=1,955-2,031).

**A. base_duration (0 vs 1+) × gap_to_trigger (median split)**:

| | gap=good | gap=bad |
|---|---|---|
| base=0 (no base) | ≥1R@d5: 42.8%, mean R@d10: 0.266 | ≥1R@d5: 32.8%, mean R@d10: 0.162 |
| base=1+ | ≥1R@d5: 44.8%, mean R@d10: 0.136 | ≥1R@d5: 41.0%, mean R@d10: 0.202 |

Gap's effect is ~10pp when base=0, only ~4pp when base=1+; base's effect is ~8pp when
gap=bad, only ~2pp when gap=good. **Real, complementary interaction, not additive** — a
real base substantially rescues an otherwise-extended entry.

**B. Adding RVOL (n=1,955)**: best-powered "all-bad" cell (base=0/gap=bad/rvol=high,
n=473) is the worst well-powered outcome (≥1R@d5 23.9%), but base=1+ rescues even that
combination substantially (same gap/rvol state, base=1+: ≥1R@d5 42.2%, n=192) — base
duration remains the single most protective factor even stacked against two other bad
signals. Several cells (n<100) too thin to trust individually.

**C. RVOL timing robustness (the answer to the earlier confound)**:

| Breach time | RVOL low→high, ≥1R@d5 |
|---|---|
| Early (≤60min) | 36.7%→33.2% (~3.5pp) |
| Mid (60-150min) | **43.9%→29.2% (~14.7pp, largest)** |
| Late (>150min) | 31.7%→30.0% (essentially gone) |

**Survives in early/mid session (strongest mid-session, not early), washes out late.**
Not a pure timing artifact (would be strongest early, fading gradually) but also not
universal — likely captures an early/mid-session-specific phenomenon (already-discovered
via overnight gap/news), not a general "volume is bad" rule holding all day.

**D. Conditional diagnostic — the two factors act on different dimensions**: within
gap=good, RVOL barely moves reach-rate (37.5%→36.5%) but devastates mean R
(0.031→-0.314) — mostly a TAIL-RISK effect there. Within gap=bad, RVOL moves reach-rate
more (34.3%→29.2%) and mean R less. Symmetrically, gap's effect is bigger within
RVOL=high (~7pp) than RVOL=low (~3pp) — bad conditions compound, not simply add.

**Verdict: Outcome A (complementary), per critic's own decision framework** — but with
real texture: base_duration is the single most consistently protective factor across
other bad conditions; gap_to_trigger and RVOL each add independent information but
affect different things (reach-rate vs. tail-risk, and different session-time windows).

**Disposition**: sufficient evidence to move to QS v0.1 gate design. RVOL stays
"provisional/telemetry" per its own small-sample and timing caveats, not a hard gate
condition. Sent to critic as the final piece before entry-gate construction.

## QS v0.1 Entry Gate built — Entry Discovery phase deliverable (2026-09-27)

Per critic's final instruction: move from discovery to readiness. Built the actual
entry gate + full readiness report as a standing document:
**`swing_qs/QS_V01_ENTRY_GATE.md`** (not duplicated here — this is a pointer entry).

Summary: gate = raw breakout population, reject only if `base_duration==0 AND
gap_to_trigger_pct > median` (conditional logic directly encoding the combination
audit's interaction finding, not independent thresholds). n=26,541 QS v0.1 candidates
(70.2% of the feature-eligible population). Lifts ≥1R reachability by ~3.2-3.5pp at
D5/D10 vs. unfiltered baseline, but does NOT improve loss-avoidance (net-negative @ D10
unchanged, 49.5%→49.6%) — disclosed honestly, not oversold. RVOL, breach time, R1/R2
same-day rejection all kept as telemetry, not gate conditions, per critic's explicit
"not enough evidence yet" call. Exit remains explicitly undecided.

This closes the Entry Discovery phase's first concrete output. Next: live observation
of real candidates against this gate, not further discovery, per the Discovery Budget
rule and critic's explicit "no more rabbit holes tonight" instruction.

## QS v0.1 Entry Discovery formally closed for tonight (2026-09-27)

Critic-confirmed closing status: **QS v0.1 Entry Gate — READY FOR CONTROLLED LIVE
VALIDATION** (not "validated strategy," not "production-ready complete system" — entry
is ready, the product is not fully solved, exit stays deliberately provisional). Six
things specifically called out as correctly handled, worth preserving as-is: the gate
encodes the actual interaction rather than two independent cutoffs; 70.2% coverage
confirms QS wasn't accidentally rebuilt into BC under another name; the performance
claim stays modest (speed of continuation improved, D10 net-negative not materially
changed — exactly the legitimate reason for QS to exist as a distinct product); S1b is
the explicit, undisturbed risk unit (Rule #20 compliance); RVOL stays telemetry, not
prematurely promoted off a 3.5-month sample; the 2025-26 regime step-down stays visible,
explicitly NOT "fixed" tonight.

**Tomorrow's purpose, explicit**: not another optimization session. Observe whether real
live trades behave like the quick-continuation population this gate was designed to
capture (base quality, extension, breach timing, RVOL, immediate continuation,
trajectory, options availability) — capture telemetry, don't change the gate mid-
session even if one trade looks bad. That becomes the next research cycle's input, not
same-day patching.

This closes the Entry Discovery research arc that began with the S1b stop definition
catch earlier this same day. Full standing reference: `swing_qs/QS_V01_ENTRY_GATE.md`.

## EX-2R — fixed 2R profit-target exit, tested on the actual QS v0.1 population (2026-09-27)

Per direct user proposal: exit at +2R if the target is hit, exit at -1R if the stop
(S1b, exact by construction) is hit first, otherwise fall back to the window-end close.
Tested on the ACTUAL QS v0.1 candidate population (n=26,541, not the raw unfiltered
population) — the population the user would actually be trading. `rq_qs_ex_2r_target.py`.

**Result: worse than doing nothing.**

| | Portfolio mean R | Portfolio median R |
|---|---|---|
| Baseline (hold to window end) | 0.352 | +0.146 |
| EX-2R | **0.105** | **-1.000** |

**Exit reason breakdown**: stop hit first 55.2%, target hit first 29.9%, neither
(fallback to window-end close) 14.9%.

**Why it fails, quantified**: damage avoided by cutting losers cleanly at -1R (vs. their
worse baseline close) averages +0.895R across 12,452 would-be-negative trades (~11,100
R-units saved). Winner sacrifice by capping at +2R averages **3.846R per trade** across
6,205 trades (23% of the whole population!) that would have gone on to ≥3R if allowed
to run (~23,900 R-units given up). The sacrifice is roughly 2x the damage avoided.

**Disposition — the fourth independent confirmation of the same lesson from EX1-EX3**:
this population's edge lives disproportionately in a smaller number of large winners;
any rule that caps them early (failure signal, giveback rule, time cap, or now a fixed
profit target) loses to simply not capping them. Important distinction, not to be lost:
the STOP half of this plan (cut cleanly at -1R) is fine and consistent with the existing
risk framework — the TARGET half (cap winners at +2R) is specifically the part costing
money. This is a real, useful negative result for the exit-design question, logged as
closed per Rule #17, not to be silently retried with a different target multiple without
new evidence (the same mechanism that killed 2R would very plausibly kill 1.5R or 2.5R
too — the problem is capping itself, not the specific number).

## Correction — EX-2R must compare against the SAME stop-loss, not a stop-free baseline (2026-09-27)

Per direct user correction: "my SL is already an exit" — the earlier EX-2R comparison
was unfair, since its "baseline" (hold to window end) never actually applied the
stop-loss at all, silently letting trades "survive" drawdowns that would have triggered
a real stop-out. Rebuilt with the SAME stop-loss active in both scenarios.
`rq_qs_ex_2r_target_v2.py`.

| Scenario | Portfolio mean R | Win rate |
|---|---|---|
| A: SL only, no target (let winners run to window end) | **0.185** | 34.8% |
| B: SL + 2R target | 0.105 | **40.2%** |

**A real, honest trade-off, not a blowout**: A wins on pure expectancy; B wins on win
rate (more frequent, smaller wins). This is a legitimate practical choice, not a math
error in either direction.

**The more precise question — what happens to the 7,947 trades that actually reach 2R,
if not capped**: averages 2.27R if let run (a modest ~0.27R extra), but it's close to a
coin flip — 50.3% end up better than the cap, 49.7% end up worse (give back some/all of
the gain). 81.9% stay net positive regardless. **A's overall edge over B doesn't come
from the typical 2R-reaching trade (that's roughly a wash) — it comes from the rare
trades that go well past 2R (4R, 5R, 8R+), every one of which gets clipped to exactly
2.0 under a fixed target.**

**Corrected disposition**: a fixed 2R target, given the SAME stop-loss either way, is a
real, defensible choice if the goal is higher win-frequency and lower variance — it costs
real expectancy specifically by capping the rare large winners, not because 2R itself is
a poor level or because the typical 2R-reaching trade would have done much better
unclipped.

## Exit Discovery reopened — after-proof management only, narrow scope (2026-09-27)

Per direct user request, following a sharp challenge to the QS v0.1 readiness report:
"if my SL is already an exit, is 2R a good target?" led to a chain of corrections and a
genuinely new, validated finding — logging the full arc since each step mattered.

**1. Fixed 2R target, first pass (flawed)**: tested "exit at 2R, else hold to window
end" against a baseline that never applied the stop-loss at all. Result looked
decisively bad (mean R 0.105 vs baseline 0.352). **User caught the flaw**: the baseline
was unfair — it let trades "survive" drawdowns that would have triggered a real
stop-out. Rebuilt with the identical stop-loss active in both scenarios.

**2. Corrected comparison**: A (SL only, let winners run) mean R 0.185 vs B (SL + 2R
target) mean R 0.105. A real, honest trade-off — B gives a higher win rate (40.2% vs
34.8%) for lower total expectancy. The cost of capping is concentrated in the rare
trades that go well past 2R (23% of the population reaches ≥3R if unclipped, averaging
~3.85R given up per such trade when capped).

**3. Time-based variants, tested progressively**: blunt 5-day max hold (C, mean 0.085),
blunt 3-day max hold (G, mean 0.080 — worse, confirming cutting earlier is worse not
better when the cutoff is blunt), two-stage proof-then-ceiling (F, mean 0.085) — all
underperform B. Selective proof-check-only rules (D: cut only if never reaches 0.25R by
day3, mean 0.103; E: same at day5, mean 0.103) come very close to B's expectancy while
still removing the genuinely dead trades (forced-exit mean R -0.39/-0.42, only 5-7%
still non-negative when cut) — confirms Momentum Absence (MA1, validated earlier this
session) is real and nearly free to act on, while blunt time capping is not.

**4. The "why still developing" clarification**: at day3, 59.3% of the whole population
is still unresolved (neither stop nor target); at day5, 44.8% still is. This is expected,
not anomalous — median time to even reach 1R is day3, median time to 2R is day5-6, so a
large fraction of trades are mathematically still "in between" early on.

**5. The product-identity challenge**: user pointed out that letting proven trades ride
to day15 if unresolved is exactly BC v2's own patient behavior — QS has no real exit-side
identity yet, only entry-side differences (different filters, different risk unit).
Explicitly acknowledged as a genuine, unresolved gap — motivated reopening exit design,
narrowly scoped to "what happens after a trade proves itself," not a broad re-sweep.

**6. After-0.25R-proof breakeven/giveback (H0-H3) — decisive failure, same mechanism as
E1A**: moving the stop to breakeven the instant 0.25R is cleared is far too tight —
44.9-51.2% of ALL trades end at exactly 0 (breakeven whipsaw), all four variants
(H0-H3) show NEGATIVE portfolio mean R (-0.025 to -0.051) vs D's +0.103. A bare 0.25R
proof is too small a move to survive normal digestion with zero buffer — identical
failure mode to E1A's 1-day-lag trail.

**7. After-1R-proof breakeven/giveback (J0-J3) — meaningfully better, still short**:
raising the tighten threshold to 1R fixes most of the damage (J0: mean 0.052, positive)
but still underperforms D (0.103) at every giveback setting tested (J1-J3: 0.018-0.042).
Consistent monotonic pattern: looser giveback allowance → closer to D; tighter → worse.

**8. "Are we entering too casually" — tested directly, hypothesis REJECTED on setup
quality, CONFIRMED on stock volatility**: split J0's whipsaw rate by entry setup
quality (gap_to_trigger quartile, base_duration bucket) — essentially flat (53-64%
whipsaw regardless of setup quality; if anything the "best" setups whipsaw slightly
MORE, e.g. base_duration=3-5 shows the highest whipsaw rate at 64.2% and NEGATIVE mean R
-0.001). **Setup quality does not predict whipsaw.**

**9. The real lever — stop width relative to the stock's own ADR**: split by
`adr_multiple_of_stop` (already-established telemetry) instead. Clean, monotonic,
nearly-halved result:

| ADR-multiple quartile | Median stop width vs ADR | Whipsaw rate |
|---|---|---|
| Q1 (tightest vs ADR) | 0.89x (stop narrower than a normal day's move) | 72.0% |
| Q2 | 1.15x | 65.9% |
| Q3 | 1.41x | 56.0% |
| Q4 (widest vs ADR) | 1.85x | 37.3% |

**Confirmed: the whipsaw problem is about how tight the stop is relative to the stock's
own normal daily noise, not about entry setup quality.** When the stop is already
narrower than a typical day's move (Q1), ordinary noise alone reaches it 72% of the
time once tightened. This is a real, validated, actionable lever — the fix is likely
ADR-relative tightening/giveback thresholds (or restricting any tightening mechanism to
the subset where `adr_multiple_of_stop` is comfortably high), not a fixed R-multiple
threshold applied uniformly, and not stricter entry filtering on setup quality (already
ruled out).

**Disposition**: exit design remains open on this specific question — no rule has yet
been found that beats D (hold with the original wide S1b stop, cut only if truly dead by
day3) by a meaningful margin, but the ADR-relative finding gives a concrete, motivated
next direction rather than another blind threshold sweep. Sending the full story to
critic now.

## QS Stage 1 — Feature Battle: Blast vs Drift vs Failure (2026-09-28)

Per critic's exact bounded scope from the architecture-pivot discussion. New labels
(S1b risk unit, mutually exclusive; minor day5/day10 wording ambiguity in critic's
original spec resolved explicitly, disclosed): **BLAST** = reaches ≥2R by day 5.
**FAILURE** = not blast, and either hits the -1R stop before ever reaching 0.25R
(through day 10) or never reaches 0.25R by day 10 at all. **DRIFT** = everything else
(real but modest/slow progress — the "tiny winner" territory explicitly NOT counted as
success per the user's standing instruction).

**Label distribution on the full feature-eligible population (n=37,802)**: DRIFT 57.1%,
FAILURE 26.3%, BLAST 16.6%. Confirms the concern that motivated this whole relabeling —
most of what looked like "wins" under the old framing is Drift, not genuine Blast.

**New features computed, all T-1/decision-time-safe**: `ema34_persistence_t1` (reuses
signals.py's existing production `ema34_rising10` column directly, not reimplemented),
`dist_from_ema21_pct_t1`, `base_contraction_ratio_t1` (a PROPERLY rebuilt base-tightness
proxy this time — mean daily range over the last 5 days vs a non-adjacent, non-
overlapping earlier reference window 15-25 days back, avoiding the earlier failed
proxy's overlapping-window circularity), `prior_20d_advance_t1`.

**Feature Battle, ranked by normalized Blast-vs-Drift effect size (median gap / pooled
std — the harder, more valuable question than Blast-vs-Failure)**:

| Feature | Blast-vs-Drift effect | Blast-vs-Failure effect |
|---|---|---|
| ema34_persistence_t1 | **0.517 (strongest)** | 0.258 |
| gap_to_trigger_pct | -0.250 | -0.131 |
| prior_20d_advance_t1 | 0.154 | 0.119 |
| dist_from_ema21_pct_t1 | 0.151 | 0.076 |
| base_contraction_ratio_t1 (new proxy) | -0.127 | -0.076 |
| rs_rating_t1 | 0.111 | 0.066 |
| body_pct_SAMEDAY (EOD telemetry) | 0.102 | **0.640 (strongest of any feature/comparison)** |
| vol_ratio_t1 | -0.026 | -0.015 |
| base_duration | **0.000 (exactly zero)** | 0.000 |
| rvol_at_breach (separate intraday population, n=1,955) | -0.008 | -0.006 |

**Critic's 5 pre-written falsifiable predictions, checked**:
1. Base duration separates Blast from Failure — **REFUTED, flatly** (effect exactly
   0.000 both ways). The single strongest survivor from the entire literature audit
   predicts *whether something happens at all* but has zero power over *what kind* of
   outcome results. A genuinely important correction to last session's framing.
2. Gap-to-trigger separates Blast from Drift — **CONFIRMED** (2nd strongest effect).
3. EMA21 distance outperforms EMA34 persistence — **REFUTED, in the opposite
   direction**. EMA34 persistence is the single strongest discriminator in the whole
   battle (3.4x the effect size of EMA21 distance) — a real, previously-untested
   production feature turning out to matter more than the literature-motivated
   alternative.
4. Volume dry-up is weak alone — **CONFIRMED** (2nd weakest).
5. RVOL won't survive as an entry discriminator — **CONFIRMED** (weakest of all,
   checked on the separate small intraday population). Real, useful distinction from
   the earlier RVOL finding: RVOL predicts *whether* a trade works at all (established
   earlier), but has ~zero power over *what kind* of outcome results once it does —
   different question, different answer, not a contradiction.

**Bonus finding**: `base_contraction_ratio_t1`, the newly (properly) rebuilt base-
tightness proxy, shows real, moderate signal (-0.127) — unlike the earlier failed
ATR-ratio version (~0 effect). Building it with non-overlapping reference windows
instead of adjacent rolling windows appears to have fixed the earlier circularity
problem. `body_pct_SAMEDAY` is the single best signal for spotting outright FAILURE
specifically (0.640) but does not distinguish Blast from Drift — matches the
"conviction vs drift" framing, just for the failure side of that distinction, not the
blast side.

**Disposition**: one output table, no thresholds chosen, no filtering, no promotion —
per the bounded scope. 3 of 5 predictions confirmed, 2 refuted (one completely). This
is real, actionable evidence for constructing QS v0.2's gate around `ema34_persistence`
and `gap_to_trigger` as the primary Blast-vs-Drift discriminators, with `base_duration`
demoted from "the strongest finding" to "predicts activity, not quality" — a genuine,
disclosed correction to last session's conclusions, not a contradiction to hide. Sent
to critic as the complete Feature Battle result.

## R1/R2 pivot-period re-investigation — daily vs weekly, static vs intraday (2026-09-27 late)

Reopened per direct user pushback with real live examples (RBL Bank, DiviLabs, Maxhealth,
Laurus Labs) and 5 screenshots, after the entire session's R1/R2 work (proximity closure,
same-day rejection, escalation audit) had used `pivots.py`'s `daily_pivots()` only.

**1. Pivot-period discovery**: the user's real reference is "Pivots Traditional Auto 15"
on a 1h chart. TradingView's documented "Auto" behavior ties pivot period to chart
resolution — 1h charts resolve to **Weekly**, not Daily. Confirmed independently by the
visual pattern in two screenshots (DIVIS on the replay tool, Max Healthcare on live
`tv.dhan.co` — not just a replay-tool artifact): pivot line clusters hold for ~5-day
(weekly) stretches, not daily or monthly. `weekly_pivots()` already exists in `pivots.py`,
already bug-fixed (2026-08-30 ffill bug) — reused directly, not rebuilt.

**2. Same-day rejection replicates under weekly pivots too, direction unchanged, R1 gap
bigger**: rejected (≥2% overshoot + same-day close back below) vs held, subsequent ≥1R:

| Period | Level | Rejected | Held | Gap |
|---|---|---|---|---|
| Daily | R1 | 64.9% | 55.0% | +9.9pp |
| Daily | R2 | 82.8% | 56.2% | +26.6pp |
| Weekly | R1 | 82.0% | 58.6% | +23.4pp |
| Weekly | R2 | 85.1% | 56.1% | +29.0pp |

Cross-checked new daily numbers byte-identical (max diff 0.0, n=37,802) against the
already-validated `qs_litfeat_full.csv` before trusting anything new — not a pipeline bug.

**3. Circularity catch (user-caught, real)**: an overshoot-bucket "days-to-1R" table was
built comparing whole-window peak vs level to whole-window peak vs 1R price. Since R1/R2
sits BELOW the 1R price for 82-100% of events (median 0.08R-0.62R depending on
level/period), "never reached the level" mechanically forces "never reached 1R" for the
bottom buckets — arithmetic, not a finding. Upper buckets (≥5% overshoot) separately
verified NOT purely mechanical (median maxR=2.21R in that bucket, only 6.5% "just barely"
1.0-1.2R) — real continued momentum, but retract the bottom-bucket framing as invalid.
**Lesson, added to standing discipline**: never bucket by (peak vs threshold A) and then
measure (peak vs threshold B) when A and B are computed from the same extremal statistic
and A sits below B for most of the population.

**4. Static entry-time proximity (decision-time-safe, not circular) — real gradient under
Daily, flat under Weekly**:

| Level/period | 0-1% | 1-2% | 2-5% | 5-10% |
|---|---|---|---|---|
| R2 Daily, %reach 1R in ≤5d | 47.6% | 40.2% | 31.5% | 23.0% |
| R2 Weekly, %reach 1R in ≤5d | 42.7% | 41.5% | 41.8% | 43.1% |

R2-Daily is a real, clean, monotonic, decision-time-safe signal (more than halves as
distance grows). R2-Weekly is dead flat — the level sits too far away on average
(median 0.49R vs daily's 0.24R) for distance-within-it to discriminate anything.

**5. D+1 and breach-day EOD close — no gradient, near coin-flip, but genuinely mixed (not
uniformly bad)**: median D+1/breach-day close sits near breakeven (-0.01R to -0.07R)
across every proximity bucket, ~44-51% positive everywhere. Full distribution (R2-daily,
pooled, n=25,349): 11.6% already ≤-0.5R, 37.1% small red, 11.0% flat, 26.7% small green,
**13.6% already ≥+0.5R by the entry day's own close**. Mean +0.018R vs median -0.040R
disagreeing is the tell — real right tail, not uniform decay. A single median understated
this; should show the full distribution by default for any "how does the day resolve"
question going forward.

**6. Pivot-shift discovery (real, UNRESOLVED — flagged, not yet corrected for)**: R1/R2
recomputes daily in production and on the user's live chart — it is NOT fixed at entry.
Breach-day range (H-L/Close) is median 4.28% vs the prior day's 2.72% (76.2% of events
wider), because crossing a lookback-high is usually a genuine range-expansion day. Since
`R2 = PP + (High-Low)`, this mechanically pushes the NEXT day's recomputed R2 much
farther out: median distance-from-entry jumps from +0.12% (entry-day, fixed) to **+3.53%**
(next-day, recomputed) — widens in 94.6% of events. R1 similarly flips from -1.05%
(already crossed) to +1.56% (ahead again). **Every R1/R2 test in this entire session (this
one included, items 1-5 above) held the entry-day level fixed for the whole multi-day
hold — this is NOT what a live trader actually sees from day 2 onward.** Needs a redo
using day-by-day recomputed levels (both `daily_pivots()`/`weekly_pivots()` already
produce this per-day; the earlier scripts just referenced the wrong row) before any of
items 1-5's multi-day claims can be considered a match to live chart behavior. Left open
— not redone this session, per discovery-budget discipline.

**7. Intraday hold-vs-reject on the breach day (real 5-min cache, ~2026-06-10 to
2026-09-23, ~3.5 months — smaller population, not the full multi-year one)**: classified
each touched event as held (Close stays ≥ level*0.998 for 30min after first touch) or
rejected (falls below within 30min), vs never-touched at all:

| Group | R1 (n=364) median EoD | R2 (n=1358) median EoD |
|---|---|---|
| Never touched | -0.214R (worst) | -0.210R (worst) |
| Held ≥30min | **+0.196R (best)** | **+0.309R (best)** |
| Rejected within 30min | -0.063R (middle) | +0.045R (middle) |

Ordering held > rejected > never-touched confirmed WITHIN the same fine proximity bucket
too (not a proximity-mix confound) — e.g. R2 0-1% bucket alone: never-touched -0.327R,
held +0.258R, rejected -0.034R. Never-touched is the worst outcome, not rejection —
matches the "rejection = sign of life" pattern from the earlier escalation audit, now
confirmed at intraday resolution. Median first-touch time 09:25 (R1) / 10:10 (R2) — many
touches happen right at the open.

**8. Is hold-vs-reject predictable in advance? No — checked three ways, all near-coinflip**:
fine 0.25%-wide proximity sub-buckets (47-55% hold rate, no gradient), R1 vs R2 itself
(46.9% vs 51.3% hold rate — mild, not decisive), and touch-bar volume surge vs the day's
own average (held median 3.00-3.53x, rejected median 2.84-3.15x — essentially identical;
bucketed hold-rate 42-59%, no monotonic pattern). None of these predict the outcome ahead
of the touch.

**Final disposition (user-driven, practical objection, correct)**: hold-vs-reject is real
in retrospect but not tradable — unpredictable in advance (item 8) and not scalable to
watch across a real watchlist in real time; by the time it's known (30min post-touch) the
stall is already lived through. Base rates confirm the user's lived experience is the
modal outcome, not an overreaction: only 29-35% of touches end up "held." **Closed as
descriptive/telemetry only — not a filter, not an exit trigger, not worth building
around.** The two genuinely actionable survivors of this entire R1/R2 arc (this session
and prior) are: (a) **static daily-pivot proximity** (item 4, decision-time-safe, real
monotonic gradient for R2 especially) and (b) **`body_pct_SAMEDAY`** (already established
in the Feature Battle as the single strongest Blast-vs-Failure discriminator, 0.640,
unrelated to R1/R2 specifically). Item 6 (pivot-shift/daily recompute) remains a genuine
open thread, not closed — any future multi-day R1/R2 work must account for it first.

## Blast Reverse Engineering (Blast-vs-Failure, Drift ignored) — critic's one open thread (2026-09-28)

Per critic's explicit framing: Blast-vs-Drift is a noisy comparison (Drift is a mix of
real-but-slow and near-misses); Blast-vs-Failure is the cleanest supervised problem —
"why did Blast happen, why did Failure happen." No thresholds, no promotions, just
understanding — reuses the SAME Feature Battle computation already run (both effect
sizes were computed in the same pass), just re-ranked by the Blast-vs-Failure column
instead of Blast-vs-Drift.

| Feature | Blast-vs-Failure effect | Reading |
|---|---|---|
| `body_pct_SAMEDAY` | **0.640 (dominant — 2.5x the next feature)** | Outright failure is visible almost immediately: failure trades close their own breach day near breakeven (median 0.523) vs blast trades closing strongly (median 2.589). A failure doesn't lie dormant for days before revealing itself — the breach-day candle itself is weak. |
| `ema34_persistence_t1` | 0.258 | Failures carry a less-established prior uptrend (lower EMA34 persistence) going in than blasts. |
| `gap_to_trigger_pct` | -0.131 | Failures are more extended at entry than blasts — consistent with the earlier, separately-derived ON-01 Extension finding. |
| `prior_20d_advance_t1` | 0.119 | Modest — blasts had slightly more short-term prior momentum. |
| `dist_from_ema21_pct_t1` | 0.076 | Weak. |
| `base_contraction_ratio_t1` | -0.076 | Weak — the properly-rebuilt base-tightness proxy has some signal but not much for this specific split. |
| `rs_rating_t1` | 0.066 | Weak. |
| `vol_ratio_t1` | -0.015 | Essentially no power. |
| `rvol_at_breach` (separate intraday pop) | -0.006 | Essentially no power. |
| `base_duration` | 0.000 (exactly) | Confirms again — zero power over outcome *kind*, both against Drift and against Failure. |

**Understanding, not a filter**: outright failure isn't really a pre-entry phenomenon —
none of the T-1 features come close to `body_pct_SAMEDAY`'s effect size, and that field
is only known at the close of the breach day itself, after the trade already exists.
This matches the earlier live-trading discussion this session almost exactly: a weak,
give-back-heavy breach-day close is a real tell for failure, but it can't be screened
for in advance — it's a same-day/next-day management signal (candidate for an early-cut
rule), not an entry gate input. Consistent with Rule #21: this is a real, strong, useful
signal, but "useful" here means "acted on after entry," not "filtered before it."

**Disposition**: understanding-only, per critic's explicit scope — no threshold chosen,
no promotion. If a future session wants to act on this, the natural next question is
narrowly scoped: does an early same-day/D+1 cut rule keyed off `body_pct_SAMEDAY` improve
the product objective net of the population/opportunity cost it removes (Rule #21's own
test) — not "is the signal real" (already answered: yes, decisively).

## RQ-QS-01 — Opportunity Cost of Occupancy (2026-09-28, critic-approved, first result)

Full spec in `swing_qs/trajectory_replay/RQ-QS-01.md`. Found by the user watching
AEGISLOG's real 1h chart and spotting a second, clean pin-bar-reclaim setup on 2026-09-18
that the research population structurally can't see — the real 10-day trigger fired
2026-09-10 (first gate-*passing* trigger; 09-09 also touched the raw threshold but
didn't clear the v0.1 gate) and stayed open/unresolved through the last cached date,
blocking every subsequent trigger on the same name via the standard single-position-
per-ticker convention. Critic: "that's a simulator convention, not a market truth."

**Self-contained rebuild, not reusing `qs_raw_{N}d_full.csv`**: that file's occupancy
windows were built with `population_builder`'s real primed_engine trailing-stop exit —
a different convention from QS's own frozen product (S1b fixed stop). Re-walked the
single-position simulation using ONLY QS's real mechanics (raw N-day trigger, frozen
v0.1 gate, S1b stop, MAX_TRACK_DAYS=15 cap) so A and B are measured on the same terms
everything else in this project uses.

**Phase 1 — frequency (per guardrail: report this before quality)**: 500/500 tickers
have ≥1 blocked trigger. 46,568 A positions taken (all 3 lookbacks); **79,614**
v0.1-gate-passing triggers blocked by an already-open position — more blocked
candidates than positions actually taken.

**Phase 2 — blocker state at the moment of blocking**:

| State | n | % |
|---|---|---|
| winner (A already ≥1R) | 35,901 | 45.1% |
| proven (A ≥0.25R, <1R) | 21,136 | 26.5% |
| unresolved (A <0.25R, not stopped) | 21,308 | 26.8% |
| underwater (A negative) | 1,269 | 1.6% |

26.8% unresolved-blocking rate crosses critic's own pre-declared bar (18-25% = "a real
structural issue," not "AEGISLOG is just memorable").

**Phase 3 — outcome by blocker state (the real payoff table)**:

| Blocker state | A loses/B loses | **A stalls/B BLASTS** | A wins/B loses | A wins/B wins |
|---|---|---|---|---|
| winner | 9.1% | **~0.0%** (1 of 35,901) | 61.1% | 29.8% |
| proven | 50.5% | 2.8% | 18.7% | 28.0% |
| unresolved | 52.5% | **4.2%** | 17.5% | 25.8% |
| underwater | 61.2% | **7.5%** | 6.1% | 25.1% |

**Confirms critic's hypothesis precisely, not just directionally**: blocking while
already sitting on a proven winner is essentially costless (practically zero
stalls-then-blasts cases across 35,901 events). The real, quantified cost concentrates
exactly where predicted — unresolved/underwater blockers lose a materially better
signal 4.2-7.5% of the time, worse the more clearly the blocker is already failing.
Top 25 examples are real, liquid, well-known names (SWANCORP, AIIL, COROMANDEL, ABB,
DMART, TRENT, ULTRACEMCO, INDIGO among them), not obscure noise — full data in
`swing_qs/trajectory_replay/replacement_analysis.csv` and `blocked_trigger_calendar.csv`.

**AEGISLOG body% example — illustrative only, NOT additional evidence** (critic
correction, 2026-09-28, Rule #19 discipline): the user separately flagged real
discomfort about the specific breakout candle itself — "by the time I'm entering, most
of the momentum is already gone." Checked directly: AEGISLOG's 09-10 entry (₹1365.49)
fires at 09:15; that SAME 5-min bar spikes to ₹1384.60 — almost the entire day's
eventual High (₹1385.00) is consumed in the first 5 minutes — then the session grinds
down all day to close ₹1307.60. This trigger has `base_duration=0` (no real base),
`gap_to_trigger_pct=1.64%` (modest enough to still clear the v0.1 conditional gate),
and `body_pct_SAMEDAY=-3.23%`. `body_pct_SAMEDAY` was ALREADY established as the
strongest Blast-vs-Failure discriminator by the Feature Battle (0.640 effect) — this
one example illustrates that finding vividly, it does not strengthen it. Explicitly
flagged so a single memorable chart never gets miscounted as a second data point for
an already-closed statistical question. One real, separate contribution this DOES
make: it's a clean illustration of Rule #21's distinction — entry-time features
(`base_duration`/`gap_to_trigger`) passed this trigger; same-day telemetry
(`body_pct_SAMEDAY`, only knowable after the candle closes) already knew better.
Passing the entry gate never guaranteed a clean same-day close. **`body_pct_SAMEDAY`
stays frozen as telemetry/replay-annotation only — explicitly NOT promoted to an exit
or filter tonight** (critic: the moment this gets a rule, the next step is body% →
close location → engulfing → wick → volume → RSI, rebuilding candlestick exits we
already spent two weekends proving don't beat holding).

**Disposition**: RQ-QS-01's bounded deliverable is complete — no new filters, no exit
redesign, no threshold tuning, per its own guardrails. Sent to critic with the full
report. Two natural, NOT-yet-started follow-ups this surfaces (do not start without
new sign-off): (a) should a decisive time-based/replacement exit rule exist
specifically for the `unresolved`/`underwater` blocker-state cases, since that's where
the real cost concentrates; (b) does `body_pct_SAMEDAY` deserve a same-day/D+1
management role now that two independent lines of evidence (Feature Battle's ranking,
this real worked example) point at it.

**Critic's tighter A-stalls/B-blasts redefinition (2026-09-28, tiny tweak not a new
RQ)**: A stalls = never reaches +1R by day10 (from A's own entry) OR closes below
+0.25R at day10; B blasts = ≥2R specifically by day5 (not "eventually within 15 days").
Recomputed against the same 79,614 blocked events:

| Blocker state | A OK/B no blast | A OK/B blasts | **A stalls/B blasts (strict)** | A stalls/B no |
|---|---|---|---|---|
| winner | 73.0% | 18.4% | **0.6%** | 8.0% |
| proven | 37.7% | 18.0% | 2.7% | 41.5% |
| unresolved | 34.7% | 16.3% | 2.4% | 46.6% |
| underwater | 25.5% | 16.1% | 3.5% | 54.9% |

Core finding survives the stricter test: winner-blocker stays by far the safest state
(0.6% vs 2.4-3.5% elsewhere) — roughly 4-6x safer, same qualitative ordering as the
looser definition, though absolute magnitudes compress (overall rate 1.68% vs the
looser 2.0%) since "stalls" is now an easier bar to clear (~30% of all blocked events
qualify as "A stalls" under this definition vs the loose definition's narrower buckets).
Confirms the winner-blocker "leave it alone" conclusion is robust to definition choice,
not an artifact of a loosely-drawn boundary.

## RQ-QS-02 — Replacement Policy (2026-09-28, critic-approved, bounded to 3 policies)

Full spec: three policies only, no proven/winner replacement, no scoring. Genuine
re-simulation (not a post-hoc reclassification of RQ-QS-01's descriptive data) — at
any moment exactly one position is open per ticker, replacing A with B closes A
immediately (realized at that day's close) before B opens, never both held at once,
per the "no overlapping positions" guardrail. Same mechanics as RQ-QS-01 (raw N-day
trigger, frozen v0.1 gate, S1b stop, MAX_TRACK_DAYS cap).

| Policy | n trades | mean R | median R | win% | total R | n replaced |
|---|---|---|---|---|---|---|
| never_replace (baseline) | 46,572 | 0.1776 | -1.0 | 35.9% | 8,268.6 | 0 |
| replace_unresolved | 48,331 | 0.1590 | -1.0 | 35.5% | 7,685.4 | 1,568 |
| replace_underwater | 46,574 | 0.1775 | -1.0 | 35.9% | 8,267.2 | 3 |

**Falsifies critic's own pre-written falsifiable prediction** ("I expect replace
unresolved only to improve QS... by a modest amount"). `replace_unresolved` makes
mean R and total R WORSE, not better, despite more trades taken (a real, disclosed
negative result, not a null result). `replace_underwater` is a non-event — only 3
actual replacements fire across the whole 5-year/500-ticker universe, statistically
identical to baseline, because RQ-QS-01's descriptive count (1,269 underwater-state
blocked instances) counts repeat blocks against the SAME persistently-open A over its
whole life, while this live simulation removes A the moment one replacement fires —
most of those 1,269 counted instances were repeat touches on a small number of
already-open positions, not independent replacement opportunities.

**Disposition**: per critic's own pre-committed framing ("if the RQ says no
improvement, we close the replacement thread with confidence") — **closed**. The
opportunity-cost phenomenon documented in RQ-QS-01 is real and real-money-relevant to
watch (via the trajectory replay tool / live telemetry), but a mechanical replacement
policy built on the blocker's simple R-state does not improve portfolio expectancy —
if anything it's a net negative. No further replacement-policy work without new
evidence.

## QS Trajectory Replay — Minimum Viable Replay v1, first Observe-stage result (2026-09-28 late)

Built exactly per critic's approved A-G verdict on `REPLAY_BRIEF.md` (section B: no exit
simulation, no replacement, no new filters, no BLAST/DRIFT/FAILURE labels). Code and
outputs in `swing_qs/trajectory_replay/mvp_v1/`.

**Sample**: 100 candidates, deterministic stratified draw (25 early/25 mid/25 late/25
random period, fixed seed) from the real 1,782-candidate v0.1-gate-passing pool with
intraday coverage. AEGISLOG deliberately excluded — kept separate as illustrative-only.
96/100 replayed successfully (4 excluded, no real intraday touch found — CONCOR,
CANFINHOME, ZEEL, JSWSTEEL — logged in `excluded.csv`, a ~4% data-coverage gap, not a
bug). Sanity-checked the replay engine against AEGISLOG's already-known-correct numbers
before trusting it on the real sample (D0 close_r=-0.597 matches the independently
computed -4.24%/7.096% risk from earlier tonight, exactly).

**Deliverables produced**: per-bar trajectory table (41,063 5-min bars,
`per_bar_trajectory.csv`), events table (MAE/MFE, first R-thresholds, first
return-to-trigger/reclaim, `events.csv`), D0-D5 state table (`state_table_D0_D5.csv`),
and normalized trajectory plots (`plot_overlay_all.png` + three small-multiples grids
covering all 96 trades individually).

**Purely descriptive numbers** (no labels, no thresholds chosen): MAE median -0.633R
(10th-90th pct -1.70R to -0.20R), MFE median +1.024R (10th-90th pct 0.17R to 2.80R). D0
closes above trigger 52.1% of the time, D5 above trigger 60.4%. 99% of trades touch
back down to the trigger at some point after moving away, and of those, 87% (83/95) go
on to reclaim above it again.

**Observe-stage finding (eyeballed across all 96 individual trajectory plots — NOT yet
a measured/Described definition, disclosed as such)**: five recurring shapes, tallied
by eye:

| Shape | Approx. count / 96 |
|---|---|
| Flat/quiet, then late resolve (either direction) | ~28-30 |
| Steady, clean failure, no recovery | ~12-15 |
| Choppy, never resolves either way | ~10-12 |
| Immediate blast, then multi-day giveback (AEGISLOG's shape) | ~6-8 |
| **Immediate blast, sustained** (the archetype QS is explicitly built to catch) | **~7-8** |

**The uncomfortable headline**: the one shape QS's whole product thesis is built
around — immediate, sustained continuation — looks like roughly the rarest outcome in
this sample (~7-8%), not the common one. "Flat-then-late-resolve" and "steady clean
failure" together are well over half the population. This directly bears on critic's
stop-condition F ("is QS trajectory coherent") and needs to be checked with a real,
precise measured definition (the "Describe" step), not left as an eyeball count, before
drawing any conclusion about QS's viability.

**Disposition**: this is Observe-stage output only, exactly per the approved protocol
— not a finding to act on yet. Two likely data-quality outliers flagged, not yet
excluded from anything: HFCL (stale/stepped prices, suspicious of a low-liquidity
artifact) and BHARATFORG (one sudden, large discrete gap, likely a real news/earnings
event, not organic price action) — worth a second look before either counts as
"typical" QS behavior. Next step per critic's protocol: Describe — turn
"flat-then-late-resolve" into a precise, measurable definition and re-check its
frequency against the full 96 properly, not by eye.

**First Describe-stage attempt (2026-09-28 late) — a real difficulty, not a clean
definition**: per critic's explicit instruction, described "immediate blast,
sustained" FIRST (not "flat-then-late-resolve," despite it being the largest visual
bucket) — critic's framing: define the target trajectory, not the largest non-target
one. Studied the 7 eyeballed examples precisely; dropped CYIENT (its
`first_new_post_entry_high_min`=1660 — over a day — reveals it's actually a
flat-then-late-resolve case, miscategorized by eye). Remaining 6 (TECHM, LODHA,
SONACOMS, PPLPHARMA, INDGN, HINDZINC): MFE 1.9-4.9R, sustain_ratio (D5 close/MFE)
0.61-0.78, all make SOME new post-entry high within 5-40min, but first +0.25R proof
ranges from 25min to 1395min (over a day) across the same 6 — no consistent speed.

First measurable definition tried (fast new high ≤40min + MFE≥1.9R +
sustain_ratio≥0.6): blind-applied to all 96, matched **12**, not the eyeballed ~7-8 —
new names APARINDS, CDSL, POONAWALLA, MANKIND, **INDIGO**. INDIGO's inclusion exposed
the flaw directly: its "new high within 5min" is a trivial 0.157R→0.223R increment,
nowhere near its real 3.944R peak which arrives much later — genuinely a
flat-then-late-resolve trade that cleared a too-weak bar. Tried tightening to "reaches
+0.5R within one trading day" instead of "any new high" — this fix broke on the
CONFIRMED examples instead: LODHA/SONACOMS/INDGN/HINDZINC all take well over a day to
first reach 0.5R despite being real, visually-confirmed archetype members.

**Disposition**: stopped rather than keep silently trying thresholds until one
happens to fit all 6 (exactly the overfitting-to-visually-compelling-charts failure
mode flagged in the replay brief's guardrails). The "immediate" quality seen by eye
does not correspond to any single speed-based threshold tried so far. Sent to critic
as an open question rather than resolved unilaterally — candidates for the real next
step: redefine around persistence/consistency of progress instead of a single
crossing-time, or drop "immediate" from the definition entirely and measure "sustained
winner" on magnitude/retention alone.

**Decomposition result (2026-09-28 late) — a real negative result, per critic's exact
protocol**: decomposed the 6 confirmed examples on every requested dimension (no
thresholds). Key finding: `time_to_mfe` is 8500-10200 minutes for ALL SIX — roughly
the entire 5-day observation window. None peak early; all are still near their best
point when the window ends. `time_to_half_mfe` (2840-6960 min) confirms none reach
even half their eventual move on day 1. Daily higher-high sequences are genuinely
heterogeneous across the six (LODHA perfectly monotonic 6/6; INDGN plateaus after
day1, only 2/6; the rest mixed give-back-then-partial-recovery) — not internally
homogeneous even before comparing to the other 90.

Two continuous axes across all 96 (`d0_max_r` = early expansion, max R on D0 alone;
`mfe_r` = eventual peak; `max_giveback_r` = giveback from peak), six examples
highlighted, plotted in `plot_two_axes.png`:
- d0_max_r vs MFE: the six do NOT cluster — spread 0.20 to 0.95 on the x-axis, just
  sitting near the top of MFE wherever they land.
- d0_max_r vs max_giveback: the six DO cluster (0.7-1.2R giveback, lower-middle of
  the full 0-4+ range) — moderate giveback despite some of the highest peaks in
  the sample.

**Synthesis**: the six share no early, observable structural signature — no common
expansion speed, no common D0 magnitude. What they share is a hindsight-only property
(big eventual winner, didn't give most of it back). No visible early precursor
separates them from the other 90 before the outcome is already known. **The original
"immediate blast, sustained" visual archetype looks like a perceptual grouping (biggest
eventual winners, seen after the fact), not a real, early-detectable trajectory class**
— at least not on the two axes tested (D0 magnitude, giveback-from-peak). Sent to
critic as the valuable-negative-result their own protocol anticipated, with an open
question: is there truly no early tell, or were D0-magnitude/giveback simply the wrong
two axes to decompose on (e.g. first-pullback shape or D0 volume/participation
untested so far).

## 1H structure layer — data infrastructure note (2026-09-27 late, Stage A prep, not a finding)

Built `../resample_1h.py` (tests in `../tests/test_resample_1h.py`): resamples the
existing 5-min `intraday_cache` into 1H OHLCV, bins anchored at 09:15 IST and never
straddling a session (09:15, 10:15, 11:15, 12:15, 13:15, 14:15, plus a 15-minute stub at
15:15 where the session runs to 15:30 — same shape a broker chart or Dhan's 60-min
endpoint gives, so a future 5-year pull slots in without re-binning). Output in
`../intraday_cache_1h/<ticker>.csv`, one row per bar with `n_bars`/`expected_bars`/
`complete` so holes are visible, not silent, and `session_close` per row. Reshapes data
only — no swings, levels or features live here (Stage 0 rule intact).

**Session close is per ticker and per date, applying the OX1 Continuous Trading Rule
at the data layer** (user-caught on first cut, which had assumed 09:15-15:30 for
everyone): F&O names (`fo_universe.csv`) on/after CAS 2026-08-03 have a 09:15-15:15
continuous session = exactly six full hourly bins, no stub; any 5-min bar at or after
15:15 on those days is auction residue and is dropped, not aggregated (the thin 15:15
bar yfinance emits on ~71% of post-CAS F&O days has roughly a quarter of the 15:10
bar's volume — it is the auction boundary leaking, not trading). Non-F&O and pre-CAS
sessions keep 09:15-15:30 with the 3-bar stub.

Validation on all 500 tickers, 74 sessions (2026-06-10 to 2026-09-23), 251,209 bars:
- Session-level Open/High/Low/Close/Volume rebuilt from 1H equal the 5-min source over
  the same continuous window exactly, 0 mismatches.
- `session_close` mix: F&O 7,770 sessions at 15:15 and 7,770 at 15:30 (the window
  straddles CAS start almost evenly), non-F&O 21,458 at 15:30.
- Incomplete bins: 1,579 of 251,209 (0.6%). 1,276 interior (a missing 5-min bar
  between 09:15 and 15:15, lunch-hour heavy — yfinance gaps on thin names) and 303
  stubs, all on 15:30 sessions where the feed truncated the tail.
- 1H-rebuilt session High/Low vs `data_cache` daily: median abs diff 0.02%, ~2% of
  sessions deviate >0.5%, and the sign is consistent (1H high slightly below daily high,
  1H low slightly above daily low) — the daily feed includes prints the 5-min feed does
  not. Pre-existing feed difference, not introduced by resampling; identical before and
  after CAS.
- Replay population (`trajectory_replay/mvp_v1/events.csv`, 96 events), 5 prior sessions
  of 1H bars: 89 fully complete, 6 too close to the window start (fewer than 5 prior
  sessions), 1 with an interior hole (CONCORDBIO 2026-07-31, one 11-bar bin on 07-27).
  89/96 usable for the pre-breakout structure audit.

## Stage A — pre-breakout 1H structure audit (2026-09-28): no common 1H setup behind the confirmed six

Question tested (from the 1H-hypothesis memo): do the desirable QS moves sit on a
recognisable 1H swing/base immediately before the breakout that the daily chart hid?
Code: `structure_1h/01_pre_breakout_1h_audit.py` (features + `AUDIT_SUMMARY.md`),
`structure_1h/02_plot_examples.py` (`plot_confirmed_six_1h.png`). Preflight answered in
the script header. Population: the 96 replay events, 88 audited (7 lacked five complete
prior 1H sessions, listed in `structure_1h/excluded.csv`; TECHM 2026-07-13 appears twice
in events.csv under two entry_definitions and was counted once). Entry clock: only 1H
bars whose close is at or before the first 5-min trigger touch; k=1 swing points on
already-closed bars. 21 descriptors, no thresholds, no rule.

**Eyeball (the six + AEGISLOG as illustrative only)**: heterogeneous. TECHM = pullback
then gap-up shelf; LODHA = V-bottom then a steady 1H staircase into the trigger;
SONACOMS = flat chop; PPLPHARMA = rally, pullback, chop under the highs; INDGN = range
with a late push; HINDZINC = rally then a flag; AEGISLOG = rally, lower-high pullback,
higher low, push. Nothing that reads as one setup. One shared trait is NOT 1H
structure: five of six breached before 11:40 with 0-2 entry-day bars closed, and the
trigger sat 1.2-2.4% above the last 1H swing high in five of six (LODHA 0.1%) — the
breakout arrived as a morning drive/gap through a daily level, not as a 1H base
resolving at its own high.

**Six vs rest (n=6 vs 82, Cliff's delta)**: the six show tighter recent 1H ranges
(range_contraction_12v18 -0.37, last_session_range_vs_prior5 -0.35, 6v24 variant -0.20,
same sign), a last close lower in the 30-bar range (close_position -0.46), more swing
points (n_swing_highs +0.36) and a lower efficiency ratio (-0.30). With n=6 these are
suggestions, not findings.

**Blind check, reached 0.25R by D5 vs not (n=77 vs 11)**: the contraction signals
vanish (12v18 +0.04, 6v24 +0.02, last-session ratio +0.02); close_position -0.01;
swing counts -0.05. What does move: a wider 30-bar consolidation (+0.36) and a trigger
further above the last 1H swing high (+0.35) in the FAST group — i.e. the opposite of
"tight base, breakout at its own high" — plus two timing features that are not 1H
structure (0 vs 2 entry-day bars before breach, -0.33; smaller open gap, -0.30).

**Rank correlations, all 88**: nothing above |0.36|. higher_lows_run vs mfe_r +0.27 and
vs D5_close_r +0.18 is the only structural descriptor with a consistent sign across
outcome axes. last_session_range_vs_prior5 vs max_giveback_r -0.36 and
consolidation_width_pct_12 vs max_giveback_r -0.34 (tighter pre-breakout range,
bigger later giveback) are post-entry-trajectory associations, exploratory only.

**Disposition (Rule #17, #19, #21)**: on this window the 1H chart does not organise the
six into a recognisable setup, and the small-n contraction hint fails the blind split.
Stage A does not support building a 1H swing algorithm (Stage B) yet, and does not
justify the 5-year Dhan pull on this hypothesis alone. Two exploratory threads only:
(1) higher_lows_run, to be re-checked with pre-declared k=2 pivots and 18/42-bar
lookbacks before it is called anything; (2) the "morning drive through a daily level"
trait of the six is a trigger-timing property already partly known
(`n_entry_day_bars_before_breach`), not new structure. Logged as closed-negative for
"common 1H base behind the six", open-exploratory for the two threads.

## Hourly entry recipe — running the QS breakout logic itself on 1H bars (2026-09-28 late)

Distinct from Stage A above (which tested 1H structure BEFORE a daily-defined
breakout, closed negative). This tests the user's separately clarified intent: redefine
the entry population with the HOUR as the base unit, same recipe as the frozen v0.1
gate (raw N-bar-high breakout + base_duration/gap_to_trigger conditional), reading
`intraday_cache_1h/` directly. Code: `swing_qs/structure_1h/03_hourly_entry_recipe.py`.

Two lookback conventions tested since no single hourly-swing-trading standard exists
(checked online — 20-bar lookback is a commonly cited retail convention, nothing
universal): **literal** (N_hours = 10/20/40, same numbers as daily, unit relabeled) vs
**wall-clock** (N_hours = 65/130/260, ≈10/20/40 trading days of context at the cache's
own ~6.5 bars/session average, same real-world window as the daily recipe).

**Real bug caught by direct user question ("is the SL the low of the previous candle
or previous day?")**: first pass used the prior HOURLY bar's low as the stop — far too
tight, and it silently inflated every winning trade's measured R (R is defined
relative to the stop distance; a tiny stop denominator makes ordinary gains look like
big R-multiples, while a stop-out still costs exactly -1R regardless of stop width —
the two are not on a comparable scale). Explains the suspiciously good-looking first
numbers (stopped%~80%, but literal-20h mean R +0.145, oddly close to the daily
product's own baseline mean R of +0.1776 from RQ-QS-02 — a coincidence created by the
inflation, not a real correspondence).

**Corrected** (stop = prior TRADING DAY's low, aggregated across that session's hourly
bars, matching real S1b semantics — not the prior hourly candle):

| Variant | Lookback | n | mean R | win% | stopped% |
|---|---|---|---|---|---|
| Literal | 10h | 2,949 | +0.036 | 28.0% | 67.7% |
| Literal | 20h | 2,338 | -0.037 | 29.1% | 65.1% |
| Literal | 40h | 1,628 | -0.102 | 28.2% | 65.3% |
| Wall-clock | 65h | 1,129 | -0.119 | 30.1% | 62.1% |
| Wall-clock | 130h | 669 | -0.136 | 29.1% | 61.6% |
| Wall-clock | 260h | 297 | -0.246 | 29.0% | 60.3% |

**Disposition**: with a properly comparable (day-scale) stop, none of the six variants
show a real edge — literal-10h is roughly breakeven (+0.036), everything else is
negative, wall-clock degrades monotonically as lookback grows (partly data-starvation
given only ~70 days / ~455-481 bars per ticker exist — the 260h lookback alone
consumes more than half that window before any event can fire). This is Stage 0 only —
one single ~3.5-month window, zero robustness/sub-period checks, no blind validation —
not a finding to act on either way. Does not currently support pursuing an hourly-bar
QS entry recipe further on this data. Real next fork, not yet decided: extend the
robustness checks on literal-10h specifically (the only non-negative variant) using
just this window, or acquire more hourly history first (Dhan/Upstox APIs, per the
1H-hypothesis memo) before trusting anything here further.

## Daily vs 1H structural sanity check — H2 verdict (2026-09-28 late)

Per critic's revised recommendation (reading the overfitting/multiple-testing
literature first, then explicitly retracting the earlier "early/late split
literal-10h" suggestion as a mild selection-after-seeing-result risk): no more
backtesting on the hourly recipe. Instead, a purely visual, non-metric sanity check
of the underlying hypothesis (H2: "1H is a useful representation of the QS swing
itself, distinct from daily") before spending anything acquiring more history.

**Method**: 6 already-confirmed winners (fixed set from the decomposition work) + 6
failures selected by an objective, mechanical, disclosed rule (worst D5_close_r in the
96-trade replay pool: ASTERDM, BHARATFORG, SWIGGY, SBICARD, INFY, HOMEFIRST) — not
eyeballed, to avoid selection bias. For each: daily candles (15 bars into the breach)
plotted directly above the matching 1H candles (5 prior sessions + entry-day bars
closed before the breach), side by side, no metrics computed, no swing definition
designed. Code: `swing_qs/structure_1h/04_daily_vs_1h_sanity_check.py`, output
`plot_daily_vs_1h_sanity.png`.

**Finding**: in all 12 examples, the 1H chart does not reveal anything the daily chart
didn't already show — both timeframes tell the same shape at different resolution
(e.g. LODHA's V-bottom-then-rally, SONACOMS's initial pop then chop, INDGN's choppy
range are equally visible/equally ambiguous on both). No case showed a "hidden
coherent swing" that daily bars were aggregating away. Winners and failures also look
visually similar to EACH OTHER on both timeframes — no obvious eyeball-level tell
separates the two groups (ASTERDM, a failure, and HINDZINC, a winner, have nearly the
same silhouette).

**Disposition**: direct, negative answer to critic's stated H2 question ("does the 1H
chart make the QS swing visibly/mechanically coherent across both good and bad
examples") — independently consistent with every other check run tonight (Feature
Battle's zero-power `base_duration`, Stage A's no-common-1H-setup, the decomposition's
no-early-signature). Per critic's own pre-stated stopping rule, this is grounds to
close the "1H is the missing structural layer" hypothesis without acquiring more
hourly history or building a swing algorithm — not proceeding to Stage B/C on this
thread. Sent to critic as the H2 verdict.

## 1H "missing structural layer" hypothesis — formally CLOSED, negative (2026-09-28 late)

Critic's final verdict, confirmed: close it. Three independent tests, all pointing the
same direction: (1) direct 1H entry recipe, stop made comparable — no meaningful edge;
(2) Stage A pre-breakout 1H structure audit — no common structure among the confirmed
winners, fails a blind split; (3) daily-vs-1H visual sanity check (mechanically
selected winners + failures, no metrics) — 1H exposes no hidden swing that daily
loses, and winners/failures remain visually similar to each other regardless. The
earlier Feature Battle result (`base_duration`'s zero discriminating power) is
supportive: the existing daily descriptors aren't secretly encoding the wrong
timeframe either — the signal simply doesn't show up at either resolution tested.

**Precise scope of the closure (do not overstate)**: this does NOT establish "hourly
data is useless for QS" — 5-minute intraday data is already proving useful for
post-entry execution/trajectory research (the replay tool). It establishes the
narrower claim: **1H is not currently the missing structural representation needed to
define what makes a breakout a good QS candidate.** No more 1H data acquisition
(the Dhan/Upstox 5-year pull is explicitly not justified by any surviving hypothesis),
no hourly swing algorithm, no further parameter tuning on the hourly recipe. The
`structure_1h/` research track is done for now.

**The real open question this leaves, carried forward**: daily structure alone is
insufficient (Feature Battle), porting the recipe to 1H finds no edge, 1H hidden-swing
structure isn't observed, and 5-min post-entry trajectory is informative but shows no
universal "blast" signature (the decomposition result). Neither daily structure nor a
lower timeframe reliably distinguishes a good QS candidate from a bad one on the
evidence gathered so far. **What exactly makes a breakout suitable for a short-duration
continuation trade, if neither daily structure nor a lower-timeframe swing reliably
distinguishes it — that is the standing, unresolved question for whenever this research
resumes.**

## RQ-QS-06 — QS-A Early Monetization Envelope (2026-09-29, critic-specified, answers the real-stakes question)

**Why this exists**: after BPC (D3), the impulse-rest population (04A-C), and the
base-quality triple-cut (05A) all closed negative or failed robustness, critic's
explicit pivot: stop inventing new entries, ask instead whether the ALREADY-REAL
QS-A edge (never rejected on entry quality, only judged too slow for options)
contains a genuine early, options-compatible monetization window. Pre-declared
decision tree: (A) little early movement -> QS-A is structurally a slow
continuation edge, stop forcing it into options; (B) real early movement that
gets given back -> exit/harvesting becomes the frontier, AEGISLOG-style; (C) real,
persistent early movement -> stop searching for entries, move to OX1/execution.

**Method**: frozen inputs only, exactly as specified — reused `walk_ticker()` from
`rq_qs_01_opportunity_cost.py` VERBATIM (imported, not reimplemented): same raw
10D/20D/40D trigger, same v0.1 gate (`passes_v01_gate`), same S1b stop, same
single-position walk. No new filter, no new pattern, no parameter optimization —
this script adds ONLY a D1-D5 measurement layer on top (MFE/MAE, first-hit day per
R level, giveback, unresolved%). n=46,613 frozen QS-A positions, full nifty500
universe, all three lookbacks.

**Bug caught and fixed before trusting the aggregate (Rule #22)**: hand-verifying
the two most extreme giveback rows found TRENT's 2025-12-24 entry showing a
fabricated -17.26R "loss" on D5 — a real 33.04% overnight bonus-issue drop that
slipped past production's shared `corp_action_day` column, whose 35% threshold
missed this specific ratio. Added a stricter, independent 25% check inside this
script (not a change to the shared production column) — 64 of 46,613 rows
truncated as a result. Aggregate percentiles barely moved (they were already
fairly robust to ~74 outliers out of 46,613), but this needed fixing and
disclosing regardless. A remaining 65 rows with |close_r_D5|>10R were checked and
are real, not artifacts: entries with an unusually tight S1b stop (~0.5% initial
risk) turning an ordinary 7-9% move into a 15-27R multiple — a known tail of the
S1b risk-unit convention, not a bug.

**Result — clear, substantial early movement exists (rules out Outcome A)**:

| R threshold | reached by D5 | median day |
|---|---|---|
| 0.25R | 76.4% | 1 |
| 0.5R | 63.9% | 1 |
| 0.75R | 52.2% | 1 |
| 1.0R | 41.7% | 2 |
| 1.5R | 26.8% | 2 |
| 2.0R | 17.4% | 3 |

Median running MFE (High-based, cumulative) climbs steadily: **+0.35R by D1**,
+0.49R by D2, +0.61R by D3, +0.71R by D4, **+0.80R by D5**. This directly refutes
"little early movement" — most of a 15-day QS-A trade's eventual favorable
excursion is already visible intraday within the first 1-2 days.

**But the median CLOSE stays near flat every single day** (close_r_D1..D5 medians:
-0.03R, -0.02R, -0.01R, -0.01R, -0.00R) — a striking, separate finding from the
giveback stat below: even though the running peak grows every day, the typical
trade's own daily CLOSE never shows a real gain through D5. Whatever favorable
excursion happens intraday round-trips back to roughly breakeven by the time a
close-based decision point would even see it, for the median trade. This is the
sharpest single fact for an OPTIONS product specifically, which needs a real edge
AT the decision moment, not merely "the stock touched a good price sometime."

**Giveback (Outcome B, confirmed) — among the 63.9% that touch >=0.5R at some
point by D5**:

| | |
|---|---|
| Median giveback from D5's own peak | **55.6%** |
| Give back >=50% of peak | 54.1% |
| Give back >=80% of peak | 35.3% |
| Give back the ENTIRE move (close<=0 despite touching 0.5R+) | **27.2%** |

**MAE is symmetric and fast too**: median running MAE is already -0.34R by D1,
-0.73R by D5; 37.1% are stopped out (-1R, S1b) by D5, median day 2. Real risk
shows up just as fast as real opportunity.

**Unresolved (no stop yet, no 1R yet)**: 68.3% at D1 falling to 27.9% by D5 — QS-A
genuinely resolves fast, consistent with its own "quick swing" self-description;
by D5 roughly 72% of positions have already either proven out (>=1R) or stopped.

**Answer to the pre-declared branching question: Outcome B, not A or C.** Real,
fast, substantial early movement clearly exists (median +0.80R MFE by D5, 63.9%
touch a meaningful 0.5R excursion within 5 days) — QS-A is NOT structurally a slow
continuation edge with nothing to monetize early. But the median trade gives back
more than half of that peak by D5's close, and over a quarter give back the whole
thing. Per critic's own pre-declared decision tree, this makes **exit/harvesting
the legitimate next research frontier** — not another entry search, and not yet a
specific exit rule (none chosen here, per the explicit "don't immediately test
another stock exit" instruction). AEGISLOG (real, live, not research — see the
same-session trade-monitoring note) is a motivating real-world instance of exactly
this shape (real early continuation to +2.86% at a valid signal, later a much
larger peak, then a full round-trip below entry) but is NOT being used as a rule
here, per critic's own caution against treating one example as the answer.

**Not yet done, by design**: no exit rule, no threshold on WHEN to harvest, no
options translation (OX1), no comparison to the existing MAX_HOLD_DAYS=15/S1b/
ZigZag mechanics already used elsewhere. This is the "Observe" step only, matching
this project's own established Observe -> Measure -> Decide discipline.

**Files**: `trajectory_replay/rq_qs_06_early_monetization_envelope.py`,
`trajectory_replay/rq_qs_06_envelope.csv` (46,613 rows).
