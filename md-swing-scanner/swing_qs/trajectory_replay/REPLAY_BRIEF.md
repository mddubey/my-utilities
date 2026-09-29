# QS Replay Validation — Brief for Critic Audit (2026-09-28)

**Status**: critic's verdict RECEIVED (full A-G at the bottom of this file) — the
Minimum Viable Replay (section B of the verdict) is APPROVED to build exactly as
specified. Nothing beyond that MVP scope is approved yet.

## Why this exists

Tonight's arc: RQ-QS-01 found a real structural phenomenon (opportunity cost of
occupancy). RQ-QS-02 cleanly falsified the obvious mechanical fix (replacement policy).
Along the way, the user opened one real AEGISLOG chart and, within 30 seconds, found a
genuine discomfort (entering near the top of a violent breakout wick) that no backtest
had surfaced. That's the flag: **we have validated the entry gate's population-level
statistics, but have never watched QS candidates behave bar-by-bar as if trading them
live.** Critic's verdict: don't trade QS live tomorrow. Do a replay/dry-run session
instead. This brief is what gets handed to critic for a design audit before that
session happens.

## Honest QS status tonight (do not overstate this)

| Area | Status |
|---|---|
| Entry gate | Provisional, not validated as a finished product |
| Exit | Unresolved / provisional |
| Replacement policy | Tested and closed negative (RQ-QS-02) |
| Opportunity occupancy | Real phenomenon (RQ-QS-01), no intervention found |
| Body/candle quality (`body_pct_SAMEDAY`) | Known telemetry, no intervention |
| Trajectory replay | Not yet actually researched at scale |
| Live trading | **Not ready** |
| Next research | Replay, not another filter |

A couple of live trades **generate better hypotheses** than three months of
backtesting — they do not **validate** a strategy. AEGISLOG didn't validate anything;
it generated RQ-QS-01, RQ-QS-02, the body% illustration, and this replay brief. That's
the correct role of live experience, and it should stay that role.

## 1. Research question

What does a genuinely good QS trade look like in its first few sessions, and what does
a bad one look like, observed at 5-minute resolution from actual entry? Specifically:
does the desired product have a recognizable *trajectory*, not merely an eventual
return threshold? A trade that works after 8-15 days may be a fine positional (BC)
trade but is not automatically a good QS trade. No arbitrary win-rate target (e.g. 60%).

## 2. Replay population

Recent candidates with real 5-minute data (~June-Sept 2026). Prefer actual QS
candidates / recent BC-v2-eligible candidates under the current research definition.
Enough names to expose different behaviors, not cherry-picked. Start manageable,
expand if unclear. **Do not optimize the sample to produce a desired conclusion.**
Daily-bar entry definition stays the source of truth — intraday data is the
post-entry microscope, never a reason to redefine the entry universe.

## 3. Replay clock

Entry: actual IOC/breach timestamp and price where available. Replay every 5-min bar
through at least the first several sessions. Record BOTH raw market behavior (price,
%-from-entry, intraday H/L, distance from trigger, time of day, gap/reclaim, EOD close)
AND risk-normalized descriptors (R, MAE/MFE, time to +0.25R/+0.5R/+1R/+2R, time above/
below entry). **R must not become the only language of the research.**

## 4. Events worth capturing (critic should challenge/prune this list)

First meaningful continuation, immediate extension/exhaustion, first pullback, return
to trigger, reclaim, sustained hold above trigger, momentum disappearance, first
+0.25R/+0.5R/+1R/+2R, MAE, MFE, time to first positive move, time to meaningful profit,
longest continuous underwater period, intraday H/L timing, D0 EOD state, D1 open state,
D1 EOD state, D2/D3 state. Daily descriptors: close vs trigger, close vs prior close,
daily range, candle/body behavior, accelerating/decelerating progress, pullbacks
absorbed vs deepening.

## 5. Candidate behavioral archetypes (observe, do not pre-test as filters)

