# swing_qs_emapb/FINDINGS.md

## RQ-EMAPB-01 — Pullback-to-support after a volume-confirmed breakout (2026-10-04, IN PROGRESS)

**Origin**: user chart review (RITES, VEDL, REDINGTON — HINDPETRO didn't fit) found that after
an impulsive, volume-confirmed move, price often pulls back to some support, then bursts
again. Explicitly NOT an EMA8-specific claim — EMA8 was just what the user's chart had by
default. The real question: after profit-booking following a high-volume breakout, where do
institutions actually re-enter for the next leg, and is that re-entry point identifiable and
tradeable (target holding period: minutes to half a day, options-sized, not multi-day swing)?

### Definitional attempts, in order, and why each one failed before the current state

1. **Daily-bar "any EMA touch"** — too loose (EMA8 touched 94.7% of the time, no discriminating
   power) and didn't match the confirmed real examples cleanly.
2. **+ bullish pin bar filter** (literature wick:body definition, K=2/3) — rejected: excluded
   BOTH confirmed ground-truth examples (VEDL 2025-12-12, REDINGTON 2026-07-30). A pin bar is
   a single-candle concept; the real examples showed multi-day/multi-bar holds, not one
   dramatic rejection candle.
3. **+ "hold >=M consecutive touch-bars, then expand"** on DAILY bars — still excluded both
   ground-truth examples. Root cause found: **wrong timeframe entirely** — the real examples
   were described and only visible on the HOURLY chart; a multi-hour hold-and-expand can
   happen entirely within one daily candle.
4. **Rebuilt on 1H bars** (`data/intraday_60m/`, coverage from 2023-10-23) — simplest "any
   touch" definition finally matched both ground-truth examples with sensible numbers (VEDL
   +5.5% / REDINGTON +2.0% over 3 trading days from the touch).
5. **First aggregate "edge" turned out to be a timing confound** — EMA8 touch rate was 100%
   (zero discriminating power again), and the apparent edge over a baseline measured at a
   FIXED bar (window midpoint) was really just "measured early in the window beats measured
   late" — already known from tonight's other two closed threads (options_momentum,
   RQ-BPC-05: A beats B, early beats late). **Fixed baseline methodology from here on**: every
   touch's forward return is compared against the population's own typical return AT THAT
   SAME bar-offset, not one arbitrary fixed bar.

### Literature read before building the real candidate list (2026-10-04)

- **Wyckoff "Last Point of Support" (LPS)**: named concept for exactly this — after a "Sign
  of Strength" (the breakout), a pullback occurs, and the LPS is where buying absorbs the
  last selling, confirming old resistance is new support. Framed as a *cleaner, lower-risk
  entry on the same move*, not a separate source of extra return.
- **Classic throwback/retest**: high-volume breakouts throw back to retest the original level
  ~70% of the time; of those, 65% recover and continue, 35% fail. Volume is supposed to
  contract during a legitimate throwback.
- **Fibonacci retracement — ACADEMICALLY NOT VALIDATED.** Batchelor & Ramyar and other
  peer-reviewed sources found no statistically significant evidence Fib levels stand out from
  random proportions; "do not represent a real phenomenon," explainable by chance/volatility
  alone. Retail trading sources oversold this; corrected after the user directly challenged
  "is Fib even a support."
- **Floor-trader pivot points**: mixed/contradictory academically — price does react near
  pivots often (64-67% of sessions), but profitability from trading them alone is contested
  (one study: 70% of pivot-based trades lose).

### RQ-EMAPB-01 full side-by-side comparison (13 candidates, same corrected methodology)

Population: 6,400 volume-confirmed A's (10-day lookback only, no lookback-mixing, >=1.5x
`vol_avg10_prior`, A after 2023-10-23 for 1H coverage). Touch = decision-time-safe (Low vs
level as of the prior bar, Close vs level same bar). Baseline = population's own typical
return at the SAME bar-offset as the touch (fixes the timing confound in #5 above).

| candidate | touch% | median offset (bars) | 3D excess vs typical | %beat typical | resumed | reversed |
|---|---|---|---|---|---|---|
| retest (orig. breakout level, 100% retracement) | 72.2% | 7 | +0.051% | 51.0% | 38.0% | 37.4% |
| Fib 38.2% | 77.7% | 7 | **+0.109%** | 51.4% | 39.2% | 37.1% |
| Fib 50% | 78.2% | 7 | +0.095% | 51.3% | 39.0% | 36.7% |
| Fib 61.8% | 77.7% | 7 | +0.054% | 50.9% | 38.2% | 37.5% |
| EMA8 (1H) | 99.9% | 8 | -0.010% | 49.9% | 37.2% | 38.1% |
| EMA20 (1H) | 98.6% | 17 | -0.091% | 48.8% | 35.6% | 40.6% |
| EMA50 (1H) | 83.8% | 28 | -0.121% | 48.6% | 35.1% | 40.3% |
| EMA8 (daily, production col) | 77.2% | 30 | -0.173% | 48.2% | 34.3% | 40.3% |
| EMA21 (daily) | 54.9% | 31 | -0.102% | 49.0% | 35.8% | 40.7% |
| EMA34 (daily) | 46.7% | 28 | +0.062% | 50.8% | 37.4% | 39.2% |
| SMA21 (daily) | 49.4% | 29 | -0.066% | 49.1% | 34.7% | 39.6% |
| SMA50 (daily) | 38.1% | 24 | +0.028% | 50.3% | 38.3% | 38.4% |
| Pivot S1 (daily, production col) | 93.4% | 28 | -0.101% | 48.7% | 34.2% | 40.8% |

**Clean pattern**: price-geometry levels (retest + all 3 Fib ratios, each computed from THIS
move's own swing, not a generic indicator) are the only ones that land consistently positive,
clustered together (+0.05% to +0.11%). Every EMA/SMA/pivot-based level is flat-to-negative,
several showing reversal MORE common than resumption (worse than touching nothing). Given
Fibonacci's own lack of academic validation (above), this reads less like "38.2% specifically
matters" and more like "a moderate pullback into this stock's own recent move has a small
generic tendency to resume" — the depth-ordering is monotonic (shallower retracement = better:
fib38 > fib50 > fib618 > full retest), consistent with the standard reading that a shallow
pullback signals a still-strong trend and a deep one signals a weakening one.

### Depth-ordering check (shallow -> deep retracement)

| level | 3D median return | %positive |
|---|---|---|
| Fib 38.2% (shallowest) | +0.084% | 51.0% |
| Fib 50% | +0.093% | 51.0% |
| Fib 61.8% | +0.049% | 50.5% |
| retest/100% (deepest) | +0.044% | 50.6% |

### Is the pullback a real base/flag/channel? Checked as a FILTER, not an average.

Range should narrow in a real flag (Minervini/Bulkowski) — median range trend is POSITIVE
(widening), only 26% narrow. Volume should dry up — close to a coin flip (49.7% decline).
**Critically, conditioned as a filter (not just averaged)**: cases that ARE genuinely
flag-shaped (narrowing range AND declining volume together) show NO better outcome than cases
that are neither (-0.048% vs -0.067% median 3D return, resumed/reversed rates near-identical).
This is not "we didn't average correctly" — the flag-shaped subset was checked directly and
still shows nothing. Same "not a recognizable base" signature as RQ-QS-04B's original finding,
now independently replicated in a second population.

### Waiting for confirmation (base breakout) makes it WORSE, not better

Tested: 3-bar "base" after the Fib 50% touch (M=3, not tuned), "breakout" = first bar
exceeding that 3-bar high. 84.5% eventually "broke out" (not a selective criterion — this was
a minimal placeholder, not a real tightness/duration-qualified base definition). Result:
-0.313% excess, 45.7% beat-typical (worse than the touch alone's 51.3%), reversed (39.3%) now
exceeds resumed (36.7%). Reading: confirmation delays the entry (median 5 more bars) past
wherever the small edge actually lived, consistent with the "early beats late" pattern found
twice already tonight (options_momentum, RQ-BPC-05).

### Peak vs. close — the most promising thread so far

D1 (next full session after the base-breakout signal) close-to-close return is weak/negative
(median -0.324%, only 43.1% positive). But **D1's intraday peak (1H-bar-derived, not the
coarser daily file) is real**: median +1.378% above the signal bar's close, P75 = +3.03%,
P90 = +5.23%. Same shape as the options_momentum study closed earlier tonight: the stock
genuinely moves intraday; holding to the close gives most of it back. Points toward a
short-dated-options / quick-exit framing rather than a close-to-close equity framing — matches
the user's own stated target holding period (minutes to half a day).

### Open items, explicitly not yet decided (next: read properly, then critic)

1. **Pullback depth**: currently testing Fib ratios (now known to be arbitrary, not
   literature-validated) — need a non-arbitrary way to pick/characterize "how deep" matters,
   or confirm the monotonic-depth pattern itself (shallower=better) is the real, usable
   signal rather than any one specific ratio.
2. **Base/consolidation definition**: current M=3-bar placeholder is explicitly not a real
   base definition (84.5% "break out" of it — not selective). Needs real duration/tightness
   criteria, read from literature, not picked by eye.
3. **Expected next-session behaviour / holding period**: peak-vs-close gap suggests a
   short-dated-option, quick-exit framing. Needs a proper read on realistic holding-period
   expectations for this kind of signal, not assumed.
4. **Stop-loss / risk-unit convention**: NOT YET DISCUSSED AT ALL (per Rule #20 — correctly
   out of scope until the above are settled, since R is undefined until the stop is defined,
   but now explicitly flagged as the next thing needed, not forgotten).
5. Once 1-4 are read and pre-declared, compile and send to critic for buy-in on the combined,
   final candidate definition before any further building.

## RQ-EMAPB-02 — Critic-Specified Audit (2026-10-04) — CLOSED, D (no useful phenomenon once made real)

Critic correctly rejected RQ-EMAPB-01's premature closure attempt, specified a 9-track audit
with D1 (not D3) as the decision metric. Full result: `RQ-EMAPB-02_REPORT.md`.

**Structural tracks (1,2,4,5,6) all confirmed on BOTH D1 close and D1 peak**: retracement
depth doesn't matter; waiting for any form of confirmation (stabilization, structural
breakout) makes outcomes monotonically worse, not better; the textbook tight/volume-dry base
shape is actually a negative signal, inverted from flag/VCP theory. All robust (year-by-year,
ticker concentration, outlier trimming all clean).

**"Contained" (price doesn't undercut the touch bar's low in the 2 bars after) looked like a
strong, real signal on idealized metrics** (88% positive D1 peak, median +1.72%, stable across
all 4 years 2023-2026, broad across 480 tickers) — **but did NOT survive translation into a
real, tradeable entry/exit**. Real entry (first actually-transactable price, 3 bars after the
touch) to a real, fixed exit (D1 close): median -0.026%, 49.3% positive — a coin flip. Root
cause, precisely isolated: confirming "contained" requires watching 2 bars hold up without
breaking down, and those exact 2 bars are also where the favorable move happens — the median
price already moves +0.16-0.37% before you can transact, accounting for essentially the whole
idealized edge. This is structural (confirmation and payoff are the same event), not a
timing-calibration problem.

**Final classification: D — no useful phenomenon**, once entry/exit realism is enforced.
Supersedes the earlier "B — conditional support" verdict reported mid-session in the same
document (kept for the record, not deleted). Peak-timing (56% at the open, 44% later in the
day, with a clean monotonic give-back-by-peak-time pattern) is real but non-actionable — you
cannot know which archetype you're in before the peak has already occurred. Simple fixed-time
exits (afternoon, realistic 9:30 via 5-minute data) each capture only ~11-15% of the
theoretical peak.

**Status: CLOSED.** Do not reopen the EMA-pullback / retracement-touch / confirmation-base
line of research without a materially different mechanism, not another threshold or timing
tweak on the same touch-then-confirm structure — three separate confirmation definitions
(pin bar, hold+expand, "contained") have now all failed once properly tested against real
entry/exit mechanics.

## RQ-EMAPB-03 — Population timescale bug found from the metadata table alone, before any chart was opened (2026-10-04)

Critic specified a blinded 30-episode visual audit (`RQ-EMAPB-03_SPEC.md`) to check whether
mechanical definitions were simply failing to capture a real, visually-recognizable base. Before
any of the 30 blinded chart images were reviewed, the user noticed something wrong purely from
the **in-chat metadata table** (ticker, A date, A price, peak date, peak price): `peak_date ==
a_entry_date` for all 30 sampled episodes, with no exception. No chart was opened to catch this.

**Root cause, confirmed by reading `07_visual_audit_build.py`**: `find_peak()` starts at A's own
bar and walks forward on 1H candles, extending a running high until a bar fails to exceed it.
On a breakout day with continued intraday momentum, this loop frequently never leaves day A
before finding "the peak" — so what every prior EMAPB test (01, 02, and this 03 sample) has
labeled "pullback" is actually **the fade after the breakout day's own intraday high**, not a
multi-day cool-off/base. This is a different, timescale-mismatched phenomenon from the real
ground-truth examples the hypothesis was built from (RITES/VEDL/REDINGTON — multi-bar, multi-
session holds).

**Literature check, done before building anything new (per standing literature-first discipline)**:

- Minervini VCP: a valid base needs a **minimum of ~3 weeks (15 daily bars)** — "anything
  shorter is too compressed to have meaningfully shaken out weak holders and absorbed supply."
  Typical VCP bases run 4-12 weeks.
- Classic bull flags: typically **5-25 trading days** (roughly 1-4 weeks); patterns resolving
  in under a day are not what the pattern describes.
- Wyckoff re-accumulation: **"On intraday charts, many ranges look like re-accumulations but
  are noise... On a daily chart, accumulation ranges typically last weeks to months; on
  intraday charts, a range might form and resolve in hours."** Volume asymmetry (rallies on
  stronger volume than dips) is the real discriminator, not shape alone, and is only reliably
  assessable at the daily/weekly timescale.
- Intraday breakout failure rates are structurally much higher than daily-timeframe breakouts
  (50-70% fail intraday vs 40-45% on daily), consistent with intraday "pullbacks" being
  noise-dominated.

**Implication**: this likely explains why all three prior EMAPB mechanical definitions (pin bar,
hold+expand, "contained") failed once tested against real entry/exit mechanics — the population
was never testing the multi-day basing/digestion phenomenon the hypothesis was named for. It was
testing same-session profit-booking dressed up with Fib levels, which the literature says is
dominated by noise at that timescale.

**Further literature, read before drafting any redefinition (not sent to critic until this was
done)**:

- Bulkowski (empirical, large-sample): bull-market flags average **9% rise, 44% break-even
  failure rate**; pennants average **7% rise, 54% failure**; volume trends downward during the
  flag **74% of the time** for eventual up-breakouts. Average time from pennant to the ultimate
  high is **~10 days** — i.e. even Bulkowski's own base rate for "how long this takes to play
  out" is on the order of 1-2 weeks, not hours.
- Minervini VCP, volume specifics (concrete, pre-declarable thresholds): pullback/contraction
  volume should decline to roughly **40-50% of the 50-day average**; the eventual breakout
  should expand to **140-150%+** of average. "Volume dry-up" (VDU) is generally defined as volume
  falling **50%+ below** a trailing average. Useful because our existing A/breakout gate
  (`>=1.5x vol_avg10_prior`) already sits inside the literature's breakout-volume range (1.5-2x+)
  — the breakout side of the definition was never the problem; only the pullback-duration side
  was undefined/implicitly same-day.

**Consolidated implication for the redefinition**: two independent literature families (Bulkowski
empirical flags/pennants: ~10 days typical; Minervini VCP: ~15 trading days / 3 weeks minimum)
converge on a **multi-day-to-two-week minimum**, not hours. Per this project's Parameterized
Feature corollary (pre-declare 2-3 materially distinct horizons before looking at results, don't
pick after seeing outcomes), the next build should test minimum A-to-peak-confirmation separations
of roughly **5, 10, and 15 trading days** side by side — not one number chosen after the fact —
plus a volume-dry-up check on the pullback itself (pullback volume <= ~50% of its own trailing
average, literature-sourced, not fit to this data).

**Next step, not yet built**: redefine the population so the peak must be confirmed on a later
calendar day than A, with a pre-declared minimum day-separation (tested at 5/10/15 trading days
per the above, not tuned after seeing results) plus a volume-dry-up check on the pullback —
before any new mechanical or visual-audit test is run. Full critic handoff below. The 30-episode
blinded visual audit built under the old (same-day) definition is parked, not reviewed
chart-by-chart, since it would be auditing the wrong phenomenon.

**Caveat raised by the user before sending to critic**: Minervini/Bulkowski/Wyckoff are all
literature for longer-term SWING setups (multi-week-to-month holding periods) — not necessarily
the right analog for this product (options, minutes-to-half-a-day holds). The user's actual
mental model of "true breakout" is closer to an order-flow/absorption concept: resting buy
interest already queued opposite resting sellers (profit-takers) at/near the breakout level, so
once those sellers are absorbed, the already-queued buyers push price through quickly — a
supply/demand-at-the-level dynamic, not necessarily a multi-week base requirement. Flagged to
critic explicitly: verify whether reframing "genuine digestion" as seller-absorption-at-level is
legitimate for a short-duration product, and whether more applicable literature exists on
short-horizon continuation/order-flow absorption specifically, separate from the multi-week
basing literature above (which may only validate the TIMESCALE problem, not the right mechanism
for this product).

