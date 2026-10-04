# RQ-TA1 Discovery Audit — Prime BC Trigger Transition / Fast-Move Discovery, Stage 1-3 + D/E

Separate thread, started 2026-10-03 IST, under `pre_breach/` (new-thread-vs-fold-in
decision deliberately left open). Does **not** modify production, does not write to the
shared `../FINDINGS.md`/`../PARKING_LOT.md`. Covers Stage 1 (reconstruct the two
motivating cases + a pre-declared comparison set), Stage 2 (G.1 — order the S1 break
against the touch), Stage 3 (fast vs slow approach), Family C (R1/R2 distance to
trigger, motivated by the RBLBANK reconstruction), and Family D/E (activity-vs-
displacement, post-touch participation).

**Scripts**: `01_reconstruct_cases.py`, `02_r1r2_distance.py`, `03_s1_timing.py`,
`04_approach_speed.py`, `05_activity_displacement.py` (Family D), `06_post_touch_
participation.py` (Family E), `07_lead_time_sweep.py` (Family D, actionability
follow-up), `08_peak_shape.py` (baseline funnel, time/magnitude of the same-day peak),
`09_candidate_state_snapshots.py` (TA1-C, dashboard-anchored candidate state),
`10_randomization_tests.py` (formal tests on cum_vol_ratio/dist_open_atr/touch_vol_ratio),
`11_formal_closure_audit.py` (family-wise test on the remaining TA1-C features + G.1).
Outputs: `recon_*.csv`, `r1r2_feats.pkl`, `s1_timing.csv`, `approach_speed.csv`,
`activity_displacement.csv`, `post_touch_participation.csv`, `lead_time_sweep.csv`,
`peak_shape.csv`, `candidate_state_snapshots.csv`.

## TA1 Formal Closure Audit (critic-specified, 2026-10-04)

**A. Family-wise test — the 4 remaining dashboard-observable candidate-state features
(`gap_pct`, `first_dir_up`, `range_so_far_atr`, `dist_to_trigger_atr`) across the 7
pre-declared snapshots, 28 combinations total.** Per the critic's exact spec: null
distribution built by shuffling the (ticker,date)→r5 outcome mapping once per
permutation (preserves the fact that a candidate appears in several snapshot rows
before it touches), recomputing all 28 Spearman rhos under that shuffle, taking the
max |rho| across the family, 5,000 iterations — not independent 95th-percentile
fishing on each of the 28.

Every real rho is tiny (|rho| ≤ 0.095, most under 0.06). **Real max |rho| = 0.095
(`gap_pct` at 12:00) sits at the 54.5th percentile of the null — essentially exactly
where a family of 28 pure-noise tests would land by chance (50th percentile).**

**CLOSED. The entire "morning/dashboard-observable candidate state predicts eventual
stall" direction is now exhausted for current OHLCV data** — `cum_vol_ratio`,
`dist_open_atr`, and all 4 remaining Family A/B/C features (6 of 7 tested features;
`progress_pct` was flagged unreliable before testing and never formally run) are null,
on top of the already-closed prior-art `RVOL@Trigger`. Do not revisit "find a
dashboard-state predictor of stall" with this data without a genuinely new feature
family or a new data source (per the critic: this is what legitimately reopens the
order-flow/depth question — not because resting sellers are proven, but because the
obvious pre-touch OHLCV state variables are now exhausted).

**B. G.1 (S1-break timing vs. the touch) — formal permutation test, eta-squared
(variance explained) as the statistic, before/after/never groups (n=67/66/1,322),
same_bar dropped (n=2).** Real eta² = 0.0099 (a small effect size), but the
null-distribution percentile is **99.9** — this exact separation is essentially never
produced by 5,000 random relabelings.