A. Immediate blast — expansion, meaningful profit fast, shallow contained pullback.
B. Healthy continuation — progress, controlled pullback, reclaim, second expansion.
C. Immediate exhaustion — entry near local extreme, little follow-through, reversal.
D. Failed breakout — returns through trigger, can't reclaim, deteriorates.
E. Intraday fakeout / daily recovery — violent intraday failure, EOD structure recovers.
F. Slow drift — no meaningful progress, no decisive failure either.
G. Progression stall — initial move works, then repeated inability to extend.
H. Overhead interaction — reaches a meaningful level, continuation changes character.

Critic decides whether these are real recurring states or just storytelling.

## 6. Critical timing discipline

For every observation: **could we have known this at that exact moment?** Separate
IOC-entry-known / D0-intraday-known / D0-EOD-known / D+1-known / hindsight-only
information. Do not let an EOD candle characteristic become an IOC entry filter by
accident — this is exactly the AEGISLOG problem (the bearish D0 candle wasn't knowable
at the IOC entry moment).

## 7. AEGISLOG's status

Sanity-check example only, not evidence. Illustrates the uncomfortable scenario
(breakout entry near the top of a violent early 5-min expansion, followed by major
reversal) but is not a second data point. Do not let one memorable chart become a
hypothesis merely because it's compelling.

## 8. Closed findings — do not silently reopen

- Feature Battle: closed.
- R1/R2 hold/reject research: closed.
- Mechanical replacement based on blocker R-state: closed, falsified (RQ-QS-02).
- `body_pct_SAMEDAY`: telemetry/replay annotation only, not a filter.
- Exit discovery EX1-EX3: closed.
- 2R cap / blunt time-cap: underperformed.
- Breakeven/giveback tightening: negative.
- ADR-relative stop behavior: an interesting mechanism, NOT permission to widen S1b.
- S1b (prior-day-Low) stop remains the current QS risk-unit candidate — do not change
  it because replay makes a different stop look nicer.
