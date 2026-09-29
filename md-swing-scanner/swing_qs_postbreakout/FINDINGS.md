# swing_qs_postbreakout — Findings (append-only)

## Research Preflight — RQ-QS-05A, Layer A (answered before writing any code, 2026-09-29)

1. **Population**: what events exist? Not yet the same "A" as BPC/QS (a v0.1-gate-
   passing breakout). This is broader and un-gated on purpose: any day, for any ticker
   in `nifty500_universe.csv`, with (a) Volume >= 3x that ticker's own trailing 50-day
   MEDIAN volume (median, not mean, so the spike day itself and any single recent
   outlier can't inflate the baseline it's being compared against) and (b) an absolute
   day return |Close/PrevClose - 1| >= 5%. Both numbers are literature-anchored, not
   invented: 3x matches Weinstein's cited "2-3x average volume" for a Stage 2
   breakout (using the top of his range as the search net, not a promoted threshold);
   5% reuses Bulkowski's own break-even reference point for pennants, already verified
   this session — not a new number picked to fit JUSTDIAL/GOCLCORP. This is a
   deliberately GENEROUS candidate net (Layer A's job is to split it, not narrow it
   further yet).
2. **Entry clock**: what information exists at decision time? Everything Layer A
   computes is trailing/backward-looking only (50-day median volume as of the day
   itself, and a lookback count over the 63/126/252 days BEFORE the candidate day) —
   naturally decision-time-safe, no lookahead risk the way the 04-series HH/LH work
   had to catch and fix.
3. **Stop definition**: N/A for this RQ. No performance, no R, no returns computed
   anywhere in Layer A — purely a classification/description of novelty. Per Rule #20,
   a risk unit will only be declared when Layer B or later actually needs one.
4. **Exit engine**: N/A, same reason as above.
5. **Comparison unit**: entries only, and specifically a PROPERTY of one entry
   (candidate expansion days), not a comparison between different products/gates.
   Layer A's whole output is: for each candidate day, was it "novel" (no other
   qualifying day in the trailing lookback) or "re-acceleration" (at least one other
   qualifying day in that lookback) — reported at 3 pre-declared, non-optimized
   lookback horizons (63/126/252 trading days ~ 3/6/12 months), per Rule #19's
   Parameterized Feature corollary. No thresholds are chosen or promoted here.