**SURVIVES, but per the critic's own framing this is "evidence the ordering contains
information, warranting a larger/stronger test" — not "G.1 is a predictor."** Status:
BANKED as a real, small-effect mechanism clue (same tier as `touch_vol_ratio` below),
not promoted to any decision role. Effect size (1% of variance) is modest even though
the statistical significance is clean — these are different claims (correctness vs.
usefulness, this project's own standing distinction).

**Revised board after this audit**:
| Item | Disposition |
|---|---|
| 6-year touched→STALL baseline | ESTABLISHED |
| Peak-shape anatomy | ESTABLISHED / useful context |
| `cum_vol_ratio` | CLOSE |
| `dist_open_atr` | CLOSE |
| `gap_pct`, `first_dir_up`, `range_so_far_atr`, `dist_to_trigger_atr` | CLOSE (family-wise null) |
| `touch_vol_ratio` (stock) | BANK AS DIAGNOSTIC — real, but not available at the real IOC decision point (known only once the touch bar closes; the user never watches a candidate touch live) |
| `touch_vol_ratio` (real options P&L) | BANK, coverage-limited (36.5%), same diagnostic-only status |
| G.1 S1 timing | BANK AS DIAGNOSTIC — survives formal test, small effect, same non-actionable status |
| Order-book/order-flow/depth | legitimately reopened as the next research direction — dashboard-observable OHLCV state is now exhausted |

## Baseline funnel — how big is the problem, before chasing any predictive feature

User's own framing, asked directly: "when I see a primed candidate, how many of them
actually breach, and of those, how many instant-stall vs run further then stall vs
really continue?" Pure descriptive baseline, no new features, done before any further
discovery work — same discipline as "establish the phenomenon before explaining it."

**Primed → touched (fire rate), full history, by year (n=134,264 primed candidate-days,
2021-11 to 2026-09):**

| Year | primed | touched | fire rate % |
|---|---|---|---|
| 2021 | 1,394 | 308 | 22.1 |
| 2022 | 25,729 | 5,750 | 22.3 |
| 2023 | 31,753 | 7,307 | 23.0 |
| 2024 | 31,312 | 6,880 | 22.0 |
| 2025 | 23,862 | 5,007 | 21.0 |
| 2026 | 20,214 | 4,144 | 20.5 |
| **Total** | **134,264** | **29,396** | **21.9** |

A stable ~20-23% of primed candidates ever touch the trigger at all, every single year.

**Touched → outcome (BLAST/STALL/FAIL, T+5 close), full history, by year (n=26,265
clean touches — gap-through days excluded):**

| Year | n | BLAST% | STALL% | FAIL% |
|---|---|---|---|---|
| 2021 | 254 | 18.9 | 50.8 | 30.3 |
| 2022 | 5,169 | 17.0 | 53.6 | 29.4 |
| 2023 | 6,561 | 23.7 | 53.8 | 22.6 |
| 2024 | 5,995 | 18.9 | 55.6 | 25.4 |
| 2025 | 4,526 | 14.7 | 57.5 | 27.8 |
| 2026 | 3,760 | 15.3 | 55.7 | 29.0 |
| **Total** | **26,265** | **18.5** | **55.1** | **26.5** |

**Not a fluke of one regime — STALL sits between 51-58% and FAIL between 23-30% in
every one of the 6 years tested.** This is the real, stable baseline the user's
"why am I even trading this" concern is grounded in.

**Finer split within touched & non-BLAST (STALL+FAIL): is the stall instant, or does
price run further first?** Restricted to the 5-min-covered window (n=1,456, the same
population `06_post_touch_participation.py` built) — "instant" = `excursion3_atr <= 0`
(price never made even one more new high in the 15 min after the touch bar closed);
"ran further" = it did, before eventually fading into STALL/FAIL by T+5.

| | n | % of non-BLAST |
|---|---|---|
| Ran further, then faded | 998 | **79.7%** |
| Instant, no further progress at all | 254 | 20.3% |

**The dominant failure shape is NOT an instant rejection at the trigger — it's "runs a
bit further (consistent with both RBLBANK's real 65-minute push and COALINDIA's real
20-minute push before fading), then gives it back."** Only 1 in 5 stalls/fails never
even attempts a second push. Row-wise, the "instant" group is somewhat more FAIL-heavy
(32.6% vs 26.8%) and less BLAST-heavy (9.9% vs 15.0%) than the "ran further" group, but
the difference is modest, not a clean separator on its own.

**How long, and how far — the full distribution (`08_peak_shape.py`), scanning the
entire rest of the session after the touch bar for the real same-day peak, not just a
15-minute window:**

| | time-to-peak (min): P25/med/P75/P90 | magnitude (ATR): P25/med/P75/P90 | magnitude (%): P25/med/P75/P90 |
|---|---|---|---|
| BLAST | 15 / **103** / 255 / 345 | 0.27 / **0.58** / 1.19 / 1.87 | 0.76 / **1.73** / 3.25 / 5.71 |
| STALL | 5 / **35** / 160 / 300 | 0.14 / **0.34** / 0.68 / 1.14 | 0.43 / **1.03** / 2.08 / 3.82 |
| FAIL | 0 / **15** / 85 / 204 | 0.10 / **0.24** / 0.53 / 0.89 | 0.29 / **0.72** / 1.56 / 2.71 |
| non-BLAST overall | 5 / **30** / 135 / 280 | 0.12 / **0.31** / 0.63 / 1.08 | 0.37 / **0.94** / 1.93 / 3.47 |

**The typical failed/stalled trade still runs ~30 minutes and ~1% past the trigger
before fading — a real push, not a token one.** RBLBANK itself (65 min, +0.70%) sits
longer-but-shallower than the non-BLAST median. The clean gradient from FAIL → STALL →
BLAST is itself informative: eventual real winners push roughly **3x longer** (103 vs
30 min) and **nearly double the distance** (0.58 vs 0.31 ATR) on their first same-day
peak, compared to the typical non-BLAST outcome — before anything about the later
fade/hold distinction even comes into play. Sanity-checked: the script reproduces
RBLBANK's hand-verified 65-min/+0.70% figure exactly.

## Verdict

No mechanism is promotable as a pre-entry filter yet, but one real, if unproven, lead
emerged: **unusually high volume on the touch bar itself (`touch_vol_ratio`, Family D)
is the one feature in this whole pass that is both economically sensible as an
absorption-adjacent proxy and directionally consistent in every one of the 4 available
months.** Family C (R1/R2 distance) and raw approach speed (Stage 3) are flat and
closed in their simple forms. G.1 (S1-break timing) gives a small-sample lead toward
"deterioration appears after the touch, not before." Family E (post-touch
participation) is clean and strong but same-day telemetry, not decision-time
information — it describes the failure, doesn't predict it in advance. **Checked
directly against RBLBANK itself** (the only one of the two anchors inside this
population — COALINDIA's 2026-09-30 event post-dates `panel.csv`'s current build and was
never scored by these scripts): its actual `touch_vol_ratio` is **13.31, solidly inside
T3**, real outcome FAIL with r5=−1.89 — a genuine, not asserted, match to the aggregate
pattern. (Its same-day close was roughly flat vs. the trigger — the FAIL label is a
T+5-close outcome, a materially later horizon than the intraday reconstruction
described above; the two are not in tension, just different windows.)

## What we are trying to understand

Does Prime BC enter after the fast, valuable part of the move has already happened —
and if the trigger stalls immediately, is that because of pre-existing weakness, the
trigger level's own resistance structure, or something that only shows up after the
touch? Per the brief: mechanism-neutral, no strategy construction, separate real
observation from price/volume proxy from hypothesis (§17 terminology).

## Scope / guardrails

- Prime BC v31 untouched. No stop/R defined (purely observational, Rule #20 N/A here).
- No order-book/depth data used or claimed — none exists in this project (verified
  2026-10-03, see the critic handoff this thread opened with).
- Population for G.1/Stage 3: `panel.csv`'s touched & non-gap-through rows, restricted
  to the 5-min cache window (**2026-06-10 to 2026-09-29, 78 sessions, 386 tickers,
  n=1,475**) — materially smaller than the full 26,265-trade daily-only population RQ-
  PB-2 used elsewhere. This is a real, single-regime window; no year-by-year robustness
  check (Rule #19) is possible with this data. Treat everything below as exploratory.
- Population for Family C: the full `pivot_feats.pkl` population (n=26,265, daily bars
  only, no intraday timing needed).
- All comparisons use RQ-PB-2's own pre-declared outcome definition (`cls`: BLAST
  r5≥1.5 ATR, FAIL r5≤−1.0 ATR, STALL between, measured at T+5 close) — no new outcome
  metric invented.
- Comparison-set sampling (Stage 1) was pre-declared before looking at any result: seed
  42, 3 STALL + 3 BLAST tickers from `pivot_feats.pkl`, restricted to the 5-min window,
  excluding the two motivating dates. Not cherry-picked on fit.

## Results

### Stage 1 — RBLBANK and COALINDIA reconstruction (hand-verified against raw 5-min bars)

**A real bug caught before trusting either reconstruction (Rule #22)**: the first pass
computed the trigger from the *prior* row's `high10_prior`, double-shifting it — `high10_
prior`, `pp`, `r1`, `r2`, `s1` are already T-1-known **on the current row**
(`signals.py`'s `high10_prior=High.shift(1).rolling(10).max()`; `daily_pivots()` shifts
H/L/C internally). Only `atr14` needs the prior row (not pre-shifted). The first-pass
RBLBANK trigger (422.50) was a day stale; the corrected value (426.52) matches
`panel.csv`'s independently-built `trigger` column exactly — cross-validated, not just
asserted.

**RBLBANK, 2026-09-23** — trigger 426.52. Touched at 09:25 (10 min after open, not a
gap-through). Price continued up on real volume to a session high of **429.50 at
10:30**, then chopped sideways/down for the remaining ~4.5 hours, closing at 428.00 —
essentially flat vs. the trigger, never regaining the 429.50 high. **Side finding**: the
project's standard *daily* R2 that day was 438.37 (irrelevant, far overhead) — but the
*weekly* R2 was **429.1999, matching the real intraday top to within 0.3**. This matches
`../FINDINGS.md:6719`'s original live note ("touched R2=429.20 ... rejected") exactly —
that note was computed from weekly pivots, not daily, which is why it didn't match this
thread's default daily-pivot convention. Real, hand-verified, but a single anecdote (see
Family C below for whether it generalizes — it doesn't).

**COALINDIA, 2026-09-30** — trigger 431.55. Touched at 10:55. Pushed to a session high of
**432.15 at 11:15 on the day's single biggest volume bar (401,194 shares — matches the
trade-journal's "4.01 lakh shares" exactly)**, then declined for the rest of the session,
closing at **425.00 — well below the trigger**, a real failed breakout (FAIL by the T+5
definition), not just a mild stall.

**Shared shape in both anchors**: touch → a further push to a local intraday peak (on
real volume) → multi-hour decline/chop → close back at or below the trigger, giving
back most or all of the post-touch gain. **Corrected (`08_peak_shape.py`, verified
against the raw bars): RBLBANK's push was 65 minutes to +0.70% (+0.24 ATR) past the
trigger; COALINDIA's was 20 minutes to +0.14% past it** — an earlier draft of this
section said "10-20 minutes" for both, which was wrong for RBLBANK specifically (caught
by the dedicated peak-shape script's own sanity check against this exact reconstruction,
Rule #22). Both reconstructions are saved in full (`recon_RBLBANK_2026-09-23.csv`,
`recon_COALINDIA_2026-09-30.csv`) for direct inspection.

**Comparison set** (seed 42, pre-declared, n=6): STALL — MEESHO (2026-09-03), APLAPOLLO
(2026-08-27), PGEL (2026-07-13); BLAST — APLAPOLLO (2026-08-13, a different date from
its own STALL pick above), PPLPHARMA (2026-07-27), SONATSOFTW (2026-07-29). Full
per-ticker reconstructions saved as `recon_<ticker>_<date>.csv` for hand review. Not
used to draw a population conclusion (n=6) — purpose was solely to confirm the
reconstruction code produces sane, readable output on cases other than the two
anecdotes, which it does.

### Family C — R1/R2 distance to trigger (`02_r1r2_distance.py`), n=26,265

Not in RQ-PB-2's original confluence sweep (which tested pp/s1/ema8/13/21/34 only).
Tested both **daily** and **weekly** R1/R2, in ATR terms, tercile-bucketed, plus the
RBLBANK-motivated specific cut ("is R2 within 1 ATR overhead of the trigger").

| Cut | BLAST% range | FAIL% range | r5_mean range |
|---|---|---|---|
| d_r1 (daily), terciles | 17.8–19.5 | 25.7–27.4 | 0.07–0.15 |
| d_r2 (daily), terciles | 18.3–18.6 | 25.5–28.3 | 0.07–0.13 |
| d_r1 (weekly), terciles | 17.1–19.8 | 25.5–27.3 | 0.05–0.14 |
| d_r2 (weekly), terciles | 17.7–19.6 | 25.7–27.3 | 0.08–0.13 |
| R2 (daily) within 1 ATR overhead | 18.4 vs 18.8 | **25.8 vs 28.2** | 0.10 vs 0.09 |
| R2 (weekly) within 1 ATR overhead | 18.4 vs 18.5 | **25.7 vs 27.0** | 0.11 vs 0.10 |

**Flat, in every cut, both pivot periods.** If anything, being within 1 ATR of
overhead R2 shows a *slightly lower* FAIL rate than being far from it — the opposite of
a resistance-causes-failure story, though the gap (2-3pp) is well within the noise this
project has already flagged for near-identical pp/s1/ema cuts (Section E: "closer
support lowers FAIL and BLAST together... mostly measures how wide yesterday's range
was" — the same range-width confound plausibly applies here, since R1/R2 are built from
the same prior H-L as the ATR denominator). **RBLBANK's weekly-R2-matching-the-exact-
top is a real, hand-verified single case. It does not generalize population-wide.**
Family C is closed in this simple form — do not build an R1/R2-proximity filter.

### Stage 2 / G.1 — S1-break timing vs. the touch (`03_s1_timing.py`), n=1,475

| S1-break timing | n | BLAST% | FAIL% | r5_mean |
|---|---|---|---|---|
| never | 1,337 (90.6%) | 14.6 | 26.0 | −0.00 |
| before the touch | 68 (4.6%) | 8.8 | 39.7 | −0.37 |
| after the touch | 68 (4.6%) | 10.3 | **52.9** | **−0.80** |
| same bar | 2 | 0.0 | 100.0 | −1.78 |

A same-day S1 break is rare (9.2% of touches overall, matching the order of magnitude
of RQ-PB-2's own `SAME_low_above_s1` daily-bar check). Split almost exactly evenly
before/after the touch. **Both are worse than never, but "after" is meaningfully worse
than "before"** (FAIL 52.9% vs 39.7%, r5_mean −0.80 vs −0.37) — the opposite of what a
"these were already-doomed setups" story would predict (that would show "before" as
equal or worse). This favors the brief's Pattern 2 (price stays healthy until the touch,
then deterioration appears immediately after) over Pattern 1 (deterioration already
under way before the touch) for the specific S1-break mechanism, though n=68 per bucket
is small and this has not been robustness-checked (can't be, with only 78 sessions of
intraday data) — **exploratory, not promotable** (Rule #19/#21).

### Stage 3 — fast vs. slow approach (`04_approach_speed.py`), n=1,475

Pre-declared cut (touched within first 30 min of session vs. later): BLAST 13.5% vs
14.7%, FAIL 28.2% vs 27.6%, r5_mean −0.02 vs −0.10. Tercile and decile breakdowns show
no monotonic trend (FAIL bounces 17.6%–37.4% with no relationship to approach speed).
**Flat. Pattern 4 (fast approach itself changes the outcome) does not hold** in this
simple form — raw minutes-to-touch, by itself, carries no information about BLAST vs
FAIL. (RBLBANK touched in 10 minutes and chopped for hours; COALINDIA took 100 minutes
and failed outright — the two anchors themselves don't even agree on speed, consistent
with this null result.)

### Family D — activity vs. displacement (`05_activity_displacement.py`), n=1,475

The closest honest proxy this project's OHLCV data can build toward "absorption" — a
volume/price proxy throughout, never an order-book claim (sec. 17 terminology).

| Feature | T1 (low) | T2 | T3 (high) | Direction |
|---|---|---|---|---|
| touch_vol_ratio (touch bar Volume / day's own median 5-min bar) | FAIL 26.8%, r5 +0.11 | FAIL 22.2%, r5 +0.08 | **FAIL 34.8%, r5 −0.37** | worse at the high end |
| touch_progress_atr ((High_touch−trigger)/ATR) | FAIL 27.6%, r5 −0.11 | FAIL 29.3%, r5 −0.13 | FAIL 26.8%, r5 +0.06 | weak, non-monotonic |
| post_pre_vol_ratio (3-bar post / 3-bar pre volume, n=313 — needs 3 bars before touch) | FAIL 22.4%, r5 +0.00 | FAIL 29.1%, r5 −0.12 | FAIL 27.8%, r5 −0.14 | worse when post-touch volume surges relative to pre |
| net_progress_15m_atr ((Close[t+2]−trigger)/ATR) | FAIL 34.0%, r5 −0.37 | FAIL 26.8%, r5 −0.09 | FAIL 22.8%, r5 +0.29 | expected — near-tautological, same-day telemetry |
| FLAGGED (top-tercile volume AND bottom-tercile progress, same bar) | — | — | n=140, FAIL 31.4% vs not-flagged 27.6%, r5 −0.33 vs −0.03 | real but modest |

**`touch_vol_ratio` is the standout lead**: unusually high relative volume on the touch
bar itself (top tercile, 6.5×–385× the day's own median 5-min bar volume) comes with
markedly worse outcomes than low-volume touches. **Checked by month (the closest
available substitute for Rule #19's year-by-year check, given only 4 months of 5-min
coverage)**: T3 (high volume) is worse than T1 on r5_mean in **every single month**
tested (Jun +0.33→−0.15, Jul +0.39→−0.27, Aug −0.01→−0.28, Sep −0.98→−1.39) — the most
consistent-in-direction result this entire thread has produced, though it is still one
regime / 4 months, not a true multi-year robustness pass. `touch_progress_atr` alone is
weak — it's the raw volume spike driving the effect, not volume-per-unit-of-displacement
specifically (the FLAGGED composite, which requires both, is *weaker* than `touch_vol_
ratio` alone). `net_progress_15m_atr` is expected/tautological same-day telemetry (if
price hasn't progressed 15 min after the touch, it's more likely to fail by T+5 — not
surprising, not a new mechanism).

### Family E — post-touch participation (`06_post_touch_participation.py`), n=1,456

| Feature | T1 (low/absent) | T3 (high/present) |
|---|---|---|
| next_bar_ret_atr | FAIL 32.8%, r5 −0.24 | FAIL 24.5%, r5 +0.07 |
| next_bar_clv (close location of the bar after touch) | FAIL 31.5%, r5 −0.20 | FAIL 25.9%, r5 +0.02 |
| excursion3_atr (best price in the 15 min after the touch bar) | FAIL 31.5%, r5 −0.27 | FAIL 22.6%, r5 +0.29 |
| successive_highs (0 vs 3 of the next 3 bars making a new High) | FAIL 31.6%, r5 −0.27 | **FAIL 16.8%, BLAST 21.4%, r5 +0.54** |
| held30 (closes stay ≥ trigger×0.998 for 30 min) | FAIL 31.2%, r5 −0.22 | FAIL 22.3%, r5 +0.22 |

**Every Family E feature is clean and strongly monotonic** — far cleaner than anything
in Families C/D. `successive_highs` is the sharpest: 0-of-3 new highs in the 15 min
after the touch bar closes vs. 3-of-3 spans a 15-point FAIL-rate gap and a 0.8 swing in
r5_mean. **But every one of these is same-day telemetry, known only minutes into the
trade — not pre-entry information.** They answer "did follow-on buying show up" (the
brief's own Family E question) cleanly: when it doesn't, the trade fails at a much
higher rate. They cannot distinguish *why* it didn't show up (absorbed vs. no one was
ever going to buy) — exactly the limit the brief itself flagged for OHLCV-only data.

### Lead-time sweep on `touch_vol_ratio` (`07_lead_time_sweep.py`) — no early-warning signal at any tested lead

Direct follow-up to the critic's actionability question, reframed per the user: not "is
this visible before the touch bar closes" (unanswerable — the historical cache only
ever stores closed candles, confirmed by checking how `intraday_cache.refresh()`
fetches: always after the candle has finished), but "does volume-so-far already look
abnormal while a stock is still APPROACHING the trigger, before it has touched at all."
Fully testable with existing closed-bar data — no granularity problem here, unlike the
critic's original proposal.

Three pre-declared checkpoints, feature = cumulative volume up to that point, normalized
against that ticker's own historical median cumulative volume at the same time-of-day
(prior 20 sessions, strictly before today — reusing `rq_pb2/01_approach_entry.py`'s
`typ` baseline / `live_checkpoint.py`'s `_clock_time_volume_fraction` idea, not a new
construction):

| Checkpoint | n | T1 (low) | T2 | T3 (high) |
|---|---|---|---|---|
| A. 5 min before the touch | 786 | FAIL 29.8%, r5 −0.27 | FAIL 27.5%, r5 +0.00 | FAIL 26.0%, r5 −0.02 |
| B. 30 min before the touch | 589 | FAIL 35.7%, r5 −0.29 | FAIL 22.4%, r5 +0.06 | FAIL 28.9%, r5 −0.11 |
| C. fixed 09:45 (only rows where the touch happens after 09:45) | 589 | FAIL 35.7%, r5 −0.26 | FAIL 25.5%, r5 −0.03 | FAIL 25.9%, r5 −0.06 |

**Flat/non-monotonic at every checkpoint — no detectable buildup.** B and C both show a
U-shape (low AND high volume-so-far are worse than the middle), the opposite of a clean
"more pre-touch volume = worse" trend, and nowhere close to the touch bar's own clean
monotonic pattern. Hand-checked against RBLBANK itself (the NaNs on its earliest dates
are a legitimate exclusion — insufficient prior-session history that early in the
5-min-cache window for the time-of-day baseline, the same `min_periods=10` constraint
`01_approach_entry.py` already uses, not a bug; its one valid reading, ratio_5before =
2.07, lands in the T2 bucket, which shows no real effect either way — consistent with
the aggregate null). **The touch-bar volume spike is not something that was already
building in the 5 or 30 minutes before the touch, or visible at a fixed 09:45 check —
it appears to materialize at the touch bar itself, not before it.**

**This resolves the actionability question the critic raised, differently than
expected**: there is no early-warning version of this feature to chase, at any lead
time tested. But per the user's own clarification of how they actually use this system
— they are never watching a candle form in real time, so by construction, whenever they
do check the dashboard, the touch bar (which closes 5 minutes after the touch) has
already finished — `touch_vol_ratio` is, in practice, always already known by the time
a real decision gets made. The "is it known early enough" framing turns out not to be
the right question for this specific signal and this specific user's workflow; the real
open questions are robustness (Rule #19) and the Rule #22 spot-check already requested,
not timing.

## Mechanism interpretation

- **Not explained by raw approach speed or by overhead R1/R2 distance** — both tested
  cleanly, both flat. The RBLBANK/COALINDIA anecdotes are real and well-documented, but
  neither "it got there too fast" nor "there was resistance overhead" survives as a
  population-level explanation in the form tested.
- **The clearest lead so far is temporal**: when a hard reversal (S1 break) happens, it
  mostly happens *after* the breakout attempt, not before — and post-touch breaks are
  notably worse than pre-touch ones. This is more consistent with "the trigger-level
  interaction itself produces the failure" (Pattern 2) than with "BC is entering an
  already-decaying transition" (Pattern 1) — but it's one proxy (S1), on a small,
  single-regime sample, not yet a mechanism.
- **`touch_vol_ratio` (Family D) is a same-touch-bar phenomenon, not a precursor** — the
  lead-time sweep found no buildup beforehand at 5 min, 30 min, or a fixed clock-time
  checkpoint. Whatever is happening, it happens at the touch itself, consistent with
  (though not proof of) something that only becomes visible once aggressive buying
  actually meets the trigger level, rather than a gradually accumulating imbalance.

## What existing data can and cannot observe

- **Can observe**: 5-min OHLCV timing (touch time, S1-break time, approach speed),
  daily-bar pivot structure (R1/R2/S1/PP, both daily and weekly), volume at specific
  bars (used qualitatively in the reconstructions — COALINDIA's 11:15 peak bar volume
  matched the journaled real trade exactly).
- **Cannot observe**: any direct evidence of resting sell-side quantity, order
  cancellations, or absorption. Every Family D/E feature built this pass is a
  volume/price proxy, never a Level 1-4 claim per the brief's own ladder — this audit
  stays capped below Level 1 throughout, including `touch_vol_ratio`, the strongest
  lead found.
- **Would historical order-book data materially change this?** Possibly, specifically
  for distinguishing "absorbed" (resting supply met the buying) from "no one showed up"
  (buying interest simply ran out) — `touch_vol_ratio` is consistent with either story,
  since it only measures that volume was high, not what was behind it. Families C
  (R1/R2) and raw approach speed (Stage 3) were fully testable with existing data and
  came back flat regardless, so missing data isn't why those two were negative. Per the
  critic's own sequencing (Stage 7, after mechanism discrimination), this question is
  not re-opened here — but `touch_vol_ratio` is now the first concrete candidate where
  the order-book question would actually matter if this gets promoted further.

## Exact next action

The actionability question is now resolved, not open: `touch_vol_ratio` has no early-
warning form (lead-time sweep, above) and needs none — given the user's actual
workflow (never watching a candle form live), the touch bar is always already closed by
the time a real decision happens. What's left is Rule #19 (only 4 months, one regime —
can't be fixed without more 5-min history becoming available) and the Rule #22
spot-check the critic separately requested (1-2 hand-checked examples per month,
including the critic's explicit counterexample ask: high-ratio-but-good-continuation
and low-ratio-but-FAIL cases). That spot-check is the next concrete step — not another
timing test.

## Decision

Two of five candidate families closed negative in their tested form (Family C/R1-R2;
raw approach speed). Family E (post-touch participation) is real and clean but
same-day telemetry, not a pre-entry signal — informative about the mechanism, not
usable as a filter. G.1 (S1-break timing) and Family D (`touch_vol_ratio`) are the two
genuine open leads, both small-sample/single-regime/exploratory, both pointing the same
direction: something distinguishing stall-then-fail from continuation shows up **at or
after** the touch, not before it (Pattern 2, not Pattern 1 — the brief's own framework).
`touch_vol_ratio`'s actionability concern is resolved (no early-warning form exists, but
none is needed for this user's real workflow). Recommend: BANK `touch_vol_ratio`, run
the Rule #22 spot-check next, do not promote either it or the S1-timing lead to a
filter yet, and treat Pattern 5 (no OHLCV mechanism distinguishes outcomes) as ruled
out, not confirmed — something real is there, it just isn't actionable pre-entry with
this data yet.

## RQ-OM-00 — Measurement-Integrity Audit of the touched population (2026-10-05, per CLAUDE.md Rule #23)

Audits the exact population behind the 6-year baseline and every candidate feature test
above (`rq_pb2/pivot_feats.pkl`, n=26,265, `touched & ~gap_through`, BLAST/STALL/FAIL =
r5 ≥1.5 / ≤−1.0 / between, ATR-normalized, at T+5 close). Existing fields only, no new
filters, no removed observations. Script: `12_measurement_integrity_audit.py`, output
`rq_om00_out.txt`, round-trip reconstruction `rq_om00_roundtrip.csv` (gitignored,
regeneratable).

**Dim 1 — trigger-candle sanity.** 24.5% of touches (6,446/26,265) are red candles
(Close < Open) on the touch day itself. `touched` is correctly wick-based for the
trigger itself (Rule #18) — this isn't a bug in the trigger definition — but the
pooled 55.1/26.5/18.5 baseline silently mixes red and green touch-day candles, which
have very different composition: red touches are 40.4% FAIL / 9.5% BLAST; green
touches are 21.9% FAIL / 21.4% BLAST. A touch that pokes the trigger and reverses hard
intraday behaves nothing like one that pushes through cleanly.

**Dim 2 — wick vs close.** 57.1% of ALL touches (14,992/26,265) give back intraday and
close BELOW the trigger same day (`close_above=False` — already a stored field, never
conditioned on in any prior test). Composition: `close_above=False` → 34.2% FAIL /
11.5% BLAST; `close_above=True` → 16.2% FAIL / 27.8% BLAST — more than 2x the FAIL-rate
spread of anything in the Family A/B/C sweep (max real effect there was |rho|=0.095).
Mechanically, since `gap_through` rows are excluded (Open always < trigger here), every
red-candle touch is *necessarily* also a give-back (Close < Open < trigger) — Dim 1's
24.5% is a strict subset of Dim 2's 57.1%, not an independent second finding.

**Dim 3 — gating.** Verified by source read (`01_build_panel.py`'s `build()` loop has
no position-state variable at all) and the file's own docstring ("observational, no
gating of positions... NOT a position population"). **PASS — this population is
genuinely ungated.** Does not establish anything about downstream consumers; checked
only for this specific shared panel.

**Dim 4 — structural context (round-trip before resolution).** Reconstructed from raw
daily bars (not a stored field): did price ever close below the touch-day's own Low,
or back below the trigger, at any point in T+1..T+5 before the cls label was set?
**60.1% of ALL touches breach the touch-day's own Low within 5 days; 73.7% close back
below the trigger again.** By class: FAIL 97.4%/100.0% (expected, that's close to the
definition). STALL 55.9%/76.8%. **BLAST — the labeled "winner" class — still breaches
its own entry-day Low 19.2% of the time and closes back below the trigger 26.6% of the
time before going on to post r5≥1.5.** Hand-verified (Rule #22): HBLENGINE
2024-02-01 touched at High 544.50 (Low 520.15, trigger 542.70), pulled back to a Low of
506.05 and a Close of 518.95 on 2024-02-05 (below both the touch-day Low and the
trigger), then closed 593.70 by 2024-02-09 — r5=1.92, correctly labeled BLAST, but any
real stop at the touch-day's own Low would have been hit three days before the move
happened. Matched 26,252/26,265 touches (99.95%) to raw bars; numbers are not a join
artifact.

**Interpretation — not a "Superseded" result, a "Conditional" one.** The pre-touch
dashboard-state closure (Family A/B/C, G.1, `touch_vol_ratio`) is unaffected: none of
Dim 1/2/4 above is knowable at the live IOC decision moment, so "no pre-entry OHLCV
predictor" still stands. What changes: the **pooled 6-year baseline itself** was never
decomposed by the simplest possible same-day-close signal (did the touch bar even close
above the level it touched) — a much bigger effect than `touch_vol_ratio`, which *was*
tested and banked. This is the same information family (same-day-closed, not
live-IOC-actionable — same non-actionability caveat as `touch_vol_ratio`/G.1), just a
stronger, cheaper, previously-untested member of it, worth a note on the board even
though it doesn't reopen the pre-entry question.

**Cross-reference, not yet reconciled**: `close_above` here is conceptually the same
split as `confirmed_day1/RQ-CD1`'s "Confirmed" (Close0 > raw pivot) — RQ-CD1 called
that split "weak" using a Day+1-return lens (+0.26% vs +0.05%). This audit's 5-day
BLAST/STALL/FAIL lens makes the same underlying split look much larger (34.2% vs 16.2%
FAIL). Both can be true (a small daily edge compounding into a materially different
5-day distribution) but this hasn't been directly checked against RQ-CD1's own numbers
— flagged, not resolved, per the theoretical-sanity-check discipline.

**Prime BC positional-character connection**: Dim 4 directly supports the reframe —
"BC's tested implementation didn't establish the short-horizon phenomenon and evolved
into a positional trade" is more consistent with this data than "the phenomenon doesn't
exist." A meaningful share of real winners (BLAST, 19-27%) only resolve as winners
*after* round-tripping through a level a tight near-term stop would have hit — a stop
tight enough to capture the "fast" cases cuts into real eventual winners, which is
exactly the kind of pressure that pushes an exit engine toward wider stops/trailing
over time, independent of whether a genuinely fast subset of moves also exists.

**Revised board, per Rule #23's closure taxonomy:**

| Item | Prior disposition | Rule #23 taxonomy |
|---|---|---|
| 6-year touched→STALL baseline | ESTABLISHED | **Conditional** — correct as stated, but never decomposed by same-day-close; not wrong, just not yet earning "high-confidence" as *the* reference population |
| Peak-shape anatomy | ESTABLISHED / useful context | High-confidence (not touched by this audit) |
| `cum_vol_ratio`, `dist_open_atr`, 4-feature family-wise (gap_pct/first_dir_up/range_so_far_atr/dist_to_trigger_atr) | CLOSE | **High-confidence** — these are genuinely pre-touch/live-IOC-moment features; Dim 1/2/4 don't touch their null result |
| `touch_vol_ratio` (stock + options), G.1 S1 timing | BANK AS DIAGNOSTIC | High-confidence as diagnostic; **strengthened**, not undermined, by Dim 2 showing a same-day-closed sibling signal with a much bigger effect |
| RQ-TA1 overall "order-flow/depth question is what legitimately reopens" framing | — | Unchanged — still true for the pre-entry question specifically |

**Not done, deliberately**: no new filter built on `close_above`/red-candle (per
RQ-OM-00's own scope — existing fields, no new thresholds); no re-audit yet of
options_momentum/OMD-01/02, RQ-BPC-05, or SST1 (highest-leverage shared population
audited first, per the rule's own "don't reopen everything at once" instruction); no
reconciliation with RQ-CD1 attempted yet.
