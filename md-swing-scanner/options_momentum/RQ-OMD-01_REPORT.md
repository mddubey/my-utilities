# RQ-OMD-01 — Stock-Level Fast-Move Behaviour Map — Report

2026-10-04 IST. Built per `RQ-OMD-01_PREFLIGHT.md` (all horizons/buckets/thresholds frozen
before this run). Raw output: `verification_output.txt`, `behaviour_map_output.txt`. Hand-
verified 5 real (ticker, date, bar) examples against the raw `data/intraday_60m/` CSVs before
trusting any aggregate (Rule #22) — all 5 matched the manual calculation exactly.

**Correction, 2026-10-04, post-critic-verdict (Rule #22):** while building RQ-OMD-02's
reversal panel, a `pre_reversal_mfe <= next_mfe` invariant check caught that `np.sign(0) == 0`
was silently falling into the "down" branch everywhere (`direction > 0` is False for exactly-
flat returns). 5.1% of all bar-to-bar returns are exactly flat (`r_T == 0`), concentrated in
illiquid/stale-price tickers (AKSHAR, GTLINFRA, ...), and every one of them was being emitted
as a meaningless "down move" event. Fixed by excluding `r_T == 0` from qualifying events (kept
in the rolling z-score baseline, since "this stock sometimes doesn't move" is legitimate
information about its own distribution — only excluded from being classified as a directional
event). **Effect, checked by diffing the full before/after output line by line:** every
unusual/elevated bucket number below is byte-identical — the numbers already sent to the
critic are unaffected. Only `dn_normal` (the down-side baseline comparator) and `gap_down`
shifted, both upward (contamination was exclusively mislabeled-as-"down" flat bars dragging
those two down). Net effect: the down-side fade-with-size pattern, reported below as "not
monotonic," **is now also cleanly monotonic** once the baseline is corrected — this
strengthens the finding rather than undermining it. Tables 1, 3 and 5 below are the corrected
numbers; the surrounding narrative is updated to match.

## Population

- 2,266 / 2,328 universe tickers have a `data/intraday_60m/` file; 2,192 have >=100 usable
  bars after cleaning. No F&O/Nifty-500/liquidity/technical restriction at any point.
- 2023-10-23 -> 2026-10-01, 8,843,168 raw bars, median 5,039 bars/ticker.
- 544/2,192 tickers are late starts (history begins after 2024-06-01).
- Panel after corp-action exclusion + first-bar drop + flat-return exclusion (see correction
  note above): **8,379,394 qualifying (ticker, bar) events** — 5.2% loss from the raw bar
  count, almost all of it (452,958 rows) exactly-flat returns, the rest the narrow
  +-1-session exclusion window around 913 price-affecting corporate actions.
- **7,120,173 intraday-bar events** (10:15-15:15 close-to-close), **1,259,221 gap-bar events**
  (09:15, overnight+first-hour).
- F&O tickers are 9.5% of the panel by ticker-count (current list, reporting split only).

## Headline result

**No repeatable "big move -> fast continuation" phenomenon exists in the direction the
original hypothesis needed.** The opposite is more prominent: **the larger the stock-relative
move, the more it tends to fade** — a clean, monotonic dose-response in both directions (see
correction note above), with the down side showing the larger swing.

### Table 1 — continuation rate (% of signed forward return > 0) by bucket, growing horizon

| bucket | 1H | 2H | 3H | rest-of-session | next session |
|---|---|---|---|---|---|
| dn_unusual | 40.4% | 42.8% | 43.6% | 44.7% | 47.7% |
| dn_elevated | 44.7% | 47.0% | 48.0% | 48.8% | 51.3% |
| dn_normal | 50.2% | 51.7% | 52.3% | 54.2% | 55.2% |
| up_normal | 43.2% | 44.5% | 45.1% | 41.8% | 44.4% |
| up_elevated | 39.2% | 41.1% | 42.2% | 39.6% | 43.3% |
| up_unusual | 38.0% | 39.1% | 39.9% | 39.0% | 42.1% |

(n per cell: 82,991 - 1,768,572; full table with median/mean/MFE/MAE in `behaviour_map_output.txt`.)

**Both sides are now a clean, monotonic dose-response** (corrected — see the note above):
up side normal (44.4%) > elevated (43.3%) > unusual (42.1%); down side normal (55.2%) >
elevated (51.3%) > unusual (47.7%) — the bigger the move, the more it fades, in both
directions, at every horizon tested. The down side's fade is the larger swing of the two
(55.2% -> 47.7%, a 7.5pp drop, vs up's 44.4% -> 42.1%, a 2.3pp drop) — a real asymmetry in
magnitude, not in the shape of the pattern.

**Robustness (Table 2, pre-declared windows W=504/1512/3024):** the up_unusual and
dn_unusual fade signs and rough magnitudes hold at all three windows — e.g. up_unusual
next-session median signed return: -0.0048 (W=504), -0.0054 (W=1512), -0.0064 (W=3024).
Not a W-1512-specific artifact.

**Independent corroboration from gap bars (Table 5, not z-bucketed, different bars entirely):**
gap-up continuation rate stays below 50% at every horizon (38.3%-43.1%); gap-down is close to
50% early and crosses clearly above it by rest-of-session/next-session (53.5%/54.5%). Gap-ups
fade noticeably harder than gap-downs continue — the same directional asymmetry shows up in a
completely separate slice of the data (overnight+first-hour moves, not pure intraday moves) —
this is not a pipeline artifact of one bucket definition.

### Table 3 — A/B/C/D shares, unusual buckets vs normal (W=1512, primary)

| bucket | n | A immediate cont. | B immediate reversal | C stall | D delayed cont. |
|---|---|---|---|---|---|
| dn_unusual | 89,647 | 13.7% | 25.9% | 37.1% | 23.2% |
| dn_normal | 1,769,464 | 14.7% | 39.6% | 10.1%* | 35.6% |
| up_normal | 1,423,910 | 11.9% | 47.3% | 12.7%* | 28.1% |
| up_unusual | 119,992 | 13.8% | 27.4% | 39.5% | 19.0% |

(*checked and ruled out right-censoring as the explanation — every bucket's "no delayed-
window data yet" share is ~0%, not just unusual's. The much lower stall share in normal
buckets is therefore a real pattern, with one important mechanical caveat: A/B/C/D's 0.5x
threshold is relative to each event's OWN |r_T|, so "continuing by half of itself" is a much
bigger absolute move to clear for an unusual (large) |r_T| than for a normal (tiny) one —
part of the higher unusual-bucket stall share may be this threshold scaling, not purely
duration. Table 1's continuous distributions, which don't depend on this threshold at all,
are the primary evidence; Table 3 is corroborating, not standalone.)

**Combined continuation (A+D) is lower for unusual moves than normal moves in both
directions** — dn: 36.9% (unusual) vs 50.3% (normal); up: 32.8% (unusual) vs 40.0% (normal).
This is the exhaustion/mean-reversion signature you'd expect from market logic: an unusually
large move consumes the liquidity/participants willing to push further at that price right
now, inviting a fade, whereas an ordinary-sized move has more room left to run. B (immediate
reversal) alone is close to **2x** A (immediate continuation) in both unusual buckets.

### Table 6 — F&O vs non-F&O (the actually-tradable subset), unusual buckets

| | n | A | B | C | D | A+D |
|---|---|---|---|---|---|---|
| non-F&O, dn_unusual | 79,651 | 13.1% | 26.3% | 37.4% | 23.2% | 36.3% |
| F&O, dn_unusual | 9,996 | 18.8% | 23.1% | 34.8% | 23.1% | 41.9% |
| non-F&O, up_unusual | 106,896 | 13.1% | 28.1% | 40.0% | 18.4% | 31.5% |
| F&O, up_unusual | 13,096 | 18.9% | 21.7% | 35.4% | 23.4% | 42.3% |

F&O names (the only ones you can actually buy options on) show a meaningfully higher combined
continuation rate (~42%) than non-F&O names (~32-36%) after an unusual move, in both
directions. Still a minority outcome (58% don't continue), but the practical population looks
better than the full-universe number suggests — worth carrying into any follow-up.

### Table 7 — year-by-year (2024/2025/2026), unusual buckets

A/B/C/D shares are stable within a few points across all three years for both unusual
buckets (A: 13-19%, B: 22-28%, C: 34-41%, D: 19-24%) — no regime collapse, this isn't a
2025-specific artifact. Full table in `behaviour_map_output.txt`.

### Timing (Table 4)

Within unusual buckets: **B (immediate reversal) peaks fastest** — median time-to-favorable-
extreme is 1 bar, and it carries the deepest adverse excursion against the original holder
(median MAE -0.0405). **D (delayed continuation) takes until bar 7** (next-session) to reach
its favorable extreme, consistent with its definition, and comes with much less adverse heat
along the way (MAE -0.0126) than C_stall carries (-0.0275) even though C never reaches
continuation. **A (immediate continuation)** is the cleanest outcome (MAE only -0.0054) but is
the smallest group.

## Answer to the spec's question

**"There is / is not a robust fast directional phenomenon worth investigating further."**

Not in the direction asked for (continuation as a basis for a long directional option
bought right after a big move). That hypothesis is closed, negative — real result, not
inconclusive, per Rule #10: don't re-litigate this under a new name later.

**There is a different, robust phenomenon sitting right next to it:** unusually large
up-moves see weaker continuation, monotonically with move size, consistently across 3
z-windows, 3 years, and an independent gap-bar slice.

**Critic verdict, 2026-10-04 (superseding this report's original framing below the line):**
bank the behaviour, not the trade. The earlier framing here ("that's the actionable thread —
closer to a short/put-buying-after-a-spike idea") overclaimed on two points the critic caught:
(1) the gap-bar corroboration does NOT establish this is independent of well-documented
overnight-to-intraday reversal — it needs an explicit overnight-vs-intraday decomposition,
not an assumption either way; (2) a stock-level reversal rate is not evidence of an option
edge until retracement depth/speed is measured continuously and the IV/premium hurdle is
addressed. See `FINDINGS.md`'s critic-verdict section and `RQ-OMD-02_SPEC.md` for the
required next step before any options framing is revisited. The F&O-restricted
delayed-continuation minority (~19-23% of unusual moves, Table 3/6) and the F&O-vs-non-F&O
continuation gap (Table 6) are both diagnostic leads only — Table 6's comparison (F&O-unusual
vs non-F&O-unusual) is the wrong cut for establishing an F&O-specific effect; the right one
(F&O-unusual vs F&O-normal) hasn't been run yet (Rule #21 — no filter claim is made here).

## What this report explicitly does NOT do (Section 7, confirmed)

No entry rule, no stop/target, no strike/DTE, no breakout detector, no F&O population
restriction, no threshold search, no ML, no options backtest. The 0.5x A/B/C/D threshold is
a pre-declared first-cut classification for readability — Tables 1/2/5 (continuous
distributions, not touching that threshold) are the primary evidence; Table 3 corroborates
with the same sign and roughly the same magnitude pattern.

## Next-decision options (not decided here)

1. Reframe the discovery around the up-move fade: characterize what makes a fade sharp vs
   mild vs absent (candidate for a put-buying-after-spike product).
2. Characterize what distinguishes the ~19-23% delayed-continuation (D) unusual-move cases
   from the ~35-40% stalls (C) — the long-side thread, if still wanted, lives here, not in
   the raw unusual-bucket base rate.
3. Close the "unusual move -> fast long continuation" framing outright and move to another
   market-behaviour family, per the spec's own framing.