**Pre-registered anchors for Rule #22 (declared before running)**: JUSTDIAL's
2026-07-14 candidate day is expected to classify as NOVEL at all three horizons
(nothing comparable in the prior year per the hand-check). GOCLCORP's 2026-09-03
candidate day is expected to classify as NOT NOVEL at the 6- and 12-month horizons
(March 24/25's 6.7M/8.6M volume days), and its 3-month-horizon classification is
genuinely uncertain going in (March to September is ~5 months — outside a 3-month
lookback) — this is written down BEFORE running the script, specifically so a
convenient-looking result can't be quietly treated as expected after the fact.

## RQ-QS-05A, Layer A — Breakout Novelty, run (2026-09-29)

**Population fix, disclosed before results**: neither JUSTDIAL nor GOCLCORP — the two
motivating hand-checked examples — are in `nifty500_universe.csv`. JUSTDIAL is only in
`extended_universe.csv` (the 195 StrykeX-watchlist names outside NIFTY 500); GOCLCORP
is in NO tracked universe list at all, just a stray cached file. 198 of 703 cached
tickers sit outside `nifty500_universe.csv`. Running Layer A against that list alone
would have silently excluded both anchor cases. Used every ticker with real cached
daily history instead (703 tickers) — the honest population given what data actually
exists, not an idealized official subset.

**Bug caught by the pre-registered anchor, fixed before trusting any aggregate (Rule
#22 working as designed)**: first pass counted every individual candidate DAY as its
own event. JUSTDIAL's 2026-07-13 and 07-14 are BOTH individually candidate days (same
continuing flagpole) — counting July 13 as a "prior candidate" against July 14 wrongly
flagged a single 2-day breakout as its own re-acceleration, and the anchor immediately
caught it (JUSTDIAL came back `novel_63d=False`, directly contradicting the
pre-registration). Fixed by clustering candidate days within `EPISODE_GAP=3` trading
days into one episode, anchored at the episode's first day — 3 chosen from the
flagpole literature (Bulkowski: flagpole is typically 1-3 bars) BEFORE rerunning, not
tuned to fix the anchor. Re-ran once with the fix; anchors below are that result.

**Full population (703 tickers, ~5yr history): 17,989 candidate days -> 14,032
distinct episodes** (median episode length 1 day, max 14). Trigger: Volume >= 3x
trailing-50-day median AND |day return| >= 5%, both trailing-only/decision-time-safe,
both literature-anchored (Weinstein's cited 2-3x volume; Bulkowski's own 5%
break-even reference point) not fit to either example.

| Horizon | Novel | Re-accel |
|---|---|---|
| 63d (~3mo) | 3,954 (28.2%) | 10,078 (71.8%) |
| 126d (~6mo) | 1,746 (12.4%) | 12,286 (87.6%) |
| 252d (~12mo) | 880 (6.3%) | 13,152 (93.7%) |

Median episode-start vol_mult 6.5x (P90 23.6x), move 7.0% (P90 12.2%) — the 3x/5%
search net is generous, most real candidates clear it by a wide margin.

**Anchor results, reported honestly including where my own pre-registration was
wrong**:

- **JUSTDIAL 2026-07-14**: novel at 63d (True), NOT novel at 126d/252d (False, False).
  My pre-registration guessed "novel at all three horizons" from a casual by-eye read
  of "quiet Feb-July" — wrong on the letter of it. The systematic scan found a smaller,
  easy-to-miss qualifying event on 2026-01-23 (3.8x volume, 6.3% move — barely over the
  3x/5% floor) sitting ~5.5 months before July 14, inside the 126-day/252-day windows
  but outside the 63-day one. This is NOT a bug — it's exactly why Rule #19's
  multi-horizon pre-declaration matters: at a 3-month standard, July 2026 IS a novel
  breakout for JUSTDIAL; at a 6-12 month standard, it technically is not, because of one
  much smaller prior blip. Worth being honest that "quiet by eye" and "quiet by a
  precise, pre-declared rule" are not the same claim.
- **GOCLCORP 2026-09-03**: NOT novel at all three horizons (False, False, False) — more
  decisively non-novel than the pre-registration anticipated. The manual hand-check
  only caught the March 2026 events; the systematic scan additionally found qualifying
  episodes on 2026-06-18 (16.3x, 5.4%) and 2026-08-07 (31.9x, 6.7%), both within the
  63-day window before Sept 3. GOCLCORP has 55 total candidate days since 2021 (vs.
  JUSTDIAL's much sparser history) — a serial candidate-generator, not a stock with one
  isolated prior event.

**Disposition**: Layer A is established and internally consistent — it produces a
real, non-trivial split (6.3% to 28.2% "novel" depending on horizon, exactly the range
you'd want for a meaningful gate rather than a near-100%-or-near-0% degenerate split),
and both anchor cases land in the direction their hand-checks predicted, once the
episode-clustering bug was fixed and the pre-registration's imprecision on JUSTDIAL's
longer horizons is understood rather than papered over. Per critic's exact sequencing,
Layer B (post-breakout decay characterization) is the next step, gated on this holding
up — not started yet. No performance, no thresholds, no returns computed anywhere in
this RQ, as designed.

**Not yet done**: Layer B itself; any comparison of decay behavior between the novel
and re-accel buckets (that's the critic's stated "critical comparison," explicitly for
after Layer B exists); no promotion of the 3x/5%/3-trading-day parameters, all three
are pre-declared search-net choices, not validated thresholds.

## RQ-QS-05A, Layer B — Post-Breakout Decay characterization (2026-09-29)

Per critic's exact spec: range decay, volume decay, decay-day-count, monotonic vs
merely-declining, whether price holds the breakout area, whether there's a
subsequent expansion. No thresholds, no returns, no gate. Two forward windows
pre-declared before running: 15 trading days (Bulkowski's own stated flag/pennant
duration) and 40 (long enough to have caught JUSTDIAL's real Aug-28 secondary pop
during the earlier hand-check — chosen for that documented reason, not tuned after
seeing this script's output). Reused the existing production `vol_declining5` column
(the literal 5-day-declining-volume flag `reject_theta_trap()` already uses for an
unrelated options-side rejection rule) rather than reimplementing it, plus a new
`decay_run_len` anchored at the episode's own end (vol_declining5 is a rolling flag
anywhere in history, not anchored to "counting from right after this breakout").

**Full population (14,032 episodes, 703 tickers, ~5yr), 15-day window:**

| Metric | P25 | P50 | P75 | P90 |
|---|---|---|---|---|
| vol_ratio_to_baseline (vs trailing-50d median) | 1.28x | 1.81x | 2.88x | 4.71x |
| vol_trend_corr (day-index vs Volume) | -0.545 | -0.304 | 0.027 | 0.305 |
| range_over_atr | 0.78x | 0.93x | 1.12x | 1.34x |
| range_trend_corr | -0.382 | -0.137 | 0.134 | 0.350 |
| decay_run_len (consecutive day-over-day vol drops) | 1 | 1 | 2 | 3 |
| min_low_vs_prebreakout_pct | -8.3% | -1.1% | 3.7% | 7.6% |

vol_trend_corr negative in 73.0% of episodes; range_trend_corr negative in 63.2%.
vol_declining5 (the literal production flag) is True on 0% of days at P50 — median
episode never even hits one qualifying 5-day run, let alone the user's screener's
implicit "watch for this" moment. Only 44.5% of episodes keep their low above the
pre-breakout close within 15 days; 0.2% keep the low above the flagpole's own peak
High (this last field is closer to tautological given how extreme a 1-2 day spike's
own High typically is — reported for completeness, not a real finding on its own).
Subsequent expansion (another qualifying episode, same ticker) within 15 days:
30.0%; within 40 days: 57.6%.

**40-day window**: same shape, slightly softer — vol_ratio_to_baseline P50 1.75x,
vol_trend_corr P50 -0.150 (67% negative), only 30.8% hold above the pre-breakout
close by then.

**Descriptive split by novel_252d (NOT a performance comparison, per critic's
instruction)** — the gap is small in both directions and doesn't cleanly support
"novel breakouts decay better":

| | novel (n=880) | re-accel (n=13,152) |
|---|---|---|
| vol_trend_corr median, 15d | -0.320 | -0.304 |
| holds above pre-breakout, 15d | 41.9% | 44.7% |
| subsequent expansion, 15d | 26.1% | 30.2% |
| holds above pre-breakout, 40d | 26.7% | 31.1% |
| subsequent expansion, 40d | 48.2% | 58.3% |

Novel breakouts are, if anything, marginally LESS likely to hold above their own
pre-breakout level in this simple cut — the opposite direction of the naive
hypothesis, though the gap is small enough (2-5pp) that it shouldn't be read as a
real reversal either. Re-accel's higher subsequent-expansion rate is intuitive on
its own (a stock that already spikes often is more likely to spike again soon,
almost by construction) and doesn't by itself say anything about decay QUALITY.

**Rule #22 anchors — the two hand-checked examples show a clean, real contrast that
the population split above does NOT capture:**

- **JUSTDIAL** (episode 2026-07-13->07-14): 15d vol_trend_corr **-0.625** (strong real
  decay), decay_run_len 3, min_low_vs_prebreakout **+24.1%** (held well above where it
  broke out from). 40d: vol_trend_corr still -0.421, min_low_vs_prebreakout still
  **+13.0%**, subsequent_expansion_day=**33** — correctly detects the real Aug-28
  secondary pop found in the manual chart read.
- **GOCLCORP** (single-day episode, 2026-09-03 only — confirms this one was a lone
  spike, not a 2-day flagpole like JUSTDIAL/its own March events): 15d vol_trend_corr
  **+0.211** (volume rising, not decaying), decay_run_len 1, min_low_vs_prebreakout
  **-3.8%** (gave back the whole move within 15 days), subsequent_expansion_day=**9**
  (re-accelerated again in under 2 weeks). Both windows agree.

**Honest disposition**: the two anchor cases behave exactly as their hand-checks
predicted and cleanly opposite each other — real signal exists for AT LEAST some
episodes. But this does NOT show up as a strong population-level effect when split
simply by novel-vs-re-accel at one horizon: the aggregate gap is small (2-5pp) in
both directions, the literal "N consecutive declining volume days" the user's own
screener checks for is a rare event (median run-length 1, not 5), and a meaningful
minority of ALL episodes (55-70%, depending on window) give back the entire
breakout move rather than holding it. Two honest readings, not yet adjudicated:
(a) the true discriminating factor isn't well-captured by "novel vs re-accel at
252d" as currently defined, or (b) a real effect exists in a genuinely distinct
minority subset (mirroring how RQ-QS-04A found an 18% "holds-above-A" subset
buried inside a much noisier overall population) and averaging across all 14,032
episodes dilutes it. Not resolved here — no threshold-hunting attempted, per
critic's explicit instruction. Next step, per this project's own established
04A->04B precedent, would be a further DESCRIPTIVE (still no returns) anatomy pass
isolating episodes with an unusually sustained/monotonic decay AND price holding
the pre-breakout level, to see if THAT specific slice looks like JUSTDIAL — not yet
run, pending critic's read on whether that's the right next cut or whether this
result should instead close the "generic decay after any big-volume breakout"
framing the way 04B closed the "holds-above-A pause" framing.

**Not yet done**: any performance/return numbers anywhere in this line; any subset
isolation/anatomy beyond the coarse novel/re-accel split; any promotion of the
15d/40d windows or the 3x/5% Layer A trigger.

## RQ-QS-05A, Layer A0 — Established Base/Range precondition (2026-09-29, caught by direct user pushback)

**Why this exists**: user pushback, verbatim in spirit — "that just means some of the
bases we have not cleared." Layer A's "novelty" (no comparable volume spike recently)
is NOT the same claim as "this stock was actually sitting in a genuine sideways range
beforehand" — the critic's own diagram has ESTABLISHED BASE/RANGE as its own first box,
and this line skipped straight to novelty + decay without ever building it. A stock can
be novel-by-volume while still grinding in a trend with no real structure at all.

**Two measures, both trailing-only, both literature-anchored, two pre-declared windows
(40/90 trading days) before looking at results**:
- `prior_range_over_atr` — (max High - min Low) over the window / atr14, reusing
  RQ-QS-04A's own ATR-normalized width convention applied to the PRE-breakout period.
- `sma_slope_pct` — % change in sma50 across the window, Weinstein's own framing of
  Stage 1 as a flattening moving average, a different claim than "tight range."

**Anchors**: JUSTDIAL's 90d window: range_over_atr 6.8x (near the tight end, P10-P25 of
the population), sma_slope -22.2% (was declining, then flattened into the breakout —
not a perfectly flat multi-month base, a real, if imprecise, match). GOCLCORP's 90d
window: range_over_atr 13.7x (loose, near P90), sma_slope +50.1% (clearly already
trending hard) — correctly flags GOCLCORP as NOT a real base, consistent with
everything else known about it.

**Full-population cross-cut (14,032 episodes) — honest, somewhat deflating result:
NEITHER single dimension discriminates outcomes on its own.** Tercile of
range-tightness: holds-above-prebreakout_40d is 31.6% (tightest) / 31.8% (mid) / 32.0%
(loosest) — statistically indistinguishable. Tercile of flatness: 32.2% / 32.2% / 31.0%
— same story. A likely mechanism for why range-tightness in particular fails to
discriminate: ATR itself is elevated for a stock that's ALREADY volatile/trending (as
GOCLCORP's own history shows), so "tight relative to ATR" can mean "consistently
volatile in its own already-active regime," not "genuinely calm" — the normalization
doesn't cleanly separate the two cases the way it does for RQ-QS-04A's post-breakout
pauses (where it was validated on a cleaner population).

**Only the full intersection (novel_252d AND flattest tercile AND tightest-range
tercile) shows a real but modest lift**: n=123, holds-above-prebreakout_40d=38.2%
vs. the full-population baseline of 31.8% (+6.4pp), subsequent-expansion_40d=37.4%
(vs ~58% baseline — genuinely less likely to spike again soon, consistent with these
being less "serially active" names). Neither single-condition novel-only cut (by
range tercile alone or flatness tercile alone) showed this cleanly — mid/loosest
terciles within novel_252d were noisy and non-monotonic (n=123 per tercile, thin).

**Rule #22 hand-verification of 3 real examples from the n=123 intersection, spanning
different years and outcomes — all 3 computationally exact against raw bars (episode
dates/prices/volumes, and the 40-day min-Low-vs-prebreakout-close figure matched to
the decimal)**:
- MAZDOCK (2022-04-04): +1.9% — barely held, marginal.
- ADANIPORTS (2022-04-26): **-24.0%** — a real, hard loss, during the broad April-May
  2022 market correction (checked the calendar distribution of the full n=123: 26% fall
  in 2022, elevated vs an even ~20%/year spread but not dominated by one event — 20 of
  123 in April-May 2022 specifically, worth flagging as a real regime concentration,
  not disqualifying but a caution against reading the aggregate lift as clean of
  regime effects).
- AIAENG (2022-05-23 to 05-31, a 5-day flagpole): +13.1% — held well.

**Honest disposition**: the user's instinct is directionally right but the effect is
much narrower and weaker than "bases not cleared explains the whole picture" would
imply. It takes ALL THREE conditions together (genuinely novel, genuinely flat,
genuinely tight) to show ANY lift, the lift is modest (+6.4pp, not dramatic), the
sample is thin (n=123), real outcomes inside that n=123 are still a mixed bag
(confirmed by hand, not just asserted), and there's a real, uninvestigated regime
concentration (April-May 2022) that could be inflating or deflating the number in
either direction. This is a LEAD, not a finding — per Rule #19, needs robustness
checks (different tercile boundaries, the 40d base-window instead of 90d, excluding
the April-May 2022 cluster to see if the lift survives) before being trusted further,
and per this project's standing practice should go to the critic before any more
compute is spent chasing it.

**Not yet done**: robustness sweep on the tercile boundaries/windows; a regime-excluded
re-check; any performance/return numbers (still none anywhere in this whole line);
any promotion of novel/flat/tight as a combined gate.

## RQ-QS-05A robustness check on the Layer A0 triple-cut — FAILS, CLOSED (2026-09-29)

Four variants pre-declared before running (`04_rq05a_robustness_check.py`): (A) same
intersection using the already-computed 40d window instead of 90d, (B) a quartile
split instead of terciles on both windows, (C) year-by-year breakdown (Rule #16),
(D) the original 90d triple-cut with April-May 2022 excluded.

**(A) Window robustness — fails.** 90d window: +7.4pp lift (n=123, 38.2% vs 30.8%
baseline). 40d window, same tercile methodology: **-0.6pp** (n=126). The effect does
not survive its own alternate pre-declared horizon.

**(B) Quartile robustness — fails, more clearly.** 90d bottom-quartile: **+11.5pp**
(n=78) — looks even stronger. 40d bottom-quartile: **-5.8pp** (n=80) — reversed. Same
pattern as (A), confirmed under a second, independent cut methodology.

**(C) Year-by-year (Rule #16) — the 90d lift is one year's artifact, not a stable
effect**:

| Year | n | hold-rate_40d |
|---|---|---|
| 2022 | 32 | 25.0% |
| 2023 | 26 | **61.5%** |
| 2024 | 24 | 33.3% |
| 2025 | 16 | 37.5% |
| 2026 | 25 | 36.0% |

2023 alone accounts for most of the overall +7.4pp lift; 2022 sits BELOW the 30.8%
baseline on its own. n per year (16-32) is thin, but the swing (25.0% to 61.5%) is far
too large to read as a stable, year-independent effect.

**(D) Regime exclusion — doesn't rescue it, and is moot given (A)/(B)**: ex-April/May-
2022, lift rises to +10.9pp (n=103); the April-May-2022-only subset alone is -10.8pp
(n=20) — confirms that specific correction dragged the number down, but doesn't
address the more fundamental (A)/(B) window-instability failure.

**Verdict: this is exactly the same failure shape as the earlier Sector Relative
Strength candidate** (real-looking at one lookback, reversed at a nearby one — see
`../FINDINGS.md`'s Sector-RS Independence Test) — **REJECTED per Rule #19, not
promoted, and CLOSED per Rule #10 (a real-but-insufficient signal is a completed
research outcome, not an open thread)**. The user's original instinct — "some of the
bases we have not cleared" — was directionally worth checking and DID surface a real
methodological gap (Layer A0 was missing entirely before this). But the specific
"novel + flat + tight, by these two measures" operationalization does not survive its
own pre-declared robustness check, and should not be re-litigated under a new name
without genuinely new evidence.

**Where this leaves the whole RQ-QS-05A line**: Layer A (novelty) is established and
real. Layer B (decay characterization) shows a modest-but-real average decay tendency
population-wide, with two hand-verified anchor examples (JUSTDIAL vs GOCLCORP)
showing a clean, real contrast that does NOT generalize into a strong population-level
effect on any cut tried so far (novel/re-accel, base-tightness, base-flatness, or
their intersection). No gate, no filter, no promoted parameter exists anywhere in
this line. Next step, if any, is the critic's call — this project's own convention is
not to keep independently re-cutting a thin population in search of a surviving
slice (that IS the threshold-hunting Rule #19 exists to prevent).
