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
