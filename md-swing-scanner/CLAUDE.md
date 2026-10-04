# md-swing-scanner — read this before running or trusting any backtest

This file is auto-loaded every session in this directory, so it survives context
compaction even when the conversation history doesn't. Its job: stop this project
from re-making the same measurement mistakes it has already caught and fixed before.
The full story behind every rule below lives in `FINDINGS.md` (search the rule
number or name) — this file is only the checklist, not the explanation.

## Before trusting ANY new backtest number in this project, check:

1. **Is the entry gate evaluated on the right day's row?** (Rule #18, 2026-09-26)
   Production filters (trend/momentum/fragility) must be checked against the PRIOR
   day's row, matching `shortlist_primed()`'s real live convention — not the trigger
   day's own completed candle. The trigger touch itself (`High >= high10_prior*1.005`)
   correctly uses the trigger day's real-time High; the GATE fields do not get the
   same pass. This bit BC v2's entire 2026-09-25/26 promotion package — check whether
   it's been re-validated before citing old numbers.

2. **Is the exit engine the real one?** (Exit Engine Integrity Rule, 2026-09-25)
   Primed/BC v2 research must use `primed_engine.py`'s real `check_primed_exit`/
   `_new_state`/`current_primed_stop_level`, never `backtest.py`'s legacy `check_exit()`
   (which stays correct and untouched for VCP/Coiled Spring only — do not "clean up"
   or modify it without being asked).

3. **Is the population correctly gated, with no position-blocking bias?** (Gate
   Integrity Rule, 2026-09-25) Never build a "raw" comparison population by
   monkeypatching/bypassing `base_filters_pass` inside a real simulation loop — a
   bypassed trigger still consumes a ticker's single-position slot, undercounting
   what a correctly-gated run produces. If you need a genuinely ungated population
   (e.g. testing whether the gate hides an effect), label it explicitly as a
   **trigger-price counterfactual** and don't compare its position count directly
   against a gated population's.

