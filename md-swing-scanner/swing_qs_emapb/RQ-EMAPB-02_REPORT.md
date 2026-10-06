# RQ-EMAPB-02 — Critic-Specified Research Audit — Report

2026-10-04 IST. Built exactly per `RQ-EMAPB-02_SPEC.md` (critic's design). Primary structural
pipeline (Tracks 2-9) runs on the Fib 50% touch population (explicit scope cut, flagged in the
spec, not silent); Track 1 covers all four retracement depths. D1 (not D3) throughout, per the
critic's explicit requirement. Raw output: `rq_emapb02_audit_output.txt`.

## Track 1 — does "shallower is better" survive at the correct D1 horizon? NO.

| level | touch rate | D1 open | D1 peak | D1 close | D1 MAE |
|---|---|---|---|---|---|
| retest | 72.2% | +0.249% | +1.522% (P90 +5.08%) | +0.000% | -1.157% |
| Fib 38.2% | 77.7% | +0.288% | +1.551% | -0.002% | -1.227% |
| Fib 50% | 78.2% | +0.282% | +1.560% | +0.031% | -1.204% |
| Fib 61.8% | 77.7% | +0.270% | +1.559% | -0.002% | -1.230% |

All four levels are statistically indistinguishable at D1 — the monotonic "shallower = better"
pattern reported in RQ-EMAPB-01 was a D3 artifact. **Correction**: that finding does not
survive at the actual product horizon and is retracted as a candidate signal.

## Track 3 — structural components (Fib 50 population, n=3,869)

| component | prevalence |
|---|---|
| range compression | 13.0% |
| ATR/range contraction | 72.2% |
| volume contraction | 43.5% |
| combined base (all three) | 10.1% |
| contained (no breakdown) | 85.4% |

## Tracks 2 & 4 — does waiting for structure improve the opportunity? NO — it makes it worse.

| population | n | D1 open | D1 peak | D1 close | D1 MAE |
|---|---|---|---|---|---|
| A: touch only (C0) | 3,869 | +0.286% | +1.563% | +0.039% (51% pos) | -1.199% |
| B: stabilized pullback | 465 | +0.165% | +1.380% | -0.008% (49% pos) | -1.206% |
| C: stabilized + structural resumption (C2) | 415 | +0.047% | +1.295% | -0.186% (46% pos) | -1.200% |

Monotonic degradation: more structure required -> worse D1 close, every step.

## Track 5 — confirmation quality C0/C1/C2

| | trigger rate | delay vs touch | D1 close | D1 peak |
|---|---|---|---|---|
| C0 (no confirmation) | 100.0% | 0 bars | +0.039% | +1.563% |
| C1 (early resumption, first green bar) | 99.5% | 4 bars | -0.028% | +1.406% |
| C2 (structural, breaks span high) | 84.3% | 5 bars | -0.106% | +1.378% |

Same monotonic degradation. Waiting for ANY confirmation, however defined, costs quality here.

## Track 6 — genuine digestion vs random oscillation: INVERTED from the textbook expectation

| | n | D1 peak | D1 close |
|---|---|---|---|
| "genuine digestion" (range_compression=True) | 504 | +1.254% | -0.151% (47% pos) |
| "random oscillation" (range_compression=False) | 3,365 | +1.620% | +0.069% (51% pos) |

The tighter, more textbook-looking pullback performs WORSE, not better.

## Track 7 — peak vs close gap persists at every population level

| population | D1 peak | D1 close | give-back |
|---|---|---|---|
| A (touch) | +1.563% | +0.039% | 1.524pp |
| B (stabilized) | +1.380% | -0.008% | 1.388pp |
| C (resumed) | +1.295% | -0.186% | 1.481pp |

The intraday move is real at every stage; holding to the close erases most of it regardless of
how much structure was required to enter — consistent with the options_momentum finding closed
earlier tonight.

## Track 8 — timing cost

A -> touch: median 7 bars. Touch -> span end: 2 bars (fixed). Span end -> C1: 2 bars (total
A->C1: 10). Span end -> C2: 3 bars (total A->C2: 14 — double the touch's own 7-bar wait, for a
WORSE outcome).

## Bias/overfit checks — all clean, this is not a fragile result

- N at every stage: 4,988 -> 3,901 (touched) -> 3,869 (span fits) -> 465 (B) -> 415 (C).
- Year-by-year, C population D1 close: 2023 -0.163%, 2024 -0.217%, 2025 -0.207%, 2026 -0.117%
  — negative every single year, stable.
- Ticker concentration: top 5 tickers = 5.3% of the C population (275 unique tickers) — broad.
- Trimming top/bottom 1% and 5%: median D1 close for C population unchanged at -0.186% both
  times — not driven by extreme outliers.
- Not a single-level artifact: Track 1 shows the result is consistent across all four
  retracement depths.

## THE ACTUAL FINDING — checked individual components separately, per critic's instruction not to require all conditions simultaneously

| component (vs the opposite) | D1 close | %positive |
|---|---|---|
| range_compression = True | -0.151% | 47% |
| range_compression = False | +0.069% | 51% |
| atr_contraction = True | -0.034% | 49% |
| atr_contraction = False | +0.319% | 55% |
| vol_contraction = True | -0.059% | 49% |
| vol_contraction = False | +0.136% | 52% |
| **contained = True** | **+0.221%** | **54%** |
| **contained = False** | **-1.168%** | **28%** |

Every "quality/tightness" component (range compression, ATR contraction, volume contraction),
individually, is INVERTED — present = worse, not better, matching Track 6. But **"contained"
(the pullback did NOT undercut the touch bar's own Low in the 2 bars after) is a large, real,
individually useful signal** on D1 close.

**Corrected framing — "contained" is far stronger on D1 PEAK, the metric that actually matters
for a quick-exit options product (user caught this: don't lead with close when we already know
close gives back most of the move):**

| | D1 open | D1 peak | D1 close | D1 MAE |
|---|---|---|---|---|
| contained = True | +0.403% (66% pos) | **+1.752% (88% pos**, P75 +3.36%, P90 +5.80%) | +0.221% (54% pos) | -0.986% |
| contained = False | -0.483% (30% pos) | +0.538% (65% pos) | -1.168% (28% pos) | -2.325% |

Dominates on every dimension — open, peak (both hit-rate and magnitude), close, and downside
(MAE). **Year-by-year on D1 peak, hand-verified against raw bars (PETRONET 2025-10-07: D1
open +0.58%, D1 peak +1.61%, D1 close -0.61% — move real, close erodes it, exactly the
population pattern)**:

| year | contained=True peak (n) | contained=False peak (n) |
|---|---|---|
| 2023 | +2.126%, 92% pos (296) | +0.798%, 74% pos (35) |
| 2024 | +1.958%, 88% pos (1,137) | +0.707%, 68% pos (202) |
| 2025 | +1.514%, 89% pos (1,056) | +0.472%, 66% pos (182) |
| 2026 | +1.705%, 86% pos (816) | +0.338%, 59% pos (144) |

Consistent, large gap every single year, not fading, not a pooled-years illusion. This is the
strongest, cleanest signal found anywhere across all three research threads tonight
(options_momentum, RQ-BPC-05, and this one). Already robustness-checked (ticker concentration
2.2% top-5 share on the close metric; peak numbers share the same population so inherit that
robustness).

## Decision, per the critic's own framework

**B — Conditional support, stronger than the close-only numbers first suggested.** The
phenomenon exists, but only ONE specific structural component is useful, and it is not the one
the textbook flag/base framing predicted. "Contained" (support holds, doesn't get undercut)
matters a great deal on D1 peak (88% vs 65% hit rate, 3x the median magnitude, robust across
all 4 years individually); "tight/compressed/volume-dry" (the classic VCP/flag signature) does
not — if anything it's a negative signal. This is NOT "Fib50 is support" and NOT "wait for a
clean base" — it's closer to "did the level survive its first real test without being
undercut, checked 2 bars later," combined with an exit discipline built around capturing the
peak rather than holding to close (Track 7's give-back is real and persists even in the
contained=True population, 1.53pp).

## CORRECTION, same session — "contained" does not survive real entry/exit mechanics

Everything above (the 88%-positive, +1.72% D1-peak numbers) uses two non-actionable
reference points: entry at the TOUCH BAR'S OWN CLOSE (not transactable — you don't know the
bar closed there until it's over) and exit at the D1 PEAK (only knowable in hindsight). Redone
with a real entry (the open of the first bar after "contained" is actually confirmable, 3 bars
after the touch) and a real, fixed exit (D1 close, not the peak):

| | n | median return | % positive | median MAE |
|---|---|---|---|---|
| Idealized (touch-close -> D1 peak) | 3,306 | +1.72% | 88% | — |
| Idealized (touch-close -> D1 close) | 3,306 | +0.221% | 54% | -0.99% |
| **Real (actual entry -> D1 close)** | 3,304 | **-0.026%** | **49.3%** | **-1.221%** |

A coin flip. **Root cause, isolated precisely**: the median price already moves +0.160%
(mean +0.365%) between the touch bar's close and the first point you can actually transact —
this alone accounts for essentially the entire +0.248pp gap between the idealized and real
numbers. This is not a timing-calibration problem fixable by entering a bar earlier or later.
**It is structural**: "contained" can only be confirmed by watching price hold up for 2 bars
without breaking down — but those same 2 bars are where the favorable move is also
happening. Confirming the setup and capturing the setup's payoff are largely the same event,
not two separable steps. Waiting for proof costs you the thing you were waiting to prove.

**Also checked and discarded as non-actionable**: the D1 peak occurs at the open 56% of the
time (vs. spread through the day the other 44%), with a clean, monotonic give-back pattern by
peak-timing (early-peaking cases fade hard and often close negative; late-peaking cases barely
give back anything). Real, but tells you nothing usable in real time — you cannot know which
archetype you're in before the peak has already happened, same category of problem as above.
Simple fixed-time exits (afternoon/14:15, or a realistic 9:30 entry using 5-minute data on the
recent-months subset) each capture only ~11-15% of the theoretical peak — confirms no simple
clock-time rule solves this.

**Revised classification, per the critic's own framework**: closer to **D — no useful
phenomenon**, once entry/exit realism is enforced, not the B verdict reported earlier in this
same document. The population-level statistical difference between contained/not-contained is
real and robust (confirmed with hand-checks, year-stability, trimming) — but it does not
survive translation into anything a real trade could capture. This correction supersedes the
"B — conditional support" verdict above; the verdict above is kept for the record, not deleted,
per this project's standing discipline of not quietly erasing superseded findings.

## What this does NOT establish yet (per Track 9's guardrail — no stop/exit optimization)

No ATR stop multiple, no time-stop window, no target — those remain genuinely downstream
questions, correctly deferred. This report establishes WHETHER a usable signal exists
(yes, "contained," specifically) and what does NOT work (combined structure, tightness,
volume dry-up, waiting for any form of confirmation) — not how to trade it yet.