## Critic verdict on the above (2026-10-04)

Confirmed the bug is real and the catch-before-opening-a-chart order of operations was correct.
Confirmed the caveat: literature is swing-style, not necessarily our product's mechanism.
Grounded the absorption/order-flow reframing in market-microstructure literature — order-flow
imbalance (OFI) at the best quotes is empirically linked to short-horizon price moves (stronger
with thinner depth); NSE evidence shows order imbalance has real predictive power for very
short-term returns, strongest in the first ~5 minutes, decaying by ~30 minutes. But correctly
noted we cannot see resting buyers "queued" from 1H OHLCV — only order-book/trade-level data
could show that directly. Hypothesis renamed: **short-horizon supply exhaustion / order-flow
imbalance around a recently established level**, not "resting buyers waiting."

**Rejected the proposed 5/10/15-day grid as a second overcorrection** — swapping "same-day is
wrong" for "a multi-day swing base is right" smuggles the Minervini/Bulkowski timescale back in
unjustified, for a product that is explicitly short-duration, not a swing hold. Both the 5/10/15
grid and the 30-chart visual audit stay parked. Directed next step: rebuild episode construction
on a **daily-session basis** (not 1H) with no pre-chosen minimum separation, and report the
**distribution** of real post-A timescales as a pure diagnostic — not a filter, not a promotion.
Volume dry-up kept as an observational variable, not hard-coded to the 50% Minervini number.

## RQ-EMAPB-04 — Daily-session episode reconstruction + timescale distribution (2026-10-04, DESCRIPTIVE ONLY)

Built per the critic's direction: same population (unchanged, 6,400 A's, entry_definition=10,
vol_ratio>=1.5, a_entry_date>=2023-10-23), same running-high-walk logic as the old `find_peak()`,
but on **daily bars** (`data/daily/`) instead of 1H — this is the actual fix. No new filter, no
pre-chosen day-count threshold. Window: 50 trading days post-A (pre-declared, generous, not
tuned). Script: `08_daily_episode_reconstruction.py`. Output: `rq_emapb04_daily_episodes.csv`
(6,390 episodes with a valid window).

