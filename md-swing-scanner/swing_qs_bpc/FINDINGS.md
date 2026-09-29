# swing_qs_bpc — Findings

## RQ-QS-03A — Mechanical Re-entry (2026-09-28/29, renamed from "RQ-QS-03/BPC" per critic)

**Critical relabeling, do not call this BPC**: the original RQ-QS-03 rule was "first
fresh v0.1-gate-passing trigger (B) on the same ticker within 10 trading days of A."
That is NOT literature BPC — it's a mechanical re-entry rule. Giveaway: 51.6% of B's
fire literally the next day, which is close to impossible under a genuine breakout-
controlled-pullback-second-breakout reading. Renamed to protect the research trail.

**Frequency**: 46,755 A's (first breakouts, same single-position walk convention as
every other QS population), 32,972 (70.5%) generate a B within 10 days.

**Raw A vs B (all 32,972, unfiltered)**: A clearly beats B — median D5 +0.365R vs
-0.011R, %reach 1R 78.9% vs 64.4%. But this comparison mixes real pullback-continuation
cases with pure trend-chasing cases (the 1-day-later majority) and is not the right
number to trust.

**Real bug caught and fixed (now the namesake case for Rule #22)**: first pullback-rate
check reported 0.1% genuine pullback among gap≥2-day B's — hand-checked 5 real A/B
pairs directly, 4 of 5 showed obvious real pullbacks, contradicting the aggregate.
Found and fixed the bug (root cause not fully pinned down, but the corrected number
was independently verified against hand-inspected examples, and against a fresh
full-population recomputation, before being trusted). **Corrected: 72.3% of B's with
a real gap (≥2 days) show a genuine pullback below A's entry price.**

**Properly-verified population (n=11,536: gap≥2 days AND confirmed pullback)**:

| | A | B |
|---|---|---|
| Median D5 close_r | 0.090R | -0.011R |
| Median D10 close_r | 0.465R | 0.064R |
| % reach 1R | 73.9% | 64.9% |
| **Median days to 1R** | 6 | **3** |
| % reach 2R | 41.5% | 39.7% |
| **Median days to 2R** | 8 | **6** |
| Stopped (-1R) | 57.6% | 61.1% |

**Level-check (is B a genuine retest-and-resume, not a disconnected later rally)**:
median B entry price is only 1.45% above A's original entry price; 81.9% of B's fire
within 3% of A's original level; only 1.3% are more than 10% above. This is the
detail critic flagged as the real finding — B isn't chasing, it's the market
returning to approximately the same price and offering a second decision.

**Disposition**: not "better" or "worse" than A — different. Slightly lower hit rate,
similar payoff ceiling, meaningfully faster resolution. That "faster resolution"
property is exactly the dimension QS has been trying to optimize for all along,
without success, until this result. Genuinely a different entry hypothesis from
first-breakout QS ("what if position A wasn't the trade at all," not "what if I
replace position A" — the RQ-QS-01 question). This is now the frozen baseline table
for this sibling research line — do not re-litigate the 0.1%→72.3% correction, it's
closed.

## Volume dry-up — reclassified as PROXY MISMATCH, not negative evidence (critic
correction, 2026-09-29)

Three checks run, all against a TIME-SERIES-TREND operationalization of "volume dry-up
within one pullback":
- Pullback volume vs breach-day volume: median 65%, 80% lower — but partly mechanical
  (breach day is inherently high-volume by construction).
- Pullback volume vs the stock's own normal 10-day average: median 93%, only 55.6%
  below normal — near coin-flip.
- Progressive compression (volume/range trending down as price approaches the level):
  does NOT hold — trend correlation median **+0.214** (increasing, not decreasing);
  only 41.6% show declining volume; range compression is a coin-flip (48.3%).

**Critic's correction, adopted**: none of these three checks are actually Minervini's
VCP claim. VCP's real claim is a SEQUENCE property across MULTIPLE successive
contractions (each contraction smaller than the last — e.g. 20%→10%→5%), not a
time-series trend property within a SINGLE pullback. This is the same category of
mistake as the earlier (already-corrected) Base Tightness proxy failure — measuring
the wrong thing, not evidence the real phenomenon is absent. **Status: PROXY
MISMATCH, untested — not negative evidence.** The real "successive shrinking
contractions" claim has not been tested yet.

## Literature checklist, prioritized by critic (2026-09-29) — test 3, not 7

| Idea | Worth testing next? | Reason |
|---|---|---|
| Resistance-becomes-support (polarity/retest) | ✅ already tested (RQ-QS-03A) | — |
| Pullback lands near EMA20/EMA50 | ✅ yes | executable, decision-time-safe |
| Handle depth ≤50% of prior base depth | ✅ yes | structural geometry, not tuning |
| ATR contracts to ~1/3 of 50-day average | ⚠️ later | numeric claim, likely parameter-sensitive |
| Breakout volume 40-50%+ above average | ⚠️ later | volume story already complicated |
| Successive shrinking contractions (real VCP claim) | untested, not yet scheduled | needs multi-leg detection, not a single-pullback check |
| Fibonacci retracement depth (38.2/50/61.8%) | not prioritized | one specific convention among several equally-valid ones |

Do not open all seven at once — critic's explicit instruction, three is enough for
one bounded pass.

## RQ-QS-03B — Quality Pullback Audit (run, 2026-09-29)

Not a backtest, not a gate, not an exit. Descriptive only — output distributions, no
thresholds, no pass/fail, no expectancy, exactly like the earlier anatomy audits.
Code: `02_rq03b_quality_pullback_audit.py` (fields 1,2,4,5) + `03_handle_depth_check.py`
(field 3 / the handle-depth hypothesis). n=9,060 (the saved pullback-verified
population was already narrowed to `b_days_after_a>=3` from an earlier check in this
same session — disclosed, not a new filter applied here).

**Real bug caught before trusting the handle-depth result (Rule #22 in action
again)**: first merge (joining the audit output back to the base population) omitted
`entry_definition` from the join key — since the same ticker/date pair often appears
under multiple lookback definitions (10D/20D/40D), this silently cross-multiplied
duplicate rows, inflating n from 9,060 to 17,008. Caught by noticing the merged count
was LARGER than either input population (impossible for a real inner join) before
reporting the result. Fixed by adding `entry_definition` to the join key; corrected
numbers below.

**Results, all five fields**:

1. **Pullback depth**: median -3.52% below A's entry (mean -4.06%); in R terms median
   **-0.869R** — the typical pullback goes almost as deep as a full stop distance.
   **40.8% of pullbacks reach -1R or beyond** — a real fraction of "genuine pullbacks"
   are deep enough that A's own position would already be stopped out. Important
   caveat for interpreting "pullback quality" — many aren't gentle handles.
2. **Pullback duration**: median 5 days, IQR 4-7 — roughly matches "handle = 1-2
   weeks," shorter end.
3. **Handle depth vs prior base depth** (O'Neil's cup-and-handle rule: handle ≤50% of
   cup depth): median ratio 0.325, **73.7% of events stay within the 50% convention**.
   Real, majority-level match.
4. **EMA21 distance at the pullback's low** (dynamic-support convention, ema21 reused
   as the project's existing near-equivalent to "EMA20," not a new indicator): median
   +0.59%, **58.6% land within ±2% of EMA21**. Real, majority-level match.
5. **B's own breakout-day volume vs its own 10-day average** (never checked before —
   everything prior checked A's volume or the pullback's volume, never B's): median
   1.50x, **54.3% clear the 1.4x ("40%+ above average") convention**. Real majority,
   less dominant than #3/#4 but still a genuine confirmation.

**Disposition**: all three of critic's prioritized hypotheses (retest holds near the
original level, pullback lands near EMA20/50, handle depth ≤50% of the prior base)
are now confirmed at real, majority levels (81.9%, 58.6%, 73.7% respectively). Precise
wording correction (critic, 2026-09-29): these are three independent *structural
properties*, measured within the SAME already-verified-pullback population (had a
breakout, had a pullback, gap≥3 days) — not three independent populations. "Three
independent confirmations" overstates it; "three independent structural properties
within verified pullbacks were confirmed" is the accurate framing. Still real,
still convergent (price level, trend support, and geometry are genuinely different
dimensions, not restatements of each other) — just not three separate samples.
This is the strongest, most coherent evidence yet that BPC's structural anatomy is
real and present in this population, not a perceptual pattern. Still purely
descriptive — no gate, no filter, no promotion decided here. B's own volume surge
(54.3%) is confirmed too, a weaker
but real fourth data point.

