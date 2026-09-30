# swing_qs_07a — Findings (append-only)

## RQ-QS-07A-1 — Neutral Event Matrix, complete (2026-09-29, critic-specified)

**Objective (critic's exact wording)**: "Across the full eligible universe, what
types of short-horizon price paths naturally precede and follow unusually large
1-, 2-, and 3-day moves?" No fast-mover threshold chosen, no predictor tested, no
model, no filter — purely the neutral characterization step.

**Population**: `nse_equity_universe.csv` (RQ-QS-07U, 2,327 tickers), NOT
restricted to NIFTY 500 or F&O eligibility — both attached as metadata only.
Eligibility: 60+ days prior history, T itself and T+1..T+3 all corp-action-clean
(the forward window truncation matches every other RQ this session — a split
inside the window would fabricate the forward return). **2,056,725 eligible
stock-days across 2,090 tickers**, 2021-11-26 to 2026-09-24. 237 of 2,327
universe tickers had insufficient history (too recently listed).

**Method verified twice by hand (Rule #22)** before trusting the aggregate:
RELIANCE 2021-11-26 (an ordinary day) — every one of the 12 computed fields
matched raw bars exactly, including day_of_max correctly identifying day 1 as
the peak. KOTYARK 2022-08-03 (a P99.9+ extreme, deterministic pick, not cherry-
picked) — matched exactly too, and exposed something real: the 58.4% D3 move is
three CONSECUTIVE UPPER-CIRCUIT-LOCK days (Open=High=Low=Close each day) — a
genuine illiquid micro-cap circuit-hitting pattern, not organic trading. This is
exactly the "poor historical continuity" risk the critic flagged when discussing
whether to widen past NIFTY 500 — now confirmed present and real in this data,
not theoretical. Flagged for anyone using extreme-tail rows from this matrix.

### Forward distributions (High-based MFE, Low-based MAE, close-to-close sustained)

| Horizon | max_return (MFE) P50/P90/P99 | adverse (MAE) P50/P90/P99 | close_ret (sustained) P50/P90/P99 |
|---|---|---|---|
| D1 | 1.77 / 5.00 / 12.69 | -1.43 / 0.13 / 2.57 | -0.11 / 3.26 / 9.30 |
| D2 | 2.41 / 7.67 / 17.97 | -2.08 / 0.00 / 2.04 | -0.16 / 4.68 / 12.98 |
| D3 | 2.94 / 9.44 / 20.97 | -2.61 / -0.15 / 1.99 | -0.21 / 5.91 / 15.94 |

**The same gap RQ-06 found on the QS-A population shows up here on the entire,
unconditioned market — this is NOT a QS-A-specific artifact.** Median D3 max
favorable excursion is +2.94%, but median D3 close-to-close (sustained) return is
actually slightly NEGATIVE (-0.21%). Touching a good price and closing at a good
price are very different claims, market-wide, with zero entry filter applied.

**Joint MFE/MAE (D3)**: stocks in the worst adverse-move tercile have much lower
median upside (1.74%) than the best tercile (4.97%) — reward and realized risk
move together within the same stock-days, consistent with both being driven by
the same underlying volatility, not independent.

**Day of max**: peak occurs on day 1 43.9% of the time, day 2 23.5%, day 3 32.6%
— the single most common day is day 1, but the majority (56.1%) of the time the
best price of the 3-day window comes LATER, not immediately.

### Path shape (pre-declared, priority-ordered, mutually exclusive)

| Shape | n | % | Median max_return_d3 | Median close_ret_d3 | Median adverse_d3 |
|---|---|---|---|---|---|
| spike_and_fade | 787,728 | 38.3% | 1.81% | -2.22% | -3.99% |
| other | 674,614 | 32.8% | 3.73% | 0.75% | -1.88% |
| progressive | 398,576 | 19.4% | 6.10% | 4.00% | -1.08% |
| burst | 115,121 | 5.6% | -0.06% | -3.48% | -5.36% |
| delayed | 80,686 | 3.9% | 1.45% | -0.79% | -4.52% |

**spike_and_fade is the single largest category in the entire market, 38.3%.**
Of all day-1-peak cases specifically (spike_and_fade + burst = 43.9%, exactly
matching day_of_max==1's share — a clean internal consistency check), 87.2% are
spike_and_fade rather than burst. When ANY stock peaks on day 1, giving back more
than half that gain by day 3's close is by far the dominant outcome, not the
exception. This directly echoes RQ-06E's QS-A-specific finding (the first
pullback after a fresh high is near-universal and largely uninformative) — except
this shows the SAME shape is a market-wide characteristic, present with zero
entry gate at all, not something QS-A's specific entry created.

**progressive is the smallest clean category (19.4%) but by far the best
outcome** — median +6.10% D3 max return, +4.00% sustained close, only -1.08%
adverse — the only path shape whose median close_ret is a meaningfully large
positive number.

**Honest, disclosed definitional gap in "burst," found via hand-check, not
hidden**: 69% of burst-labeled days have max_return_d1 <= 0 — day 1 was merely
the LEAST-BAD day of an ongoing decline, not a real upside spike that held up.
"burst" as literally pre-declared (day_of_max==1, not spike_and_fade) doesn't
require max_return_d1 to be positive, only that spike_and_fade's specific
giveback condition didn't trigger. This explains burst's counterintuitive
slightly-negative median outcome. NOT patched retroactively — reported exactly
as pre-declared, per this project's own discipline against redefining categories
after seeing results. A cleaner "burst" (requiring real day-1 upside AND no
fade) is a legitimate, disclosed candidate refinement for a later, explicitly-
labeled pass — not applied here.

### Year-by-year (Rule #16 — never pool years)

| Year | n | max_return_d3 median | close_ret_d3 median | adverse_d3 median |
|---|---|---|---|---|
| 2021 (partial) | 16,955 | 3.33% | 0.88% | -1.71% |
| 2022 | 379,442 | 3.19% | -0.21% | -2.82% |
| 2023 | 400,802 | 2.85% | 0.00% | -2.14% |
| 2024 | 428,328 | 3.10% | -0.15% | -2.69% |
| 2025 | 465,974 | 2.68% | -0.41% | -2.65% |
| 2026 | 365,224 | 2.92% | -0.37% | -2.86% |

Raw upside potential (MFE) is stable across years, 2.68-3.33%. Sustained
(close-to-close) return sits at or below zero in every full year since 2021 —
this is the real, honest, unconditioned baseline any future "fast mover" cohort
or filter needs to clear by a meaningful margin, not a low bar.

### NIFTY 500 / F&O metadata split (current membership, v1 point-in-time caveat)

| | n | max_return_d3 median | close_ret_d3 median | adverse_d3 median |
|---|---|---|---|---|
| NIFTY 500 member | 534,511 | 2.32% | +0.03% | -2.04% |
| Not NIFTY 500 | 1,522,214 | 3.19% | -0.31% | -2.85% |
| F&O eligible | 242,138 | 2.08% | +0.10% | -1.85% |
| Not F&O eligible | 1,814,587 | 3.08% | -0.26% | -2.73% |

Non-index and non-F&O names show real, larger raw movement in both directions —
expected for smaller/less liquid names — but slightly WORSE sustained outcomes,
not better. More raw movement outside NIFTY 500 is confirmed real, but it isn't
obviously higher-quality movement on a close-to-close basis. Consistent with the
critic's own caution about small/micro-cap noise, and directly relevant to
whether a future cohort should be built stock-only or restricted to a more
liquid subset.

### Tail anchors (no threshold chosen — for reference only)

P90 max_return_d3 = 9.44% (205,673 stock-days), P95 = 12.94% (102,837), P99 =
20.97% (20,568), P99.5 = 25.76% (10,284).

**Not yet done, by design**: no "fast mover" cohort defined; no matched-control
comparison; no feature/predictor tested against any outcome; no model, score, or
threshold promoted anywhere. This is the neutral distribution step only, per
critic's exact sequencing — deciding what constitutes a fast mover, and building
the winner-vs-control comparison, comes next and has not started.

**Files**: `01_event_matrix.py`, `02_characterize_distribution.py`,
`event_matrix.csv` (2,056,725 rows, 474MB, gitignored — fully reproducible from
`data_cache/` + `nse_equity_universe.csv`, not committed), `event_matrix_sample_
200k.csv` (deterministic seed=42 sample, committed for quick inspection).

## RQ-QS-07A-2 — Fast-Mover Cohort Characterization + Matched Controls (2026-09-29, critic-specified)

**Method, exactly as pre-registered**: two separate cohorts, kept deliberately
distinct per critic's core 07A-1 finding ("large opportunity and large sustained
movement are not the same phenomenon"). **Cohort A (Opportunity)**: D3 MFE >= its
own empirical P95 (12.94%). **Cohort B (Sustained)**: D3 close-to-close return >=
ITS OWN empirical P95 (8.89% — not the MFE threshold forced onto a different
distribution). Both n=102,837 by construction. Matched control: same calendar
date + same cross-sectional liquidity decile (`traded_value_sma20` at T, ranked
among all eligible stock-days that date) + not itself a cohort member, one draw,
seed=42. 100% matched (130,175 of 130,175 cohort events found a same-date/decile
non-cohort partner). Circuit-day annotation added to the event matrix itself
(O==H==L==C within 0.05% tolerance, the exact KOTYARK signature verified in
07A-1), plus liquidity, F&O, NIFTY-500 as stratification, not filters — nothing
removed from either cohort. `burst_clean` (max_return_d1>0, secondary label) added
alongside `burst_v0` (unchanged, per critic: "don't rerun... carry burst_v0").

**Rule #22**: hand-verified JIOFIN 2024-02-01 (deterministic middle-of-list pick
from the "clean tradeable" subset defined below, not cherry-picked) against raw
bars — every field exact, including day_of_max correctly identifying day 2 (the
Feb 5 spike to 295.70) as the peak, with day 3's close still up 7.35% despite the
peak already softening intraday.

**Cohort A and B overlap heavily (73.4%) despite measuring different things.**
Most extreme-MFE events are also extreme-sustained-return events. The "not the
same phenomenon" finding from 07A-1 describes the OVERALL population (where the
median diverges sharply, MFE +2.94% vs close +/-0.21%) — at the very top of
either distribution, the two substantially converge. Worth holding both facts at
once, not treating them as contradictory.

### Cohort A (Opportunity) vs. matched control

| | Cohort A | Matched control |
|---|---|---|
| max_return_d1 (median) | 5.00% | 2.06% |
| max_return_d3 (median) | 15.91% | 3.56% |
| close_ret_d3 (median) | 12.34% | 0.26% |
| adverse_d3 (median) | -0.51% | -2.38% |
| path_shape: progressive | 59.2% | 20.5% |
| path_shape: spike_and_fade | 6.6% | 21.5% (pop. baseline 38.3%) |
| NIFTY 500 member | 11.2% | 15.0% |
| F&O eligible | 3.0% | 5.2% |

**The path-shape gap is the single starkest number, and it's largely mechanical,
not a deep discovery — worth being honest about that.** Selecting for an extreme
D3 MFE naturally selects for paths whose peak keeps extending through day 3
(progressive-like), and mechanically excludes early-peak-then-fade paths from
ever reaching that extreme (a fade, by construction, caps out before D3). This
IS still useful — it confirms the cohort is behaviorally coherent, not noise —
but it should not be oversold as an independent predictive insight; it follows
substantially from how the cohort and the path-shape taxonomy are both derived
from the same underlying MFE/day-of-max quantities.

