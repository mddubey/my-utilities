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