- Signal ≠ Intervention (Rule #21) — a predictive signal is not automatically an
  intervention.

## 9. Failure modes critic should explicitly audit for

Lookahead, survivor bias, selection bias from only replaying "interesting" names,
intraday-coverage bias, entry-price reconstruction errors, timestamp/session
alignment, stale vs contemporaneous levels, using future-confirmed swing points,
R-unit contamination, confusing descriptive trajectory with predictive feature,
confusing predictive feature with profitable intervention, overfitting a handful of
visually compelling charts, accidentally turning QS back into BC/positional trading,
defining "blast" after seeing the trajectories, cherry-picking the observation window.

## 10. What's wanted back from critic (concrete verdict, not another framework)

- **A. Replay design verdict** — what's sound, what's wrong/missing, what must change.
- **B. Minimum viable replay** — smallest implementation that answers the product question.
- **C. Observation schema** — exact fields/events, split must-have / useful / don't-bother.
- **D. Sampling plan** — how many candidates, how to avoid cherry-picking.
- **E. Analysis protocol** — Observe → Describe → Hypothesize → Measure → Decide, without
  prematurely turning observations into filters.
- **F. Stop conditions** — when is there enough evidence for "coherent" / "not coherent" /
  "needs another research branch."
- **G. Deployment verdict** — is there enough evidence to trade QS live now? Burden of
  proof should be meaningful, especially if options get used eventually.

**Guardrail for critic**: the failure mode to avoid is "here are 25 more features to
test" — that is not the task. The gap is understanding the object being built, not
generating more candidate features.

## Current project status to preserve

QS is research-only. No live deployment decision has been made. Replay validation is
the next gate.

---

## Critic's verdict (received 2026-09-28 late) — APPROVED, build exactly this

### A. Replay design verdict
Sound: 5-min replay is the highest-ROI next step (exposes trajectory, not just
endpoint return). Wrong/missing: the original brief was too open-ended — replaying
charts and collecting "interesting observations" risks another anecdotal-feature loop.
**Must change before build**: freeze one observational replay dataset and one fixed
event schema BEFORE looking at results. No BLAST/FAILURE/DRIFT labels initially. Must
produce both raw price trajectory AND timestamped state transitions.

### B. Minimum viable replay (build ONLY this)
- Fixed sample of QS-eligible entries with 5-min coverage.
- Start at the actual entry timestamp/price.
- Replay every 5-min bar through D0-D5.
- Record price path + the predefined events (schema below).
- Produce: (1) per-trade trajectory table, (2) normalized trajectory plots,
  (3) D0/D1/D2/D3/D5 state table.
- Do NOT simulate exits or replacement. Do NOT add new filters.
- Answers exactly one question: does QS have a recognizable short-duration
  trajectory at all?

### C. Observation schema
**Must-have** — per 5-min bar: timestamp, OHLC, volume, price %-from-entry, absolute
high/low excursion from entry, R (frozen S1b), minutes since entry, session/day number.
Events: first move above entry, first +0.25R/+0.5R/+1R/+2R, first return/touch of
breakout trigger, first reclaim after return, first new post-entry high, MAE, MFE,
D0/D1/D2/D3/D5 EOD state. Daily descriptors: close vs entry, close vs trigger, daily
high/low excursion, daily range, new-high flag, closed above/below trigger flag.
**Useful**: time of first meaningful expansion, consecutive bars making/losing
progress, time below entry, time above +0.25R/+1R, pullback depth after first
expansion, recovery after deepest intraday drawdown, breach-bar characteristics,
contemporaneous (non-hindsight) pivot/overhead interaction if already available.
**Don't bother (v1)**: Greeks/options pricing, ML features, dozens of technical
indicators, new volume-derived indicators, automated pattern recognition, threshold
optimization, simulated exit policies, portfolio replacement, new entry filters,
arbitrary Blast/Failure labels.

### D. Sampling plan
**100 candidates, not 20** (approved pool is 1,782 — plenty of room). Deterministic
stratified sample, selected BEFORE looking at 5-min trajectories: 25 early-period + 25
middle-period + 25 late-period + 25 random, randomly drawn WITHIN each time block from
the full eligible population. Never select on eventual return, ticker, visual
attractiveness, or memorability. AEGISLOG stays in a small, separately-maintained,
explicitly-labeled illustrative sanity set — excluded from inference. If 100 stays
ambiguous, expand to 300 next, not straight to thousands.

### E. Analysis protocol
1. **Observe** — trajectories, no success/failure labels, plain structural language
   ("a large fraction of early extensions retrace most of the move within the same
   session" — NOT "large early extension is a bad filter").
2. **Describe** — convert into explicit, measurable definitions ("retraces ≥X% of the
   first excursion within Y minutes") — only now does a hypothesis exist.
3. **Hypothesize** — does the state plausibly distinguish quick-continuation /
   slow-continuation / deterioration; keep it directional and mechanism-based.
4. **Measure** — test on the FULL eligible replay sample, never just the charts that
   generated the idea. Frequency, trajectory distributions, forward outcomes, timing,
   robustness across periods. No threshold hunting.
5. **Decide** — classify each finding: descriptive only / candidate predictive signal /
   worth intervention research / falsified. A predictive relationship does not
   automatically become an entry/exit rule. Standing question: does this help define
   what a QS trade IS, not merely explain its eventual return.

### F. Stop conditions
- **Coherent**: a recognizable short-duration continuation pattern repeats across the
  fixed sample, materially distinguishable from drift/slow positional behavior,
  survives across different time periods, stateable without hindsight, concentrated
  enough that a smaller live population could plausibly be defined from it. No
  specific win-rate required.
- **Not coherent**: trajectories highly heterogeneous, no stable short-duration
  behavior emerges, apparent patterns vanish when measured, or "good QS" can only be
  defined retrospectively by eventual returns. Forcing another gate at that point is
  the wrong response.
- **Needs another branch**: replay reveals a specific missing dimension that plausibly
  explains the heterogeneity (e.g. "D0 intraday behavior separates into two structural
  regimes our daily entry definition can't distinguish") — open ONE bounded branch
  around that observation, not another feature sweep.

### G. Deployment verdict
**No.** Not enough evidence to trade QS live right now. The population contains useful
ingredients, but it has not been demonstrated that the actual thing we want to trade —
a short-duration continuation trajectory — is a coherent, reproducible population.
AEGISLOG exposing a completely different-looking path immediately after entry is
exactly why replay must happen first. Gate: **replay first → understand the QS
object → then decide whether an executable QS population exists.** No live QS
deployment before that gate.