**Cohort A skews toward LOWER liquidity even after matching on liquidity decile
against the control** — 16.9% of Cohort A sits in the lowest liquidity decile
(vs. an even 10% if liquidity didn't matter at all), falling steadily to 3.6% in
the highest decile. Real opportunity is genuinely concentrated in the less-liquid
tail, exactly the pattern the critic anticipated when the universe was widened
past NIFTY 500 — now quantified, not assumed.

### Cohort B (Sustained) vs. matched control — very similar shape to Cohort A

`path_shape` even more skewed toward progressive (72.5%) with almost no
spike_and_fade (0.2% — makes sense, spike_and_fade's own definition requires a
big D3 giveback, which is close to the opposite of what defines Cohort B).
NIFTY-500/F&O representation (14.4%/4.7%) sits between Cohort A and the control,
consistent with sustained moves being somewhat, but not dramatically, more
common among larger/liquid names than pure MFE spikes are.

### Tradeability audit of Cohort A — a breakdown, not a filter

| | % of Cohort A |
|---|---|
| 0 circuit days | 91.3% |
| 1 circuit day | 4.2% |
| 2 circuit days | 2.7% |
| 3 circuit days (KOTYARK-style) | 1.8% |
| F&O eligible | 3.0% |
| NIFTY 500 member | 11.2% |

**Circuit-locking is real but is NOT the dominant driver of the extreme tail** —
91.3% of Cohort A involves zero circuit days. Circuit involvement concentrates
almost entirely in the non-F&O population (F&O share falls from 3.3% among
zero-circuit events to 0.3% among fully-circuit-locked ones — exactly the
pattern expected, since F&O eligibility requires liquidity/market-cap floors
that make circuit hits rare).

**The clean, tradeable-looking subset (0 circuit days AND F&O-eligible) is small
(3,072 events, 3.0% of Cohort A) but its outcomes are just as strong as the
cohort as a whole** — median max_return_d3 15.74% (vs. 15.91% cohort-wide),
close_ret_d3 12.58% (vs. 12.34%). **This is the most economically important
result of the pass**: real, large, sustained short-horizon moves are not only a
microcap/illiquid phenomenon — they occur, at comparable magnitude, within the
genuinely liquid, F&O-tradeable universe too, in a meaningful (if not huge)
sample. Hand-verified example above (JIOFIN, 2024-02-01) is a member of exactly
this subset.

### Year-by-year (Rule #16), Cohort A's share of the eligible population

| Year | Cohort A n | Total n | % |
|---|---|---|---|
| 2021 (partial) | 1,176 | 16,955 | 6.94% |
| 2022 | 22,746 | 379,442 | 5.99% |
| 2023 | 19,504 | 400,802 | 4.87% |
| 2024 | 23,990 | 428,328 | 5.60% |
| 2025 | 18,461 | 465,974 | 3.96% |
| 2026 | 16,960 | 365,224 | 4.64% |

Roughly stable around the 5% construction rate every year, with 2025 notably
lower (3.96%) — consistent with the same "something changed after 2024" softer-
regime pattern several other lines in this project (QS-A's own year-by-year
among them) have independently flagged. Not investigated further here.

**Not yet done**: no predictive feature has been tested against cohort
membership (this is still outcome/stratification characterization, not a
"what precedes it" search — that is the next, separate step); no ML, score, or
threshold promoted; the delisted-companies universe gap (RQ-QS-07U) still applies
to any performance-adjacent reading of these numbers.

**Files**: `03_cohort_matched_controls.py`, `cohort_a_events.csv` (102,837 rows),
`cohort_b_events.csv` (102,837 rows). `event_matrix.csv` rebuilt with
`traded_value_sma20`, `circuit_days_in_window`, `burst_clean` columns added
(still gitignored, 528MB, reproducible).

## RQ-QS-07A-2B — Cohort B Tradeability Symmetry Audit (2026-09-29, critic-specified, small scope)

**Purpose, per critic**: "Does B also retain its extreme behavior inside the
zero-circuit, F&O-eligible subset? If yes, that strengthens the interpretation
that both tails contain genuine tradeable phenomena. If no, that's important
too." Deliberately small — no feature search, no filtering, no new thresholds.

**Rule #22**: hand-verified JSWENERGY 2022-08-01 (deterministic middle-of-list
pick from the clean subset, not cherry-picked) — max_return_d3=11.60%,
close_ret_d3=11.19%, day_of_max=3, all matched raw bars exactly.

| | Cohort A | Cohort B |
|---|---|---|
| Zero circuit days | 91.3% | 90.4% |
| F&O eligible | 3.0% | 4.7% |
| NIFTY 500 member | 11.2% | 14.4% |
| Clean subset (0 circuit + F&O) n | 3,072 | 4,752 |
| Clean subset % of cohort | 3.0% | 4.6% |

**The answer to the critic's own question is a genuine, honest "partially."**
Cohort A's clean subset retained essentially the FULL cohort's magnitude
(max_return_d3 15.74% vs 15.91% cohort-wide — a ~1% relative difference).
**Cohort B's clean subset shows real, if modest, magnitude compression**:
max_return_d3 13.26% vs 15.48% cohort-wide (~14% relative reduction),
close_ret_d3 11.08% vs 12.43% cohort-wide (~11% relative reduction). Still
large, real, substantial numbers — this is NOT a collapse — but a genuinely
different pattern from Cohort A's near-identical clean/full comparison. This is
exactly the kind of asymmetry the 73.4% A/B overlap could otherwise obscure: A
and B behave similarly at the surface level but are not fully interchangeable,
and B's extreme sustained moves lean somewhat more (not overwhelmingly) on the
noisier, less liquid part of the population than A's extreme MFE moves do.

**Year-by-year clean-subset coverage** stays in a similar 3.4%-8.4% range as
Cohort A's, with the same modest recent-year softening (2025: 4.3%, 2026: 3.4%,
vs 2021-2022's 8.4%/4.8%) — consistent with every other year-by-year check this
project has run recently.

**Disposition**: does not contradict anything found in 07A-2 — both cohorts
contain a real, meaningful, liquid/tradeable subset, not purely microcap noise,
but B's is somewhat softer than A's. No filtering applied to either cohort as a
result of this audit — both stay fully intact for RQ-QS-07A-3.

**Files**: `04_cohort_b_audit.py` (no new CSV output — reuses `cohort_b_events.
csv` and `event_matrix.csv` directly).

## RQ-QS-07A-3 — scope correction, logged before building (2026-09-29)

**Sequencing correction, critic + user jointly**: the original 07A-3 proposal
(restrict discovery search to the clean F&O subset) was REVISED after direct
user pushback — "why are we restricting to just F&O... given we have not yet
filtered out on what is actually causing these outcomes... we should only run
the F&O filtering after that." Critic agreed explicitly: conditioning the
DISCOVERY population on F&O eligibility before searching for a precursor risks
hiding the real mechanism if it exists more broadly (e.g., in non-F&O names)
and only occasionally shows up in F&O names too — F&O eligibility is itself a
market-quality label (NSE's own criteria: rolling market cap, traded value,
order-size, deliverable-value, position limits), not a neutral characteristic,
so conditioning on it upfront changes the population being studied.

**Corrected architecture, adopted**:
- **Phase 1 (next)**: precursor discovery on the FULL Cohort A (102,837 events)
  + its already-built matched controls (03_). F&O/NIFTY/circuit/liquidity
  recorded as stratification/annotation on every row, NOT used as a pre-filter
  on the search population and NOT used as a candidate predictor feature
  itself (they are market-quality labels, not the kind of "precursor state"
  being searched for).
- **Phase 2 (after a candidate precursor is found)**: check whether it
  survives/generalizes across those same strata (F&O vs non-F&O, liquidity
  buckets, circuit-involved vs not) — this is where the question "does this
  predict fast movers, or only fast movers because F&O names have
  characteristic liquidity" gets answered.
- **Phase 3 (only after that)**: an explicit actionability/product-fit gate
  (F&O eligibility) applied to whatever real precursor survives Phase 2.

Cohort A and Cohort B stay separate outcome labels throughout — not unioned,
no A-vs-B classifier, no A-only/B-only study yet (the 73.4% overlap is evidence
worth having, not a reason to collapse the two questions). Once a candidate
precursor is found, it will be checked against A, B, and A∩B/A\B/B\A as
evaluation, not built around one of them chosen in advance.

## RQ-QS-07A-3 — Broad Pre-Event State Search, first read (2026-09-29, critic+user corrected sequencing)

**Method, per the corrected architecture**: FULL Cohort A (102,837 events, no
F&O/liquidity restriction) + matched controls, reconstructed identically (same
seed=42, same method) from `event_matrix.csv` — not re-drawn. 19 pre-declared
features across 3 families (price structure/trend, volume, volatility), every
one reused directly from `signals.py`'s existing, already-validated production
indicator columns — none re-derived from scratch. F&O/NIFTY/circuit/liquidity
recorded as annotation on the working set, NOT used to filter the population and
NOT included as candidate features themselves. Information cutoff: every feature
is Close-of-day-T or earlier, matching the same day whose forward D1-D3 window
defines cohort membership.

**Spot-checked one row (A2ZINFRA 2025-06-03) against raw indicators** — exact
match. Full hand-verification (multiple examples) deferred: every feature here
is a direct lookup of an already-hand-verified, already-production-trusted
column (`ema34`, `rsi14`, etc.) via a plain date lookup, not a new formula — a
materially lower-risk operation than the custom return/path-shape computations
hand-checked earlier in this line, so one spot-check was judged sufficient for
this first read; a fuller check should still happen before anything here is
promoted past "candidate."

### Result — trend/momentum distance is the clearest signal; volume/volatility/candle-shape are weak

| Feature | Cohort A median | Control median | Gap |
|---|---|---|---|
| dist_ema8_pct | +0.48% | -0.17% | +0.65 |
| dist_ema21_pct | +0.88% | -0.44% | +1.32 |
| dist_ema34_pct | +1.11% | -0.61% | +1.72 |
| dist_sma50_pct | +1.59% | -0.80% | +2.40 |
| dist_sma150_pct | +1.66% | -1.13% | +2.79 |
| dist_sma200_pct | +2.63% | -0.69% | +3.32 |
| ret_5d | +0.70% | -0.27% | +0.98 |
| ret_10d | +1.01% | -0.55% | +1.56 |
| ret_20d | +1.68% | -0.71% | +2.38 |
| dist_low252_pct | +47.40% | +35.69% | +11.72 |
| rsi14 | 51.86 | 48.82 | +3.04 |
| dist_high252_pct | -27.44% | -26.18% | -1.25 |
| range5_width_over_atr | 2.20x | 2.08x | +0.12 |
| vol_zscore | -0.19 | -0.34 | +0.15 |
| vol_ratio_10d | 0.89x | 0.77x | +0.12 |
| atr_expansion | 1.06x | 0.99x | +0.07 |
| body_atr | 0.37 | 0.34 | +0.03 |
| ad_fraction | 0.56 | 0.53 | +0.03 |
| vol_declining5 | 0.7% | 0.7% | 0 |

**A real, directionally consistent pattern across the whole trend/momentum
family, and it GROWS with longer lookback windows** — distance-above-EMA gap
climbs from +0.65 (8-day) to +1.72 (34-day); trailing return gap climbs from
+0.98% (5-day) to +2.38% (20-day); distance above the 52-week low is the
single largest gap (+11.72pp). Stocks that go on to produce an extreme 3-day
move are, on average, ALREADY in a moderately stronger position beforehand —
not extreme (median RSI 51.86 is still roughly neutral, not overbought), but
consistently, measurably stronger across every trend-distance and return
horizon tested.

**By contrast, volume, volatility, and candle-shape features show weak-to-
negligible gaps** — vol_zscore, vol_ratio_10d, atr_expansion, body_atr, and
ad_fraction all sit close to their control values, none showing the kind of
consistent, growing separation the trend family does. `vol_declining5` shows
literally zero difference (0.7% both). This matches the pattern this project
has now found repeatedly, tonight and before: volume/volatility state rarely
carries discriminating information on its own, while trend/momentum measures
do show something real.

**One genuinely counter-intuitive result worth flagging, not smoothing over**:
`range5_width_over_atr` gap is small and in the WRONG direction for a
compression-precedes-breakout (VCP-style) story — Cohort A shows slightly
WIDER recent 5-day ranges than the control (2.20x ATR vs 2.08x), not tighter.
And `dist_high252_pct`'s gap is small and also slightly negative — Cohort A
sits marginally FURTHER below its own 52-week high than the control, not
closer to it. Extreme 3-day movers in this population are not obviously
"stocks quietly compressing near their highs" — they can be moderately-strong
stocks recovering from further down too. Neither of these small, backwards-
direction gaps should be over-read given their size, but they're reported
honestly rather than only reporting the results that fit a tidy story.

**Disposition — a real candidate signal, not yet a finding.** Per this
project's own standing discipline (Rule #19, Robustness Before Finding; Rule
#21, Signal ≠ Intervention), a directionally consistent, cross-feature pattern
is exactly the kind of result that must survive robustness checks — year-by-
year stability, stratification across F&O/non-F&O/circuit-involved (Phase 2 of
the corrected architecture), and an honest test of whether the gap is large
enough to build anything on, not just statistically present — before being
called a finding. **None of that has been done yet.** No threshold has been
chosen on any feature, no combination has been tested, no model has been
built. This is the first, purely descriptive read of the 19 pre-declared
features, exactly as scoped.

**Not yet done**: robustness/year-by-year check on the trend/momentum gap;
Phase 2 stratification (does the gap survive in F&O vs non-F&O, circuit-
involved vs not, across liquidity deciles); relative-strength/sector features
(deferred, same known infra limitation as RQ-QS-07U); any feature combination
or composite score; Cohort B run through the same feature search (not started
— Cohort A was the priority per the corrected sequencing, Cohort B's own
precursor search is a natural next step, not yet begun).

**Files**: `05_precursor_discovery.py`, `precursor_features.csv` (205,674
rows, committed — feature values only, no returns/outcomes duplicated in this
file, cross-referenced to `cohort_a_events.csv` by ticker+date).

## RQ-QS-07A-3, pivot-distance supplement (2026-09-29, direct user request)

**Motivation, checked before building anything**: user's own live observation
of a COAL INDIA R1 rejection. Verified against real cached bars first — 2026-09
-28 shows exactly this: High 429.30 poked above R1 (428.05), failed to clear R2
(430.00), closed 422.50, back below the pivot itself. A real, genuine instance.
2026-09-29 (the fictional "today") does NOT yet show the same clean pattern in
the EOD cache (High so far 426.00, still below R1 at 427.47) — flagged honestly
as a live-vs-cache timing gap, not asserted as matching.

**Added `monthly_pivots()` to `pivots.py`**, reusing the exact same shared
`_levels()` formula and prior-period-shift, no-lookahead convention as the
existing `weekly_pivots()` — own dedicated test added to `tests/test_pivots.py`
(monthly analogue of the existing weekly/daily tests, including the same
no-lookahead assertion). 3/3 pivot tests pass.

**Hourly, explicitly NOT run as a population-wide check**: real intraday data
only covers 2026-06-10 to 2026-09-23 (confirmed directly against
`intraday_cache/`, ~3.5 months) — only 11,582 of 205,674 (5.63%) of the
Cohort A + control population falls inside that window, too thin a slice for
a population-wide finding. Reported as a known, disclosed gap, not attempted.