**Hand-check (Rule #22) against 5 of the old buggy same-day-peak sample** — confirms the fix
does the right thing: BDL/ATUL/PVRINOX genuinely are single-day spikes even on daily bars (real,
not an artifact this time) with days_to_continuation of NaN/31/30; GESHIP and HUDCO now correctly
show the peak landing 2 days and 0 days later with continuation at 4 and 2 days respectively —
spread that the old 1H logic could never produce.

**A -> peak (does the impulse itself extend past A's own session)?**

| | n | % |
|---|---|---|
| same day (0 extra days) | 3,197 | 50.0% |
| 1-2 extra days | 2,432 | 38.1% |
| 3-5 extra days | 672 | 10.5% |
| 6+ extra days | 89 | 1.4% |

Half the time the breakout day's own high IS the peak for a while — this is now a genuine
finding (daily resolution), not the 1H-granularity artifact from RQ-EMAPB-03.

**Peak -> continuation (the actual pullback/base duration) — the key diagnostic, n=6,390:**

| bucket | n | % |
|---|---|---|
| 2-3d | 2,005 | 31.4% |
| 4-6d | 1,017 | 15.9% |
| 7-15d | 1,139 | 17.8% |
| >15d | 963 | 15.1% |
| never (within 50d window) | 1,266 | 19.8% |

(Minimum possible value is 2 days by construction — the day after the peak is, by definition,
the first day that failed to extend the running high, so it cannot itself be the continuation
day.) **No dominant single timescale** — the population is spread roughly evenly across 2-3
days, 4-6 days, 7-15 days, and >15 days, with a real ~20% that never resume within 50 trading
days at all (genuine failures/terminations, not a data artifact — caught via a NaN-vs-None
bucketing bug fixed during this run, which had been silently inflating the >15d bucket to 34.9%
before the fix). This empirically confirms the critic's instinct: imposing a single 5/10/15-day
cutoff would have been arbitrary — there is no one phenomenon here, likely several, and they
should not be mixed in one population.

Pullback depth (min Low during the pullback, % below peak high, observational only, no gate):
median -12.54%, P25 -18.71%, P75 -7.83% — considerably deeper than the Fib-ratio retracements
tested in RQ-EMAPB-01/02, consistent with this being measured over a daily/weekly window rather
than an intraday one.

**Status**: descriptive only, not yet handed to critic. Next decision needed: which timescale
segment(s), if any, to carry into a rebuilt visual audit — or whether to split into genuinely
separate RQs per segment, per the critic's suggestion not to mix distinct phenomena.

## Critic buy-in on RQ-EMAPB-05 (hourly-native), 2026-10-04

**Granularity-consistency principle, confirmed and sharpened**: "A state defined on timeframe T
becomes observable/complete only at the close of its defining T-bar. No sub-bar observation
inside that bar may be classified as occurring after the T-bar event." For daily-native A: all 1H
bars inside day A belong to the breach event; pullback can only begin day A+1. For 1H-native A:
the next 1H bar, even same calendar day, is legitimately "after."

**Terminology correction for RQ-EMAPB-04**: do not describe the 50% same-day result as "the peak
occurred after A" — it didn't; it occurred AT A. Correct framing: 50% of daily A's make their
maximum ON A itself (an **A-day excursion**), not that 50% have a meaningful **post-A excursion**.
RQ-EMAPB-04's FINDINGS text above should be read with this distinction in mind.

**RQ-EMAPB-05 construction approved as-is** (10-bar/1.5x translated to 1H, first-of-cluster
dedup) — explicitly NOT to be swept (1.2/1.3/1.5/1.7/2.0x) since the question is "does the
existing structural concept have a native 1H manifestation," not "which hourly threshold
performs best."

**Two required additions before running, per critic**:
1. **Record cluster length** per A (how many consecutive qualifying bars extend the same
   cluster) as a diagnostic field — NOT a filter. Large cluster-length share would indicate
   volume-confirmed hourly breakouts frequently behave as one extended impulse rather than
   independent events.
2. **Expand the reconstruction to expose whether the running-high-walk mis-segments the
   episode** — for every A, report: A bar/price, the first post-A local high (old "peak"),
   the TRUE maximum High over the full 300-bar window and its timestamp, whether that true max
   occurs at/before the local-pause point or strictly after it (i.e. whether the "local peak"
   undercounted a bigger move that came after a pullback+re-continuation), the existing
   continuation definition's result unchanged, and pullback depth. Do NOT change the
   continuation definition itself — this is auditing the population/method, not redesigning it.

**Pre-registered judgment framework (written BEFORE running, per standing discipline)** — no
fixed win-rate/profitability threshold, since the RQ's job is to establish whether the
phenomenon exists and at what speed, not to prove a strategy:

> RQ-EMAPB-05 will be judged descriptively, not by a fixed profitability threshold. The
> hourly-native branch remains alive only if it demonstrates (1) a non-trivial population of
> post-A continuation episodes, (2) measurable separation from an appropriate
> unconditional/baseline forward-movement distribution, and (3) a materially faster realization
> timescale compatible with the intended minutes-to-half-day options product. No parameter
> optimization or strategy promotion occurs from this RQ. If the hourly population simply shows
> more frequent noise, smaller excursions, and no meaningful conditional separation, the
> hourly-native branch is closed rather than rescued through threshold changes.

Explicitly NOT a valid gate: "hourly must beat daily" — they serve different products (daily =
medium-horizon swing continuation; hourly = fast continuation for options). Hourly can have a
lower win rate and smaller moves and still be the better research branch if realization is
dramatically faster.

**Sequence, per critic**: EMAPB-03 parked (semantically wrong population) -> EMAPB-04 established
the real daily-native multi-day timescale distribution -> EMAPB-05 asks whether the same
impulse/pullback/continuation mechanism has a legitimate, fast, 1H-native manifestation.

## RQ-EMAPB-05 result — closed, literal bar-count translation does not work (2026-10-04)

Built per the approved design (10-bar/1.5x translated to 1H, first-of-cluster dedup, cluster
length recorded, mis-segmentation diagnostic added). Script: `09_hourly_native_episode.py`.

- **Trigger count exploded**: 351,574 hourly-native A's vs. 6,400 daily A's — 55x more, 4.61% of
  all 1H bars. Root cause: a 10-BAR lookback is NOT a timeframe-invariant unit of structure — 10
  daily bars = 2 trading weeks of context; 10 hourly bars = under 2 trading days. Bar-count
  equivalence across timeframes != structural equivalence.
- **Mis-segmentation, exactly the failure mode the critic asked to check for**: the running-high-
  walk's "local peak" (first point extension pauses) is the TRUE max of the 300-bar window only
  10.5% of the time — 89.5% of the time the real max comes strictly later. The walk is catching
  routine 1-2 bar wiggles inside ongoing moves, not real tops.
- Cluster length: 79.7% isolated (not pathologically clustered) — the trigger-count explosion is
  a real property of the 1H-native definition, not a dedup artifact.

**Status: CLOSED.** A literal bar-count translation of the daily structural concept to 1H does
not represent "the same phenomenon, faster" — it represents a categorically different, far more
common, noise-dominated signal. Per the critic: "05 and 06 are not competing parameterizations —
05 asked whether a native 1H version of the entire phenomenon exists (no, under literal
translation); 06 asks whether the daily structural event conditions a useful short-horizon 1H
post-event state (a different, better-posed question)." Do not reopen 05 by sweeping the hourly
lookback/threshold (1.2/1.3/.../2.0x) — that was explicitly rejected as parameter-fitting, not
discovery.

## RQ-EMAPB-06 (proposed) — top-down multi-timeframe synthesis, user's idea, critic buy-in received

User's proposal, confirmed against literature (standard "top-down multi-timeframe analysis":
higher timeframe decides whether a move is real and what the structure is; lower timeframe
decides when to time entries within that confirmed structure — never the reverse) and approved
by critic with two required mechanics changes:

1. **Freeze `rq_emapb04_daily_episodes.csv` completely** — daily A/peak is NOT recomputed. Only
   rows with a valid (non-null) `peak_date` are used.
2. **No new algorithmic "hourly peak."** The running-high-walk just proved unreliable (89.5%
   mis-segmentation in RQ-EMAPB-05) — do not reuse it post-peak. `peak_high` (frozen from 04) is
   the sole structural reference. Measurement starts at the first completed 1H bar of the
   session STRICTLY AFTER `peak_date` (the daily event is fully closed first — this is why it is
   NOT the same error as the original RQ-EMAPB-03 same-bar-slicing bug).
3. Two reference prices kept explicitly separate per critic: **`peak_high`** (structural —
   where the move actually topped, known only in hindsight) vs. **the next session's first 1H
   bar's Open** (the tradable starting point — the earliest actually-actionable price). MFE/MAE
   computed relative to the tradable start, not the hindsight peak, to avoid manufacturing
   fake executable P&L.
4. **New baseline requirement (critic's point 4)**: post-peak 1H behavior must be checked against
   an UNCONDITIONAL 1H baseline on the same tickers (same mechanics: reference = a random day's
   daily High, start = next session's first 1H bar, same 300-bar window, same metrics) to confirm
   the daily conditioning adds real information beyond ordinary 1H price behavior — not just that
   some 1H metric is nonzero after a peak.

**Pre-registered judgment framework (written BEFORE running, per standing discipline)**:

> RQ-EMAPB-06 remains viable only if the frozen daily A/peak population produces a non-trivial
> post-peak 1H population in which (1) subsequent continuation/stabilization is measurably
> different from an appropriate unconditional 1H baseline, (2) the effect occurs on a timescale
> compatible with the intended options product, and (3) the daily structural conditioning
> provides meaningful information beyond ordinary 1H price behavior. No optimization or strategy
> promotion occurs from this descriptive RQ. 06 is not required to "beat" 05 — they test
> different hypotheses.

**Build plan**: reuse `rq_emapb04_daily_episodes.csv` unchanged. For each valid episode, start at
the first 1H bar of the session after `peak_date`; over a 300-bar window (same convention as
04/05, not re-tuned) report max pullback from `peak_high`, time to retrace 38.2/50/61.8% of the
A->peak move (diagnostic only, no gate), time to regain `peak_high`, resumed-within-window (bool),
MFE and MAE relative to the tradable start price. Baseline: same mechanics on randomly sampled
(ticker, day) pairs from the same ticker universe, NOT conditioned on being a daily peak — sample
size matched to the real population, fixed seed. Overlap between baseline sample and real
episodes expected negligible (~6,350 real episodes vs. ~1.4M ticker-days in the universe) and not
explicitly excluded.

## RQ-EMAPB-06 result — closed, population construction bug found via user chart review (2026-10-04)

RQ-EMAPB-06 (post-daily-peak 1H vs. unconditional 1H baseline) initially showed the real
population underperforming baseline on every metric (resumption rate, speed, MFE, MAE, pullback
depth). Before that could be treated as a finding, the user manually checked one episode (SRF)
against a real Dhan/TradingView chart and found the population's A was wrong.

**Root cause, traced to source**: `find_a_positions()` (`04_rq03c_define_b.py`), reused by every
EMAPB script via `10_rq_bpc05_volume_confirmed_a.py`, enforces a single-position-per-ticker walk
built for BPC's realistic trade-simulation purpose (can't hold two positions on one ticker). A
marginal trigger (vol_ratio barely 1.5x) blocks any new A for up to 15 trading days or until
stopped out. For SRF, a marginal Jan-7-2025 trigger blocked the real, violent breakout on Jan 9
(10.3M volume, 13.7% one-day gap) from ever becoming its own A -- it was absorbed into the
already-"open" Jan 7 position, which then closed purely via the 15-day timer, surfacing Jan 29 as
the next A (a re-acceleration deep into an already-extended move, not a fresh launch).

**Quantified population-wide**: of 20,477 consecutive same-ticker A-pairs (entry_definition=10),
13.8% are EXACTLY 15-16 trading days apart (the forced-timer signature, not a real stop-out);
49.9% occur within 20 trading days of the ticker's prior A; median gap 21 days. A large share of
the "A" population is not independently-selected fresh breakouts.

**User's key question**: EMAPB is pure pattern-discovery -- no position is being taken, no trade
simulated -- so there is no principled reason to inherit BPC's position-blocking machinery at all.
Critic agreed; RQ-EMAPB-06's conclusions are retracted pending a rebuild on an ungated population.
Likely explains the earlier result: late re-accelerations inside already-extended moves (the kind
position-blocking systematically creates) structurally resemble exhaustion more than launch
points, consistent with underperforming a random baseline.

**Status**: CLOSED pending RQ-EMAPB-07's ungated rebuild. Do not cite RQ-EMAPB-06's real-vs-
baseline numbers as a finding.

## RQ-EMAPB-07 — Episode Lifecycle Mapping (critic-specified, 2026-10-04) — pre-registered design

Objective: map the full lifecycle (Expansion -> Peak -> Pullback -> Consolidation ->
Resumption/Failure) on the CANONICAL population, rebuilt ungated. Descriptive discovery only --
no entries, exits, indicators, thresholds, or profitability. Decision rule at the end: does the
population show a sufficiently repeatable lifecycle to justify moving to 1H analysis of the
consolidation/resumption transition, or does this close EMAPB.

**Population**: same A definition, unchanged (`High[i] > max(High[i-10:i])`, `Volume[i] >= 1.5 x
mean(Volume[i-10:i])`), but NO position-blocking and NO 15-day lockout -- every qualifying day
retained. First-of-cluster days identified as episode starts; cluster length recorded as
diagnostic (same pattern as RQ-EMAPB-05), not a filter.

**Phase 1 (Expansion -> Peak)**: reuses the exact zero-parameter running-high walk from
RQ-EMAPB-04 (extend running high day by day; peak = first day extension fails). No new threshold.

**Phase 2 (Peak -> Pullback low), with user's 3-day box-confirmation + re-arm mechanism**:
mirrored running-low walk from the peak. A candidate stabilization day (first day that fails to
make a new low) must survive a literature-grounded 3-trading-day confirmation window (sources:
"a consolidation is three or more days of sideways price action... 3-5 bars is the minimum
duration commonly cited," distinct from stricter high-conviction-base frameworks like VCP's
15-25+ days -- this is the floor below which it isn't consolidation at all, not the ideal
duration) before being accepted:
- If the window is broken by a NEW LOW below the candidate -> REJECTED, re-armed: the running-low
  walk continues from that new low (decline wasn't actually done). Re-arm count tracked.
- If the window is broken by price exceeding the ORIGINAL peak_high -> REJECTED as "immediate
  continuation" (tracked as its OWN first-class category with its own characteristics, per user's
  explicit instruction -- not discarded, not merged into the confirmed-consolidation bucket).
- If neither happens for 3 full days -> CONFIRMED consolidation. Watched forward from there for
  eventual resolution: breaks the box low (failure) or regains peak_high (resumption, reusing the
  same already-established "regain the structural peak" definition from 04/06, not inventing a
  new consolidation-box-breakout rule) or neither before the window ends (unresolved).

**Phase 3 (Consolidation, confirmed cases only)**: raw descriptive stats only (range, ATR/range,
volume, higher/lower-low counts) over the confirmed-box span -- no EMA/Fib/box-shape rule.

**Outcome buckets** (critic's 5, mapped onto the state machine, tracked separately as the user
requested -- not merged):
1. Immediate continuation (box broken upward within the 3-day confirmation window)
2. Consolidation -> resumption (confirmed box, eventually regains peak_high)
3. Consolidation -> failure (confirmed box, eventually breaks box low)
4. Continued decline / no stabilization (running-low walk re-arms repeatedly through window end,
   never finds a surviving candidate)
5. Unresolved at data boundary (confirmed box, window ends before either resolution)

Window: 150 trading days post-peak (pre-declared, generous -- literature puts genuine bases at
4-12+ weeks, so a tight window would truncate real cases).

**Literature read before building (per user's request, "watching 1H breakout of the flag")**, for
later use once this RQ confirms the phenomenon -- NOT built yet: top-down MTFA applies here too
(daily = structure/direction, 1H = entry timing). Three concrete rules for watching a 1H breakout
of a daily-defined box: (1) candle CLOSE beyond the level, not an intrabar wick -- a close back
inside the range is the classic false-breakout signature; (2) volume surge on the breakout bar
vs. the preceding ~20 1H bars; (3) patience -- enter on the confirming close, not intrabar.
Hourly breakout failure still ~50% regardless -- this filters which breakouts to trust, doesn't
eliminate the base rate.

**Guardrails** (critic's, explicit): descriptive only; no trading performance, entry simulation,
stop/target, EMA rule, Fibonacci rule, fixed consolidation-duration optimization, F&O/liquidity/
NIFTY restriction; does not reopen previously-closed EMAPB experiments; daily A/peak remain the
higher-timeframe layer -- 1H is never used to redefine the daily A or daily peak.

## RQ-EMAPB-07 chart-audit corrections (2026-10-04) -- user checked 3 real examples (TCS, TATACONSUM, HILTON) on Dhan/TradingView before trusting the mechanical report

**TCS (real methodological gap, fixed)**: user visually spotted a 1H candle that pierced the box
level intrabar but closed back inside -- exactly the "close over wick" false-breakout signature
from the literature review earlier this session. The code's box-break/resolution checks were
using `High`/`Low` (the wick), not `Close`. **Fixed**: all state-transition checks (the running-low
walk's "new low" detection, the 3-day box confirmation, and the final Phase 4 resolution scan,
both the breakdown AND resumption sides) now require `Close` beyond the level, not an intrabar
wick poke. Descriptive extent fields (`max_retracement_pct`, range stats) still use the real
Low/High, since "how far did price actually reach" is a different question from "did the level
break." Phase 1 (peak-finding) is unchanged -- critic's spec explicitly defines the peak via High.

**TATACONSUM (not a bug -- documented data caveat)**: user's chart showed O763/H774/L758/C765 vs
our O773/H784.5/L767.4/C774.85 for 2022-11-01 -- every one of the 4 values sits ~1.3% below ours,
uniformly. A row-selection bug would not produce a clean uniform scaling across all 4 OHLC values;
a dividend-adjustment basis mismatch would. Confirmed against `data/README.md`'s own documented
caveat: "Adj Close is unreliable. Rows were written at different fetch times, so they carry
different dividend bases." Our cached row likely reflects an earlier (less-adjusted) basis than a
fresh pull/live chart would show today. Real, documented limitation -- not a row/date bug. Worth
remembering for any future precise price-level comparison against a live chart.

**HILTON (not a bug -- a presentation gap on our side)**: user's "convincing bar" was 2024-12-13
(Volume 2,058,323, range 92.82->104.70) -- confirmed present in the ungated population as its own
episode (first-of-cluster 2024-12-11, peak 2024-12-17 at 107.78, outcome=consolidation_resumption).
The earlier example shown to the user was a DIFFERENT, much weaker HILTON episode (A=2024-10-30,
vol_ratio only 3.28x but still real; peak=2024-11-01 at 93.00, outcome=consolidation_failure) --
user looked at the peak date expecting it to be the breakout day, when peak and A were 2 days
apart. Lesson: always present A-date and peak-date clearly separated, never implying they're
interchangeable. Checked liquidity too -- no near-zero-volume gap days for HILTON in Oct 2024, so
the user's separate "sparse trading inflates vol_ratio" hypothesis doesn't apply to this specific
ticker (though it's a real general risk -- SAYAJIHOTL elsewhere this session had Volume=1 days).

**New: A-day vol_ratio now tracked per episode (`a_vol_ratio` column)**, per user's explicit
request for "a good differentiator" between marginal triggers (TATACONSUM 1.64x) and genuinely
convincing ones (HILTON Dec-13 at a much higher ratio). Reported as a diagnostic tier breakdown
(1.5-2x / 2-5x / 5-10x / 10x+) against outcome rates -- NOT a filter, per this RQ's guardrails.

## Two further chart catches (GRASIM, BAJFINANCE) and a standing meta-concern raised by the user (2026-10-05)

Literature research on "ideal breakout candle shape" (Close Location Value / CLV, marubozu
criteria) led to testing CLV as a third factor. Formal randomization confirmed it is real but weak
(1.95pp spread vs volume ratio's 7.23pp). User asked for concrete counter-examples (bad CLV that
still resumed) to inspect by hand -- this surfaced two further, more basic catches:

**GRASIM 2025-12-08 is a RED candle** (Open 2747.00, Close 2744.20) being counted as "the
breakout." Quantified population-wide: **17.8% of all 112,556 A-days (20,080) are red/bearish
candles** -- days that satisfied `High > prior-10-day-high` and `Volume >= 1.5x` intraday but
closed below their own open. The canonical A definition never required a bullish close. Red vs
green A's show almost identical resumption rates (34.3% vs 35.2%) -- NOT a reason to dismiss the
issue (initially mischaracterized as such and corrected by the user) -- a red candle is not a
breakout by any human definition regardless of its downstream statistics. Fix proposed, not yet
built: require Close > Open (or Close > prior Close) for A.

**BAJFINANCE 2025-11-27** (CLV 67.4%, a "resumption") pulled back for 5 sessions to within 0.3% of
the A-day's own Low (1013.90 low vs 1010.90 A-day low) before recovering and closing above
peak_high on day 6. Current `consolidation_resumption` label treats this identically to a clean
move that never threatened the entry's own structural level. Fix proposed, not yet built: track,
per episode, whether Close ever drops below the A-day's own Low before resolution -- a
"clean vs. round-trip" quality dimension orthogonal to resumed/failed.

**Standing meta-concern, user-raised, to be taken to critic as its own item, not buried in this
RQ**: within this single session, five basic (not subtle) definitional errors were found in
quick succession: same-day peak bug (EMAPB-03), inherited position-blocking (EMAPB-06), wick-vs-
close resolution (TCS), no bullish-candle requirement (GRASIM), no structural-invalidation
tracking (BAJFINANCE). Each one, left uncaught, would read as "no signal" / "theory doesn't work"
in a final report -- exactly the pattern this project's own CLAUDE.md checklist exists to catch
(it is itself a running list of past instances of this same failure mode: wrong-day gate
evaluation, wrong exit engine, position-blocking bias, circular anchoring). User's explicit
concern: a full month of research repeatedly concluding "closed, no useful phenomenon" or
"inconclusive" may be substantially explained by this recurring error class contaminating
measurement, not by genuine absence of tradeable patterns, across threads well beyond EMAPB
(BPC, options_momentum, earlier EMAPB rounds). This needs to go to the critic as a standing
process question, not a one-off finding: does this warrant a targeted audit pass across prior
closed/negative RQs specifically for this narrow error class (bogus/non-confirming trigger
candles, wick-vs-close ambiguity, gating/position-blocking artifacts, lookahead leakage) before
any of them continue to be treated as genuinely closed.

## RQ-EMAPB-07, both fixes implemented (2026-10-05)

1. **Bullish-candle requirement (GRASIM fix)**: `find_episode_starts()` now requires `Close > Open`
   in addition to the existing breakout + volume conditions. Removes the 17.8% of the prior
   population that were red candles merely poking a new 10-day high intraday.
2. **A-day-low breach tracking (BAJFINANCE fix)**: new `a_low_breach_stats()` helper, called at
   every resolution point in `lifecycle()`, tracks the minimum Low reached from the day after the
   peak through resolution (or window end if unresolved), vs. the A-day's own Low. Reports
   `breached_a_day_low` (bool) and `min_low_vs_a_day_low_pct` (how close, signed). Applied to
   `immediate_continuation`, `consolidation_resumption`/`failure`/`unresolved_at_window_end`, and
   `continued_decline_no_stabilization` -- every outcome branch. New report section explicitly
   splits `consolidation_resumption` into clean vs. round-trip, per the user's direct question
   ("do you really think it's a good breakout continuation" for a resumption that nearly undercut
   its own entry low).
Script: `13_rq_emapb07_lifecycle.py`. Full rebuild (not an enrichment join this time, since the A
population itself changed).

**Population after the bullish-candle fix**: 94,708 episodes (down from 112,556 -- the expected
~17% removed), 2,099 tickers. Outcome mix essentially unchanged (consolidation_failure 47.3%,
immediate_continuation 26.6%, consolidation_resumption 25.6%) -- confirms red-candle removal was
a correctness fix, not one that was hiding or inflating the earlier aggregate findings.

**THE HEADLINE RESULT from the breach-tracking fix** -- the honest, stop-respecting picture,
using the single most natural stop level (the A-day's own Low):

| category | % of population |
|---|---|
| Clean win (never breached A-day Low, then continued/resumed) | **31.1%** |
| "Round-trip win" (breached A-day Low, THEN still eventually resumed -- a real stop would have been hit) | 21.1% |
| Outright failure | 47.9% |

Of all 24,209 `consolidation_resumption` episodes specifically, only 41.8% are clean -- **58.2%,
the majority, broke below the entry day's own low before eventually recovering**. The old binary
resumed/failed label was counting these as indistinguishable wins. This is a direct, concrete
illustration of Rule #20 (Risk Unit Integrity) -- once a stop is actually defined, a result that
looked like "roughly half the population continues" collapses to a real 31.1% clean-win rate,
cleanly separated from a 47.9% failure rate and a 21.1% "technically resolved up but any real
stop discipline would have exited first" group. Volume-ratio tier pattern (bigger spike = worse
outcome) is unchanged by either fix, confirmed robust a third time.

**Status**: descriptive, not yet promoted to critic as a finding -- the population/mechanics are
now materially more correct than the version already sent for the standing-process-concern
handoff. Next: send this updated picture to critic alongside (or as part of) that handoff, since
it both validates the user's concern (the fixes materially changed interpretation) and gives a
concrete, defensible number (31.1% clean win) for the first time this research family has
produced one.

## RQ-EMAPB-08 — Joint CLV x Volume (critic-specified, 2026-10-05) — YELLOW verdict: CLV survives, volume does not

Critic's call: test CLV and volume-ratio jointly before touching 1H timing or narrowing to
"clean winners" (explicitly rejected both as premature). Also retired the generic 30-chart-audit
plan after the user pointed out it doesn't match their real workflow -- replaced with an adaptive
"small representative chart packet" protocol (a handful of clean wins, failures, and round-trip
cases shown on request, OHLCV in full, A-date/peak-date separated; escalate only if something
looks wrong) for future use, standing going forward in place of any fixed-N chart audit.

**Test 1 (5x4 joint matrix, CLV quintile x volume-ratio bucket, n=94,172)**: CLV effect is strong
and monotonic within EVERY volume bucket (e.g. at 1.5-2x volume: 18.5% -> 35.1% clean win across
Q1->Q5; at 10x+ volume: 17.1% -> 38.7%). Volume's own effect within a fixed CLV quintile is
small and inconsistent (e.g. Q1: 18.5/19.1/19.9/17.1 across volume buckets -- essentially flat).

**Test 3 (independence check)**: Spearman rank correlation between CLV and volume ratio = 0.043
(p=9e-40, significant only because of n, practically zero) -- the two are NOT proxies for each
other; median CLV is ~0.71-0.73 regardless of volume bucket, median volume ratio ~2.8-3.1x
regardless of CLV quintile.

**CRITICAL CORRECTION, caught by this joint test**: the MARGINAL clean-win rate by volume bucket
alone (collapsing CLV) is 29.1% / 31.4% / 33.3% / 32.2% across 1.5-2x -> 10x+ -- essentially FLAT,
NOT the strong, monotonic "bigger volume = worse" pattern reported in RQ-EMAPB-07 and sent to the
critic in the consolidated handoff. Root cause: RQ-07's volume finding was measured against
`consolidation_failure` rate specifically (one narrow outcome slice), not the full stop-aware
clean-win metric. Volume ratio genuinely does shift which BUCKET an episode lands in
(immediate_continuation share falls, consolidation_failure share rises, as volume increases) --
but immediate_continuation and consolidation_resumption have very different internal
clean/round-trip breach rates, and these shifts happen to roughly cancel out once measured on the
metric that actually matters (clean win, stop-aware). **The "volume ratio is the second-strongest
confirmed signal" claim already sent to the critic is RETRACTED here and should be corrected in
any future reference** -- it was a metric-choice artifact, not confounding with CLV (ruled out by
Test 3's near-zero correlation) and not an illiquidity artifact (Test 4 below).

**Test 2 (incremental value, pre-declared broad combinations, population + lift together)**:

| group | n (% of pop) | clean-win | lift vs baseline (31.2%) |
|---|---|---|---|
| CLV favorable (Q4-Q5) | 37,669 (40.0%) | 37.5% | **+6.3pp** |
| CLV unfavorable (Q1-Q2) | 37,669 (40.0%) | 23.6% | **-7.6pp** |
| Volume lower (1.5-5x) | 69,558 (73.9%) | 30.6% | -0.6pp |
| Volume extreme (>5x) | 24,610 (26.1%) | 32.9% | +1.7pp |
| CLV favorable + volume lower | 27,403 (29.1%) | 36.7% | +5.5pp |
| CLV favorable + volume extreme | 10,262 (10.9%) | 39.6% | +8.3pp |
| CLV unfavorable + volume lower | 28,198 (29.9%) | 23.3% | -8.0pp |
| CLV unfavorable + volume extreme | 9,471 (10.1%) | 24.6% | -6.6pp |

CLV alone produces most of the lift in every combination; adding volume as a second condition
shifts the result by at most ~2pp in either direction and not in a consistent direction across
the two CLV groups -- no evidence it adds real incremental information.

**Test 4 (liquidity robustness)**: CLV effect holds, if anything slightly stronger, within the
top-liquidity tercile (n=31,391, median daily traded value ~Rs 49 crore): 20.3% (Q1) -> 43.9%
(Q5). Not an illiquid-tail artifact.

**Decision, per critic's pre-registered gate**: **YELLOW** -- "If only CLV survives and volume
adds little: keep CLV as the candidate signal and drop volume as a conditioning variable. Don't
force the combination." CLV is retained as the sole candidate A-day signal; volume ratio is
dropped from further conditioning (it may still be worth keeping as telemetry/context, but not as
a second filter dimension). Per critic's revised sequence, next step is a small representative
chart packet (not a 30-chart audit) of the CLV-favorable phenotype, then -- if that holds up --
1H timing of how quickly a clean, CLV-favorable continuation actually develops.

## RQ-EMAPB-08b — does the 1.5x volume GATE itself matter, even if magnitude above it doesn't? (2026-10-05)

User's follow-up, correctly distinguishing two different questions: RQ-08 tested "does MORE
volume beyond the 1.5x gate help" (no). It did not test "does clearing the gate AT ALL matter,
vs. below it." Built a comparison population with the volume floor relaxed to 0.3x
(`14_rq_emapb08b_novolfloor.py`, 136,730 episodes) to see the full curve.

| volume ratio | n | clean win |
|---|---|---|
| 0.3-0.75x | 12,735 | 26.2% |
| 0.75-1.0x | 12,946 | 26.3% |
| 1.0-1.25x | 13,450 | 27.8% |
| 1.25-1.5x (just below canonical gate) | 12,089 | 28.2% |
| 1.5-2x (canonical gate) | 19,130 | 29.2% |
| 2-5x | 42,347 | 31.3% |
| 5-10x | 13,717 | 33.4% |
| 10x+ | 9,651 | 32.1% |

**No cliff at 1.5x** -- a smooth, gentle, roughly monotonic climb across the entire range (26.2%
-> 33.4%), with a slight reversal at the very top (10x+ dips below 5-10x, consistent with the
extreme-move-as-exhaustion theme found elsewhere in this research). The 1.5x threshold is not a
special dividing line -- 1.0x or 2.0x would show essentially the same gradual slope. Real, but
minor (~6-7pp full-range spread) next to CLV's ~19pp spread. Conclusion unchanged from RQ-08's
YELLOW verdict: CLV is the dominant signal; volume (gate included) is a minor, continuous,
non-threshold-like factor, not worth a second hard filter dimension.

## RQ-EMAPB-09 -> 09b: entry-anchoring correction, then a bigger structural catch (box_high), 2026-10-05

RQ-09 (critic-specified) measured the 1H path starting right after A -- found favorable CLV shows
a materially better EARLY path (better MFE from hour 1, reclaims A-day's own High in a median of
2h vs 16h for unfavorable) but NO speed advantage on "making a new episode high." User correctly
objected: this measures PRE-ENTRY behavior -- the user's actual strategy enters only after a base
forms and breaks, so everything before that break is irrelevant noise, and `immediate_continuation`
episodes (no base ever forms) aren't the user's setup at all.

**RQ-09b, entry-anchored correction**: restricted to `consolidation_resumption` only (the only
outcome with a real upward base-break at all), located the exact 1H bar where the daily-confirmed
resolution happens, entered at the next bar's Open, and measured MFE/MAE from THERE. Result:
**CLV shows almost no effect post-entry** -- all three CLV groups statistically identical on
MFE/MAE at every time bucket, and identical post-entry stop-out risk (~6-7%, measured over the
first ~4 trading days post-entry only). Hand-verified two examples (INFY, TITAN) bar-by-bar
against raw 1H data -- mechanics confirmed correct. **Conclusion: CLV predicts WHETHER/HOW FAST a
tradeable setup develops at all (real, large effect, established in RQ-07/08) but NOT the quality
of the trade once the entry signal actually fires (no effect) -- belongs in scanning/selection,
not position sizing.**

Classic D1 metrics (open/close/peak/MAE), pooled across all entry-anchored trades (n=12,912,
CLV ignored since it doesn't differentiate post-entry): D1 open median +0.6-0.8%, D1 close median
+0.4-0.7% (both ~57-67% positive), D1 peak reaches >=0% 90.3% of the time, >=2% 59.2%, >=5% 25.8%
-- same "big peak, close gives it back" shape found throughout this entire project. D1 MAE: half
of all trades see at least -2% intraday drawdown on day 1 alone, 11.7% see worse than -5%.

**BIGGER CATCH, found while reviewing the INFY/TITAN charts**: the resolution trigger used
throughout RQ-07/08/09 (`Close > peak_high`) is WRONG. Standard breakout logic is "buy the break
of the BASE," not "wait to re-exceed the entire original move's peak." Once a base is confirmed,
its own high (reached during the base's own 3+ day consolidation) -- which can sit meaningfully
below the original, often much higher and harder-to-reach peak_high -- is the real, actionable,
much earlier breakout level. This affected every resolution timing computed so far (TITAN's
13-trading-day resolution was measuring time-to-reclaim-the-ORIGINAL-peak, not time-to-break-the-
base, which likely happened days earlier and was never detected).

**FIXED in `13_rq_emapb07_lifecycle.py`**: added `box_high` (max High over the confirmed box span,
already available from the existing range_width_pct computation) as a new field; the
`consolidation_resumption` trigger now checks `Close > box_high`, not `Close > peak_high`.
`peak_high` is retained as a secondary/reference field only. Rebuilt the full pipeline.

**Effect of the box_high fix on the population**: consolidation_resumption rose 25.6% -> 34.8%,
consolidation_failure fell 47.3% -> 38.4%, median time-to-resolve dropped 6 -> 4 days. CLV finding
re-confirmed, slightly stronger: Q1 19.5% -> Q5 40.2% clean-win (20.7pp spread, was 17.6pp).
RQ-09b re-run with corrected box_high entry: same conclusion (CLV irrelevant post-entry), post-
entry stop-out risk rose 6-7% -> 11-12% (expected: earlier/lower entry leaves more give-back room).

**NEW FINDING -- gap-fade, formally confirmed**: pooled D1 analysis (n=18,328 entry-anchored
trades) bucketed by D1 open-gap size, measuring open-to-close return: gap down >2% -> median
open-to-close +0.92% (60.6% pos); gap up >2% -> -0.83% (35.9% pos). Clean, monotonic across all 7
buckets. Permutation test: observed spread 1.82% vs null p95 0.48%, p=0.0000. Independent of CLV
(measured post-entry, where CLV has no effect) -- a genuinely new, separate D1-level signal.

## CLV promoted from descriptive bucket to population GATE (2026-10-05) -- TATAN catch

User caught a concrete case (TITAN A=2025-01-07, CLV=0.22 -- 78% of the day's range was upper-wick
rejection, barely closed green) and pushed back: a candle like this shouldn't count as "a
breakout" at all, not just get flagged Q1 after the fact. Tested the population-adjusted effect of
making CLV>=0.80 (the literature's own "strong" threshold, not picked post-hoc) part of the A
DEFINITION rather than a downstream bucket:

| CLV gate | population retained | clean-win rate | lift |
|---|---|---|---|
| None | 94,449 (100%) | 32.7% | -- |
| **>=0.80** | 33,789 (35.8%) | **40.0%** | **+7.2pp** |
| >=0.85 | 24,191 (25.6%) | 40.3% | +7.6pp |
| >=0.90 | 14,310 (15.2%) | 39.6% | +6.9pp |

Clear plateau right at 0.80 -- tighter gates cost population for no further lift. **Decision:
promote CLV>=0.80 to a hard requirement for A**, not just a comparison bucket.

**Gated population (CLV>=0.80), final state for tonight**: n=33,789, 2,066 unique tickers,
2021-09-14 to 2026-09-18. Outcome mix: consolidation_failure 37.0%, consolidation_resumption
35.4%, immediate_continuation 27.6%. Result3: clean_win 40.0%, failure 37.0%, round_trip_win
23.0%. **Year-by-year clean_win (no pooling)**: 2021=38.2%, 2022=38.3%, 2023=48.1% (standout),
2024=37.1%, 2025=35.7%, 2026=39.9% (partial year) -- stable across years, no regime decay, not
driven by one outlier year.

## STATUS, end of session 2026-10-05 -- honest assessment, not yet a tradeable strategy

What's established and reasonably solid: (1) the canonical ungated population with bullish-candle
+ box_high-correct resolution; (2) CLV>=0.80 as a validated, population-adjusted entry-quality
gate (+7.2pp clean-win lift, stable across years); (3) post-entry trade quality is independent of
CLV -- stop/target design doesn't need to vary by candle quality; (4) gap-fade as a new, separate,
confirmed D1-level signal not yet integrated into anything.

What's still missing before this is a strategy, not just a discovery result: a real, defined
stop-loss and target (R-unit still undefined per Rule #20 -- box_low is the natural stop
candidate but has not been formally adopted); an actual entry execution rule at 1H/intraday
resolution (we know WHEN the daily base breaks, not yet how to time a real intraday order); the
gap-fade finding is not yet folded into any exit logic; no option-economics pass at all (strikes,
IV, theta, realistic slippage); the small representative chart-packet sanity check (critic's
revised protocol, replacing the 30-chart audit) has not been done on the CLV>=0.80 gated
population specifically. Next session: send this consolidated state to critic, get direction on
sequencing the remaining pieces before calling anything a strategy.

**Small representative chart packet, CLV>=0.80 gated population** (critic's revised protocol):
2 clean wins (INFY 2024-07-12->peak 07-19, ITC 2022-07-01->peak 07-04), 2 failures (WIPRO
2026-08-31, CLV=1.000 -- a textbook-perfect candle that still failed; TCS 2024-12-05), 2
round-trip wins (CIPLA 2021-10-27, TATASTEEL 2024-09-24). INFY hand-verified bar-by-bar against
raw daily data -- exact match on CLV, peak, box_high, box_low. Not yet reviewed by the user.

**Final D1 sweep, CLV>=0.80 gated + box_high-corrected entries, n=6,708**: D1 open median +0.70%
(67.7% positive), D1 close median +0.55% (58.6% positive), D1 peak median +2.41% (reaches >=2%
55.6% of the time, >=5% 21.3%), D1 MAE median -1.07%. Same shape as the ungated sweep (expected,
since CLV doesn't change post-entry behavior) with a modest overall improvement (open/close
positive rates both up ~2pp, MAE slightly better). This is the final number set for the session --
the gate's value is in getting to a trade at all (40.0% vs 32.7% clean-win), not in reshaping the
trade once you're in it.

**Session closed here 2026-10-05.** Consolidated critic handoff already sent (box_high fix +
gap-fade + CLV-as-gate decision + 5-item missing-pieces list). Next session: read critic's
sequencing response first; do not re-derive or re-litigate tonight's results without new reason.

## Morning chart review 2026-10-06: trend-context question + two new observations logged

**WIPRO and CIPLA, both CLV>=0.80 examples from the chart packet, both rejected hard at the daily
EMA34.** User's question: is a breakout even valid if the trend-defining EMA sits above a
declining price? Literature confirmed this is one of the most basic trend-filter rules in the
field -- Minervini's Trend Template (built on Weinstein's Stage Analysis) requires price above
50/150/200-day MAs in rising alignment before a breakout counts at all; empirically "99% of
superperforming stocks traded above their 200-day MA, 96% above their 50-day MA" before their
gains; Weinstein only buys breakouts in Stage 2 (advancing), never Stage 4 (declining, which is
what WIPRO's chart shows -- multi-month decline from ~195 to ~160, EMA34 above and still sloping
down). This is a different, complementary dimension from CLV (candle quality) and volume (trigger
strength) -- it asks whether the backdrop is favorable at all, not whether this specific candle
is well-formed. Next test: price vs. daily EMA34 (and EMA34's own slope) at A, independent of and
then combined with the existing CLV>=0.80 gate.

**Two new observations logged, NOT yet tested/filtered on** (ITC, INFY chart review):
1. The actual base-break hour is often concentrated in the first 1H bar (9:15) of the breakout
   session -- ties into the already-known D1-open-heavy pattern (median D1 open +0.70%, 67.7%
   positive) but worth its own look later.
2. Day-over-day volume jump (breakout day's volume vs. the SINGLE prior day) can look unremarkable
   even when the 10-day-average ratio clears 1.5-2x+, if the preceding several days were already
   on a rising volume trend (ITC: Jul 1 breakout 36.5M vs Jul 30's 20.0M = only ~1.83x day-over-
   day, despite comfortably clearing the 10-day-average gate; Jun 27-30 were already climbing
   8.5M->11.7M->16.6M->20.0M beforehand). A genuine volume spike arguably should look
   discontinuous against the immediately preceding day, not just like the tail of an
   already-accelerating run. Candidate future diagnostic, not yet built.

## Three literature-grounded trend/extension tests (2026-10-06), triggered by the WIPRO/CIPLA chart catches

User asked to go beyond the single EMA34 proxy (chosen only because it happens to be on their
chart) and test what the literature actually specifies. Also asked whether "is this just an
extension of an existing uptrend, not a fresh breakout" has a named measure (RSI/ADX etc).
Literature read before building: Minervini's exact Trend Template (price above 50/150/200-day MA
in 50>150>200 alignment, 200-day MA rising >=1 month, price >=30% above 52-week low, within 25% of
52-week high); O'Neil's chase rule (buy within 5% of the pivot, 15%+ past it is "chasing," flagged
as materially worse risk/reward); ADX as the literature's answer to fresh-trend-start (rising
through 20-25, backtested to precede 8%+ moves 61% of the time over 10 years) vs exhaustion
(>=40-50 and turning down).

**Test 1 -- Minervini full template** (n=76,515, needs 200d+ history): pass=35.5% clean-win vs
fail=31.5% -- real but modest (~4pp), weaker than hoped, not obviously better than the simple
EMA34 proxy already logged.

**Test 2 -- ADX, BOTH closed negative, literature does not hold up in this data**: "fresh"
(ADX crossing 20-30 from below 20) shows no edge (31.9% vs 33.0%, if anything worse). "Exhausted"
(ADX>=40) shows the OPPOSITE of the textbook prediction -- 35.3% vs 32.6%, supposedly-tired
trends do BETTER. Consistent with how often textbook exhaustion/quality signals have inverted in
this research family. CLOSED.

**Test 3 -- O'Neil extension-from-pivot ((Close_A / prior_10d_high - 1)), the real finding,
properly reconciled**: raw clean-win rate rises monotonically and steeply with extension (25.6%
at <0% up to 44.8% at 10-15%, formally confirmed: 18.27pp spread vs 1.66pp null ceiling,
p=0.0000). Confirmed genuinely incremental, not just CLV restated (correlation rho=0.59, but the
gradient survives fully within BOTH CLV<0.80 and CLV>=0.80 bands separately). Combined gate
CLV>=0.80 + extension>=5%: 45.0% clean-win, +12.1pp over baseline, on 7.3% of population.

**R-multiple reconciliation (user's explicit ask, since probability != risk-adjusted reward,
Rule #21)**: merged with the entry-anchored population (n=17,430), stop = box_low (the confirmed
base's own low, the same reference used throughout this research). R-unit (risk %, entry to stop)
GROWS with extension: 6.68% (<0% extension) -> 9.76% (>10% extension) -- the stop doesn't move
with a more-extended entry price, so a bigger chase costs proportionally more risk. Once reward is
measured AS a multiple of that risk: median R-mult(MFE) at Day+3 actually DECLINES slightly with
extension (+0.54R at <0% down to +0.47-0.48R at >10%) -- the earlier "more extension is better"
result evaporates once risk-adjusted. One genuine upside for extended entries: % hitting a full
-1R loss within 3 days is lower (3.8% vs 7.9%), a somewhat better-behaved downside tail.

**Resolution**: extension-from-pivot raises the PROBABILITY of an eventual clean win but does NOT
improve (and mildly worsens) the RISK-ADJUSTED reward, because the required stop widens
proportionally with the chase. This is exactly what O'Neil's "don't chase" rule protects against
-- not a lower win rate, a worse reward for the risk taken. The two tests (win-probability,
R-multiple) are NOT in conflict once each is read for what it actually measures. **Decision:
extension-from-pivot is NOT promoted as a gate** -- it roughly cancels out once risk-adjusted. CLV
remains the only factor that is unambiguously good news on both counts (better win probability AND
no post-entry R penalty, since CLV was already shown to have zero post-entry effect).

## Critic's independent verification + RQ-EMAPB-09A daily-setup audit (2026-10-06)

**Critic independently checked both literature claims before accepting our read**:
- ADX: narrowed our claim -- literature does NOT say "ADX>=40 means exhausted and will fail,"
  that's too strong; ADX measures trend STRENGTH, exhaustion is about a high ADX rolling over, not
  a static high value. Correct verdict: "static ADX>=40 does not identify a worse continuation
  population, so it's not a useful gate" -- NOT "ADX exhaustion theory is false" (different,
  unproven claim). RED on the gate specifically; not pursuing another ADX variant.
- O'Neil extension: GREEN, hypothesis reconciled, called the more interesting finding of the two.
  Confirmed O'Neil's actual material says don't buy >5-10% above the pivot because risk/reward
  deteriorates -- our R-multiple result is exactly that mechanism (worked example: pivot Rs100,
  stop Rs93 = 7% risk; same stop after a run to Rs110 = 15.5% risk -- paying more for a
  higher-probability setup because the stop didn't move with the extended price). Not adding an
  extension gate -- the research value is in holding both facts at once (extension is a real
  strength signal AND a worse entry-price problem), not forcing a single filter decision.
- Bigger-picture framing: don't go shopping for another trend indicator. The better question
  WIPRO/CIPLA actually raised is structural -- does EMAPB require an already-established uptrend,
  or can the expansion itself BE the transition into one -- not "EMA34 yes/no." Provenance matters:
  this whole test battery came FROM a chart catch, not a pre-planned indicator sweep, and that
  order should stay visible in how this gets written up.

## RQ-EMAPB-09A -- Daily setup semantics audit (critic-specified, before any 1H trigger design)

On the CLV>=0.80, valid-daily-box population (outcome=consolidation_resumption, n=6,709 with 1H
coverage):

**A. Timing + mechanism of the first qualifying resumption** (Close > box_high, 1H-localized):

| bar position in session | % of resolutions |
|---|---|
| 1st bar (9:15) | **53.2%** |
| 2nd bar | 13.5% |
| 3rd bar | 9.5% |
| 4th+ bar | 23.8% |

Over half of all resolutions happen in the very first hour. Critically, of those 1st-bar cases,
only 44.5% are gap-opens (Open already above box_high) -- the majority (55.5%) are genuine
INTRABAR moves, opening below/at the box high and closing above it during that first hour's real
trading (2nd/3rd/4th+ bar cases are ~93-94% intrabar, as expected). This is the single most
important input yet for eventual 1H entry-timing design: most of the opportunity window is the
first hour, and most of that first hour is real, watchable, reactable price action, not a
pre-decided gap.

**B. Volume character -- ITC's divergence confirmed real but rare**: Spearman correlation between
the existing 10-day-average ratio and a day-over-day (vs. single prior day) ratio = 0.717 --
mostly the same information, not two different populations, as the critic anticipated. Only 7.7%
of the gated population clears the 10-day gate without a genuine day-over-day jump (>=1.2x); 85.5%
show both. But that 7.7% minority (n=511) DOES perform meaningfully worse: 36.2% clean-win vs
43.8% for the rest -- a 7.6pp gap, confirmed via formal randomization (p=0.0010, though with a
closer null margin than CLV/extension given the small subgroup size). Per critic's framework
("mostly the same population -> probably just color, but check"): confirmed as real, rare color,
not a systemic gate problem. Candidate cheap micro-filter (cost: only 7.7% of an already-small
population) -- not yet adopted, flagged for critic's call.

**C. Trend context**: kept descriptive only per critic's instruction, not re-run as a gate this
round (EMA34/Minervini components already tested in the prior section).

**Status**: RQ-09A complete, sent to critic alongside the ADX/O'Neil reconciliation. Per critic's
sequencing, RQ-09 proper (the actual 1H resumption-trigger discovery, now informed by the
53.2%-first-bar / 55.5%-intrabar finding) is next.

**Critic's verdict on 09A**: A is the important finding, move straight to RQ-09 proper. B
(day-over-day volume) parked explicitly -- "a filter can be cheap in population terms and still
be useless or harmful once we define the actual 1H entry and risk" -- confirmed secondary
observation, not adopted, revisit after a trigger is actually defined. No new RQ for B right now.

## RQ-EMAPB-09 proper -- first-hour mechanics of the daily-box resumption (2026-10-06)

Critic's explicit guardrail: `Close > box_high` was only ever used to LOCALIZE timing in 09A --
this RQ does not assume it's the right execution event, and investigates what actually happens
around that moment before any trigger is proposed. 1H observation starts once the daily box is
CONFIRMED (box_span_end = consolidation_start + 3 days) -- granularity-consistent, since the
daily state is fully settled at that point. Population: CLV>=0.80, valid daily box, n=6,709.

**Opening position at the cross bar**: 25.2% gap above box_high, 74.8% cross intrabar (inside the
box at that bar's open, breaks through during the bar).

**Hold vs. reject in the 3 bars after the cross -- overall essentially a coin flip**: 50.7% hold
(never dip back below box_high), 49.3% get rejected at least once. The daily-confirmed Close >
box_high event is NOT, by itself, a stable 1H-level signal -- confirms the critic's guardrail was
warranted.

**Split by timing, the coin flip resolves sharply -- the headline result, one of the largest
effects found in this entire research program**:

| | n | hold rate | reject rate |
|---|---|---|---|
| First-hour cross | 1,870 | **69.5%** | 30.5% |
| Later-hour cross | 4,839 | **43.4%** | 56.6% |

Formally confirmed: 26.08pp observed spread vs 2.58pp null p95 ceiling (2000-permutation test),
p=0.0000 -- ~10x the random-chance ceiling. A later-hour cross is actually worse than a coin flip.

**MFE/MAE comparison -- the distinguishing factor is reliability, not reward size**: first-hour
crosses show SMALLER median MFE in the first few hours (1H +0.34% vs +0.47% for later-hour; 3H
+0.57% vs +0.92%), converging by ~Day+2 (+2.93% vs +2.91%). So first-hour crosses aren't bigger
winners -- they're far less likely to shake you out before the move plays out. MAE is similar or
slightly better for first-hour crosses throughout.

**Practical implication for eventual trigger design**: a later-hour cross should be treated as a
meaningfully weaker/riskier signal, not an equally valid alternative entry to a first-hour cross --
timing-of-cross is now a real, large, confirmed conditioning variable on top of CLV, independent
of reward magnitude. No trigger proposed yet, per guardrail -- this is still descriptive. Sent to
critic alongside this update.

**Critic's verdict on RQ-09 proper**: move toward trigger definition, but via one tightly-scoped
semantic step first -- NOT a broad "why do later crosses fail" investigation (explicitly declined,
the later-hour result is already actionable as a research constraint without a causal
explanation). Specified RQ-10A: restrict to the 1,870 first-hour-cross episodes only, characterize
the earliest observable transition distinguishing the 69.5% holds from the 30.5% rejections. No
threshold optimization, no trigger proposed yet -- descriptive distributions only.

## RQ-EMAPB-10A -- first-hour resumption geometry, candidate trigger event (2026-10-06)

Resolution caveat stated up front: our data is 1H OHLC, not sub-bar/tick -- literal intra-hour
sequencing of touch/high/close (critic's phrasing) is not directly observable. What IS
observable: the cross bar's shape relative to box_high, and the immediately following bar's
behavior. Population: the 1,870 first-hour-cross episodes from RQ-09.

**Cross-bar geometry, held (69.5%) vs rejected (30.5%) -- a genuinely distinct signature, visible
during the cross hour itself**:

| field | held | rejected |
|---|---|---|
| Open vs box_high | **+1.20%** | **-0.49%** |
| Low vs box_high | +0.22% | -1.15% |
| High vs box_high | +3.59% | +1.41% |
| Close vs box_high | +2.43% | +0.54% |
| Body % of range | 59.8% | 51.6% |
| Dipped below box_high at any point intrabar | **45.1%** | **87.2%** |

Two standout signals: (1) held cases decisively GAP ABOVE box_high at the open (+1.20% median);
rejected cases typically open BELOW box_high (-0.49%) and have to climb during the hour -- known
the instant the cross bar opens. (2) 87.2% of eventual rejections dip back below box_high at some
point during that very first hour (vs only 45.1% of holds) -- a shaky, back-and-forth first hour
is a real warning sign even when it still technically closes above the level.

**Immediate next-bar check -- held side is partly circular (held_3bars is defined as the next 3
bars never dipping below box_high, so ~100% of held cases trivially satisfy bar 1 of that), but
the rejected side is genuinely informative**: only 27.5% of eventual rejections still have their
very next hour's Low above box_high -- 72.5% of eventual failures reveal themselves within just
ONE MORE HOUR after the cross, well before the full 3-bar window closes.

**All three standout fields formally confirmed** (2000-permutation test): open_vs_box_pct
p=0.0000 (observed 18.51 vs null p95 6.53); dipped_below_box_intrabar p=0.0000 (0.421 vs 0.048);
post_pullback_pct (next bar's low vs box_high) p=0.0000 (18.77 vs 6.17).

**Status**: a clean event has emerged -- per critic's own decision rule ("if a clean event
emerges, define the candidate trigger"), next step is defining the candidate trigger from these
geometric signals (gap-above-open and/or no-intrabar-dip-below-box, confirmed within ~1-2 hours).
Sent to critic for that call.

**Scope reminder, explicit, confirmed by critic**: deprioritizing the later-hour-cross population
(43.4% hold) in favor of first-hour geometry is sequencing, NOT a negative verdict. 43.4% is
non-trivial, not noise. The later-hour branch stays on the research ledger, to be revisited once
first-hour trigger mechanics are understood -- and when revisited, the question should be whether
it contains a DIFFERENT valid resumption mechanism, not an attempt to force it into whatever
first-hour trigger gets defined. RQ-10A (first-hour geometry, already built and sent) remains the
single next action per critic -- awaiting their substantive call on the trigger definition itself.

**Critic's verdict on the candidate trigger**: B confirmed as the candidate ("breach -> no
immediate give-back below the structural level" -- a clean structural interpretation, not an
arbitrary indicator). C explicitly downgraded to "possible confirmation/management concept later,
not the primary trigger" -- it buys only 3.4pp for an extra hour of delay, wrong tradeoff for a
fast product, and changes the nature of the event (continued acceptance vs initial acceptance).
Construction concern flagged and accepted: B is only knowable at the END of the cross hour, so any
real execution must act at the first opportunity AFTER the hour closes, never backdated to the
intrabar cross moment. B's exclusion of "penetrates then touches/re-enters the level, closes
strongly above anyway" cases is the hypothesis being tested, not a bug -- stated explicitly.
Explicit instruction: no threshold variants on B yet (0.1%/0.25%/0.5%/close-location/body-size/
volume), that would be threshold fishing before establishing whether B vs B-fail is genuinely
meaningful. Next: RQ-10B, B-pass vs B-fail complement validation, specifically checking whether
B-fail ever recovers (critic's explicit framing: B-fail is NOT "rejected," it's simply "the
complement of the proposed first-hour trigger," per the project's ledger discipline).

## RQ-EMAPB-10B -- B-pass vs B-fail complement validation (2026-10-06)

Same n=1,870 first-hour-cross population, split by the already-defined B rule (cross-hour Low
stays above box_high the whole hour, vs dips below at some point):

| group | n | % of pop | 3-bar hold |
|---|---|---|---|
| B-pass | 753 | 40.3% | **92.2%** |
| B-fail | 1,117 | 59.7% | 54.3% |

**B-fail is NOT garbage** -- 54.3% still hold, formally confirmed real (37.91pp observed spread
vs 4.33pp null p95, p=0.0000). Per critic's explicit instruction, NOT labeled "rejected" --
labeled the complement of the B trigger.

**MFE/MAE, same reliability-not-reward-size pattern as RQ-09**: B-pass shows SMALLER early MFE
(1H +0.10% vs B-fail's +0.48%) but converges/slightly exceeds by Day+2 (+3.29% vs +2.81%) --
consistent with B-pass being the more reliable, not the higher-reward, path.

**The recovery split inside B-fail -- the largest effect size found in this entire research
program**: does B-fail's price come back above box_high within just 1 more hour?

| B-fail sub-group | % of B-fail | 3-bar hold |
|---|---|---|
| Recovers above box_high within 1 more hour | 65.4% | **82.9%** |
| Still below box_high after 1 more hour | 34.6% | **0.3%** |

Formally confirmed: 82.62pp observed spread vs 5.95pp null p95, p=0.0000 -- essentially a perfect
separator. B-fail is not one population -- it's two wildly different ones, and the "quick
recoverer" sub-population (82.9% hold) is almost as reliable as clean B-pass (92.2%).

**Practical implication, not yet adopted as a trigger change -- flagged for critic**: combining
B-pass with "B-fail but recovers within 1 hour" captures ~79% of the whole first-hour-cross
population (753 + 731 of 1,117 = 1,484 of 1,870) at a blended hold rate around 87-88%, while the
remaining ~21% (dips below and stays below for a full hour) is a near-automatic reject (0.3% hold).
This is materially more inclusive than B alone and may reshape the trigger definition itself, not
just validate B as a standalone rule -- sent to critic for that call, no threshold variants built
yet per standing instruction.

## CORRECTION -- the B-fail recovery split (82.9% vs 0.3%) was contaminated by overlap, user caught it (2026-10-06)

User asked directly: "how much of this is look-ahead, or something decided after entry." Traced
the exact code and confirmed a real, significant circularity, NOT a minor nuance:

`post_held` (the classifier for "recovers within 1 more hour") checks bar `cross+1`. `held_3bars`
(the outcome it was compared against) checks bars `[cross+1, cross+2, cross+3]` -- bar `cross+1`
is literally the FIRST of the three bars in both. So "still below at cross+1" (post_held=False)
makes held_3bars=False MECHANICALLY GUARANTEED (one of three ANDed conditions already failed) --
the reported "0.3%" was never a discovery, it was supposed to be exactly 0% by construction, using
the same bar as both predictor and part of the outcome. The "recovers -> 82.9%" side was also
inflated (recovering at cross+1 guarantees 1 of 3 required bars, not all 3).

**What does NOT need correction**: the original B-pass vs B-fail split (92.2% vs 54.3%) has no
such overlap -- B is classified purely from the cross bar itself (bar 0); held_3bars is measured
purely from bars 1,2,3 AFTER it. That comparison stands as reported.

**Corrected recovery-split result**, using a clean, non-overlapping outcome window (bars
cross+2,3,4, excluding the classifying bar cross+1 entirely):

| | n | clean 3-bar hold (non-overlapping) |
|---|---|---|
| Recovers at bar cross+1 | 730 | **77.4%** |
| Still below at bar cross+1 | 387 | **16.0%** |

Still real and substantial (observed spread ~62.68pp vs null p95 ~6.14pp, p=0.0000) -- but NOT
the near-perfect 82.9%-vs-0.3% separator originally reported. The "still below" group is not a
near-automatic reject -- roughly 1 in 6 still goes on to hold cleanly. Retraction sent to critic
immediately. Standing lesson: any classifier built from bar X must be checked against an outcome
window that does NOT include bar X, every time -- this is the same family of mistake Rule #22
exists to catch (hand-verify surprising aggregates, check for mechanically-impossible-or-guaranteed
results before trusting them). A ~0% or ~100% result is a red flag to check for exactly this kind
of overlap before reporting it as a finding.

## Pivot: critic agreed we zoomed too far on B; A promoted as the primary starting candidate (2026-10-06)

User directly challenged why B was getting so much attention when A (broader, knowable
immediately at the open, 84.2% hold on 53.6% of population vs B's 92.2% on 40.3%) might be the
better starting point for an actual tradable product -- critic agreed fully ("we zoomed in too
far on B"), named the trap being avoided (92%->95%->97%->98% while the usable population shrinks
to near-nothing), and reset the sequence: build Candidate Strategy v0.1 on A, test tradability
(entry price, MFE/MAE, speed, failure rate), THEN deliberately study failure scenarios -- the
user's own proposed workflow. B and the recovery branch stay on the ledger as secondary/refinement
candidates, not discarded.

**User's own follow-up clarification, verified**: A and B are NOT two independent alternatives --
B is a strict mathematical subset of A (Low <= Open always, so Low>box_high implies Open>box_high;
confirmed 0 counterexamples in the data). The real, non-overlapping 3-way split: B-pass (gapped
AND never dipped) n=753, 92.2% hold; A-pass-but-B-fail (gapped, then dipped) n=249, 60.2% hold;
A-fail (no gap, climbed from inside the box) n=868, 52.5% hold. A's 84.2% headline is a blend of
the first two. Since B is only knowable in hindsight (not at entry time), the user's practical
conclusion -- just trade A, since you can't pre-filter for B anyway -- is sound.

**Volume side-question -- real data-quality catch**: tested whether the breakout hour's OWN
volume (not the already-tested daily vol_ratio) predicts B-pass vs dip. Found 83-85% of
first-of-session 1H bars have Volume<=0 across every ticker checked (TITAN, HILTON, TCS, INFY,
RELIANCE) -- a pervasive, systematic gap in `data/intraday_60m`, NOT random noise. This does NOT
affect any already-confirmed result in this research line (all were OHLC-based, never 1H Volume),
but it means hour-level volume as a predictor is currently untestable with this dataset, not
disproven. Flagged for whoever maintains the intraday_60m cache. Using the reliable proxy instead
(the A-day's own daily vol_ratio, already validated data): flat, no relationship with B-pass rate
across quartiles (72.9%-77.2%, no trend) -- consistent with RQ-08's earlier finding that volume
magnitude adds little once other factors are controlled.

## RQ-EMAPB-11A -- Candidate A execution mechanics: gap vs first pullback (critic-specified, 2026-10-06)

Population: 1,002 A-pass first-hour crosses. Pre-registered per critic: gap entry = opening price
of the cross hour; pullback reference = 1H EMA8 (pre-existing convention, not invented post-hoc,
and decision-time-safe -- uses the EMA8 level known BEFORE each bar starts via shift(1), not a
same-bar value that would use that bar's own unclosed price); pullback event = first of the next
3 completed 1H bars whose Low touches/crosses EMA8 (touch only, no close-below-reclaim
requirement); window = 3 bars, fixed, not chosen after results. Three populations per critic's
explicit correction (not a naive immediate-vs-EMA two-way comparison, since EMA-offered is
selected after the fact).

**1. Gap economics**: median gap is 2.00% above box_high. MFE from box_high by ~Day+2 is +7.89%,
but MFE from the actual gap-open entry is only +3.77% -- roughly half the "total" opportunity
(measured from the structural level) is already consumed by the gap itself before any real entry
is possible.

**2. Pullback offer rate**: only 31.4% of A-pass cases touch 1H EMA8 within the next 3 bars --
most (68.6%) just run without ever offering a second, better-priced entry. When offered, it
typically happens fast (median 1 bar later) with a real median improvement of +0.94% vs the
gap-open price.

**3. The critical, counter-intuitive finding -- waiting for the pullback is NOT free money**:

| population | n | % of A-pass | held_3bars |
|---|---|---|---|
| Immediate-open (all A-pass) | 1,002 | 100% | 84.2% |
| EMA-offered (pulls back to EMA8) | 315 | 31.4% | **72.1%** |
| EMA-not-offered (runs without pulling back) | 687 | 68.6% | **89.8%** |

Formally confirmed: 17.75pp observed spread vs 4.78pp null p95, p=0.0000. **Cases that pull back
to their own 1H EMA8 are a WEAKER subset, not a neutral-or-better one** -- a stock needing a
pullback within 3 hours shows less immediate conviction than one that just runs. MAE confirms the
same pattern: EMA-not-offered has the smallest drawdown throughout (Day+2 MAE -1.40% vs -2.05% for
immediate-open and -2.42% for EMA-offered). So the entry-price improvement from waiting (+0.94%)
comes bundled with selecting into a meaningfully worse-performing population -- not a clean
replacement for chasing the gap, exactly the tradeoff the critic predicted before seeing the
numbers ("a choice between immediate participation and better-but-selective entry, not an obvious
replacement"). Sent to critic for the next call.

## Morning chart review round 2 (2026-10-06): 5 ticker verifications + two new tests

User manually checked TATASTEEL, ICICIBANK, HDFCBANK, TCS, INFY against the EMA8-proximity
examples. All 5 hand-verified against raw daily data, matching exactly:
- **TATASTEEL/HDFCBANK**: user independently spotted that the pullback closes well below the
  ORIGINAL A-day's own Low (TATASTEEL: Dec20 close 129.75 vs A-day's Low 133.00; HDFCBANK: Mar20/26
  closes 715.53/712.70 vs A-day's Low 714.625) -- raised, unprompted, the question of whether this
  invalidates the breakout. Literature confirmed this is a standard, named principle: "a close
  back below the breakout level is the signal the move has failed... the natural stop is placed
  just below the broken level." This is EXACTLY what `breached_a_day_low` already measures --
  both episodes are round-trip wins, not clean wins, in our existing framework. Independent
  validation that the clean/round-trip distinction captures something theoretically real, not an
  arbitrary bookkeeping choice.
- **TCS**: user felt Nov 22 (not Nov 25, the actual A) was the more convincing breakout candle.
  Verified: Nov 22's High (4254.95) did break the prior-10-day high (4234.30), but volume ratio
  was only 1.37x -- just under the 1.5x gate. Nov 25 cleared it at 1.85x. Quantified how common
  this "near-miss filtered by volume" pattern is population-wide: **24.3% of all 94,449 A-episodes
  (22,931) have a near-miss day in the prior 7 trading days** (price broke its own 10-day high,
  volume 1.0-1.5x, just short of qualifying) -- not a one-off, a real, recurring pattern.
- **ICICIBANK**: user's "doesn't look like a real breakout, just small up days" matches the data --
  peak extends 3 more quiet days past A (May16, May19) in a low-volatility grind, consistent with
  a technically-qualifying but visually unconvincing episode.
- **INFY**: user raised a new hypothesis -- does the ABSOLUTE SIZE/magnitude of the breakout candle
  matter, independent of CLV (which only measures close LOCATION, not magnitude)?

**Literature on candle size**: found a specific, named failure mode -- "if breakout bar volume is
5x average but the candle body is narrow (large upper wick), this may be a SELLING CLIMAX
disguised as a breakout... a large range expansion with poor close location is actually a BEARISH
signal." This predicts size should specifically worsen a WEAK CLV outcome (the climax effect).

**Tested, 5x5 fine grid (size quintile x CLV quintile), n=94,449**: the climax hypothesis is NOT
confirmed in this population. Within weak CLV (Q1), size barely matters (17.8%->20.7%->20.1% clean
win across size quintiles, only 2.90pp spread, p=0.0095 -- barely above the noise ceiling, the
weakest confirmed effect in this entire research program). Within strong CLV (Q5), size matters a
lot (34.3%->44.3%, 10.01pp spread, p=0.0000). **The real interaction runs the OPPOSITE direction
from the literature's specific climax claim: size AMPLIFIES a good close, it does not specially
punish a bad one.** "Big candle, weak close" is not meaningfully worse than "small candle, weak
close" in this data -- but "big candle, strong close" is meaningfully better than "small candle,
strong close." Candidate refinement for later: within the already-adopted CLV>=0.80 population,
candle size/range could be a real secondary gate (size matters there); not useful as a gate on its
own or as a way to punish weak-CLV cases specifically.

## Near-miss gap-length test -- closed negative (2026-10-06)

Follow-up to the TCS near-miss finding above: does the gap length between a near-miss day and the
actual A predict outcome quality (theory: immediate-gap cases like TCS are stale continuations
riding on a volume average that hadn't caught up yet, real-pause cases are genuine second
breakouts)?

| group | n | clean-win |
|---|---|---|
| No near-miss in prior 7 days (baseline) | 71,518 | 32.5% |
| 1-day gap (immediate) | 8,021 | 32.1% |
| 2-3 days | 6,647 | 33.5% |
| 4+ days (real pause) | 8,263 | 34.4% |

Formally confirmed real but tiny: 2.29pp observed spread vs 1.78pp null p95 ceiling, p=0.0070 --
clears significance but is an order of magnitude smaller than every other confirmed effect this
session (CLV 20.7pp, first-hour-vs-later 26.08pp, EMA-offered-vs-not 17.75pp). **CLOSED NEGATIVE**:
the continuation-vs-fresh-second-breakout distinction does not meaningfully predict outcome
quality in either direction -- not worth filtering on, not worth re-litigating under a new name.

## Base-building-period A-Low breach -- exclusion tested, critic ruling against it (2026-10-06)

User's hypothesis, raised independently during the chart review (separate from the near-miss
question): if price breaches the A-day's own Low *during the base-formation window itself*
(peak+1 to box_span_end, before the box is even confirmed), the base shouldn't count as a valid
candidate -- its own reference low got taken out before it was confirmed. Tested the straightforward
exclusion rule on resumption rate:

| | resumption rate |
|---|---|
| Keep breached-during-formation episodes | 50.0% |
| Exclude breached-during-formation episodes | 43.8% |

Excluding them makes the number WORSE, not better. Hand-verified 3 real examples (SAHYADRI,
SARDAEN, GPIL) per Rule #22 -- not a bug, deeper retracements during base-formation genuinely
correlate with stronger eventual rebounds.

**User correctly refused to let this settle the question** -- pointed out the test above answers
"which group resolves more often," not "is the label even right." Framed precisely: does an A-Low
breach during base-formation invalidate the base as a structural object, such that the later
box_high break is actually a DIFFERENT event (fresh breakout of a reformed/lower base) mislabeled
as "A's resumption" -- regardless of which labeled group has the better empirical number? Sent to
critic as a definitional question, explicitly not to be resolved by the 43.8%/50.0% result (Rule
#23, dimension 4: does the binary label survive the real structural path).

**Critic's ruling: reject the exclusion, for a different reason than the data above.** Three
distinct levels exist and were being conflated: (1) A-day Low -- just the initial expansion
candle's own reference, not the base's floor; (2) the developing base -- it is structurally normal
for the eventual base to settle BELOW A-day's Low after a peak/pullback, this is not failure; (3)
box_low -- once the box is CONFIRMED, this is the real structural floor, and a break of it is a
legitimate candidate for invalidation (with the caveat that box_low isn't a finalized object until
the box matures -- no retroactively inventing a box_low threshold during the formation period
either). **Ledger ruling, verbatim per critic:**

> A-day Low breach during the pre-box formation period does not invalidate the episode. It is an
> observed path characteristic, not a structural invalidation rule. Once a valid box exists, a
> meaningful break below the established box structure is a candidate structural failure. Whether
> that means box_low itself, a close below it, or something more nuanced is a later semantic
> question, and should not be invented now. Do not use empirical resumption rate to decide this
> definition.

**Decision**: episode definition (A -> peak -> pullback -> valid >=3-day box -> resumption) is
unchanged. A-Low breach during formation stays an observed/reported path characteristic (already
captured elsewhere, e.g. clean-vs-round-trip accounting), never a population-exclusion rule. Per
critic's explicit instruction, **no new RQ launched to find the "right" invalidation threshold** --
that's a later question, only relevant once/if the candidate strategy needs an actual structural
invalidation rule (distinct from the stop/risk convention below). **CLOSED** -- both the original
43.8%/50.0% empirical question and the definitional question underneath it.

## Critic re-tags EMAPB Candidate A: STRUCTURALLY PLAUSIBLE / UNVALIDATED, not yet tradable (2026-10-06)

User, explicitly uncomfortable trusting an attractive hold-rate number with no R:R framework
behind it, asked the critic to read the breakout/pullback/invalidation literature and re-state how
much confidence the project should actually have in Candidate A. Critic read it and revised the
confidence label downward from the previously implied "strong result" framing:

| dimension | status |
|---|---|
| Daily setup has coherent structural logic | green |
| First-hour timing has strong empirical evidence | green |
| A-pass has strong conditional hold rate | green |
| Candidate entry is executable | yellow |
| Structural failure/invalidation defined | yellow |
| Stop/risk convention defined | red |
| R:R / realized-R validated | red |
| Prospective/live behavior | red |
| Strategy validated | red |

**Label: Candidate A is "structurally plausible, unvalidated" -- stage 2 of 4** (interesting
empirical phenomenon -> plausible trade setup -> defined-risk strategy -> validated strategy), not
stage 3 or 4. Literature support for the reframe: a breakout is generally expected to hold the
broken level; a pullback that tests and holds the old resistance is a recognized "breakout-pullback"
continuation structure, not automatically a failed breakout -- but established methodologies (e.g.
O'Neil) always pair the breakout/pivot concept with a PREDEFINED loss limit, never judge success by
"eventually went higher" alone. Our 84.2% hold-rate number is exactly that kind of unqualified
"eventually went higher" statistic -- real, but not yet a trading edge.

**Explicit recommendation: do not move to live trading Candidate A yet.** The next required step is
to DEFINE (not optimize) what subsequent price behavior means the resumption thesis has failed --
i.e. the stop/risk/invalidation convention that Rule #20 already requires before any R-based claim
is meaningful. Critic explicitly rejected importing any off-the-shelf convention without this step
first -- not O'Neil's 7-8%, not A-day Low, not box_low, not EMA8, not an arbitrary percentage --
each needs to be justified against "what does thesis failure actually look like here," not picked
because it's lying around or because the literature uses it elsewhere.

**RQ-11A's EMA8 result reinterpreted, not retracted**: the 72.1%-vs-89.8% result is not evidence
EMA8 is a bad filter -- it shows waiting for ANY pullback selects a weaker subset and sacrifices
68.6% of opportunities, a real tradeoff, not a flaw in EMA8 specifically. If pullback entries are
revisited later, the critic's reading of the literature suggests box_high itself (the broken level
being retested) is the more structurally meaningful reference than EMA8, which was always our own
observation, not a literature-grounded level.

**Status**: EMAPB Candidate A remains an open, promising research line -- not a demoted or paused
one -- but is formally NOT a tradable strategy yet. The single next required step, per critic, is
defining Candidate A's structural-invalidation/stop convention (a logic-first design decision per
this project's standing discipline, not a data-mining exercise) before any further resumption-rate
or R-based work is built on top of it.

## Pivot to a realistic entry clock: user can only act around 3pm, not instantly (2026-10-06)

User flagged a real execution constraint that invalidates most of the prior entry-timing research
for practical use: they will realistically be checking and placing trades around 3pm, not catching
`box_high` breaks the instant they happen. Everything tested earlier this week (first-hour vs
later-hour cross, instant-entry MFE/MAE, EMA8 pullback) assumed near-instant execution. Rebuilt the
baseline around the actual constraint: entry = the 14:15 hourly bar's Close (the realistic price
available checking in ~3pm), on the FULLY UNFILTERED resumption population (no CLV gate, no gap
condition) -- entry day = first day (any day after box confirmation) where price has closed above
`box_high` at any point up to and including the 14:15 bar.

**Raw baseline, unfiltered, instant entry vs ~3pm entry (n=18,399 / 18,311)**:

| checkpoint | instant entry | ~3pm entry |
|---|---|---|
| Today's close | median 0.00%, 46.3% positive | median 0.00%, 45.7% positive |
| Tomorrow's open | median +0.41%, 59.9% positive | median +0.43%, **71.0%** positive |
| Tomorrow's close | median +0.11%, 51.7% positive | median +0.13%, 52.3% positive |
| Peak (next ~2 days) | median +2.30%, 97.6% positive | median +2.10%, 99.2% positive |

**Result: a realistic 3pm entry is NOT worse than catching the break instantly** -- if anything the
overnight-gap win rate is meaningfully higher (71.0% vs 59.9%). This matters practically: the user's
real constraint (can't watch a screen all day) does not appear to cost edge on this unfiltered
baseline.

**Pullback/instant-entry question, raw unfiltered population**: 94.1% of ALL entries dip below the
instant-entry price at some point the same day (median dip -1.07%); only 5.9% never dip at all, and
that 5.9% is the stronger-performing subset (today's-close median +0.39%/57.6% positive vs -0.07%/
45.6% for the dippers). So waiting for a pullback would improve average entry price on 94% of cases
but would completely miss the strongest 5.9% -- the same "waiting selects a weaker population"
pattern RQ-11A already found with EMA8, now confirmed independently with a simpler, EMA-free
definition.

## RQ-EMAPB-3PM-01 -- extension above box_high at 3pm, formally confirmed (2026-10-06)

**Data quality catch first (Rule #22)**: before bucketing, checked for outliers -- found 256 rows
(1.4% of the 3pm-entry population) with an impossible `entry_price`/`box_high` ratio (e.g. BAJFINANCE
showing `box_high`~=750 against `entry_price`~=3,700 on the same row -- BAJFINANCE never traded that
spread in a single session; it had a 1:4 split in mid-2024 and `box_high`/`entry_price` are being
pulled from inconsistently-adjusted price series, the same unadjusted-corporate-action issue flagged
in the short-side RQ-S01 NSE data lessons). Excluded (|extension|>50%) before any aggregate --
n=18,055 remain.

**Question**: among 3pm entries, does how far price has already run above `box_high` by the time
you'd actually buy predict the next day's outcome?

| 3pm price vs box_high | n | % of pop | D1 open (median/%pos) | D1 close (median/%pos) | peak (median) | worst point (median) |
|---|---|---|---|---|---|---|
| Below box_high (already pulled back) | 3,997 | 22.1% | +0.42% / 72.7% | **+0.50% / 61.5%** | +2.24% | -1.07% |
| 0-1% above | 5,199 | 28.8% | +0.30% / 67.7% | +0.01% / 50.2% | +1.69% | -1.40% |
| 1-2% above | 3,209 | 17.8% | +0.41% / 71.8% | +0.04% / 50.7% | +1.92% | -1.57% |
| 2-3% above | 1,836 | 10.2% | +0.50% / 74.7% | +0.00% / 49.8% | +2.20% | -1.84% |
| 3-5% above | 2,024 | 11.2% | +0.63% / 74.3% | +0.17% / 52.5% | +2.88% | -1.94% |
| 5%+ above | 1,790 | 9.9% | +0.69% / 71.1% | -0.20% / 46.9% | +3.32% | -2.65% |

**Finding: chasing extension at 3pm does not pay, and a same-day pullback below the level by 3pm is
not a red flag.** The most-extended bucket (5%+ above) has the biggest peak potential but the worst
D1-close win rate (46.9%) and deepest drawdown (-2.65%) -- paying up for a worse risk/reward. The
"already pulled back below box_high" bucket has the BEST D1-close win rate of any bucket (61.5% vs
~50% for the just-above buckets) -- a same-day shakeout is not damaged goods, consistent with the
RQ-10B "quick recovery" pattern found earlier this week.

**Formally confirmed, three independent tests, all p=0.0000**:
- Below-box_high vs. rest, D1-close win rate: +11.32pp observed vs 1.74pp null p95.
- Full 6-bucket spread, D1-close win rate: 14.57pp observed vs 4.12pp null p95.
- Below-box_high vs. rest, D1-close actual return (mean): +0.56pp observed vs 0.12pp null p95.

**Hand-verified** (Rule #22): 5 real examples from the below-box_high bucket, including both a
winner (PLASTIBLEN, entry 278.00 vs box_high 281.35, D1 close +3.67%) and a real loser (INDOAMIN,
entry 175.34 vs box_high 177.80, D1 close -4.28%) -- not cherry-picked, prices are sane, no data
artifact.

**Robustness check, per Rule #19 (2-3 materially distinct splits, pre-declared)**: holds inside
both CLV bands almost identically (CLV>=0.80: +11.5pp, p=0.0000; CLV<0.80: +12.1pp, p=0.0000 --
this is NOT a CLV-restated effect) and holds in every individual year with no decay (2023 +9.2pp,
2024 +11.9pp, 2025 +9.7pp, 2026 +15.6pp -- actually strongest in the most recent year). **Clears
this project's robustness bar.** This is the first real, 3pm-entry-specific, formally-verified
piece of entry logic for a realistic (can't-watch-all-day) execution constraint. Not yet a
complete strategy -- still missing the stop/invalidation convention (Rule #20, still open from the
critic's confidence re-tag above) -- but a genuine, validated building block for one.

## Critic review + literature check on RQ-EMAPB-3PM-01 (2026-10-06)

Critic read the finding with an explicit high bar ("the result is attractive enough that we should
actively try to break it"). Verdict: plausible, not theoretically weird -- two literature-backed
mechanisms both predict it: (1) intraday return reversal from temporary liquidity imbalances
(Heston, Korajczyk & Sadka; effects documented as lasting under an hour, stronger in less-liquid/
more-volatile names), and (2) the breakout-pullback/retest structure is a recognized, named TA
pattern (old resistance tested as new support). The overlap of both mechanisms is a coherent
explanation for "big early breakout -> gives back some/all by 3pm -> subsequent continuation beats
buying the still-extended price."

**Mechanical audit requested, run immediately, passed clean**: verified in the actual code
(`21_rq_emapb_3pm_entry.py`) that `box_high` is frozen from the pre-resumption box period (computed
well before the entry-day search even starts), `entry_price` is exactly the 14:15 bar's Close
(nothing else), `d1_close_ret` is measured from that exact price (not the day's open or `box_high`),
and the extension classification (`already_run_pct`) only touches `entry_price` and `box_high` --
no information from after 14:15 leaks into either the classification or the outcome. No RQ-10B-style
overlap bug here.

**Critic's substantive pushback, three points**:
1. "Below box_high at 3pm" may not mean "cheaper is better" -- it may be measuring PULLBACK QUALITY
   (a same-day retest of the broken level as new support) rather than mere extension/cheapness. The
   aggregate bucket conflates a healthy, orderly retest with an outright failed breakdown under the
   same label.
2. The 3pm clock itself may be doing real work via well-documented intraday liquidity seasonality
   (U-shaped volume/spread patterns on NSE) rather than "breakout psychology" specifically -- noted
   for a future OOS test of whether 3pm itself is special, explicitly NOT to be tested now (would be
   clock-time fishing).
3. The strategy has quietly changed character: no longer "buy the first-hour breakout," now "at 3pm,
   inspect how the morning breakout evolved, then decide if the resulting state is attractive" -- a
   state-at-3pm strategy, not a breakout-entry-timing strategy. Explicit instruction: do NOT now sweep
   extension-bucket granularity, clock times, EMA variants, or CLV combinations -- that would be
   exactly the overfitting trap already flagged this week.

**Confidence tag applied to this finding specifically**: green (confirmed empirical building block),
yellow (mechanistically plausible per literature), red (not yet a defined-risk strategy).

**Next step specified**: RQ-12, decompose the shape of the 3pm state (not another predictor) --
specifically whether, within the below-box_high group, there's a difference between "merely drifted
down from the morning high" (still falling into 3pm) vs "broke back through box_high and then
recovered/held around it." User explicitly deferred bringing EMA8 into this (despite a real,
previously-observed chart pattern) per critic's instruction to keep this decomposition clean first.

## RQ-EMAPB-12 -- 3pm state decomposition, closed mostly negative + a real illiquidity catch (2026-10-06)

Built the critic-specified test: within the below-box_high-at-3pm group (n=3,881), split by whether
the 3pm close is at/near the day's own low-so-far ("still falling") vs meaningfully above a lower
point reached earlier ("already bounced").

**The critic's actual question came back weak and counter to the hypothesis**: "still falling"
66.2% D1-close positive vs "already bounced" 61.4% -- opposite direction from the Story
1 (healthy pullback)/Story 2 (failed breakdown) prediction, and only marginally significant
(+4.80pp observed vs 4.36pp null p95, **p=0.0400** -- barely clears, not a clean confirmation).
**Not promoted.** The secondary retracement-from-morning-high tercile check showed no clean
pattern either (64.1% / 60.6% / 61.3%, non-monotonic U-shape) -- no formal test run, inconclusive.

**A serendipitous falsification check produced a spectacular-looking number that turned out to be a
pure data artifact -- caught before it went anywhere (Rule #22 in action)**: running the same
still-falling-vs-bounced split on the ABOVE-box_high group (sanity-checking whether the feature
means anything generally) showed a huge, clean-looking effect -- "still falling" (n=373, 2.6% of
that group) at 67.6% D1-close positive vs "already bounced" at 49.7%, +17.90pp observed vs 5.23pp
null p95, p=0.0000. **Hand-verification of 5 real examples before trusting it** found real problems
in 3 of 5: PVP showed ZERO intraday range (morning_high == day_low_so_far, a frozen/illiquid name
where "at session low" is a meaningless label); EMCURE and AKUMS showed `box_high` sitting 40-50%
below the entry price, an implausible same-episode move. Quantified: **56% of the n=373 "finding"
group (209 cases) has near-zero intraday range** -- thinly-traded/frozen-price names, not genuine
price action. Re-running the test after excluding near-zero-range names across the whole
population: the effect **collapsed to p=0.1575** (+5.84pp observed vs 7.69pp null p95) -- not
significant. **CLOSED: this was a pure illiquidity artifact, not a market phenomenon.** The
below-box_high group's original test was unaffected by this same cleaning (identical counts,
517/3,364, same p=0.0400) -- it was never contaminated by this issue, it's just independently weak.

**A separate, real methodological issue surfaced during hand-verification, not yet fixed**: the
entry-day search window (up to ~300 bars / ~50 trading days forward from box confirmation) can, in
rare cases, find a qualifying cross long after the box confirmed -- distribution has a real tail
(median gap 1 day, 90th pctile 10 days, but 99th pctile 463 days, max 953 days) -- raising the
question of whether some long-delayed crosses are actually unrelated later rallies being
mis-attributed to a stale box, not genuine continuations of the same episode. Flagged, not fixed.

**Checked whether this affects the core RQ-EMAPB-3PM-01 finding -- it does not, and the result is if
anything slightly reassuring**: the long-delay ("stale") rate is low and similar (6.3-9.2%) across
the below/0-1/1-2/2-3/3-5 buckets -- the main, formally-tested below-vs-rest contrast is
unaffected. Only the 5%+-above bucket shows meaningfully elevated staleness (20.9% with gap>10
days). Split that bucket directly: clean (fresh, gap<=10 days, n=1,416) shows D1-close 45.6%
positive; stale (gap>10 days, n=374) shows 51.9% positive -- the stale cases were performing
slightly BETTER, meaning they were diluting the "don't chase extension" signal toward a less
dramatic number, not inflating it. **The core finding is intact and the chase-penalty is if
anything understated, not overstated, by the uncleaned bucket.** The search-window scope issue
remains a real cleanup item for any future RQ built on this same population, but it is not a threat
to RQ-EMAPB-3PM-01's practical conclusion.

**Net status**: RQ-12 closed, mostly negative (the specific healthy-pullback/failed-breakdown
distinction critic asked for was not confirmed). RQ-EMAPB-3PM-01 stands, unaffected, and the
illiquidity catch is a logged process win, not just a dead end.

## Critic's final verdict on RQ-12 + standing guardrail adopted (2026-10-06)

**RQ-12: CLOSED NEGATIVE, confirmed.** Critic explicitly praised the process, not just the
outcome: the attractive-looking above-box_high result was correctly rejected as a data artifact
after raw hand-verification, and the stale-box tail is a real population-definition weakness worth
guarding against going forward.

**Ledger distinction, important, recorded verbatim per critic's framing** -- do not let RQ-12's
failure weaken RQ-EMAPB-3PM-01, because they asked different questions:
- RQ-12 asked: *why* is the below-box_high group better? -- failed to establish the proposed
  explanation (healthy-pullback-vs-failed-breakdown didn't hold up).
- RQ-EMAPB-3PM-01 asked: *is* the below-box_high state better at the 3pm decision point? -- this
  remains supported, independently of RQ-12's failed explanation.

**Status tag: "3pm retracement state: empirical finding = green-ish / explanation = unresolved."**
Explicitly do NOT invent a causal story for this effect just because it's attractive -- the
literature-backed mechanisms (intraday reversal, breakout-pullback-retest) remain plausible
background context, not a proven causal account.

**New standing guardrail adopted for this subproject (not yet a CLAUDE.md-level rule, scoped to
the EMAPB resumption-episode machinery specifically)**: any future RQ using this population must
explicitly control for and report the age of the daily box at the eventual 1H cross --
at minimum: the gap-days distribution, what fresh-vs-stale definition was used (no fixed cutoff
established yet -- "10 days" was a working boundary for this one check, not a permanent rule), and
whether the tested effect survives a freshness restriction. The 99th-percentile 463-day / max
953-day tail is extreme enough that no future qualifying cross should be casually described as "a
continuation of the original setup" without checking this first.

**Next step, per critic, explicit**: do NOT launch another explanatory RQ -- enough time has gone
into "why." The next useful step is turning the surviving 3pm finding into an actual candidate
trade: at ~3pm, after a valid EMAPB resumption, what exactly constitutes an EXECUTABLE ENTRY, and
what constitutes FAILURE/INVALIDATION. This is the same missing piece flagged by the earlier
"structurally plausible, unvalidated" confidence re-tag (Rule #20 still open) -- now concretely
motivated by a real, surviving entry-side signal instead of an abstract requirement. The
search-window scope issue should be fixed/guarded before the next population is generated for this
work, not silently carried forward.

## RQ-EMAPB-13 / 13v2 -- predictive execution feasibility, CLOSED NEGATIVE (2026-10-06)

User's operational question, not a performance question: can EMAPB move from reactive (3pm
check-in) to predictive (T-1 or early-same-day IOC), the way Prime BC already operates -- since
continuously watching for "it just broke out" isn't viable. Critic specified one bounded,
pre-registered test (RQ-13), explicitly NOT a discovery program: by ~10:15 (our data's closest
honest approximation to critic's 9:45-10:00, since intraday is hourly -- stated explicitly, not
hidden), can a simple state separate today's eventual later-day resolutions from the rest of the
primed population well enough to justify an IOC?

**RQ-13, first pass (resumption-only population, n=47,307 primed mornings)**: rule = first-hour
High comes within 1% of box_high. Coverage 71.1%, precision 36.1% vs 14.76% base rate (+21.3pp
lift). Looked promising, but user immediately flagged suspicion of look-ahead. Mechanical audit
confirmed the predictor itself is clean (T-1 close + that day's own 09:15 bar only, nothing leaks
forward) -- the real issue was survivorship bias: the population only contained episodes already
known to eventually resolve (`outcome=='consolidation_resumption'`), missing all boxes that form
and never break out at all.

**RQ-13v2, full denominator (critic's required next step, same FROZEN rule, no threshold change)**:
rebuilt including `consolidation_failure` episodes (22,697, vs 19,182 resumption) in the same
primed-morning panel, capped at a 20-trading-day window per episode (the population-construction
guardrail adopted after RQ-12's stale-box finding -- not the frozen rule itself). Combined panel:
513,896 primed-morning rows, 69.1% of which come from episodes that never resolve.

| metric | resumption-only | full denominator |
|---|---|---|
| Live base rate | 14.76% | **1.33%** |
| Coverage | 71.1% | 71.7% (holds) |
| **Precision** | 36.1% | **5.21%** |
| False-positive rate | 63.9% | **94.79%** |

**Precision collapsed from 36.1% to 5.21% once failure episodes are included** -- coverage survives
(the early-session proximity condition still catches most true same-day resolutions), and the
relative lift over the live base rate is still real (~3.9x, 5.21% vs 1.33%), but 94.79% of flags
would be wrong. Not operationally useful for an automated, unmonitored IOC -- firing on noise 19
times out of 20.

**CLOSED per critic's own pre-declared decision tree** ("if precision collapses -> close
predictive automation and use T-1 shortlist + 3pm check-in"). EMAPB does not get a predictive/
IOC-automated execution path -- the project defaults to the already-validated reactive approach
(RQ-EMAPB-3PM-01's T-1-shortlist + 3pm check-in), which doesn't have this problem since it confirms
an ACTUAL breakout at 3pm rather than predicting one in the morning. Do not reopen predictive
automation for EMAPB without a materially different signal than first-hour proximity -- this one
test, done properly with the full denominator, answered the question.

## EMA8 "touch and run" -- second independent disconfirmation, CLOSED NEGATIVE (2026-10-06)

User recalled from past chart review that most EMAPB breakouts happen with the 1H EMA8 nearby, and
that price typically touches it and then runs -- asked for a full-population re-check (previously
only checked on 5 anecdotal charts). Tested properly: at the actual resolution bar, across all
17,969 episodes with EMA8 coverage, median distance from the bar's Low to its own 1H EMA8 is
**+0.61% (above it, not touching)**. Only 20.4% of resolution bars touch EMA8 at all (Low<=EMA8).
**Touching it is associated with WORSE reliability, not better**: 40.1% hold_3bars for touches vs
48.5% for non-touches, formally confirmed (-8.39pp observed vs 1.76pp null p95, p=0.0000).

**This is the second independent test with the same directional conclusion** -- RQ-11A already
found waiting for an EMA8 pullback selects a materially weaker population (72.1% vs 89.8% hold).
**CLOSED NEGATIVE, per critic**: EMA8 proximity/touch as a strength signal is rejected twice now.
Do not reopen this from chart memory/anecdote again without a materially different framing than
"proximity to EMA8 at or around the breakout."

## Critic's final verdict + the research queue is now intentionally short (2026-10-06)

**RQ-13v2 verdict, critic**: predictive/IOC automation CLOSED. Confirmed the result is informative,
not a pure null -- real predictive information exists (coverage held at 71.7%, ~3.9x relative lift)
but fails the operational bar in absolute terms (5.21% precision, 94.79% false positives). The
pre-registered decision tree resolved exactly as designed: morning prediction closed -> T-1
shortlist + 3pm confirmation is the operational path. No classifier, no threshold rescue, no second
morning predictor.

**EMA8: permanently closed per critic** -- three facts now on record (RQ-11A pullback-selects-
weaker; full-population touch test 40.1% vs 48.5%, p=0.0000; only 20.4% of resolutions even touch
it). Explicit instruction: a future chart that appears to contradict this is an anecdotal challenge
requiring a genuinely new hypothesis, not grounds to reopen the old one.

**Where EMAPB now stands, the surviving operational concept**:
```
T-1    -> identify valid/primed boxes, build a manageable shortlist
T morning -> no automated prediction, no universe-wide watching
~3pm   -> inspect the shortlist, require the actual qualifying state,
          enter only when the real resumption condition is present,
          don't chase excessive extension
```
A reactive confirmation strategy, but operationally manageable -- the expensive part (continuous
universe-wide monitoring) has been eliminated by the T-1 shortlist. The 3pm below-box_high result
(RQ-EMAPB-3PM-01) remains the strongest entry-side empirical finding and must not be discarded just
because the predictive-automation attempt failed -- they are independent results.

**Next and only open item: RQ-14 -- EMAPB 3PM Executable Entry & Structural Invalidation.** Not
another predictor search. Four things to settle, in order:
1. **Exact 3pm entry condition** -- what exactly qualifies at the decision point, what price is
   realistically executable.
2. **Structural failure** -- what price/action means the setup is genuinely broken; must be
   structurally defensible, not "because the trade went down."
3. **Stop/risk** -- fixed % vs structural level vs a bounded combination; matters because the user
   sizes position from the risk, so it cannot be quietly widened just to improve historical win
   rate.
4. **Realized-R outcome** (only after 1-3 exist) -- MAE, MFE, +1R/+2R attainment, -1R loss
   frequency, time to outcome, overnight gap behavior, slippage/transaction assumptions.

Only once these exist does Candidate A become a strategy rather than a validated entry-side
phenomenon. **Standing guardrail for RQ-14 and beyond**: every future RQ on this population must
report box age/freshness (per the RQ-12 stale-box guardrail) -- report it and assess its structural
meaning, do not introduce a new freshness cutoff yet.

**Research queue, intentionally short**: predictive morning IOC closed; EMA8 closed; no more
breakout predictors. -> Define 3pm entry + structural invalidation -> test realized R -> attack
failure scenarios. This is the point to stop discovery and start trying to break the actual trade.

## RQ-EMAPB-14a -- post-entry round-trip-to-box_high invalidation, VALIDATED (2026-10-06/07)

User's own structural invalidation hypothesis for RQ-14 point 2, path-dependent by design (not a
static level check, which would contradict the entry logic itself -- "below box_high at 3pm" is
already the BEST entry state, so "price is below box_high" can't also be the failure signal; user
caught this inconsistency directly). The actual rule: after a realistic 3pm entry, if price first
moves up >=1% from entry (a meaningful "up moment," user-specified threshold), and THEN comes back
down and re-touches `box_high`, that round-trip back to the breakout level is the failure signal.

**Three-way split, full 3pm-entry population (n=18,055, all extension buckets -- this is a
post-entry rule, independent of where entry sat relative to box_high)**:

| group | n | % of pop | D1-close (median / %pos) |
|---|---|---|---|
| A. Never reached +1% up-move at all | 3,888 | 21.5% | -1.19% / 13.5% |
| B. Reached +1%, THEN round-tripped back to box_high | 6,057 | 33.5% | -0.34% / 42.9% |
| C. Reached +1%, did NOT round-trip back | 8,110 | 44.9% | **+1.44% / 78.8%** |

B vs C formally confirmed: -35.87pp observed vs 1.65pp null p95, **p=0.0000** -- one of the largest
effects found in this entire research program.

**Circularity check, run precisely because the effect size was large enough to warrant the RQ-10B-
style scrutiny**: is the round-trip event overlapping in time with the D1-close outcome it's being
compared against? Timing audit (n=3,000 real retest events): median 5 bars of lead time remain
before the window ends (out of ~7-8 total D1 bars), only 4.1% of retests happen at the very last
bar. Not the RQ-10B exact-overlap pattern. Split further by which calendar day the retest actually
happens on:

| group | n | D1-close (median / %pos) |
|---|---|---|
| C. Reached +1%, no retest | 8,110 | +1.44% / 78.8% |
| B1. Retest on D0 (entry day -- fully separate from D1, zero timing overlap) | 1,698 | +0.46% / **59.0%** |
| B2. Retest on D1 itself (same day as the close measured) | 4,359 | -0.59% / 36.6% |

**B1 vs C, the cleanest possible test (zero overlap between signal and outcome)**: -19.76pp
observed vs 2.31pp null p95, **p=0.0000** -- the effect survives at real magnitude even with a full
calendar day of separation between the round-trip event and the measured outcome. B2's larger gap
is explained as ordinary same-day intraday momentum/persistence layered on top, not an artifact.

**VALIDATED as RQ-14's structural invalidation definition**: enter at the realistic 3pm price;
if price subsequently moves >=1% above entry and then comes back down to touch `box_high` again,
treat the thesis as confirmed-failed. This is a genuinely path-dependent, structurally-grounded
signal (mirrors the existing clean-win/round-trip-win framework's logic, applied post-entry at the
3pm timeframe with `box_high` as the reference instead of A-day's own Low), not a static level
check, and it passes the strictest available circularity test.

**Status, RQ-14 checklist**: #1 (entry condition) settled via RQ-EMAPB-3PM-01. #2 (structural
failure) now settled via this result. #3 (stop/risk sizing -- how much capital this actually risks,
or a simpler fallback) and #4 (realized-R, blocked on #3 per Rule #20) remain open. Not yet sent to
critic -- next action.

## RQ-EMAPB-15A -- Structural Risk Envelope, characterization only (2026-10-07)

Critic's explicit framing: the round-trip rule (RQ-14a) is a failure CLASSIFIER, not automatically
an executable STOP -- using it literally as the stop would let an already-winning trade (it
requires a prior +1% move) reverse all the way back to `box_high` before declaring failure, which
may be poor risk control even though it's a valid outcome label. The question before picking any
stop: is there an earlier, executable price boundary that approximates the same failure mechanism
without waiting for the full round-trip? Answering that requires first checking whether failing
and surviving trades are even separable by adverse-excursion depth.

Four groups, same 3pm-entry population, same frozen 1% threshold as RQ-14a (n=18,057): A (never
reached +1%, n=3,890), B1 (reached +1%, retested box_high on D0, n=1,698), B2 (reached +1%,
retested on D1, n=4,359), C (reached +1%, never retested, n=8,110).

**B1 vs B2 -- failure timing and depth are linked**: B1 (fails fast, same day) median MAE-before-
confirm is -0.63%; B2 (fails slower, next day) median is -1.52%, more than double. Timing and
depth move together -- a faster failure is also a shallower one. A (never showed +1% strength at
all) has the deepest typical drawdown of any group (-2.08% median), consistent with having no
conviction from the start.

**The critical comparison, per critic's explicit requirement -- MAE-before-failure (B1+B2 combined)
vs MAE-over-the-same-window for survivors (C)**:

| percentile | Failures (B1+B2) | Survivors (C) |
|---|---|---|
| 10th | -3.67% | -3.35% |
| 25th | -2.26% | -2.03% |
| 50th | -1.22% | -1.07% |
| 75th | -0.60% | -0.53% |
| 90th | -0.28% | -0.22% |

**The two distributions are nearly identical at every percentile.** Confirmed directly via a stop-
threshold sweep: at -1.0%, a stop catches 57.6% of failures but also stops out 52.6% of survivors;
at -1.5%, 41.7% vs 35.7%; at -2.0%, 30.0% vs 25.5%; at -3.0%, 15.8% vs 12.7%. **No threshold tested
meaningfully separates a dying trade from ordinary winner noise.**

**Answer to critic's pre-registered question: NO, there is no reasonably narrow adverse-movement
region that separates structurally failing trades from surviving trades.** Per critic's own
pre-declared logic ("if no -> the structural signal may be a good exit/failure classification but
a poor initial stop"), **a simple price-depth stop derived from typical failure MAE is NOT a valid
risk-control candidate** -- it would cut roughly as many eventual winners as eventual losers at
every level tested.

**What remains as real candidates, not yet decided**: (1) accept the full round-trip itself as the
exit trigger, accepting that a winner can fully reverse to `box_high` before confirmation; or (2) a
TIME-based cutoff rather than a price-depth one, since B1/B2 shows a genuine behavioral split by
speed-to-failure, not depth. Sent to critic for the call before building either.

## RQ-EMAPB-15B -- Exit-at-confirmation characterization, surfaces a B1-vs-B2 asymmetry (2026-10-07)

Critic's explicit framing: measure the economics of exiting AT the moment structural failure
confirms (assumed fill = box_high, modeling a resting stop at the level) before deciding anything
about a price or time-based stop -- is the already-validated failure signal timely enough to
function as the actual exit. Note: this run extended the observation window through D0-D3 (vs
D0-D1 in RQ-15A) to allow after-confirmation tracking for B2 cases, so group composition shifted
somewhat from RQ-15A (more retests now captured within the longer window) -- not a different
result, a wider observation lens.

| | B1 (fails same day, n=1,698) | B2 (fails next day, n=7,717) |
|---|---|---|
| Exit-at-confirmation return | **+0.64% median, 72.4% positive** | **-0.63% median, 25.9% positive** |
| MFE before confirm | +1.52% | +2.06% |
| Given back | +1.03% | +2.99% |
| Confirmation day's own close | +0.07% | -0.81% |
| Next day after confirm | +0.46% | -0.92% |
| Worst close, 3 days after confirm | -0.66% | **-2.24%** |
| % where holding past confirm was worse than exiting | 53.8% (coin flip) | 54.5% (coin flip) |

**Survivors (C, n=6,394), matching daily checkpoints from entry**: D0 close +0.00%/44.7% positive,
D1 close +1.52%/74.4%, D2 close +2.26%/79.5% -- keeps improving over time.

**Provisional payoff ratio** (avg confirmed-failure exit loss -1.53% vs avg survivor(C) D1-close
winner gain +3.36%, stated explicitly as provisional pending a real risk convention): **2.20**.

**The key surfaced finding: B1 and B2 "failures" are not the same phenomenon.** B1 (fast, same-day
confirmation) is still positive 72.4% of the time even after "failing" by the structural rule --
barely a loss on average, and holding through it is a literal coin flip with modest further
downside (-0.66% worst case over 3 days). B2 (slower, next-day confirmation) is a real loss 74% of
the time, with meaningfully compounding downside if ignored (-2.24% worst case). **The round-trip
signal appears to be doing real work for B2 but may be flagging noise, not genuine failure, for
B1** -- exiting on a B1-style confirmation could be cutting trades that are mostly fine. Sent to
critic given this raises a real question about whether the exit rule should apply identically to
both, or whether B1/B2 need different treatment.

## RQ-EMAPB-15C -- B2-only exit vs no-exit vs simple benchmark, a real bug caught and fixed (2026-10-07)

Critic's revised interpretation after RQ-15B: B1 is noise, don't exit on it; B2 is the real
candidate failure signal. Specified RQ-15C -- three predeclared paths on the same population: (A)
B2-only structural exit (ignore B1, exit B2 at confirmation), (B) no structural exit at all (hold
through), (C) a simple non-structural benchmark (exit everyone at D1 close).

**First attempt had a real timing bug, caught before sending to critic**: compared "B2 exit at
confirmation" against "hold to a fixed D2 close," but B2 confirmations actually land on D1 (56.5%),
D2 (26.6%), or **D3 (16.9%)** within the classification window -- so for 43.5% of B2 trades, the
fixed D2-close snapshot was at-or-before their actual confirmation, not a genuine "held through the
failure" comparison. Rebuilt with the terminal hold horizon extended to D5 close, safely past the
latest possible confirmation, before trusting any number.

**Clean, isolated B2 sub-comparison (exit-at-confirmation vs hold-to-D5, n=7,714)**:

| | median | % positive |
|---|---|---|
| Exit at confirmation | **-0.63%** | 25.9% |
| Hold to D5 close instead | -1.23% | 39.5% |

Exiting at confirmation gives a smaller typical loss even though holding recovers more often
(39.5% vs 25.9%) -- the trades that don't recover when held get considerably worse. Only 45.3% of
B2 cases do better by holding. **For a confirmed B2 failure, exiting at confirmation beats holding
through** -- this part of the hypothesis holds up.

**The three-policy aggregate comparison (terminal = D5 close, n=18,052), the more important
result**:

| policy | median | % positive | worst 1%ile | worst 5%ile |
|---|---|---|---|---|
| A. B2-only structural exit | -0.26% | 44.0% | -11.13% | -6.54% |
| B. No structural exit (hold to D5) | -0.01% | 49.8% | -13.53% | -8.92% |
| **C. Simple benchmark (exit everyone at D1 close)** | **+0.15%** | **52.7%** | **-6.80%** | **-3.90%** |

**The dead-simple policy -- exit everyone at D1 close, no structural tracking at all -- beats both
the structural-exit policy and simply holding, on every metric**: best median, best win rate, and
by far the shallowest tail risk. The structural failure signal remains real and validated as a
classifier (RQ-14a, RQ-15B), but once the extra time-in-market required to wait for a B2
confirmation (up to D3) is accounted for, the simple time-based exit wins outright. Sent to critic
-- may mean the candidate exit should flip: D1-close as the primary mechanism, structural failure
as a secondary overlay rather than the main exit.

## EMAPB Candidate v0.1 -- frozen for chart review, discovery phase stops here (2026-10-07)

Critic's verdict on RQ-15C, explicit self-correction: enough discovery has happened -- stop
inventing new exit experiments, put an actual candidate on the table and look at real trades.

**Candidate EMAPB v0.1** (status: yellow, candidate strategy, not validated):
```
T-1   -> daily EMAPB box confirmed, candidate goes onto the primed shortlist.
         No EMA8 condition, no predictive morning classifier, no extra volume/ADX filters.
T 3pm -> the setup has produced the qualifying resumption state; do not chase excessive
         extension above box_high; enter at the realistic 3pm executable price.
Exit  -> D1 close. That's it. No B2 machinery in the primary strategy -- RQ-15C showed the
         structural exit doesn't beat the simple D1 exit and carries materially worse tail risk.
Stop  -> deliberately UNSPECIFIED. Not manufactured from the dataset before looking at real
         trades -- candidate = defined entry + defined D1 exit + no forced stop yet.
```
The B2 signal stays logged as an observed failure classifier (RQ-14a/15B), not part of v0.1. D1
close is "the best of the three tested policies," not declared final -- no further D1-vs-D2-vs-D3
optimization until the candidate has actually been looked at.

**Discovery phase summary, per critic**: predictive IOC doesn't work; EMA8 doesn't work; chasing
extension doesn't work; price-depth stop doesn't separate winners from failures; B1 isn't real
failure; B2 is a real failure classifier; but a B2-based exit loses to the simple D1 exit, which
also has dramatically better tail behavior. That is enough discovery -- the next question is not
"what other exit can we test," it's "what does this candidate actually look like as a trade."

**Next: RQ-EMAPB-16 -- Candidate Trade Audit.** A small, predeclared, STRATIFIED sample (20-30
real trades, not another population-wide sweep), deliberately including: clear winners, ordinary
winners, small losers, large losers, B1 cases, B2 cases, highly-extended 3pm cases, below-box_high
3pm cases, different box ages, different market regimes/years. For each: the real daily chart path
(setup -> box -> breakout -> 3pm entry), the real 1H path (breakout/pullback -> entry -> D1 exit),
and the outcome (MFE/MAE/D1 return). Explicitly hypothesis-generation and semantic validation, NOT
statistical validation -- do not optimize from the 20-30 charts; if a recurring structural pattern
emerges among the losers, formulate ONE stop hypothesis from it, don't immediately test five
variants.

## Chart audit surfaces a real population-hygiene problem; liquidity floor adopted as a standing filter (2026-10-07)

Hand-checking two of the RQ-16 sample winners surfaced two distinct, real problems the stratified
sample alone couldn't catch, because it was sampling from a population that still contained them:

**ATLANTAA (2024-03-22) -- the A-day itself is weak, and separately the stock is illiquid.**
Volume ratio only 1.57x (barely clears the 1.5x gate), and LOWER than the volume on each of the
two preceding days (94,078 and 160,790 vs the "breakout" day's 115,793) -- the 10-day rolling
average was simply pulled down by quieter earlier days, so the day doesn't actually stand out from
its own immediate past. Range only 3.46% of open -- a tight, unremarkable candle sitting at the
tail of an already-running week-long grind higher (20.90->21.80->22.65->23.75->24.90, a new high
every session). Separately confirmed illiquid: average turnover Rs0.12 crore/day, nowhere near a
sane tradeable floor.

**LLOYDSENGG (2024-04-29) -- the tagged A-day is a continuation, not the real breakout.** The
actual explosive move was April 22 (39.9M volume vs ~4-9M in prior days, 18.21% range, +16.85%
body) -- April 29 is a second leg within the same already-extended move (stock had already run
+18% by then). `cluster_length=1` for both ATLANTAA and LLOYDSENGG confirms the existing cluster
de-duplication mechanism (collapses literally back-to-back qualifying days) is too narrow to catch
either failure mode -- it doesn't catch a single qualifying day sitting atop a week of gradual
climbing (ATLANTAA), nor a second, independent qualifying day appearing days after an earlier,
much more convincing one (LLOYDSENGG). This is a different, more specific question than the
already-closed near-miss-gap-length test (which asked about days that almost-but-didn't qualify,
not a FULLY qualifying prior A-day) -- not yet tested, flagged as open.

Also directly confirmed on this same LLOYDSENGG example: a real base-building wick (Low=56.50,
"way low" below the eventual box_low=58.20 reference) closed the same day at 61.00, comfortably
above the defended level -- the base held cleanly on a CLOSE basis across all 3 confirmation days,
consistent with the project's standing close-over-wick discipline (the TCS catch). Separately,
confirmed `box_low` is NOT `box_slice.Low.min()` as assumed -- it's the closing-price level that
had to hold for 3 days to confirm the base (tracked via `running_low_close`, set from BEFORE the
box_slice window even starts), not the literal lowest print within the box days. Not a bug -- a
deliberate, close-based design choice, verified against the actual code
(`13_rq_emapb07_lifecycle.py` lines 112-176) -- but asymmetric with `box_high` (which IS
`box_slice.High.max()`, a wick-based ceiling). Worth being aware of when interpreting `box_low`
elsewhere.

**Literature check before building anything** (per standing discipline): researched three specific
questions before adding filters.
1. Volume confirmation: the user's "today's volume must be an N-day volume HIGH" idea is NOT a
   recognized literature standard -- the real standard is ratio-to-trailing-average (O'Neil:
   breakout volume 40-50% above the 50-day average; Minervini: >=1.4x; Bulkowski backtested
   ratio-qualifying breakouts at 65% success vs 39% for below-average-volume ones). The N-day-high
   framing is the user's own inference, not literature -- needs testing in our own data before
   being treated as correct, not assumed. Bulkowski also found high-volume breakouts throw back
   70-74% of the time within 30 days (more confirmed AND more prone to giveback) -- a real, notable
   nuance, possibly connected to the CLV/round-trip findings, not yet investigated.
2. Liquidity floor: real, settled, both practitioner and academic. Jegadeesh & Titman's momentum
   papers explicitly exclude sub-$5 stocks and the smallest liquidity decile -- stated reason:
   transaction costs can eat 70-100% of paper profits from momentum strategies in illiquid names.
   Directly validates adding a liquidity floor.
3. Fresh vs. late-stage/continuation breakouts: a real, named concept (O'Neil's base-count rule --
   1st/2nd base best odds, 3rd/4th+ base failure rate climbs; Minervini's "late-stage base").
   Direction is consensus across sources but not rigorously quantified in any primary source found
   -- treat as a real hypothesis worth testing in our own data, not an importable statistic.

**Liquidity floor adopted and tested (RQ-EMAPB-LIQ, `31_rq_emapb_liquidity_filter.py`)**: price
>= Rs20, average daily turnover (Close*Volume) >= Rs1 crore over the 20 trading days before the
A-day -- pre-declared from the literature above, not fit to this data. Applied to the full
3pm-entry population (n=18,055): **21.8% (3,937 episodes) fail this floor** -- a real, widespread
contamination problem, not just the couple of anecdotes spotted by eye. Re-ran the core
RQ-EMAPB-3PM-01 extension-bucket finding on the cleaned population (n=14,118): **the effect
survives and is slightly stronger** (below-box_high vs rest: +12.85pp observed vs 1.97pp null p95,
p=0.0000, vs +11.32pp on the uncontrolled population). **The core finding is not an artifact of
illiquid names.** Of the 28-trade RQ-16 sample, 9 (32%, including ATLANTAA) fail this filter and
should be dropped/replaced before continuing the chart audit.

**Adopted as a standing filter for all EMAPB population work going forward** -- apply the
liquidity floor before building any future population or chart sample on this line of research.
Price floor subsequently raised to Rs50 per user's call (anything below is too easy to
manipulate) -- re-verified, exclusion rises to 25.1%, core finding unaffected (+13.03pp,
p=0.0000). The "today's volume must be an N-day high" and "exclude a continuation-style A-day if a
fully-qualifying prior A-day exists within N days" ideas remain open, untested hypotheses at this
point -- explicitly not adopted yet, pending their own bounded tests.

## RQ-17/18 -- the two chart-motivated hypotheses, both CLOSED NEGATIVE (2026-10-07)

Tested both on the liquidity-cleaned population (price>=Rs50, turnover>=Rs1cr/day, n=13,528),
pre-declared (10-day lookback for both, matching the existing price-high lookback), not fit to
results.

**RQ-17 -- is the A-day's volume ALSO the highest in the trailing 10 days** (not just >=1.5x the
rolling average, which ATLANTAA showed can be gamed by a quiet earlier baseline)?

| | n | D1-close (median / %pos) |
|---|---|---|
| Is a 10-day volume high | 9,188 (67.9%) | +0.09% / 52.0% |
| Not a volume high (ratio-gate only) | 4,340 (32.1%) | +0.18% / 53.7% |

Observed -1.70pp vs 1.73pp null p95, **p=0.058** -- does not clear significance, and the direction
is opposite the hypothesis (the "more convincing" volume-high group is marginally weaker, not
stronger). **CLOSED NEGATIVE.**

**RQ-18 -- exclude an A-day if a FULLY QUALIFYING prior A-day already existed for the same ticker
within the trailing 10 days** (continuation-of-an-already-extended-move, per the LLOYDSENGG
example -- a sharper, more specific version of the already-closed near-miss-gap-length test, which
only asked about days that almost-but-didn't qualify).

| | n | D1-close (median / %pos) |
|---|---|---|
| Fresh (no prior qualifying A-day) | 8,358 (61.8%) | +0.15% / 53.0% |
| Continuation (a prior A-day already qualified) | 5,170 (38.2%) | +0.09% / 51.8% |

Observed -1.17pp vs 1.79pp null p95, **p=0.1975** -- no effect. **CLOSED NEGATIVE.**

**Both chart-motivated hypotheses fail to generalize.** ATLANTAA and LLOYDSENGG were real,
individually legitimate observations -- the chart audit correctly surfaced them -- but neither
pattern holds up across the full population. Standard discipline applies: a single compelling
example motivates a test, not an adoption; both close here, don't reopen without materially new
evidence.