## RQ-QS-03C — Define B, don't optimize B (2026-09-29, run)

Per critic's exact instruction: five candidate definitions of "the second breakout,"
compared ONLY on count/timing/distance — no returns, no expectancy, no exit design.
Code: `04_rq03c_define_b.py`. Sanity-checked against AEGISLOG directly before running
at scale (A entry_i and entry_price matched exactly; D1-D4 all fire earlier, days
2-3, than the known mechanical trigger at day 5 — directionally sensible, since all
four are less strict conditions).

n A's = 46,776 (consistent with every other population tonight).

| Definition | n candidates | % of A | Median days after A | Median distance from A's level |
|---|---|---|---|---|
| D1: Close above pullback high (running recovery high, close-basis) | 28,369 | 60.6% | 3 | -0.21% |
| D2: High above pullback high (same, intraday/IOC-basis) | 24,243 | 51.8% | 3 | +1.66% |
| D3: Close above breakout level after a genuine retest | 21,012 | 44.9% | 4 | +1.01% |
| D4: First higher high after EMA21 touch | 15,584 | 33.3% | **6** | +0.29% |
| D5: Current mechanical QS trigger (control, same as RQ-QS-03A) | 32,984 | **70.5%** | **1** | +1.73% |

**Result**: these are genuinely five different events, not cosmetic variants of the
same thing. D5 (mechanical control) is both the loosest (highest frequency) and
fastest (median 1 day) — reconfirms it's mostly chasing, not waiting for a real
pullback, consistent with RQ-QS-03A's original finding. D4 (EMA21-based) is the most
selective (a third of D5's frequency) and most patient (6x D5's median wait) — the
strictest, most demanding definition. D1-D3 sit in between on both axes. D3 (retest
and reclaim of the ORIGINAL level specifically — the closest match to the textbook
BPC description) lands at a real, moderate 44.9% frequency and 4-day median wait.