**Same population/method as 05_** (full Cohort A, matched controls, identical
seed/reconstruction). Spot-checked one row (AARVI 2024-10-15) against raw
recomputation — exact match.

### Result — the same pattern found in moving averages, but weaker, and it's the PIVOT itself that carries it, not R1/R2

| Feature | Cohort A median | Control median | Gap |
|---|---|---|---|
| dist_daily_pp_pct | +0.13% | -0.27% | +0.40 |
| dist_daily_r1_pct | -1.93% | -2.03% | +0.09 |
| dist_daily_r2_pct | -4.05% | -3.87% | -0.18 |
| dist_weekly_pp_pct | +0.31% | -0.49% | +0.80 |
| dist_weekly_r1_pct | -4.36% | -4.44% | +0.07 |
| dist_weekly_r2_pct | -8.75% | -8.29% | -0.46 |
| dist_monthly_pp_pct | +1.25% | -0.79% | **+2.04** |
| dist_monthly_r1_pct | -8.53% | -9.06% | +0.53 |
| dist_monthly_r2_pct | -16.88% | -16.56% | -0.31 |

**Distance to the pivot (PP) itself echoes the exact same pattern as the
moving-average family in 05_ — real, and growing with timeframe (daily +0.40
-> weekly +0.80 -> monthly +2.04)**, essentially the same "moderately stronger
trend position" signal seen through a different, classical-TA lens rather than
a new, independent discovery.

**Direct, honest answer to the user's actual question: distance to R1 and R2
SPECIFICALLY does not show a clear, consistent precursor signal.** Every R1/R2
gap is small (0.07 to 0.53 in magnitude) and inconsistent in sign — R1 gaps are
positive (weakly favoring cohort A) while R2 gaps are negative (weakly favoring
the control) at every timeframe tested. This does not support "proximity to
R1/R2 resistance predicts an upcoming large move" as a population-wide
pattern. The real, single COAL INDIA instance checked above is a genuine
example of price behavior AT a resistance level — but that is a different
claim from "being near R1/R2 beforehand distinguishes future big movers from
similar stocks that don't move," which this data does not support.

**Disposition**: does not add a new candidate on top of 05_'s trend/momentum
finding — it's the same underlying signal (already-moderately-strong trend
position), visible via pivots too, not an independent confirmation from a
different mechanism. R1/R2 distance specifically is closed as a population-
wide precursor candidate; a real, single rejection event (like COAL INDIA) is
a live/reactive observation, not shown here to be predictable in advance.

**Files**: `06_pivot_distance_features.py`, `pivot_distance_features.csv`
(205,674 rows), `pivots.py` (added `monthly_pivots()`),
`tests/test_pivots.py` (added test).

## RQ-QS-07A-3R — Trend/Momentum Robustness Audit (2026-09-29, critic-specified) — the signal is real but concentrated in liquid names, and has weakened since 2024

**Question**: is the trend/momentum precursor from 05_ real, stable, and useful
across market-quality/regime strata, or an artifact of a specific slice? Frozen
population (full Cohort A + matched controls, no filter). 5 pre-declared
primary variables (not re-selected after seeing results): `dist_sma200_pct`,
`ret_20d`, `dist_low252_pct`, `dist_ema34_pct`, `rsi14`. Independently verified
the stratification arithmetic directly (liquidity decile 0 and 9's
`dist_sma200_pct` gaps recomputed from raw grouped medians) before trusting
anything — exact match.

### A. Liquidity decile — the single most important result of this whole line

**The signal is essentially ABSENT in the least liquid decile and grows
monotonically, dramatically, to the most liquid decile:**

| Decile (0=least liquid) | n cohort | dist_sma200_pct gap | ret_20d gap | dist_low252_pct gap | dist_ema34_pct gap | rsi14 gap |
|---|---|---|---|---|---|---|
| 0 | 17,428 | **-0.01** | +1.23 | +2.77 | +0.89 | +2.14 |
| 1 | 15,410 | +0.51 | +1.19 | +4.38 | +0.90 | +1.77 |
| 2 | 13,661 | +3.34 | +2.15 | +9.62 | +1.38 | +2.73 |
| 3 | 11,819 | +5.04 | +2.65 | +13.60 | +1.84 | +3.30 |
| 4 | 10,187 | +5.81 | +3.07 | +14.20 | +2.18 | +3.91 |
| 5 | 9,339 | +6.40 | +2.86 | +16.24 | +2.22 | +3.74 |
| 6 | 8,135 | +9.01 | +3.58 | +24.45 | +2.55 | +4.04 |
| 7 | 7,472 | +8.28 | +4.55 | +23.51 | +3.35 | +5.20 |
| 8 | 5,700 | +11.77 | +5.08 | +31.18 | +3.45 | +4.83 |
| 9 (most liquid) | 3,686 | **+15.80** | +6.68 | **+50.17** | +4.27 | +5.28 |

Every one of the 5 primary variables shows this SAME monotonic-or-near-monotonic
climb from decile 0 to decile 9, not just one. `dist_sma200_pct` moves from
essentially zero (-0.01, no signal at all) to +15.80 — a real, dramatic range,
not noise. This directly matches the Indian-market literature the critic cited
(momentum stronger among liquid stocks, reversal effects more pronounced among
illiquid ones) — now confirmed on this project's own data, cleanly, not merely
assumed from an external source.

**This materially changes how 05_'s original population-wide result should be
read.** Decile 0 (the least liquid) is the SINGLE LARGEST decile bucket in
Cohort A (17,428 of 102,837, ~17%) — recall from 07A-2 that Cohort A already
skews toward low liquidity. The population-wide gap reported in 05_ was real,
but it was disproportionately driven by the smaller, more liquid slice of the
cohort; for the bulk of low-liquidity events, this trend/momentum family
carries close to zero discriminating information.

### B. F&O eligibility — confirms and reinforces the liquidity finding

| | n cohort | dist_sma200_pct gap | ret_20d gap | dist_low252_pct gap | dist_ema34_pct gap | rsi14 gap |
|---|---|---|---|---|---|---|
| F&O eligible | 3,134 | +10.38 | +4.03 | +42.13 | +2.50 | +4.38 |
| Non-F&O | 99,703 | +3.81 | +2.55 | +11.74 | +1.84 | +3.26 |

F&O names (a subset of the highest liquidity deciles by construction) show a
gap roughly 2.7-3.6x larger than non-F&O names across every variable — the
trend/momentum signal is genuinely stronger, not just present, in exactly the
population that matters for an eventual options product.

### C. Circuit involvement — a real, different-flavored nuance, not a simple confound

| | n cohort | dist_sma200_pct gap | ret_20d gap | dist_low252_pct gap | dist_ema34_pct gap | rsi14 gap |
|---|---|---|---|---|---|---|
| Zero circuit | 93,908 | +3.17 | +2.30 | +10.82 | +1.60 | +2.88 |
| Circuit-involved | 8,929 | +1.66 | +5.19 | **-1.27** | **+5.84** | **+7.63** |

Circuit-involved names show a genuinely DIFFERENT pattern, not simply a weaker
or stronger version of the same one: LOWER long-term structural-position gaps
(`dist_low252_pct` actually flips negative) but MUCH HIGHER short-term
momentum gaps (`rsi14` +7.63, `dist_ema34_pct` +5.84). Consistent with a
plausible mechanism — an illiquid name waking up with a sudden short-term
momentum burst (high RSI, above its 34-day EMA) without necessarily being in a
strong long-term structural position (still closer to its 52-week low) —
flagged as a real, interesting difference worth knowing, not a reason to
exclude circuit-involved names from anything.

### D. NIFTY 500 membership — same direction as F&O/liquidity, lower priority per critic (imperfect v1 metadata)

| | n cohort | dist_sma200_pct gap | ret_20d gap | dist_low252_pct gap | dist_ema34_pct gap | rsi14 gap |
|---|---|---|---|---|---|---|
| NIFTY 500 member | 11,528 | +7.82 | +3.54 | +27.93 | +2.40 | +4.29 |
| Non-member | 91,309 | +3.56 | +2.44 | +10.94 | +1.79 | +3.18 |

### E. Year — the signal has weakened substantially since 2024, the same regime pattern found repeatedly tonight

| Year | n cohort | dist_sma200_pct gap | ret_20d gap | dist_low252_pct gap | dist_ema34_pct gap | rsi14 gap |
|---|---|---|---|---|---|---|
| 2021 (partial) | 1,176 | n/a* | +9.14 | n/a* | +6.85 | +9.10 |
| 2022 | 22,746 | +5.39 | +2.78 | +18.54 | +2.01 | +3.30 |
| 2023 | 19,504 | +5.44 | +3.04 | +14.56 | +2.19 | +3.85 |
| 2024 | 23,990 | +7.52 | +4.13 | +23.73 | +2.92 | +4.52 |
| 2025 | 18,461 | **-1.43** | +0.46 | +4.72 | +0.28 | +1.11 |
| 2026 | 16,960 | **-0.93** | +1.02 | +5.87 | +0.79 | +2.00 |

*2021's `dist_sma200_pct`/`dist_low252_pct` medians are NaN — genuinely
insufficient trailing history (200/252-day lookbacks) for most events that
early in the cached data, not a bug; the 3 shorter-lookback variables still
compute and show a real (if partial-year, thin-sample) gap.

**2022-2024 show a real, strong, consistent signal across every variable.
2025-2026 show the signal collapse to near-zero or slightly negative for the
longer-horizon variables** (`dist_sma200_pct` actually goes negative both
years) while the shorter-horizon variables (`ret_20d`, `rsi14`) weaken
substantially but don't fully vanish. **This is now the fourth or fifth
independent confirmation, within this single session, of the same "something
changed in the 2025-2026 regime" pattern** — QS-A's own year-by-year (RQ-QS-06
line), Cohort A's share-of-population year-by-year (07A-2), and Cohort B's
clean-subset coverage (07A-2B) all showed the same softening. Worth treating
as a real, standing, cross-cutting project observation, not a one-off.

### Feature-feature correlation diagnostic — confirms the critic's expectation: one latent dimension, not 5 independent signals

| | dist_sma200 | ret_20d | dist_low252 | dist_ema34 | rsi14 |
|---|---|---|---|---|---|
| dist_sma200 | 1.00 | 0.59 | 0.85 | 0.69 | 0.64 |
| ret_20d | 0.59 | 1.00 | 0.49 | 0.91 | 0.89 |
| dist_low252 | 0.85 | 0.49 | 1.00 | 0.57 | 0.54 |
| dist_ema34 | 0.69 | 0.91 | 0.57 | 1.00 | **0.98** |
| rsi14 | 0.64 | 0.89 | 0.54 | 0.98 | 1.00 |

(Spearman, within Cohort A — the Control population shows the same structure,
slightly weaker correlations throughout.) `dist_ema34_pct` and `rsi14`
correlate at 0.98 — essentially the same measurement. Two sub-groups emerge: a
longer-term "structural position" pair (`dist_sma200`/`dist_low252`, r=0.85)
and a shorter-term "momentum" trio (`ret_20d`/`dist_ema34`/`rsi14`, r=0.89-0.98),
cross-correlated at a more moderate 0.47-0.69. **Confirms the critic's
expectation exactly: these 5 variables are not 5 independent pieces of
evidence — they are one latent trend-strength dimension expressed through
slightly different lenses**, with a real but secondary split between its
longer-term/structural and shorter-term/momentum expressions.

**Honest overall disposition**: the trend/momentum precursor from 05_ is real
— it survives across every stratum tested, always in the same direction — but
it is NOT uniform. It is concentrated in liquid, F&O-eligible, larger-cap names
(exactly where it would matter most for an options product) and has weakened
substantially in the most recent 1.5-2 years. It represents one underlying
"already moderately trending" dimension, not several independent signals. This
is a materially more precise, more useful characterization than 05_'s
population-wide read alone — not a reversal of it.

**Per critic's explicit instruction: no new classical-TA feature family
explored in this pass.** The next open decision is whether relative-strength/
sector context (the genuinely different, not-yet-tried family, still blocked
on the same un-vectorized infrastructure limitation as RQ-QS-07U) is worth
building now that trend/momentum has survived this robustness pass, or whether
the liquidity/regime concentration found here changes that calculus.

**Files**: `07_trend_robustness_audit.py`, `trend_robustness_audit.csv`
(217,136 rows — includes 11,509 rows where the merge to `precursor_features.csv`
didn't find a match, e.g. very recently listed tickers with insufficient
history for a feature; excluded from median calculations via the existing
`.dropna()`-safe `.median()` handling, not silently zero-filled).

## RQ-QS-07A-4 — Relative-Strength Proxy Audit (2026-09-29, critic-specified, cheap interim test)

**Question**: does stock-minus-market momentum add information beyond the
absolute trend-strength family already found, or is a stock's strength
predominantly just broad-market participation? Deliberately narrow scope per
critic: 5D/20D stock return, 5D/20D NIFTY (market) return, stock-minus-market
at both horizons. **Market-relative only, NOT sector-relative** — this
project's only sector mapping (`_sectors.csv`) is a single current snapshot
applied across 5 years, the same disclosed point-in-time limitation as
`nifty500_universe.csv` (RQ-QS-07U) — not "already safely available," so
correctly out of scope for this cheap pass, per critic's own explicit
guardrail against calling stock-minus-Nifty "relative strength" and pretending
it answers the sector question.