4. **Is any feature/distance measurement anchored to something that's NOT circular
   with the outcome?** (Rule #7, Rule #10, and the dist_40d/dist_52w_high retractions)
   Distance-to-a-level must be anchored to a PRIOR-day-known price (e.g. the trigger
   price), never the same day's own Close — Close is also what determines the
   outcome you're trying to explain, so anchoring to it manufactures a fake
   relationship out of pure arithmetic.

5. **Is the outcome metric the real simulated P&L, or a fixed-horizon proxy?**
   (Rule #13) Whenever a real exit engine exists for the population, use its real
   `pnl_pct`/`r_multiple` — never a fixed-day-N-later Close return. A proxy answers a
   different question and can diverge sharply from what the real system captures.

6. **Are R1 and R2 pooled together?** Never — they are mechanically different
   situations (R1 is usually already cleared by our own entry's strength
   requirement; R2 is the real next rung being tested). Same discipline for any
   other "nearest of several distinct things" measurement — check whether the
   population composition changes across the comparison you're drawing (Rule #12).

7. **Is a composite/blended feature (like `freshness_score`) being tested alongside
   one of its own constituent parts?** (Rule #14) Decompose composites into their
   components before promoting anything built on them — conditioning on both a
   composite and a variable that's mechanically half of that composite is testing
   overlapping information, not two independent dimensions.

8. **Is a "recent regime" number pooling multiple years together?** (Rule #16)
   Always show each of the most recent individual years separately before promoting
   a candidate — a pooled number can hide real decay.

9. **Is win-rate/median being reported without R-multiple, drawdown, and worst
   losing streak alongside it?** Two populations can be win%/median-identical while
   decisively different in R (tail compression, not a win-rate gap) — always report
   both together, and use `risk_of_ruin.py`'s capacity-constrained methodology
   (FCFS by entry_date, no ranking) for any two populations of different sizes.

10. **Is a negative/inconclusive result being treated as an open thread instead of
    a closed one?** (Rule #17) A real-but-insufficient signal is a completed
    research outcome. Log it as closed so it doesn't get re-litigated under a new
    name months later.

11. **Is the stop-loss/risk-unit convention explicitly declared before any R-based
    analysis begins?** (Rule #20 — Risk Unit Integrity, adopted 2026-09-27) Any
    research that reports R-multiple, expectancy, payoff ratio, drawdown, win rate
    by R threshold, MAE/MFE in R, or trajectory labels derived from R must
    explicitly define the stop-loss convention before any analysis begins. R is
    undefined until the stop is defined. Changing the stop creates a new risk
    unit — previous R-based findings become non-comparable until rebuilt or
    explicitly converted. Product-definition work must treat the stop as a
    first-class design choice, not an inherited implementation detail. (Born from
    the `swing_qs/` Quick Swing line silently inheriting BC v2's 20-day
    structural-low stop for an entire weekend of R-based analysis before this was
    caught — full account in `swing_qs/FINDINGS.md`'s Stop Definition Audit.
    Progression with the two rules below it: #18 protects against using
    information unavailable at decision time, #19 protects against mistaking one
    parameter choice for a discovery, #20 protects against measuring performance
    in R before the stop that creates that R has even been defined —
    Information → Robustness → Measurement.)

12. **Does a feature's predictive ranking justify acting on it as a gate/exit rule?**
    (Rule #21 — Signal ≠ Intervention, adopted 2026-09-27, critic-specified) A feature
    may contain statistically meaningful information without improving a trading
    decision. Promotion requires evidence that ACTING on the signal improves the
    chosen product objective (population-adjusted — report the population lost
    alongside any rate gain), not merely that the signal predicts outcomes or ranks
    #1 in a comparison table. Ranking #1 among several weak candidates is not the
    same as being strong enough to build a binary gate on — check the actual
    KEPT/REMOVED shift before promoting, every time. (Born from `swing_qs/`'s Feature
    Battle: `ema34_persistence_t1` ranked #1 of 9 features for Blast-vs-Drift
    separation, but a threshold built on it moved BLAST rate by only 0.6 points while
    discarding half the candidate population — real signal, useless gate. Three more
    examples from the same weekend: RVOL predicts reachability but not Blast-vs-
    Failure; F1 touch is real information but a terrible standalone exit; R1/R2
    rejection is real telemetry but not predictable pre-entry, so it can't be a
    filter or exit trigger. Progression with the rule above it: #20 protects
    measurement before the stop is defined, #21 protects promotion after a real
    signal is found — Measurement → Promotion.)

13. **Was a surprising aggregate result hand-verified before being promoted to a
    finding?** (Rule #22 — Hand-Verification of Surprises, adopted 2026-09-29,
    critic-specified, strengthened same day) Before promoting any surprising
    aggregate result to a project finding: (a) verify 3-5 concrete real examples
    manually; (b) verify the aggregate count is mathematically plausible (joins,
    duplicates, sample size — an inner join or filter that produces MORE rows than
    either input, for instance, is never legitimate); (c) if the manual examples
    contradict the aggregate output, the finding is quarantined until reconciled, not
    reported provisionally. Born from three catches in one night, each justifying one
    bullet: a stop-width bug that silently inflated R on winners (caught by asking
    "what's the actual SL in price terms" — bullet a); a pullback-detection
    aggregation bug that reported 0.1% where the real answer was 72.3% (caught by
    hand-checking 5 real A/B pairs against the aggregate claim — bullet a/c); a
    merge missing a join key that inflated n from 9,060 to 17,008 (caught because the
    joined count exceeded both inputs, mathematically impossible for an inner join —
    bullet b). All three would have become false findings without this discipline —
    a re-run or a bigger sample would not have caught any of them, since each bug was
    in the aggregation/formula, not sampling noise. Cheaper and more reliable than
    another robustness sweep.

14. **Has a structurally-defined phenomenon's closed-negative verdict actually been
    checked against Rule #23's four audit dimensions, or just assumed closed?**
    (Rule #23 — Measurement Integrity Before Closure, see dedicated section below.)
    Applies to anything defined in visual/structural terms — breakout, pullback,
    consolidation, rejection, continuation, reversal — not to purely numeric features.

## Research Preflight (answer before writing any new RQ's code, adopted 2026-09-27)

Five questions, answered explicitly before coding starts on any new research question:

1. **Population**: what events exist?
2. **Entry clock**: what information exists at decision time?
3. **Stop definition**: what defines 1R?
4. **Exit engine**: what stays fixed in this experiment, and is it actually the
   right one for the product being tested (not just the one already lying around)?
5. **Comparison unit**: are we comparing entries, exits, filters, or entire products?

This list exists because every integrity bug found in this project so far (wrong
exit engine, position-blocking bias, same-day gate leakage, inherited stop
definition, trigger-gap circularity) would have been caught at one of these five
questions before a single line of simulation code was written.

## Canonical population builder (adopted 2026-09-26, supersedes hand-copied simulation loops)

`population_builder.py`'s `build_population()` is now the ONLY way to build a Primed-Gate-
style research population (BC current, BC v2, Cell C, or any future recipe). Per the
user's and critic's shared conclusion after finding THREE independent integrity bugs in
one weekend (wrong exit engine, position-blocking bias from monkeypatching, same-day EOD
gate leakage): the disease was research code being allowed to construct populations
independently of production logic, not any one bad number. Do not write a new hand-rolled
simulation loop for this kind of research — call `build_population()` instead.

- `filter_recipe` is REQUIRED and is always the real position gate — no bypass mode
  exists. A genuinely ungated/raw population is built by passing `ungated_recipe`
  (`lambda row: True`) through this SAME function — same code path, explicitly labeled,
  never a monkeypatched copy of something else. Label the result a **trigger-price
  counterfactual**, per the 2026-09-24 Phase 2 guardrail.
- `gate_clock` is REQUIRED-to-consider (default `"T-1"`, the live-matching default for
  any Primed/live-IOC recipe). Only pass `"same-day"` for an EOD-confirmed-entry recipe
  that inherently decides after the close — never for a live-IOC recipe.
- Exit mechanics are always `primed_engine.py`'s real functions — there is no alternative
  exit path exposed by this module.
- `structural_lookback` defaults to `backtest.STRUCTURAL_LOOKBACK_BC` (20) — this is
  INDEPENDENT of `breakout_lookback` (10 for BC, 40 for Cell C). A prior version of this
  file conflated the two by defaulting one to the other; caught by a correctness check
  against known-good numbers before this module was trusted (verify any new recipe's
  constants the same way before relying on it).

## Swing-completion / exit-horizon research pre-mortem (2026-09-26) — check before building any HH/LH or MAX_HOLD_DAYS analysis

1. **"Peak reached so far" is causally fine (a running max); "confirmed swing high/low"
   is NOT** — confirming a peak requires bars AFTER it. Never let a "confirmed HH/LH"
   label leak information from after the point being evaluated. Mirror the exact
   K_SWING=2 symmetric-confirmation convention `primed_engine.py` already uses for swing
   lows (never invent a different lag rule for highs).
2. **Never reuse `state["target"]` (ZigZag, pre-entry-computed) as if it were the
   post-entry realized peak** — they are unrelated quantities that happen to share the
   word "target/peak."
3. **Any candidate exit rule must decide at a close and execute at the next open**
   (same convention as RQ-94) — never let a rule "exit at today's close" using
   information only knowable at that close.
4. **Never let the final trade outcome leak into the predictor.** Outcome buckets
   (heavy loss/barely loss/barely win/big win) are for evaluation only; the candidate
   signal (pullback %, day of peak, etc.) must be computed independent of knowing how
   the trade ended.
5. Standard reminders that still apply: correct T-1-gated population file (verify by
   printing n and min(entry_date) at load time), correct day-index convention (day 0 =
   entry day, day 1 = first day after, matching `rq_trail1_trajectory_honest.py`),
   corp_action_day breaks the walk, one population per table (don't mix BC v2/BC
   current/Trend+EMA34 in the same comparison).

## Reporting convention (adopted 2026-09-26) — report a win-rate STACK, never just one number

For every future report: `r_multiple > 0` (gross, canonical) AND `>= 0.25` (**Meaningful
Win Rate — the headline practical number**, the user's own bar: ₹500 profit against
₹2,000 risk) AND `>= 0.5` (quality — roughly "paid for one average loser," since the
realized average loser across every cohort tested sits around -0.45R to -0.55R) AND
`>= 1.0` (full-R), plus **Payoff Ratio** (avg winner R / |avg loser R|). Do not impose a
fixed reward:risk framing (e.g. "1:2") — BC's exit engine is a trailing, evolving-target,
distribution-following mechanism, not a fixed-target setup; evaluate the realized R
distribution directly. Win rate is reported for interpretability only — it is never the
primary promotion metric. Promotion order: expectancy (meanR/Payoff Ratio) first,
portfolio pain (capacity-constrained drawdown/worst streak) second, win rate as context.

**"Winner R sacrificed" cost accounting must use Meaningful Win (>=0.25R), never gross
(>0R)** (2026-09-26) — a filter that lowers gross win rate may only be cutting trivial,
near-zero winners that were never going to survive real STT/brokerage/slippage anyway;
that isn't a real cost. Any "X% of winners sacrificed" report must say which win
definition it used, and defaults to >=0.25R unless there's a stated reason otherwise.

## Robustness Before Finding (adopted 2026-09-26, Rule #19)

A candidate feature is an exploratory observation after its first test — it may not be
called a finding, promoted, or used to motivate a production candidate until it survives
a pre-declared robustness check across materially related, non-optimized variants where
such variants naturally exist. **Parameterized Feature corollary**: if a candidate has a
natural lookback/window, pre-declare 2-3 materially distinct nearby horizons BEFORE
evaluating the result — do not pick the horizon after seeing results. (This is what
caught sector RS: real-looking at 126d, reversed at 21d, wash at 63d — a 126d-specific
artifact, not a robust effect, caught before it became a filter.) Not a blanket "test
everything 3 ways" mandate — applies where a natural parameter choice exists and could
plausibly have been fit to the data.

## Measurement Integrity Before Closure (Rule #23, adopted 2026-10-05)

A structurally/visually-defined phenomenon (breakout, pullback, consolidation,
rejection, continuation, reversal, etc.) must not be declared closed-negative until
the mechanical representation has been checked against the market event it claims to
measure. A negative result can mean four different things — the phenomenon genuinely
isn't there; the specific implementation doesn't work; the population doesn't
represent the intended event; or the measurement/labeling is wrong — and only the
first is a real finding. Experience shows the last two happen often enough that they
must be explicitly ruled out before the first is treated as high-confidence.

**Four audit dimensions, minimum, before closing any structurally-defined RQ:**

1. **Trigger-candle sanity.** If the event is a breakout/rejection/continuation:
   does the candle's actual OHLC state make semantic sense for the claimed event? If
   a bullish breakout is intended, how many qualifying events are actually red
   (Close < Open)? Is a partial/live candle ever confused with a completed one?
2. **Wick vs close, stated explicitly.** Every "broken / reclaimed / confirmed /
   resolved / continued" claim must say whether it means High/Low touched the level,
   an intrabar cross, a candle close beyond it, or a later candle's confirmation.
   Never let code use a wick where the research concept implies a close, or the
   reverse, silently.
3. **Discovery population vs. trading constraint.** State explicitly whether
   position-blocking, one-trade-per-day, cooldowns, or holding-period locks are part
   of the phenomenon's own definition or merely an inherited portfolio constraint. A
   discovery population (studying whether a phenomenon exists) should generally be
   ungated; if a gated population is used anyway, report the suppressed/ungated count
   too, same discipline as the existing Gate Integrity Rule (item 3 above) but
   applied to discovery research, not just backtest comparisons.
4. **Structural context survives the binary label.** A `resumed/failed`,
   `win/loss`, or `continued/reversed` label can hide the real path. Where the
   hypothesis is structural, retain the structural high/low, MAE, retracement depth,
   proximity to invalidation, time spent there, and recovery/reclaim behavior — don't
   collapse a complex path to a binary before checking whether that collapse destroys
   the phenomenon being studied.

**Chart audit is not strategy optimization.** Don't use charts to hunt for attractive
examples or hand-invent rules. But when a mechanical report says "this occurred N
times and has no useful behaviour," a random sample of that population must be
inspected and asked "did the code actually identify the thing we said we were
studying?" — not "does this trade look good?" If the answer to the first question is
no, the result is a measurement failure, not a negative finding.

**Closure taxonomy** — every research conclusion falls into one of three buckets,
going forward:
- **High-confidence closure**: the intended event/population was mechanically
  verified, chart semantics checked, and the negative result survived.
- **Conditional closure**: negative/inconclusive, but never received this audit —
  not wrong, just not yet earned the "high-confidence" label.
- **Superseded**: a later audit showed the population/measurement was materially
  wrong, so the old conclusion can no longer be cited as evidence against the
  underlying phenomenon (the old write-up stays, annotated, not deleted).

Do not retroactively reopen the whole closed-research backlog at once — audit the
highest-leverage shared population first (the one most other closed findings were
built on top of), then decide what else needs re-tagging. Most prior "closed"
verdicts are not wrong; some just haven't earned "high-confidence" yet.

**Applies to Prime BC's own positional character too**: "BC's tested implementation
did not establish the intended short-horizon phenomenon and evolved into a positional
trade" is a different, narrower claim than "we proved the underlying market
phenomenon doesn't exist" — don't conflate the two when citing BC's `max_hold_cap`
history as evidence either way.

**Born from**: `swing_qs_emapb/`'s RQ-EMAPB session (2026-10-04/05) finding five
separate definitional bugs in one sitting on the same population — a same-day peak
leak (EMAPB-03), inherited position-blocking (EMAPB-06), wick-vs-close resolution
ambiguity (TCS chart check), no bullish-candle requirement letting 17.8% of the
population be red candles (GRASIM chart check), and no structural-invalidation
tracking on a `resumed` label that had actually round-tripped through its own entry
low first (BAJFINANCE chart check). Each one, left uncaught, would have read as "no
signal" in a final report. Progression with the rule above it: #22 protects a
surprising positive result from being promoted on a bug; #23 protects a surprising
negative result from being closed on the same class of bug — Verify-before-promoting
→ Verify-before-closing.

## Pre-flight checklist, per RQ (critic-specified, 2026-09-26) — must pass before any number from this project is treated as promotable

- [ ] Entry gate evaluated on yesterday-known data (`gate_clock="T-1"`, or explicitly
      justified `"same-day"` for a genuine EOD-confirmed-entry recipe).
- [ ] Trigger condition uses only real intraday-touch information (today's actual High).
- [ ] Exit comes from `primed_engine.py`, never recreated or reimplemented.
- [ ] No monkeypatch changes position blocking — `filter_recipe` is the real gate inside
      the actual simulation loop, not bypassed and reapplied after the fact.
- [ ] Every candidate feature used in a filter can be stated as "known at T-1" or
      "known same-day" — if same-day, it is labeled telemetry/audit only, not promotable
      as a live-IOC filter, unless explicitly justified otherwise.
- [ ] Any distance/ratio feature is anchored to a prior-day-known reference (e.g. the
      trigger price), never to the same day's own Close.

If one box is unchecked, the RQ cannot produce promotable numbers — descriptive/
telemetry-only conclusions are still fine, just say so explicitly.

## Standing architecture facts (don't re-derive, don't "fix" without being asked)

- `backtest.py`'s legacy `detect_entry_eod()`/`check_exit()` — Entry Gate, still
  serves VCP/Coiled Spring. Frozen, per 2026-09-20 governance decision.
- `primed_engine.py` — Primed Gate, the real BC v2 mechanism. Canonical for all
  new Breakout Continuation research.
- `signals.py`'s `base_filters_pass()` — the ONE shared gate function used by
  `daily_scan.py`, `primed_engine.py`, `backtest.py`, `live_checkpoint.py`. Single
  source of truth by design — don't duplicate its logic anywhere.
- Population naming: "Confirmed Population" (`detect_entry_eod`, EOD-confirmed
  entries) vs "Primed Population" (`detect_primed_entry`, live-IOC entries) are
  intentionally different, coexisting populations — know which one a given research
  question is actually about before running anything.

## Data map (adopted 2026-10-03)

All base market data (caches) and their fetchers are being consolidated into the root `data/` folder
(copy → verify → delete, old paths left as symlinks). `data/README.md` is the single map of every
dataset: where it lives, how it is fetched and refreshed, coverage by date and universe, and known
gaps (e.g. the 5m cache is Nifty-500-only before ~2026-07-02). Read it before building any research
population on a dataset you haven't used in this session. Fetchers fetch the full NSE equity universe;
each project picks its own universe at read time.