**Disposition**: definitions are confirmed meaningfully distinct — this was the whole
point of the RQ (are we even testing different things, or five names for one thing).
No definition has been chosen or promoted. No returns/expectancy computed for any of
the five — per the bounded scope, that comparison is explicitly deferred to whatever
comes after this step.

## 20 vs 20 replay — QS-A vs QS-B/D3 (2026-09-29) — honest verdict: does NOT support BPC

Per critic's exact decision (D3 = close above A's original breakout level after a
genuine retest, the closest literature match; D5 retained as metadata only, not a
third arm). 20 pairs sampled via the same deterministic stratified method as the
100-trade replay MVP (5 early/5 mid/5 late/5 random, fixed seed), from the eligible
pool with intraday coverage and a genuine D3 event (n=1,266). A↔B relationship
preserved (both IDs + elapsed days recorded, `replay20_pairs.csv`). B's entry modeled
as the next trading day's OPEN after the D3 signal closes (decide-at-close/execute-
at-next-open convention, same as the rest of this project) — same S1b risk unit, no
new filters. Code: `05_replay_20_vs_20.py` (per-pair text replay) +
`06_plot_20_vs_20.py` (paired visual comparison, `plot_20_vs_20.png`).

**Went through all 20 pairs against critic's exact questions. Honest read: does NOT
support BPC as a cleaner/better setup.** Several of critic's own pre-specified "B
failure archetypes" recur repeatedly, not occasionally:

- **Failed reclaim, immediate rejection**: JMFINANCIL, AAVAS, BELRISE, PARADEEP — B
  reclaims the level, then declines hard shortly after (-1R to -6R by the end).