**A real join bug caught by Rule #22 before trusting anything**: the first
version merged pre-computed `ret_5d`/`ret_20d` back in from
`precursor_features.csv` on (ticker, date, group) — an unexpected row-count
jump (control n: 102,837 -> 114,299) exposed that this key is NOT unique: the
same control stock-day can legitimately be drawn as a match for multiple
different cohort A events (random sampling with replacement from a same-date/
same-decile pool), and BOTH sides of the merge carried that same duplicate
structure — a classic many-to-many join multiplying rows, the same class of
bug RQ-QS-06C hit earlier tonight for a different reason. Fixed by
recomputing the stock returns directly, per-ticker, instead of merging on a
key that doesn't naturally exist as unique — verified control n returned to
exactly 102,837 after the fix, hand-verified one row (AAREYDRUGS 2026-02-17:
ret_5d, market_ret_5d, stock_minus_market_5d all recomputed by hand from raw
bars) — exact match.

### Result

| | Cohort A median | Control median | Gap |
|---|---|---|---|
| Stock ret_5d | +0.70% | -0.27% | +0.98 |
| Market ret_5d | +0.27% | +0.27% | **+0.00** |
| Stock-minus-market_5d | +0.33% | -0.54% | +0.87 |
| Stock ret_20d | +1.68% | -0.71% | +2.38 |
| Market ret_20d | +0.58% | +0.58% | **+0.00** |
| Stock-minus-market_20d | +0.57% | -1.40% | +1.97 |

**Market return gap is exactly zero, both horizons** — a clean, free sanity
check confirming the same-date matching is working correctly (cohort A and
its controls, by construction, share the same calendar date, so the market's
own return on that date is necessarily near-identical for both groups).

**The key answer: stock-minus-market barely shrinks the gap versus absolute
stock momentum** — 5D gap goes from +0.98 (absolute) to +0.87 (relative, ~89%
retained); 20D gap goes from +2.38 to +1.97 (~83% retained). **The trend/
momentum signal is predominantly IDIOSYNCRATIC to the stock, not primarily a
reflection of broad market-wide movement.** Removing the contemporaneous
market return barely changes the picture, because both cohort and control
events experience the same market days by construction — most of the earlier
signal was never "the whole market moved" in the first place.

**The liquidity gradient from 07A-3R survives on the relative measure too,
confirming it isn't a market-participation artifact**: stock_minus_market_20d
gap climbs from +1.08 (low liquidity tercile) to +4.69 (high liquidity
tercile) — same shape as the absolute-momentum liquidity gradient.

**What this does NOT test**: sector-relative momentum (is the stock strong
relative to ITS SECTOR specifically, vs. the whole market) — genuinely
different question, still blocked on the same historical-sector-mapping
limitation, not attempted here per the deliberately narrow scope.

**Disposition, per critic's own decision framework** ("if relative adds
information beyond absolute -> build the full infrastructure; if not, we
haven't wasted a major engineering cycle"): market-relative momentum does NOT
add much SEPARATION beyond absolute momentum already found — not because the
signal is weak, but because absolute momentum already captures nearly all of
it, since market-wide movement contributes little to the gap either way. This
is a meaningful, reassuring result about the signal's genuineness (it's real
stock-specific strength, not market beta), but it's a different question from
whether SECTOR-relative momentum would add something absolute momentum
misses — that remains open and untested. Critic's read needed on whether this
result justifies building the full sector infrastructure or not.

**Files**: `08_relative_strength_proxy.py`, `relative_strength_proxy.csv`
(205,674 rows).

## RQ-QS-07R — Market Regime Diagnostic, complete (2026-09-29, critic-specified)