- **Late reclaim after most of the move already happened**: BATAINDIA (B enters
  already ~+1.5R elevated, then suffers a severe late reversal to -2.7R), JIOFIN (B
  enters near A's own peak, then just declines) — B catches the tail end of the
  opportunity, not a fresh one.
- **Deep pullback/recovery, MORE volatile than A, not less**: BHARTIARTL's B swings
  to -15R to -17R before recovering — a far more extreme round-trip than A ever
  showed. KIMS's B also swings wider than A's comparatively tame path.
- **Genuine partial successes** (real, smaller than A): TECHM, PETRONET, M&M,
  NAM-INDIA — B captures a real positive continuation, sometimes cleaner than A, but
  generally smaller magnitude.
- **Hand-verified, confirmed a stop-width artifact, not real behavior (Rule #22)**:
  SAREGAMA's B shows an extreme -4R to +8R range. Checked directly: B's stop (prior
  day's Low) sits only 1.06% below entry — unusually tight. The stock only moved a
  normal ~10% over the next few days (₹522→₹574); divided by a 1.06% risk unit, that
  renders as a +9R swing. The move wasn't unusually violent, the stop was unusually
  tight — same mechanism as the earlier hourly-bar R-inflation bug. **Broader caveat,
  not just this one pair**: since S1b stop width genuinely varies trade-to-trade,
  some of "B looks more volatile than A" across the other 19 pairs could also be
  partly stop-width noise, not purely behavioral difference — not re-checked on an
  absolute-% basis yet. The directional failure-archetype findings above (failed
  reclaim, late reclaim) don't depend on R-scaling and stand regardless.

**Answering critic's specific questions**: Does D3 produce a visibly different
trajectory? Yes — but "different" mostly means MORE volatile, not cleaner or faster.
Does B enter during renewed expansion, not the original impulse? By construction it
should, but several examples show B entering as the real move is already ending. Is
anything durably proven by the reclaim? In several cases, no — the reclaim looked
real and then failed anyway. Does B shorten the unresolved period? Mixed at best —
several B's take as long or resolve worse than A, not faster.

**Disposition**: per critic's own pre-committed stopping rule ("if the 20+20 replay
shows no meaningful behavioral distinction, close BPC rather than moving to D1/D2/D4
hunting") — there IS a meaningful behavioral distinction, but it points the WRONG
direction: real, recurring failure archetypes dominate the sample, not a cleaner
setup. This tempers RQ-QS-03A/03B's earlier positive structural-anatomy findings
considerably — the anatomy properties (retest holds, lands near EMA21, handle depth
≤50%) are real and measurable, but do not translate into visibly better trajectories
at the individual-trade level. Awaiting critic's read on whether this closes BPC or
warrants one more check (e.g. hand-verifying SAREGAMA first).

## RQ-QS-04A — Post-Breakout Consolidation Anatomy (2026-09-29, critic-approved, observational only)

**A separate hypothesis from BPC/D3, do not conflate.** D3 asked whether price dips
back below A's original level and reclaims it (tested, mixed/negative above). This
asks a different question: after A, does price hold its ground, pause in a NEW
bounded range above/around A, then break a new pivot — with a candidate structural
stop under THAT new range's low, not S1b. Traced back to the user's own memory of
Strike Money's algo curriculum; independently verified online before building (not
just trusted from critic's recollection) — Minervini VCP (stop below the final
contraction's low, 5-8% risk), O'Neil cup-and-handle (stop below the handle low, not
the cup low, plus a 7-8% max-loss backstop), and confirmed directly on strike.money
itself: the ascending-triangle page ("wait for retest... stop loss below the retest
low," verbatim) and a genuine VCP section on the swing-trading-strategies page
("stoploss: just below the low of the most recent pullback in contraction," verbatim).

**Multiple candidate stop-loss conventions now exist for this research line** (S1b,
retest-low, full-consolidation-low, final-contraction-low, plus the two already-caught
R-inflation bugs this session) — flagged as a live methodological risk per Rule #20,
but treated as a later-optimization concern, not a blocker for this observational pass
(which reports plain % distances, explicitly no R).

**Method**: decision-time-safe definition, no pre-set N-day minimum, no scanning the
full window for the best-looking range. `running_high` tracked day-by-day from A's
entry; consolidation starts the first day price fails to extend that running high;
`consolidation_high` fixes at that point (never redefined by hindsight); B = first
subsequent day's High breaking `consolidation_high`. `consolidation_low` is the one
necessarily-hindsight field (only known once the pause ends or the window closes) —
fine for an anatomy audit, not a live rule. Reused `find_a_positions()` from
`04_rq03c_define_b.py` directly (same canonical A population, no re-derivation) and
the existing `atr14`/`ema21`/`vol_avg10_prior` production columns.

**Hand-verified against raw price bars before trusting the aggregate (Rule #22)**:
CGCL 2022-06-01 and AMBUJACEM 2023-04-28 both checked by hand against `backtest.load()`
output — every field (consolidation_start_day, consolidation_high/low, duration,
resolved, b_price) matched the algorithm's output exactly. No join in this script, so
no duplication-inflation risk either.

**Full population (n=46,776 A's — same as RQ-QS-03A/B/C)**:

| Metric | Result |
|---|---|
| Consolidation detected (any pause D1-D15) | 46,750 (99.9%) |
| No pause at all (continuous new highs through D15) | 26 (0.1%) |
| Resolved with a B breakout in-window | 31,580 (67.6% of detected) |
| Still unresolved at D15 | 15,170 (32.4% of detected) |
| consolidation_start_day | median 2, mean 2.0 |
| duration | median 5, mean 6.8 |
| range_width_pct | median 6.54%, mean 8.22% |
| range_width_over_atr | median 2.11x, mean 2.58x |
| **consolidation_low stays ABOVE A's entry price** | **18.0%** |
| range_contracting_corr (neg=shrinking) | median +0.123, only 41.7% negative |
| vol_ratio_vs_10d_avg | median 1.10x (above normal, not below) |
| resolved B's structural risk (dist. to consolidation_low) | median 6.10% |

**The key diagnostic (does the "consolidation" undercut A, or hold above it) mostly
fails**: 82.0% of naive first-pause detections dip below A's own entry price at some
point — i.e. this simple detector mostly re-finds the same "pullback below A"
population RQ-QS-03A/D3 already tested and found didn't support BPC, not a new
structure. No volume dry-up (1.10x, slightly elevated) and no contraction (positive
correlation, ranges widening more often than narrowing) on this population either —
consistent with every other volume-dry-up check this session, not a new negative.

**The 18% holds-above-A subset (n=8,403) is a genuinely different, tighter, faster
population — a real 3-way split, not noise:**

| Metric | BASELINE (n=46,750) | **HOLDS-ABOVE-A (n=8,403)** | UNDERCUTS-A (n=38,347) |
|---|---|---|---|
| Resolved rate | 67.6% | **90.7%** | 62.5% |
| consolidation_start_day | 2.0 | 3.0 | 1.0 |
| duration | 5.0 | **2.0** | 7.0 |
| range_width_pct | 6.54% | **4.33%** | 7.23% |
| range_width_over_atr | 2.11x | **1.36x** | 2.37x |
| range_contracting_corr (n) | +0.123 (36,520) | +0.349 (4,762) | +0.100 (31,758) |
| vol_ratio_vs_10d_avg | 1.10x | 1.29x | 1.06x |
| b_structural_risk_pct (resolved) | 6.10% | **5.19%** | 6.41% |

- Duration collapses to 2 days median (not 5-7), range tightens to 4.33% (~1.36x
  ATR — close to S1b's own known typical ~1.37x ATR width), and it resolves 90.7% of
  the time vs 62.5-67.6% elsewhere. Structurally, this is much closer to the
  Strike/VCP description than the baseline's noisy majority.
- **Practically important**: this subset's candidate structural stop costs barely
  more risk than S1b already does (1.36x ATR vs S1b's ~1.37x ATR) — undercuts the
  "this will just become another positional/wide-stop trade" concern for this
  specific subset.
- **Caveat on range_contracting_corr, not a new tension**: it reads less-contracting
  in the holds-above-A subset (32.8% vs 41.7% negative) — but only 4,762 of 8,403
  rows even have ≥3 days to compute a meaningful trend on (median duration is 2).
  This is a limitation of that field for short spans, not evidence against
  tightening; flagged honestly rather than hidden or over-read.
- Volume dry-up still doesn't hold in this subset either (1.29x, if anything higher).
- CGCL (hand-verified above) is itself a member of exactly this subset (duration 2,
  holds above A) — so this population is already partially Rule #22-covered, not
  just an untouched aggregate.

**Not yet done**: no returns/R computed anywhere in this RQ (by design). No trajectory
replay of the holds-above-A subset yet. No decision on which of the 4+ candidate stop
conventions this line should adopt going forward. **Full next-session sequencing
(critic-specified, 6 steps, explicit decision tree, explicit do-NOT-do list) is in
`../PARKING_LOT.md`, item #9 — start there, don't reorder or skip ahead.**