**Objective (critic's exact framing)**: does the 2025-26 weakening found across
07A-3R/07A-4 come from the trend/momentum PREDICTOR breaking, or from the
underlying FAST-MOVER PHENOMENON ITSELF becoming rarer/weaker? Purely
descriptive — no new predictor, no strategy change, no Cohort-A/control
machinery. Uses the NEUTRAL broad universe: a fresh daily cross-sectional panel
(every eligible stock-day, `nse_equity_universe.csv`, 2,327 tickers) plus the
already-built neutral `event_matrix.csv` (RQ-QS-07A-1). Critic's explicit
guardrail honored: shown continuously by quarter, not hard-coded as a
2022-24-vs-2025-26 split, so an abrupt/gradual/segment-specific transition
would each look different.

**Panel**: 2,063,163 stock-days, 2021Q4-2026Q3 (corp-action days dropped, 60d
min history).

**Hand-verification (Rule #22) — one real bug caught and disclosed, not
silently absorbed**: `pct_above_sma200` reads as 0.00% for 2021Q4/2022Q1 and
0.84% for 2022Q2 — not a real market condition. Traced to source: `sma200`
needs 200 trading days of history and is genuine `NaN` for any ticker's first
~10 months in the cache; confirmed directly on RELIANCE (`sma200` all-`NaN`
2021-11-01 to 2021-11-10). `Close > NaN` silently evaluates `False` in pandas
rather than being excluded, so early-history rows are miscounted as "below
SMA200" when the truth is "unknown." **This is a burn-in artifact confined to
2021Q4-2022Q2 — the table below already excludes that window from
interpretation.** It does not touch `pct_above_ema34` (34-day requirement,
already covered by the panel's own history cutoff) or `pct_ret20d_positive`,
and critically does NOT touch the 2025-26 window this RQ actually turns on
(every ticker alive that long already has 200+ days of history). Aggregate
sanity check (bullet b): summed quarterly `n` matches the panel total exactly.

### A+B. Cross-sectional opportunity & trend breadth, by quarter (selected columns; full table in `regime_breadth_by_quarter.csv`)

| Quarter | n | median_ret | dispersion | frac_positive | %>ema34 | %ret20d>0 |
|---|---|---|---|---|---|---|
| 2023Q3 | 103,631 | 0.00 | 2.69 | 48.51 | 69.12 | 64.81 |
| 2023Q4 | 100,103 | 0.00 | 2.75 | 49.36 | 62.83 | 58.87 |
| 2024Q1 | 101,372 | -0.18 | 3.15 | 45.78 | 54.27 | 50.33 |
| 2024Q2 | 103,901 | 0.00 | 2.99 | 49.86 | 59.50 | 59.55 |
| 2024Q3 | 112,381 | -0.10 | 2.81 | 47.32 | 60.99 | 58.95 |
| 2024Q4 | 110,722 | -0.18 | 2.80 | 46.02 | 39.36 | 42.91 |
| 2025Q1 | 111,432 | **-0.45** | 3.22 | 42.70 | **18.63** | **20.57** |
| 2025Q2 | 114,034 | 0.08 | 2.85 | 51.62 | 61.67 | 65.93 |
| 2025Q3 | 121,001 | -0.22 | **2.35** | 43.64 | 45.30 | 45.19 |
| 2025Q4 | 119,555 | -0.19 | **2.34** | 44.31 | 31.61 | 33.04 |
| 2026Q1 | 117,283 | **-0.46** | 2.99 | 41.21 | **24.56** | 29.77 |
| 2026Q2 | 121,662 | 0.09 | 2.94 | 51.72 | 62.26 | 60.88 |
| 2026Q3 | 132,561 | -0.19 | 2.50 | 44.66 | 44.91 | 45.35 |

**Finding 1 — NOT a clean level shift, a regime CHANGE IN CHARACTER**: 2023-24
breadth sat in a fairly stable 54-71% band with only mild quarter-to-quarter
swings. From 2025Q1 onward, breadth started **oscillating violently**:
18.63% -> 61.67% -> 45.30% -> 31.61% -> 24.56% -> 62.26% -> 44.91%, swinging
30-40 points quarter to quarter, something 2023-24 never did. This is directly
relevant to the trend/momentum precursor found in 05_/07A-3R: that precursor
needs SUSTAINED trend persistence, and a market that whipsaws between
sub-25%-breadth and 60%+-breadth quarters is structurally hostile to a
persistence-based signal even when it's "on" a third of the time.

**Finding 2 — cross-sectional dispersion (opportunity) genuinely compressed
in H2 2025**: dispersion sat at 2.34-2.35 in 2025Q3/Q4, below anything seen in
2023-2024 (2.6-3.2 range) — a real, if modest, reduction in the spread of
available outcomes, not just an artifact of the breadth swings above.

### C. Trend breadth by liquidity tercile x year (`regime_breadth_by_liq_tercile_year.csv`)

| Tercile | 2023 | 2024 | 2025 | 2026 | 2023->2025 drop |
|---|---|---|---|---|---|
| Low liquidity | 48.44 | 46.34 | 30.40 | 33.73 | -18.0pp |
| Mid liquidity | 58.42 | 52.13 | 37.43 | 43.90 | -21.0pp |
| High liquidity | 67.26 | 62.31 | 51.09 | 54.97 | -16.2pp |

**Finding 3 — broad-based, NOT segment-specific**: all three liquidity
terciles dropped by a similar ~16-21 percentage points from 2023 to 2025, with
a similar partial rebound into 2026. This directly answers the critic's
segment-specific-change question: the breadth decline is a market-wide
phenomenon, not something concentrated in illiquid/small-cap names while
liquid names stayed fine (or vice versa). It does NOT explain why 07A-3R found
the trend precursor concentrated in liquid names in the first place — that's
a separate, already-answered question (liquid names show a stronger
gap-to-control, not that only liquid names have breadth at all).

### E. Fast-mover base rate, by quarter (`regime_fastmover_baserate_by_quarter.csv`)

| Quarter | mfe_p95 | close_p95 | %crossing fixed MFE-P95 | %crossing fixed close-P95 |
|---|---|---|---|---|
| 2023Q3 | 13.06 | 9.13 | 5.11 | 5.25 |
| 2023Q4 | 13.53 | 9.65 | 5.46 | 5.78 |
| 2024Q1 | 14.54 | 10.57 | 6.59 | 6.94 |
| 2024Q4 | 12.17 | 8.56 | 4.25 | 4.61 |
| 2025Q1 | 12.82 | 8.98 | 4.86 | 5.11 |
| 2025Q2 | 12.99 | 9.45 | 5.05 | 5.73 |
| 2025Q3 | **10.55** | **6.81** | **3.22** | **3.03** |
| 2025Q4 | **9.97** | **6.10** | **2.83** | **2.42** |
| 2026Q1 | 12.35 | 7.79 | 4.46 | 3.91 |
| 2026Q2 | 13.85 | 9.77 | **5.90** | **6.15** |
| 2026Q3 | 11.23 | 7.07 | 3.60 | 3.21 |

**Finding 4 — the underlying fast-mover phenomenon itself really did get
rarer, but only for a two-quarter window (2025Q3-2025Q4), not permanently**:
both the raw P95 magnitude and the share crossing the fixed historical P95
threshold bottom out sharply in 2025Q3/Q4 (close to half the 2024Q1 rate), then
**recover to 2023-24 levels by 2026Q2** (5.90%/6.15%, actually the best
quarter in the whole 2025-26 window) before dipping again in 2026Q3. This
directly confirms the 07A-3R/07A-4 weakening was NOT purely a predictor
artifact — the phenomenon it's trying to predict was genuinely scarcer for a
real stretch of 2025 — but it also shows that stretch was NOT a permanent
structural break; the base rate is recovering unevenly, in the same
oscillating pattern as trend breadth (Finding 1).

### Disposition

**Answer to the critic's exact question — "reduced breadth, reduced
dispersion, liquidity/size composition change, weaker fast-mover base rate, or
some combination?"**: reduced trend breadth (Finding 1) and a genuinely
weaker fast-mover base rate (Finding 4), concentrated specifically in
2025Q3-2025Q4, **coincide with and characterize** the weakening — NOT a
liquidity/size composition shift (Finding 3 rules this out — the decline is
broad-based across all terciles), and NOT a clean permanent 2025-26 regime
break (both breadth and base rate are already recovering unevenly by 2026Q2).
The dominant character of the 2025-26 period isn't "worse," it's **choppier**
— wider swings between strong-breadth and weak-breadth quarters than 2023-24
ever showed.

**CORRECTION (2026-09-29, critic's explicit catch, adopted)**: the original
version of this disposition said breadth choppiness and the base-rate dip
"explain most of the weakening." That overstates what was shown. Breadth and
dispersion are themselves correlated market-state measurements — we have
NOT decomposed causality, only shown these measures coincide with and
characterize the same weakening window. **07R closes as: regime
characterization established; causal attribution remains open.** This is the
appropriately conservative conclusion, and this correction is itself the
finding to carry forward, not a footnote.

**Sector dispersion (D)**: explicitly not attempted, per critic's instruction
— no historical sector mapping exists yet; not faked with a current-snapshot
proxy. Critic's status, adopted: **sector-relative strength is DEFERRED, not
rejected** — real sector rotation existed in 2025 per NSE's own published
review (Financials gaining Nifty 50 weight while IT/Consumer Staples lost
it), so sector remains a legitimate untested hypothesis, just not the
highest-value next build given three higher-value open threads already in
hand (trend-strength relationship exists, strongest in liquid/F&O names, and
the fast-mover environment itself got choppier/temporarily weaker).

**Next RQ, critic-specified**: not sector concentration — RQ-QS-07A-5,
Trend-State -> Fast-Mover Anatomy (see its own section below).

**Files**: `09_market_regime_diagnostic.py`, `regime_daily_panel.csv`
(gitignored, 2,063,163 rows), `regime_daily_panel_sample_200k.csv` (seed=42),
`regime_breadth_by_quarter.csv`, `regime_breadth_by_liq_tercile_year.csv`,
`regime_fastmover_baserate_by_quarter.csv`.

## RQ-QS-07A-5 — Trend-State → Fast-Mover Anatomy, complete (2026-09-29, critic-specified)

**Objective (critic's exact framing)**: "What does the trend-strength state
actually represent immediately before the fast move?" — the SHAPE of the
relationship between prior trend strength and subsequent fast-mover outcome.
NOT another predictor search, NOT a threshold optimization.

**Method**: full neutral `event_matrix.csv` population (2,056,725 stock-days,
not the matched-control subsample used in 05_/07_/08_ — a dose-response/shape
question needs the full distribution). Computed the 5 primary trend/momentum
variables from 07A-3R (`dist_sma200_pct`, `ret_20d`, `dist_low252_pct`,
`dist_ema34_pct`, `rsi14`) for every eligible row using the exact formulas
from `05_precursor_discovery.py`. Built a composite trend-strength score (my
design choice, not critic-specified, flagged for critic review): mean of each
variable's percentile rank (0-100) across the full population — all 5 share
the same "higher = stronger trend" sign convention, verified, no flips
needed. Composite used ONLY as the single binning axis, never tested
alongside its own components (would violate Rule #7). Pre-declared bins:
deciles of the composite (chosen before looking at any outcome — deciles are
of the predictor itself, not the result). 1,668,305 of 2,056,725 rows had all
5 features populated (the rest lack sufficient history, mostly early-cache
tickers).

**Hand-verification (Rule #22)**: the headline result below was surprising
enough to require checking before trusting. (a) Pulled 5 real decile-0
Cohort A events (seed=42) — AIRAN, LAGNAM, ZEEMEDIA, MOKSH, VIRINCHI, 2025-26
dates — every one shows a coherent, real pattern: 20-40% below SMA200, near
or slightly above the 52-week low, RSI 15-42, negative 20D return, followed
by genuine 15-43% 3-day max moves. Not noise. (b) Aggregate math check:
regime-split n's sum to the total (786,730+782,154+99,421=1,668,305) and
pathway-split n's sum to the total (1,631,608+36,697=1,668,305) exactly —
both stratifications are mathematically clean partitions, no leakage/overlap
bug.

### The headline result: the relationship is NOT monotonic — it's an asymmetric U-shape

| Decile (0=weakest trend, 9=strongest) | %Cohort A | %Cohort B | p90 MFE |
|---|---|---|---|
| 0 | 6.61 | 6.75 | 10.66 |
| 1 | 3.67 | 3.74 | 8.52 |
| 2 (minimum) | 3.35 | 3.49 | 8.17 |
| 3 | 3.41 | 3.50 | 8.12 |
| 4 | 3.50 | 3.59 | 8.21 |
| 5 | 3.74 | 3.76 | 8.37 |
| 6 | 3.92 | 4.03 | 8.60 |
| 7 | 4.66 | 4.63 | 9.14 |
| 8 | 5.43 | 5.49 | 9.84 |
| 9 (maximum) | 8.47 | 8.22 | 11.82 |

**Two distinct archetypes, not one**: the dominant, larger tail effect is at
decile 9 (strongest trend state — the trend-CONTINUATION archetype 07A-3/
07A-3R already found), rising steadily and only really separating from
deciles 7-9 (shape-check table: decile-over-decile delta is near-zero from
1→6, then +0.74/+0.77/+3.03 for 7/8/9 — concentrated in the top tail, not
gradual across the whole range). But decile 0 (the WEAKEST trend state —
deeply oversold, near 52-week lows, low RSI) shows a real, separate local
elevation: roughly DOUBLE the flat ~3.3-3.9% baseline sitting in deciles
1-6. This is a second, distinct **oversold-reversal/capitulation** fast-mover
archetype, invisible in every prior 07A study because none of them binned the
full population by trend state before — 05_/07_/08_ all compared Cohort A
against a matched, same-liquidity control without asking where the control's
own trend state sits.

**Confirmed NOT a circuit-lock or liquidity-composition artifact**: the U-shape
survives in the "structural" pathway alone (circuit_days_in_window==0,
1,631,608 of 1,668,305 rows) — decile 0 = 6.36% vs decile 2's minimum of
3.24%, still ~2x — so it isn't just circuit-driven violent reversals. It also
survives within every liquidity tercile individually: decile-0 vs decile-2
Cohort A rate is 9.25%-vs-4.93% (low liquidity), 5.54%-vs-2.89% (mid),
3.62%-vs-1.65% (high) — consistently ~1.9-2.2x at every liquidity level, so
it isn't explained by decile 0 simply containing more illiquid names. (The
circuit/wake-up pathway, only 36,697 rows / 2.2% of the population, does show
much higher absolute rates everywhere — 8-25% — consistent with circuit
events being inherently volatile, but that's a separate, already-expected
effect layered on top, not the source of the structural-pathway U-shape.)

### Regime dependence — critic's ask #3, answered with a real asymmetry

| Decile | Stable (2023-24) %Cohort A | Choppy (2025-26) %Cohort A | Change |
|---|---|---|---|
| 0 (oversold) | 6.65 | 6.67 | **~unchanged** |
| 9 (trend continuation) | 8.97 | 6.70 | **-25% relative** |

**The trend-CONTINUATION tail (decile 9) is the one that weakened in the
choppier 2025-26 regime** — consistent with everything 07A-3R/07R already
found. **The oversold-reversal tail (decile 0) is regime-INVARIANT** — its
rate is essentially identical in both windows. This is a materially different
answer than "the whole trend-strength dimension got weaker": only HALF of
the U-shape is regime-sensitive. The oversold-reversal archetype looks like a
more structurally robust phenomenon, not an artifact of 2022-24 having been a
friendlier environment — though it has NOT been robustness-tested the way
07A-3R tested the continuation side (Rule #19 applies: this is a candidate
observation from one pass, not yet a promoted finding).

### Cohort A vs Cohort B — critic's ask #4

No meaningful divergence at either tail: decile 0's Cohort-A/Cohort-B overlap
fraction is 4.86/6.61=73.5%, decile 9's is 6.43/8.47=75.9% — both essentially
match the population-wide 73.4% overlap (07A-2B). Neither archetype
preferentially produces "big spike only" (Cohort A-only) or "sustained close
only" (Cohort B-only) outcomes — the MFE/sustained-close split is not
differentiated by which tail of the trend-state distribution produced the
event.

### Disposition

**Real, hand-verified, non-obvious structural finding, per Rule #19 status: a
candidate observation, not yet a promoted finding** — the trend-strength
dimension's relationship to fast-mover outcomes is a two-tailed, not
one-tailed, phenomenon, and the two tails behave differently across regimes.
This reframes the whole 07A-3/07A-3R "trend precursor" result: it was only
ever describing HALF of the real relationship (the continuation half), and
that's specifically the half that weakened in 2025-26 — while an entirely
separate, apparently regime-stable oversold-reversal signal has been present
in the data the whole time, unexamined until this pass.

**Not promotable as a filter/gate yet** (Rule #21, Signal ≠ Intervention):
this is shape characterization only, no threshold chosen, no robustness sweep
run on the oversold-reversal side specifically, and average decile-9/decile-0
Cohort A rates (6.6-8.5%) are population base rates, not gap-to-control
comparisons — don't compare these percentages directly against 05_/07_'s
median-gap numbers, they're measuring a different thing (absolute rate in an
unmatched population vs. gap between matched cohort/control pairs).

**Files**: `10_trend_state_anatomy.py`, `trend_state_anatomy.csv`
(1,668,305 rows), `trend_state_anatomy_overall_by_decile.csv`.

## RQ-QS-07A-5R — Weak-State Fast-Mover Robustness & Timing, complete (2026-09-30, critic-specified)

**Objective (critic's exact framing)**: test whether 07A-5's D0 (weakest
trend-state decile) elevation is robust, and characterize its timing — NOT
"does oversold reversal work," NOT a filter/threshold build, NOT a QS-A
change. Explicit prohibition list honored in full: no oversold filter, no
RSI/SMA200-distance threshold test, no capitulation score, no QS-A gate
change, no trading-performance test, no reversal-indicator collection, no
mean-reversion strategy, no abandoning the continuation branch, no sector-RS
build.

**Frozen, per critic's instruction**: D0 = bottom decile (decile==0) of the
already-built composite trend-strength score from `10_trend_state_anatomy.py`
— not redefined. Reference = D2, the empirical trough (07A-5's own
shape-check found decile 2 is the minimum, not decile 1 or the median).
Cohort A/B reported separately throughout. Population: `trend_state_anatomy.csv`
(same 1,668,305-row full neutral population as 07A-5, no matched-control
rebuild). D0 n=166,831, D2 n=166,831.

**Hand-verification (Rule #22)**: (a) aggregate math — every one of the 4
stratification dimensions (year, liquidity tercile, F&O, circuit) sums
EXACTLY to the D0 total of 166,831, confirming clean, mutually-exclusive
partitions, no leakage/double-count. (b) Pulled 4 real F&O D0 Cohort A
events (seed=42): SUZLON (2022-10-13), AMBER (2026-01-29), ADANIENSOL
(2023-03-03, notably 72.6% below its 200-day average — the Adani Group
crisis period), PGEL (2026-06-11) — all genuine large/mid-cap names, deeply
oversold, followed by real 15-18% 3-day moves. Not noise, not microcap-only.

### Part 1 — Robustness matrix: D0/D2 ratio, every stratum tested

| Stratum | D0 %CohortA | D2 %CohortA | Ratio | D0 n |
|---|---|---|---|---|
| 2022 | 5.30 | 3.32 | 1.60x | 6,637 |
| 2023 | 7.02 | 3.26 | 2.15x | 22,049 |
| 2024 | 6.21 | 4.06 | 1.53x | 18,495 |
| 2025 | 6.28 | 3.00 | 2.09x | 67,398 |
| 2026 (YTD) | 7.16 | 3.29 | 2.18x | 52,252 |
| Liquidity: low | 9.25 | 4.93 | 1.87x | 64,313 |
| Liquidity: mid | 5.54 | 2.89 | 1.91x | 71,209 |
| Liquidity: high | 3.62 | 1.65 | **2.19x** | 31,309 |
| F&O: True | 2.01 | 0.85 | **2.37x** | 11,326 |
| F&O: False | 6.94 | 3.64 | 1.91x | 155,505 |
| Circuit: False | 6.36 | 3.24 | 1.96x | 164,156 |
| Circuit: True | 22.02 | 11.53 | 1.91x | 2,675 |

**The ratio never collapses, anywhere**: it stays in a tight 1.53x-2.37x band
across every single stratum tested — every year (including the weakest,
2024, still 1.53x), every liquidity tercile, both F&O and non-F&O, both
circuit and non-circuit. If anything the ratio is slightly STRONGER in
high-liquidity (2.19x) and in F&O names (2.37x) than in the broad
population's overall 1.97x — the elevation is not a low-liquidity/microcap
artifact. **F&O presence is real but the absolute rate is much smaller than
the broad-universe headline number**: 2.01% in F&O vs 6.61% overall (228
real F&O Cohort A events at D0, hand-verified above) — large/mid-cap names
simply produce fewer 15%+ three-day moves in general, but when they do, D0's
relative elevation over D2 is fully intact.

### Part 2 — Timing anatomy: D0 and D2's fast movers share the SAME temporal shape

| Decile | Cohort | n | Median D1 MFE | D2 MFE | D3 MFE | D1 close | D2 close | D3 close | D1's share of D3 MFE |
|---|---|---|---|---|---|---|---|---|---|
| D0 | Cohort A | 11,023 | 5.74 | 13.27 | 16.21 | 4.75 | 9.54 | 12.28 | 35.4% |
| D0 | Cohort B | 11,266 | 5.00 | 10.24 | 15.34 | 4.39 | 9.01 | 12.26 | 32.6% |
| D2 | Cohort A | 5,583 | 4.99 | 13.17 | 16.02 | 4.21 | 9.22 | 11.78 | 31.2% |
| D2 | Cohort B | 5,819 | 4.91 | 10.10 | 14.92 | 3.59 | 8.47 | 11.80 | 32.9% |

**Answers the critic's exact question — D0 is neither "already moving hard
on D1" nor "a delayed 3-day reversal," and critically it looks like D2's
already-established fast-mover shape, not a different phenotype**: median D1
close for D0 Cohort A is already +4.75% (real, tradeable directional move by
end of day 1, not flat/negative), roughly a third of the eventual 3-day MFE
is already visible by D1 (35.4%), and the D1→D2→D3 incremental shape
(+7.53pp, then +2.94pp) is nearly identical to D2's own shape (+8.17pp,
+2.85pp). **D0 and D2 fast movers don't differ in HOW the move unfolds over
time — only in how OFTEN it happens.** This is the single most
product-relevant result: it argues against D0 being some slow-building
reversal pattern incompatible with a short-horizon product.

### Part 3 — Definition-artifact check: a real, modest nominal-price tilt

D0 Cohort A close price: P10=6.35, median=72.84, P90=585.75, 25.91% under
₹20, 42.36% under ₹50 (n=11,023). D2 Cohort A: P10=9.02, median=106.30,
P90=811.43, 19.68% under ₹20, 35.34% under ₹50 (n=5,583). **D0 does skew
toward lower nominal prices than D2** — a real, disclosed caveat (thinner
tick-size/order-book effects can inflate % moves at low absolute prices) —
but the tilt is modest (median ₹72.84 is not itself penny-stock territory)
and doesn't come close to explaining a 2x rate elevation on its own.
Corp-action-cleanliness and the 60-day min-history floor are already
enforced upstream in `01_event_matrix.py`; every row here already required
252 days of price history for a populated `dist_low252_pct`, which rules out
early-listing/cache-burn-in artifacts by construction — not re-tested, noted.

### Disposition — passes the critic's own promotion checklist

Per the critic's explicit criteria (A-F, quoted in the script docstring): (A)
temporal validity — yes, D0 movers begin moving early enough to plausibly
fit a short-horizon objective; (B) cross-year persistence — yes, all 5
years/YTD, no collapse; (C) cross-liquidity persistence — yes, not
exclusively microcaps, if anything strongest in high liquidity; (D) F&O
presence — yes, established (228 real hand-verified-adjacent events), though
at materially lower absolute incidence than the broad universe; (E)
circuit-clean persistence — yes, already confirmed in 07A-5, reconfirmed
here; (F) no obvious definition artifact — mostly clean, one real but modest
nominal-price caveat disclosed above.

**This clears the critic's own bar: "If D0 survives across years, liquidity
and at least meaningfully inside F&O -> it earns a dedicated mechanism RQ."**
It also clears the parallel branch: "If it survives and its D1->D3 timing is
compatible with QS-A -> then we have a product decision to make separately:
whether QS-A should eventually contain two explicitly distinct entry
archetypes." Both conditions are met simultaneously. Per critic's own
explicit prohibition list, this does NOT mean building anything yet — no
RSI/distance threshold, no filter, no strategy test. Two follow-on questions
are now both open, per critic's own framing, and the choice between them (or
sequencing) is the critic's call: (1) a dedicated mechanism RQ — "what
actually distinguishes D0 fast movers from ordinary D0 stocks" (catalyst/
event, volume shock, volatility expansion, reversal anatomy); (2) a product
decision — whether QS-A should eventually recognize two distinct entry
archetypes rather than one gate explaining both.

**Files**: `11_weak_state_robustness_timing.py`, `weak_state_robustness_matrix.csv`,
`weak_state_timing_anatomy.csv`.

## RQ-QS-07A-6 — Weak-State Fast-Mover Mechanism, complete (2026-09-30, critic-specified)

**Objective (critic's exact framing)**: "Within the already-frozen weak-state
D0 population, what decision-time price/volume/volatility transition
distinguishes the 3-day fast movers from ordinary D0 days?" A WITHIN-D0
discrimination study — D0 Cohort A/B (fast movers) vs. D0 stock-days that did
NOT become Cohort A/B ("D0 ordinary") — not D0 vs. D2 anymore (07A-5R already
closed that: PASS, robust). No catalyst/news infrastructure built (critic's
explicit deferral — rabbit-hole risk, only pursued if price/volume/
volatility anatomy fails).

**Frozen**: D0 = bottom decile of the already-built composite from
`10_trend_state_anatomy.py`, not redefined. Same 166,831-row D0 population,
same Cohort A/B definitions. Cohort A and B tested separately throughout
(critic's prose emphasized A; B added here per this project's standing
A/B-separate discipline).

**Methodological requirement honored (composite-decomposition rule)**: the 5
state-definition variables (`dist_sma200_pct`, `ret_20d`, `dist_low252_pct`,
`dist_ema34_pct`, `rsi14`) are reported as descriptive context ONLY — D0 is a
bottom-decile bucket of exactly these 5, so any within-D0 gap in them is
expected/partially circular, not a new mechanism claim. All 12 mechanism
candidates below are verified distinct from the composite's own formulas and
lookback windows (e.g. `ret_1d`/`ret_3d` use 1/3-day windows vs. the
composite's 20-day `ret_20d`; `dist_low10d_pct` uses a 10-day local low vs.
the composite's 252-day `dist_low252_pct`).

**Separation table** (standardized effect size = median gap / ordinary-population
IQR; bands pre-declared before computing: |z|≥0.30 = CANDIDATE, 0.10-0.30 =
weak, <0.10 = null):

| Feature | Family | Cohort A z (IQR) | Cohort B z (IQR) | Verdict |
|---|---|---|---|---|
| `ret_3d` | 1-Reversal | -0.324 | -0.371 | **CANDIDATE** |
| `decline_from_high10d_pct` | 1-Reversal | -0.535 | -0.520 | **CANDIDATE** |
| `dist_low10d_pct` | 1-Reversal | +0.266 | +0.230 | weak |
| `ret_1d` | 1-Reversal | -0.099 | -0.138 | null/weak |
| `close_loc_pct`, `lower_wick_pct`, `body_atr` | 1-Reversal | ~0 | ~0 | null |
| `vol_ratio_10d` | 2-Volume | +0.186 | +0.215 | weak |
| `vol_zscore` | 2-Volume | +0.152 | +0.186 | weak |
| `vol_declining5`, `ad_fraction` | 2-Volume | ~0 | ~0 | null |
| `atr_expansion`, `atr_accel`, `range5_width_over_atr` | 3-Volatility | 0.12-0.13 | 0.12-0.17 | weak |
| `gap_pct` | 3-Volatility | ~0 | ~0 | null |

**Correlation collapse (critic's decision rule #3 applied)**: `ret_3d` and
`decline_from_high10d_pct` correlate 0.62 within D0 Cohort A — the two
CANDIDATEs are substantially the SAME latent signal (recent decline
velocity/magnitude), not two independent confirmations. `vol_ratio_10d` and
`vol_zscore` correlate 0.88 — also one signal (volume participation), sitting
just below the CANDIDATE threshold in both cohorts.

**Result: ONE mechanism family separates — recent decline velocity, not a
reversal candle.** D0 fast movers arrived at the weak state via a
meaningfully SHARPER, faster recent decline than ordinary D0 stocks (larger
3-day drop, larger fall from their own 10-day high) — but T's own candle
shows NO sign of already reversing (`close_loc_pct` and `lower_wick_pct` are
both null — T is not disproportionately a "hammer"/reversal-shaped day for
fast movers vs. ordinary D0 days). The two observations reconcile: fast
movers fell hard and fast into the state, then paused just enough that by T
they sit slightly further above their own 10-day low than ordinary D0 stocks
(`dist_low10d_pct`, weak positive) — a "sharp drop, then a pause" signature,
not "still actively crashing" and not "already visibly bouncing." Volume
participation shows a real but sub-CANDIDATE-threshold signal in the same
direction (fast movers' volume at T is closer to normal, not depressed, vs.
ordinary D0 days' below-average volume) — consistent, worth carrying forward,
not yet promotable on its own. Volatility-transition (Family 3) is close to a
clean null — no feature in that family clears even the weak band by a
meaningful margin, arguing against "D0 fast movers are a
compressed-to-expanding volatility transition" as the mechanism.

**Both cohorts agree closely** (e.g. `ret_3d` z=-0.324 vs -0.371, `decline_from_high10d_pct`
z=-0.535 vs -0.520) — no meaningful A/B divergence in the mechanism
candidates, matching this line's established pattern.

### Disposition, per critic's pre-registered decision rules

**"If one mechanism family separates: audit it across years/liquidity/F&O/
circuit-clean in a follow-up RQ"** — this is now the exact next step,
RQ-QS-07A-6R, matching the 07A-5→07A-5R precedent. Candidate mechanism to
carry forward: recent decline velocity (`ret_3d`/`decline_from_high10d_pct`,
treated as one signal per the correlation collapse), with volume
participation as a secondary, weaker candidate worth including in the same
robustness pass rather than dropped. Family 3 (volatility-transition) is not
carried forward — too close to null to be worth a robustness pass.

**Not promotable** (Rule #21): this is first-pass separation only, no
robustness sweep, no threshold chosen, no filter, no model, no strategy
simulation — exactly as scoped.

**Files**: `12_weak_state_mechanism.py`, `weak_state_mechanism_features.csv`,
`weak_state_mechanism_separation.csv`.

## RQ-QS-07A-6R — Decline-Velocity Robustness, complete (2026-09-30, critic-specified)

**Objective**: robustness-audit 07A-6's sole surviving mechanism candidate —
recent decline velocity — across the same four one-dimensional strata used in
07A-5R (year, liquidity tercile, F&O, circuit involvement). Per critic's
exact scope: `ret_3d` and `decline_from_high10d_pct` kept as SEPARATE
measurements throughout (not re-collapsed into a composite — they capture
different things: depth of decline vs. recent acceleration, and the point of
this pass is finding out which one, or both, actually survives). Volume
participation explicitly NOT retested (sub-threshold in 07A-6, would turn a
weak observation into an unwarranted second branch). Family 3
(volatility-transition) not retested (already closed null). Same effect-size
definition and bands as 07A-6. **New requirement this pass**: strata with
`n<30` are labeled `low-n/indeterminate`, distinct from a genuine `null` —
none of the 24 tested strata actually needed this label (smallest cell,
F&O=True Cohort A, still had n=228).

**Result: both features are overwhelmingly robust.** Across 12 strata × 2
cohorts (24 cells each): `decline_from_high10d_pct` clears CANDIDATE in 22/24
cells (the only 2 exceptions both in the small circuit-involved subgroup,
still "weak" there, never null). `ret_3d` clears CANDIDATE in 18/24 cells
(6 "weak" exceptions, no nulls, no low-n cells). Every single year
(2022-2026), every liquidity tercile, both F&O and non-F&O, and the
structural (non-circuit) pathway show CANDIDATE-level separation for both
features, with effect sizes frequently STRONGER than the pooled 07A-6 numbers
(e.g. `decline_from_high10d_pct` F&O=True Cohort A: z=-0.985, nearly double
the pooled -0.535).

**Hand-verified anomaly (Rule #22) — a genuine sign flip in the small
circuit-involved subgroup, not a bug**: `ret_3d` for circuit-involved Cohort
A shows a POSITIVE gap (z=+0.432, fast median=-1.58 vs. ordinary median
=-5.52) — the only reversed-direction result across all 24 cells.
Hand-checked 5 real circuit-involved D0 Cohort A events (seed=42): TRU
(2025-04-01, ret_3d=-4.11), LOKESHMACH (2025-05-08, -12.29), TRU (2024-12-16,
**+1.94**), PAYTM (2024-02-15, -23.01), INDOSTAR (2023-04-05, **+7.70**) —
genuinely heterogeneous, both extreme-negative and positive real values, not
a computation error. Most plausible mechanism: circuit-lock mechanically
freezes or distorts realized price moves (a locked day shows artificial
near-zero change, and post-unlock can gap violently in either direction),
which corrupts `ret_3d` specifically as a MEASUREMENT in this small
subgroup (n=589/676) — not evidence against the decline-velocity mechanism
itself. `decline_from_high10d_pct` (less sensitive to a single frozen day,
since it's a peak-to-current comparison) stays correctly signed even here,
just weaker (z=-0.194/-0.138). Disclosed, not smoothed over — this subgroup
is 0.35% of D0, doesn't threaten the headline result.

**Answering critic's exact decision framework — both variables are robust,
but they are not interchangeable**: `decline_from_high10d_pct` is the
stronger and more consistently robust of the two (22/24 CANDIDATE, largest
effect sizes throughout, including the strongest single reading in the
dataset: F&O Cohort A at z=-0.985). `ret_3d` is also robust in the large
majority of strata but shows more variation (weak in some individual years
for Cohort A specifically, and the one real circuit-distorted reversal
above). Per critic's own outcome taxonomy: this is **Outcome A — both
variables robust** — "recent deterioration/deceleration into a weak state
is a robust precursor characteristic of D0 fast movers," with
`decline_from_high10d_pct` (depth of decline) the more dominant of the two,
`ret_3d` (short-term acceleration) a real but somewhat noisier secondary
signal in the same family.

### Disposition

**Mechanism branch continues to post-decline transition anatomy — NOT
another feature search**, per critic's explicit instruction. The
"sharp drop → pause" hypothesis from 07A-6 remains a working hypothesis, now
resting on a robust cross-sectional base rather than a single pooled
reading — but critic's own caveat still applies: robustness of the
CROSS-SECTIONAL gap does not yet establish the TEMPORAL claim ("the
deterioration causes a subsequent pause"). That requires examining the
actual T→D1→D2→D3 transition, using already-available price-path
information — the next RQ, per critic's own roadmap, not a new TA feature
search.

**Files**: `13_decline_velocity_robustness.py`, `decline_velocity_robustness.csv`.

## RQ-QS-07A-6T — Weak-State Transition Anatomy, complete (2026-09-30, critic-specified)

**Objective**: test whether "sharp drop → pause → fast move" is actually
visible in the real day-by-day price path, or merely a plausible reading of
cross-sectional statistics. Hypothesis defined BEFORE looking at the result
(critic's exact wording, to avoid hindsight leakage): "the deterioration has
lost momentum [by T]; the subsequent move begins from a state of
stabilization rather than continued acceleration downward" — vs. the
competing reading, "continued extreme downside through T/D1, violent
reversal only afterwards." No new features, no thresholds, no composite, no
strategy simulation — pure reuse of already-computed, production-verified
trajectory columns (`max_return_d1/d2/d3`, `adverse_d1/d2/d3`,
`close_ret_d1/d2/d3`, `day_of_max`, `path_shape` from `01_event_matrix.py`;
pre-T anatomy from `12_weak_state_mechanism.py`).

**Groups, all frozen, none redefined**: D0_A (D0 Cohort A, n=11,023) is the
"successful" tail. D0_ordinary (D0 & ~cohort_a, n=155,808) is the **primary**
reference — critic's explicit instruction: NOT filtered further, kept as the
full heterogeneous background (stocks that keep falling, stagnate, recover
modestly, or move substantially without crossing the P95 threshold). D2_A
(D2 Cohort A, n=5,583) is a **secondary** reference only.

**Hand-verification (Rule #22)**: `day_of_max`/`path_shape` percentage
breakdowns all sum to 100.0% (one at 99.9%, rounding) for both groups — clean.
Pulled one real example (ADANIENSOL, 2022-12-23): 17.2% decline from its own
10-day high, -15.6% 3-day return into T, then a genuine sustained move (D1
MFE +9.8%, D1 close +8.6%, shallow adverse excursion capped at -3.9%,
building to +13.0% close by D3) — matches the aggregate story directly.

### Part 2 — the trajectory itself (this is the decisive result)

| Metric | D0_A (fast movers) | D0_ordinary (unfiltered background) |
|---|---|---|
| Cumulative MFE: D1 / D2 / D3 | +5.74 / +13.27 / +16.21 | +1.90 / +2.59 / +3.15 |
| Cumulative MAE: D1 / D2 / D3 | **-0.38 / -0.49 / -0.57** | -1.56 / -2.36 / -3.00 |
| Cumulative close return: D1 / D2 / D3 | **+4.75** / +9.54 / +12.28 | **-0.17** / -0.26 / -0.33 |
| % positive at close: D1 / D2 / D3 | 82.7% / 93.9% / 97.2% | 45.5% / 45.5% / 45.7% |
| % fresh high vs. prior day: D1→D2 / D2→D3 | 79.2% / 66.6% | 43.1% / 31.6% |
| `day_of_max` (peaks on D1/D2/D3) | 10.9% / 22.5% / **66.6%** | **44.6%** / 23.8% / 31.6% |
| `path_shape` dominant label | **progressive (55.3%)** | **spike_and_fade (38.8%)** |

**This settles the question the critic posed, and it settles it toward
Reading A, not Reading B.** D0_ordinary's own trajectory rules out "continued
extreme downside through T/D1" — its MAE is modest (-1.56% at D1), not
violent — but it also shows NO directional resolution: close return
oscillates near zero the whole window (45.5%→45.7% positive, essentially a
coin flip), and it disproportionately peaks early then gives it back
(44.6% `day_of_max`==1, 38.8% `spike_and_fade`). **D0_A, by contrast, shows
almost NO further downside past T (MAE stays at a shallow -0.38% to -0.57%,
shallower in absolute terms than D0_ordinary's) combined with a STEADY,
COMPOUNDING, still-building expansion all the way to D3** (66.6% peak on D3,
55.3% `progressive` — 3x the rate of the background population). The
deterioration genuinely appears to stop right around T, and what follows is
not a single spike that fades (already ruled out — no reversal candle,
07A-6) but a sustained multi-day build.

### Part 3 — D0_A vs. D2_A: near-identical post-T trajectories

D0_A's and D2_A's trajectories are strikingly close on every measure: MFE
(5.74/13.27/16.21 vs. 4.99/13.17/16.02), MAE (-0.38/-0.49/-0.57 vs.
-0.49/-0.58/-0.64), close return (4.75/9.54/12.28 vs. 4.21/9.22/11.78),
`day_of_max` (10.9/22.5/66.6 vs. 11.2/23.9/64.9%), `path_shape` (progressive
55.3% vs. 54.0%). **Confirms and substantially deepens 07A-5R's earlier
aggregate-MFE finding**: this isn't just similar summary statistics, the
entire day-by-day shape — MAE containment, directional persistence, timing
of the peak, path-shape mix — matches closely. Per critic's own framing:
"the weak-state pathway appears to enter essentially the same short-horizon
fast-mover state as the established continuation pathway, despite arriving
there through a substantially different pre-T trajectory." Not
over-interpreted as identical mechanisms — same endpoint class, still a
materially different pre-T route (Part 1: D0_A arrives via a much sharper
decline than D2_A, which sits at the trend-strength trough by construction).

### Disposition

**"Sharp drop → pause → fast move" is now visible in the real trajectory,
not just inferred from cross-sectional statistics** — deep prior drawdown
(established in 07A-6/07A-6R) is followed by a near-total halt in further
downside at T, then a sustained, progressive, multi-day expansion. Per
critic's decision tree: this is the outcome where "the next question becomes
whether that stabilization is observable EARLY ENOUGH to be useful at entry
time" — an important distinction from "is the pattern real" (now answered)
to "is it actionable at decision time" (not yet tested — every trajectory
column here is POST-T information, legitimate for retrospective anatomy but
not yet examined for what's knowable at T itself beyond what 07A-6/07A-6R
already established as decision-time-safe precursors).

**Not promotable** (Rule #21): no threshold, no filter, no entry rule, no
architecture decision. Product architecture (one entry pathway vs. two)
remains explicitly parked, per critic's standing instruction — this result
moves the research tree one step further (post-decline transition: now ✓)
but the architecture question still awaits both this and any further
actionability work.

**Files**: `14_weak_state_transition_anatomy.py`, `weak_state_transition_anatomy_summary.csv`.

## RQ-QS-07A-6U — Decision-Time Stabilization Test, complete (2026-09-30, critic-specified)

**Objective**: the first genuinely "can we use it" RQ in this line, after
five "is this pattern real" RQs. Critic's exact question: "Within frozen D0,
can eventual fast movers be distinguished from ordinary D0 names using only
information available at the candidate decision time?" Two distinct notions
of "T information" tested SEPARATELY, never conflated: Level 1 (T-close —
tells us whether the phenomenon is observable at all) and Level 2
(pre-close/early-session — the real actionability question). Frozen: D0_A,
D0_ordinary (unfiltered), no new cohort definitions, no new features, no
threshold optimization, no composite, no strategy simulation, no
candidate-generation freeze.

### Part A — T-close feasibility ceiling (full 166,831-row D0 population)

Joint separation via natural, non-arbitrary splits (population's own median
for continuous variables, `ret_1d`'s natural zero-crossing for T's own
direction — no fitted threshold anywhere):

| Decline depth (median split) | T's own direction | n | %Cohort A | %Cohort B |
|---|---|---|---|---|
| Below median (deeper) | Green (`ret_1d`≥0) | 22,462 | **10.23** | 10.16 |
| Below median (deeper) | Red (`ret_1d`<0) | 60,953 | 9.17 | 9.50 |
| Above median (shallower) | Green | 30,303 | 4.99 | 5.05 |
| Above median (shallower) | Red | 53,113 | 3.07 | 3.13 |
| *Marginal: below-median alone* | *(any direction)* | 83,415 | *9.45* | *9.68* |
| *Marginal: any depth* | *T green alone* | 52,765 | *7.22* | *7.23* |

(Same table using `ret_3d` instead of `decline_from_high10d_pct` shows the
identical qualitative pattern: deep+green=8.94%, deep+red=7.84%,
shallow+green=6.54%, shallow+red=4.05%.)

**Yes, there is a real joint signature at T-close** (best cell 10.23% vs.
worst cell 3.07%, over 3x spread) — **but decline depth is the dominant
driver, and T's own green/red status adds a real but smaller secondary
lift on top.** Within the deep-decline group, green vs. red only moves the
rate from 9.17%→10.23% (1.12x); within the shallow-decline group, the same
green/red split moves it from 3.07%→4.99% (1.62x) — T's own direction
matters proportionally MORE when the stock isn't as deeply oversold, and
less once it already is. Both joint cells beat their own single-dimension
marginal (10.23% > 9.45% "below-median alone"; 10.23% > 7.22% "green
alone") — real joint information, not redundant with either dimension solo.

**Important technical distinction for actionability, not previously
flagged**: `decline_from_high10d_pct`/`ret_3d`/`dist_low10d_pct` are all
computed from T's CURRENT price relative to an ALREADY-KNOWN prior 10-day
high/low — meaning the dominant separating variable is, in principle,
continuously observable INTRADAY (it updates live with the current quote,
it does not require T's close to be known), unlike `close_loc_pct`/
`lower_wick_pct` (both null in 07A-6 anyway) which genuinely require the
full day's H/L/C. `ret_1d`'s sign is similarly observable live at any point
in the session, just not "final" until close — a live-green reading can
still flip red by close, or vice versa.

### Part B — earliest-available-information side-check (SMALL SAMPLE, exploratory only)

Real 5-minute intraday cache covers only 2026-06-10 to 2026-09-23 (~3.5
months, 500 tickers) — **2,255 of 166,831 D0 events (1.35%) fall in this
window with cached intraday data, of which only 42 are Cohort A.** Explicitly
NOT a population-wide finding — reported honestly as a small exploratory
check, same disclosed-limitation convention as `06_pivot_distance_features.py`'s
own hourly-pivot side-check.

Compared each event's first-hour (09:15-10:15 IST) return against its full
day's `ret_1d`: sign-agreement between first-hour and full-day direction is
LOWER for Cohort A (69.0%, n=42) than for ordinary D0 events in the same
window (78.0%, n=2,213) — directionally consistent with fast movers being
more likely to change character between the first hour and the close (fits
the "stabilization develops during the day" story), but n=42 is far too
small to treat this gap as established.

**The one number worth carrying forward, heavily caveated**: within this
tiny window, `%Cohort A` when the first hour is already green is 2.34%
(n=853) vs. 1.57% when the first hour is red (n=1,402) — a ~1.49x relative
lift from JUST the first hour of trading, arguably a LARGER relative lift
than the full-day-close green/red marginal shows in the full 5-year
population (7.22% vs. the population's 6.61% baseline, ~9% relative lift).
This is directionally consistent with the stabilization signature being
detectable early in the session, not something that only crystallizes at
close — but it rests on 42 real events from a single 3.5-month window and
cannot be treated as more than suggestive.

### "Earliest defensible observation time" (critic's explicit requested deliverable)

**The dominant mechanism variable (decline depth) is intraday-observable in
principle** — it only needs the CURRENT live price against an
already-known prior 10-day high, not T's close. **The secondary variable
(today's own direction) is also live-observable, but not "locked in" until
close** — a real risk that a live read reverses intraday. **The tiny
available intraday sample (n=42) is directionally consistent with an early,
pre-close signal existing**, but is nowhere near sufficient to confirm this
at the population scale the T-close result (Part A) was established at.
Honest answer: **decision-time observability looks PLAUSIBLE, not yet
ESTABLISHED** — this project's own real intraday data coverage is the
binding constraint, not the phenomenon itself.

### Disposition

Per critic's outcome taxonomy: closest to **Outcome A "stabilization
plausibly visible before/at breach"**, but with an important qualifier —
the T-close result (Part A, full population, robust) is the solid finding;
the pre-close result (Part B) is suggestive but small-sample, not yet
established at scale. Per critic's explicit guardrail, **no candidate
definition is frozen here** — this result argues the weak-state pathway is
worth continuing toward candidate-generation consideration, but the
critic's own three-part checklist (visible at T-close ✓, visible
before/at entry — plausible but unconfirmed at scale, information lost
moving earlier — not yet fully measured) is not fully closed. Whether that
residual uncertainty is acceptable to proceed, or whether it requires
either a longer intraday history or an alternative decision-time proxy, is
the critic's call.

**Files**: `15_decision_time_stabilization.py`, `decision_time_joint_separation.csv`,
`decision_time_intraday_sidecheck.csv`.

## RQ-QS-07A-CG1 — Candidate Definition Freeze, complete (2026-09-30, critic-specified)

**Phase change, explicit per critic**: everything through 07A-6U asked "what
distinguishes historical winners?" (research/discovery). This RQ asks "given
information available on date T, which stocks would a FROZEN definition have
actually surfaced?" (candidate generation). Not a predictor search, not
threshold optimization, not a strategy, not an architecture decision.

**Two archetypes, both already fully established, neither re-searched**:
Route W (weak-state: 07A-5's D0 discovery + 07A-6/6R's decline-depth
mechanism + 07A-6U's T-close green/red stabilization) and Route S
(strong-state: 07A-5's D9 trend-continuation archetype, already
robustness-tested in 07A-3/07A-3R).

### Critical implementation discipline: freezing reference statistics to prevent leakage

The composite score's percentile ranks and the D0/D9 decile boundaries were
originally computed via `.rank(pct=True)`/`pd.qcut` over the FULL 5-year
research population — legitimate for research, but reusing that machinery
naively for candidate generation would leak future observations into a
historical candidate decision. Fixed by extracting exact numeric reference
statistics ONCE from the closed population (2022-09-02 to 2026-09-24,
1,668,305 rows) and hard-coding them as literal constants:

- `composite_p10_weak_state_cutoff` = **16.728**
- `composite_p90_strong_state_cutoff` = **84.064**
- `decline_from_high10d_pct_median_weak_state` = **-10.433**
- Per-variable percentile breakpoint tables (101 points each) for the 5
  composite inputs, saved to `frozen_candidate_spec.json`.

**Frozen definitions**:
- **Route W**: `composite ≤ 16.728` AND `decline_from_high10d_pct ≤ -10.433`
  AND `ret_1d ≥ 0` (T green, natural zero-crossing, no frozen constant
  needed).
- **Route S**: `composite ≥ 84.064` (single gate, matches 07A-5's already-
  established finding — no additional T-close refinement, since that
  refinement work was specific to Route W).

**Real bug caught before trusting the demonstration (Rule #22)**: the first
run of the demonstration showed Route S producing exactly 0 candidates on
EVERY single day — traced to an `inner` merge against
`weak_state_mechanism_features.csv` (which only covers D0 rows from `12_`'s
own D0-only pass), silently dropping every non-D0 row before Route S's gate
was even evaluated. Caught by directly checking `decile==9` counts in the
demo window (1,008 real D9 rows exist, not 0) before trusting the printed
output. Fixed with a `left` join; re-verified Route S then correctly
produces 93-197 candidates/day in the same window.

**Precision note, disclosed not hidden**: `compute_composite()` (using the
101-point frozen breakpoint table) reproduces the already-saved
`trend_strength_composite` column to within 0.037 percentile-rank-points
(20-row random sample) — a small, expected discretization artifact from
using a compact 101-point lookup table instead of storing the full
1.66M-row historical sample forever. Negligible relative to the ~67-point
gap between the P10 and P90 cutoffs.

**CORRECTION (2026-09-30, critic's required pre-CG2 integrity check,
`17_boundary_flip_audit.py`)**: "negligible" was verified, not assumed — a
full deterministic audit across all 1,668,305 rows found the 101-point
approximation actually flips real W/S membership on **409 rows (189 W +
220 S)**, not zero. Per critic's exact instruction, the P10/P90 thresholds
were NOT retuned — the lookup MECHANISM was replaced with an exact
sorted-array ECDF lookup (`frozen_sorted_arrays.npz`, ~1.66M stored values
per composite input, midpoint-of-searchsorted formula matching pandas'
`rank(pct=True)` averaged-tie convention bit-for-bit on a hand-tie test).
Re-running the same flip audit against the exact method gives **0 flips**
— critic's stated acceptance bar. A residual ~0.0000839 max-abs-diff
remains between the exact recomputation and the saved column; traced to
CSV float-serialization round-trip (reproduced even using pandas' own
`.rank(pct=True)` directly on the reloaded file, ruling out a formula
error) — irrelevant at this magnitude, confirmed by the 0-flips result.
`frozen_candidate_spec.json` updated accordingly;
`16_candidate_definition_freeze.py`'s own 101-point functions are now
superseded (flagged in its docstring) — CG2 onward uses the corrected
exact lookup. **CG1 is now fully frozen per critic's "last integrity
check."**

### Demonstration (real historical dates, resolved D1-D3 outcomes — 2026-09-08 to 2026-09-17)

| Date | Weak-state n | Weak-state Cohort A rate | Strong-state n | Strong-state Cohort A rate |
|---|---|---|---|---|
| 2026-09-08 | 19 | 15.8% | 197 | 6.1% |
| 2026-09-09 | 12 | 0.0% | 181 | 6.1% |
| 2026-09-10 | 15 | 6.7% | 173 | 5.8% |
| 2026-09-11 | 17 | 5.9% | 162 | 1.9% |
| 2026-09-15 | 14 | 0.0% | 93 | 15.1% |
| 2026-09-16 | 34 | 11.8% | 95 | 13.7% |
| 2026-09-17 | 50 | 10.0% | 107 | 11.2% |

Candidate decision (composite/decline/ret_1d, all T-close) and outcome
lookup (Cohort A rate, D1-D3 MFE) are strictly separated — the outcome
columns are looked up only AFTER each day's candidate list is already fixed,
never used to construct the list. Zero overlap between W and S candidates
on every day, as expected by construction (opposite tails of the same
composite score). Route W's candidate lists are consistently much smaller
than Route S's (12-50 vs. 93-197) — the three-gate compound definition is
substantially more selective than Route S's single gate. **These per-day
hit rates are a demonstration of mechanics, not a performance claim** — 7
days, 12-50 names each, is far too small and unrepresentative to draw
conclusions from (0.0% and 15.8% both appear in the same 7-day window).

### Coverage over the full 5-year reference population

D0 alone: 10.00% (by construction, a decile). D9 alone: 10.00% (by
construction). **Route W's complete 3-gate definition: 13.46% of D0 rows →
1.35% of the full population** — meaningfully more selective than the raw
D0 decile alone, consistent with the T-close stabilization gate doing real
work (matches 07A-6U's joint-separation finding).

### Hand-verification (Rule #22)

3 real weak-state candidates checked against all 3 gates directly (ABREL,
AERONEU, AFCONS — all correctly `True` on every gate). 3 real D0-but-
rejected examples checked (360ONE ×2, 3MINDIA — each correctly fails
exactly the gate it should: two on the `ret_1d≥0` gate, one on the decline-
depth gate). Classification logic verified correct by direct inspection, not
just aggregate counts.

### Disposition

**Labeled explicitly, per critic's instruction, as an EOD / next-session
candidate generator — NOT a claim about QS-A's current intraday-breach
entry architecture.** That compatibility question remains separately
tracked and unestablished (07A-6U: plausible, not confirmed at scale).
Critic's status table, current state:

| Layer | Status |
|---|---|
| Historical fast-mover phenomenon | Established |
| Weak-state precursor | Established |
| T-close stabilization | Established |
| Pre-breach/intraday stabilization | Plausible, unconfirmed |
| **EOD candidate generator** | **Frozen (this RQ)** |
| Current QS-A intraday entry compatibility | Unestablished |
| Production rule | Not established |

**Not a strategy, not optimized, not ranked.** No thresholds searched, no
ML, no sector overlay, no market-regime filter, no volume confirmation, no
intraday confirmation, no options layer, no entry/exit rules, no combined
W+S composite score — all explicitly out of scope per critic's prohibition
list. Next stage, per critic, is candidate EVALUATION (concentration,
liquidity, F&O availability, circuit involvement, year/regime stability
across a much larger sample of dates) — not more phenomenon discovery.

**Files**: `16_candidate_definition_freeze.py`, `frozen_candidate_spec.json`,
`candidate_freeze_demo_candidates.csv`.

## RQ-QS-07A-CG2 — Frozen Candidate Population Evaluation, complete (2026-09-30, critic-specified)

**Objective**: not "what else can we discover" but "what does this frozen
machine actually surface when we let it run?" Uses the CORRECTED frozen spec
from CG1's integrity patch (0 boundary flips verified). Population: every
eligible historical stock-day already in `trend_state_anatomy.csv`
(2022-09-02 to 2026-09-24, 1,668,305 rows, 1,003 trading dates, D1-D3
already resolved) — no date sampling, no threshold changes, no candidate
filtering, no W/S combination. **Labeling discipline (critic's explicit
correction)**: every number below is IN-SAMPLE DESCRIPTIVE characterization
of what the frozen definitions produce historically, since the frozen
constants were derived FROM this same population — reported as "historical
candidate events had X% Cohort A incidence," never "hit rate."

### Primary 1 — Coverage

| Route | n | % of eligible stock-days | Candidates/trading-day | Dates with ≥1 candidate |
|---|---|---|---|---|
| W | 22,462 | 1.346% | 22.39 | 944 of 1,003 |
| S | 166,831 | 10.000% (by construction, decile) | 166.33 | 1,003 of 1,003 |

### Primary 2 — historical Cohort incidence (in-sample, not a forward claim)

| Route | Cohort A incidence | Cohort B incidence | D3 MFE median/P90 | D3 close median/P90 |
|---|---|---|---|---|
| W | 10.23% (baseline 4.68%) | 10.16% (baseline 4.72%) | 4.31 / 13.07 | 0.03 / 8.98 |
| S | 8.47% (baseline 4.68%) | 8.22% (baseline 4.72%) | 3.75 / 11.82 | -0.25 / 7.78 |

Both routes show real historical enrichment over the population baseline
(~2x for both A and B, both routes) — consistent with everything already
established in 07A-5/07A-5R/07A-6U (these numbers match those RQs' own
decile-9/decile-0 findings exactly, as they should — same population, same
gates, reused not re-derived).

### Primary 3 — temporal stability, per year (never pooled)

| Route | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|
| W (%Cohort A, n) | 7.81% (730) | 16.31% (2,753) | 10.06% (2,634) | 9.46% (9,153) | 9.18% (7,192) |
| S (%Cohort A, n) | 9.77% (8,782) | 8.20% (52,980) | 9.60% (64,861) | 6.35% (19,669) | 7.04% (20,539) |

Both routes show the SAME qualitative pattern already found independently
across 07A-3R/07R/07A-5R: a real step-down into 2025-2026 relative to
2023-2024's peak (S: ~8-10% down to ~6-7%; W noisier given its much smaller
n, but the same general late-window softening is visible). Quarterly
breakdown (secondary view, saved to `candidate_eval_by_quarter.csv`)
confirms this isn't a single bad quarter — it's a broad multi-quarter
pattern, matching 07R's own regime characterization.

### Primary 4 — overlap, concentration, and the standout finding: candidate persistence

**W vs S overlap: 0 rows** — confirmed empirically (not just "should be"),
opposite composite tails as designed.

**Concentration**: Route W has 1,769 distinct candidate tickers ever, top 10
= 2.54% of all events, top 20 = 4.71% — broad, not dominated by a handful of
names. Route S has 1,805 distinct tickers, top 10 = 2.19%, top 20 = 4.04% —
similarly not concentrated by RAW ticker share.

**But candidate PERSISTENCE tells a very different story** (critic's own
added dimension — this is the standout result of CG2): Route W is mostly
transient — 52.7% of its candidate "episodes" are single-day, only 20.8% of
all W candidate-events belong to a run of 4+ consecutive days. **Route S is
overwhelmingly persistent** — only 23.0% of episodes are single-day, and
**91.9% of all S candidate-events belong to a run of 4+ days.** Of Route
S's 1,805 distinct tickers, 1,537 (85%) appear 20+ times across the whole
history — its top ticker (CUPID) appears on 403 of 1,003 trading dates
(40%). **Hand-verified (Rule #22)**: CUPID's real close price went from
₹3.02 (2023-07-24) to ₹284.40 (2026-09-15) over its candidate span — a
genuine ~94x multi-year structural uptrend, not a data artifact. Route S is
correctly, mechanically identifying "stocks currently in a persistent,
multi-year strong-trend state," which by construction means the SAME small
set of long-running winners re-qualify day after day for months. **Route S
is NOT producing ~166 fresh daily discoveries — it's mostly re-confirming a
relatively stable pool of already-known strong trends, with genuine
rotation concentrated in a smaller subset.** Route W, by contrast, behaves
much more like a rotating daily scanner.

### Secondary — liquidity, F&O, circuit (annotated, not filtered)

**Liquidity**: broad population is 30/40/30 (low/mid/high). Route W skews
toward low liquidity (44.2/39.1/16.7) — consistent with 07A-6/6R/6T/6U's own
weak-state population being liquidity-broad but base-rate-heavier in
illiquid names. Route S skews toward high liquidity (19.2/38.3/42.5) —
consistent with 07A-3R's established trend-continuation-concentrated-in-
liquid-names finding.

**F&O**: Route W is only 4.63% F&O-eligible (n=1,040); within F&O, Cohort A
incidence is 4.81% vs. 10.49% non-F&O — the weak-state archetype is
overwhelmingly a non-F&O phenomenon. Route S is 10.74% F&O-eligible
(n=17,913); within F&O, Cohort A incidence is 4.11% vs. 8.99% non-F&O —
same qualitative pattern (F&O names show a much lower absolute Cohort A
incidence than non-F&O for BOTH routes), consistent with large/mid-cap
names simply producing fewer 15%+ three-day moves overall (already
established in 07A-5R).

**Circuit**: Route W is 2.33% circuit-involved (n=523); circuit-involved
median D3 MFE is far higher (13.97 vs. 4.25 structural) — consistent with
circuit events being inherently more volatile (07A-5's own finding). Route
S is 7.55% circuit-involved (n=12,596); circuit-involved median D3 MFE
14.9→4.90 vs. 3.70 structural, same direction, smaller gap.

### Disposition

**This is the descriptive character of the frozen generator, not a
performance claim.** Route W: small, selective, rotating, non-F&O-heavy,
low-liquidity-skewed, ~10% historical Cohort A incidence. Route S: large,
persistent (dominated by long-running trend names), somewhat more
F&O/liquidity-present, ~8.5% historical Cohort A incidence, but the vast
majority of its "candidates" on any given day are the SAME small pool of
already-qualified names, not fresh signals.

**Per critic's explicit guardrail, no stratification above is acted on** —
the F&O/liquidity/circuit patterns are annotations, not new filters. Any of
these that looks worth pursuing (e.g., "should Route S dedupe its
persistent core?") is a candidate for a NEW RQ, not a CG2 modification.

**Next stage, per critic**: assuming this behaves sensibly (it does — no
red flags, internally consistent with every prior RQ in this line), the
research moves to genuine forward/out-of-sample validation (RQ-QS-07A-CG3)
— running the already-frozen generator on dates NOT used to define it,
without refitting the constants.

**Files**: `18_candidate_population_evaluation.py`, `candidate_eval_by_year.csv`,
`candidate_eval_by_quarter.csv`, `candidate_eval_route_w.csv`,
`candidate_eval_route_s.csv`.
