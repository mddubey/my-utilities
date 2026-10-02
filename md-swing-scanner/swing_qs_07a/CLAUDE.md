# swing_qs_07a — Outcome-First Short-Horizon Entry Research

**RESET 2026-10-01 (critic + user, explicit correction of the prior framing
below)**: this is NOT a satellite track that exists to eventually improve
`swing_qs/`'s QS-A/BC breakout-continuation machinery. The original research
question was always outcome-first: *forget existing entry philosophy — what
does a genuinely large short-term move actually look like, and what, if
anything, is observable before it?* That's why discovery deliberately expanded
to the full ~2,327-ticker NSE universe rather than staying inside QS-A's
breakout population. **QS-A/BC is irrelevant to this research question going
forward** — it was a useful CONTROLLED BASELINE for one integration experiment
(RQ-QS-07A-P3 through P6, now closed — see below), not the target
architecture this track exists to serve. Don't let "QS-A has feature Y"
contaminate discovery here, and don't assume findings here need to flow back
into QS-A at all.

## The actual question (RQ-QS-07A-1, critic's exact pre-registered wording)

"Across the full eligible universe, what types of short-horizon price paths
naturally precede and follow unusually large 1-, 2-, and 3-day moves?"

**Deliberately NOT yet**: "what predicts a fast mover" — that's a later question.
This first pass builds a neutral event matrix and characterizes the natural
distribution BEFORE choosing what counts as a "fast mover" (no threshold, no
score, no model, no filter this pass) — otherwise +3%/+5%/+8% becomes another
arbitrary parameter picked because it produces convenient statistics.

## Population

`nse_equity_universe.csv` (RQ-QS-07U, 2,327 tickers) — NOT restricted to NIFTY
500 or F&O-eligible names. Per critic: "artificially restricting ourselves to
NIFTY 500 creates another selection boundary... that is potentially exactly the
phenomenon we're trying to discover." NIFTY-500 and F&O membership are attached
as METADATA tags (current-membership only, v1 — see RQ-QS-07U's own disclosed
point-in-time limitation), not the population definition.

## Universe integrity, inherited from RQ-QS-07U — read before trusting anything here

v1 fixes the listing-date side only (a stock's history starts at its own real
NSE listing date). Does NOT yet include the delisted-companies backfill — real
stocks that existed and traded for years but have since delisted are still
invisible to the whole population. Known, disclosed, open gap — not attempted
further per explicit user direction ("ignore that"). Any performance-adjacent
claim from this line inherits that limitation; structural/descriptive findings
(the shape of what precedes/follows a move) are less directly affected than a
"here's the win rate" claim would be, but the caveat applies to both.

## Standing guardrails (same discipline as every other line in this project)

- Rule #22: hand-verify surprising aggregate results against real raw bars.
- No lookahead: every predictor/feature is computed from information available
  AT or BEFORE the observation day; every outcome is computed strictly forward
  from it. Corp-action days truncate the forward walk (same convention as
  04A/06B/every other RQ this session).
- Path-shape categories are PRE-DECLARED in the script's own docstring before
  running — not chosen after seeing which one looks most interesting.

## Standing closed result (2026-09-30) — S→QS-A integration, do not re-litigate without new evidence

RQ-QS-07A-P3 through P6 jointly established two precursor states (W = weak-
state/oversold-reversal, S = strong-state/trend-continuation), tested S as a
frozen intervention on QS-A's real 46,613-position trade population (Track A),
and CLOSED the integration attempt. Full chain: P3 (observational overlay — S
correlated with better retention historically; W structurally incompatible
with QS-A's breakout-high entry, cannot even coincide) → P4 (frozen S(T-1)
filter intervention on the full historical population — looked strongly
positive on every metric) → P5 (pre-registered chronological OOS validation,
cutoff 2025-01-01, chosen BEFORE looking at results — the intervention's
advantage reversed in 2026 specifically, not just weakened) → P6 (failure
anatomy using only already-existing trajectory variables — both the
opportunity/MFE channel AND the retention/giveback channel reversed together
in 2026, not a clean exit-only failure).

**Per critic's exact verdict, adopted verbatim**: "S was a valid historical
state detector, but its apparent QS-A product edge was regime-dependent and
did not survive chronological OOS intervention testing" — not "S failed."
S discovery remains validated on its own population; only S→QS-A production
integration is closed. **Do not reopen**: no new S threshold/regime filter, no
"why did 2026 specifically break" causal investigation (explicitly the
dangerous fork the critic warned against — regime? breadth? sector?
liquidity? volatility? relative strength? price level? F&O composition? —
none of it authorized), no rescuing the failure via re-slicing 2025-vs-2026
after the fact. W remains separately parked (structurally incompatible with
QS-A, never a failure of W itself — whether W could become its OWN standalone
event-driven product is a genuinely different, still-open future question,
just not opened now). Full detail: `FINDINGS.md`, "RQ-QS-07A-P3" through
"RQ-QS-07A-P6" sections — the P6 section's "FINAL CLOSURE" block has the
complete frozen ledger.

**CORRECTION (2026-10-01, critic's own explicit walk-back of the very next
line that used to be here)**: this does NOT mean "research should return to
QS-A's exit/monetization problem." That overcorrects. The actual lesson is
narrower: *S is not validated as an overlay on the existing QS-A entry
population* — it says nothing about whether the broader outcome-first
discovery program (this entire track) is finished. See "Research posture,
reset 2026-10-01" below for where this track actually goes next.

## Research posture, reset 2026-10-01 (critic + user, explicit)

**The research question, stated precisely**: among all NSE-listed stocks,
what characteristics are present before an exceptional short-term move, and
can those characteristics become a prospective, executable entry rule? This
is NOT "how do we improve QS-A" — QS-A was one controlled-baseline
integration experiment (P3-P6, now closed), not the target architecture.
W and S are **candidate precursor phenomena for a possibly entirely new
entry product**, not filters for an old one. The eventual entry architecture
could look nothing like QS-A's `breakout → gate → breach → entry → exit` —
it might instead be `broad universe → pre-event state → trigger → entry →
short-horizon exit`. We have not earned the right to choose between
architectures yet.

**The five-phase loop for turning a discovered characteristic into an entry**
(do not skip phases, do not reorder):
1. **Define the outcome** — frozen beforehand (e.g. "exceptional D3 move from
   a decision-time reference"); precise about MFE vs. close return, horizon,
   reference price, minimum meaningful movement, corp-action/circuit handling.
2. **Discover characteristics** — only information available before the move
   (most of this is already done — see "What's already established" below).
3. **Turn a characteristic into a candidate state** — this is where W/S came
   from. The question is NOT "does state X improve an existing product," it's
   "if I observed this state at T, can I define an executable trigger at T or
   T+1 that captures the subsequent exceptional-move distribution?"
4. **Candidate entry construction** — state + price trigger, state
   transition, recovery-from-decline, local-structure breakout, volume
   confirmation, etc. — but ONLY using characteristics that already survived
   phase 2. Not a new generic-indicator search.
5. **OOS/prospective validation of the ENTRY itself** — only after an entry
   construct exists does stop/sizing/exit/options/capacity/slippage become a
   relevant question. Those are downstream, not now.

**The core scientific-loop discipline (do not invert)**: never define an
entry by the outcome ("buy stocks that go on to make +10% in 3 days" is
useless by construction). Always: "among stocks that achieved the outcome,
what was observable at T-1/T that distinguished them from the rest?" — freeze
that characteristic, then test it forward.

### Breadth-before-depth rule (explicit, adopted 2026-10-01)

**We are in broad discovery. Breadth matters more than squeezing the last 2%
out of one feature.** Concretely: a feature gets at most four passes —
(1) does it have signal? (2) is the signal robust across sensible
strata/time? (3) can it become a prospective entry concept? (4) does that
concept survive an honest validation? **If still tweaking definitions,
thresholds, subgroups, or explanations after four passes — park it and move
to a different hypothesis family.** Explicitly prohibited as a continuation
of the SAME feature: "maybe split the period differently," "maybe a
different percentile," "maybe combine with N other variables," any further
post-hoc archaeology on a result already reported. Preserve the result
honestly (as this file and `FINDINGS.md` already do for S/W) and move
sideways. This is exactly what the S→QS-A chain (P3-P6, four focused RQs,
then stop) already modeled correctly — keep doing that, don't let any future
hypothesis get a fifth or sixth pass out of attachment to it.

### What's already established (don't re-derive — reuse, cite, or stratify by)

- Exceptional short-term movers are real and measurable across the broad
  universe (07A-1 through 07A-2B).
- Trend strength has real signal, but it's one underlying latent dimension
  expressed through 5 correlated variables, not 5 independent ones (07A-3R).
- Market-relative strength (stock-vs-NIFTY) retains ~83-89% of the absolute
  trend-strength gap — real, but adds little beyond what absolute momentum
  already captures (07A-4).
- The trend-strength relationship is NOT monotonic — it's an asymmetric
  U-shape. The weakest decile shows a real, separate elevation on top of the
  already-known strong-trend tail (07A-5).
- Within that weak-state tail, recent DECLINE DEPTH (how far below the
  stock's own 10-day high) is the dominant, robust mechanism — recent
  acceleration (3-day return) is secondary and noisier. Robust across every
  year/liquidity/F&O/circuit stratum tested (07A-6, 07A-6R).
- The "sharp drop → pause → fast move" shape is visible in the real
  day-by-day trajectory, not just inferred from cross-sectional stats — MAE
  stays shallow post-trigger while the move keeps compounding through D3
  (07A-6T).
- A real joint T-close signature exists combining decline-depth with the
  trigger day's own direction; the dominant variable is intraday-observable
  in principle (needs only the live price vs. an already-known prior high),
  but genuine pre-close/intraday confirmation remains UNCONFIRMED at scale —
  bottlenecked by this project's thin (~3.5 month) intraday history, not the
  phenomenon itself (07A-6U).
- Generic TA shopping (volume, volatility, candle shape, pivots, RSI in
  isolation) mostly failed to add independent explanatory power on top of
  the trend-strength dimension (07A-3, 07A-3R, pivot-distance supplement).
- The phenomenon is NOT simply "small illiquid stocks go crazy" — liquidity,
  F&O status, circuit involvement, NIFTY membership, and year all change the
  magnitude/base rate and must stay STRATIFICATION dimensions, never
  convenient filters, until a candidate earns promotion on its own terms.
- S (strong-state) and W (weak-state) are the first two candidate precursor
  STATES discovered this way — real on their own population (07A-5/5R/6U),
  frozen into a leak-free candidate spec (CG1), characterized historically
  (CG2), holdout-validated as a specification (CG3-H, encouraging), and
  separately found NOT to survive being grafted onto QS-A's specific
  breakout-continuation entry population (P3-P6, closed — see above). That
  last result is about QS-A compatibility, not about whether S/W could
  anchor their OWN entry construct (phase 3-5 above, not yet attempted).

### Research board — small portfolio of distinct hypothesis families, not one rabbit hole

**Next item to attempt, per critic's final verdict (2026-10-02)**:
compression → expansion and BT1/S monetization are both closed — **Strong-
State Transition is next up**, pre-registered scope below. Explicitly NOT
allowed on this pass: S threshold tuning, BT1 combinations, generic TA
combinations, exit optimization, liquidity rescue, BC/QS-A overlay, "best"
threshold selection — first pass characterizes the state CHANGE, not a
trading rule.

| Hypothesis family | Status | Effort allowed |
|---|---|---|
| Weak-state recovery (decline-depth, 07A-6/6R/6T) | 🔴 **PARKED, final** (E1/E1-S, 2026-10-01 — two stop conventions tried AND a literature check done before accepting closure; oversold-bounce literature's own textbook stop is E1's reversal-candle-low, already failed; widening to E1-S's structural low barely moved giveback (100.3%→99.1%) despite ~53% wider risk — strong evidence the stop isn't the lever at all, so a 3rd stop (ATR-based, also literature-legitimate) was explicitly declined as "stop discovery, not entry discovery." Banked verbatim: "W identifies a genuine exceptional short-term opportunity, but the first standalone entry construct failed under its reversal-candle stop... Published practice confirms multiple legitimate stop conventions, but provides no evidence that another stop would solve W's monetization problem. No third stop variant will be tested at this stage.") Underlying phenomenon stays validated, open only for a differently-shaped future product (e.g. longer horizon, given 33.8% of E1-S trades wanted the full 15-day cap) | Do not attempt a third stop variant without genuinely new evidence that the STOP (not the construct generally) is the cause |
| Compression → expansion (range contraction before the move — VCP-adjacent, not VCP-prescriptive) | 🔴 **Closed, negative** (C1, 2026-10-01 — all 3 pre-declared metrics (ATR ratio, range ratio, BBW percentile) agree Cohort A is mildly MORE expanded at T0 than matched control, not tighter; hand-verified on 5 real events, formulas confirmed correct, not a bug. Simple range-contraction is not a precursor signature for this outcome; effect too small/overlapping to act on regardless of direction) | Do not reopen without new evidence; VCP's full specific construct (multi-stage tightening + volume dry-up) remains untested if ever revisited |
| Static S as a 3-day stop/target trade product (BT1/BT1-S/BT1-S-H1/BT1-S-RR) | 🔴 **CLOSED AS A PRODUCT, 2026-10-02, critic's final verdict** — BT1 real/robust but closed NEGATIVE as an S supplement, confirmed twice independently (close-based + real path-based High/Low simulation). Plain S's own real stop/target edge too thin after costs (mean R +0.047-0.092 ≈ 0.2-0.25% of capital/trade across 6 tested stop/target geometries, median R always negative). Liquidity-restriction rejected as a rescue (not established that low-liquidity names are disproportionately destroying the edge). Further S filter/threshold hunting explicitly rejected (would convert outcome-first discovery into optimization-around-a-known-result). **S as a research observation (identifies a real, robust, larger-opportunity state) stays BANKED — this is a product closure, not a phenomenon closure.** Cross-track insight preserved (not a new RQ): the Primed Gate "Extended beats Fresh" pattern independently confirms crossing-the-level and already-past-it are different states, reconciling cleanly with a concurrent session's stall finding (RQ-PB-2) | Do not re-test BT1 on S, re-sweep S's stop/target, or liquidity-filter S as a rescue, without genuinely new evidence |
| **Strong-state transition** (S asks "is it strong?"; this asks "is it BECOMING strong, before the static condition has saturated?") | 🟢 **BANKED as a regime-dependent candidate** (SST1/SST1-R1/SST1-E1/SST1-E1-R1, 2026-10-02 — full chain: discovery → W-overlap audit (passed) → first entry construct (promising pooled, weak 2025-26) → frozen-path regime diagnosis). The regime diagnosis is decisive: under IDENTICAL frozen mechanics, the `established` control population degraded by almost the same shape/magnitude as fresh in 2025-26 (MFE -9% in both, target-hit rate roughly halved in both) and actually flipped negative while fresh stayed barely positive — proving this is a broad monetization difficulty in a tough regime, not a fresh-specific decay. Freshness's edge OVER established was preserved through the weak period. **Not a universal standalone product, but a real, viable trade under favorable conditions** — matches the user's standing context that 2025-26 has been a weak regime for longs generally | Do not modify/optimize further now. Revisit when market conditions turn, or as a candidate for a future regime-adaptive-exit research bucket (separate, not started) |
| Peer/sector relative strength | ⚪ Infrastructure-blocked (no point-in-time sector mapping exists) | Parked, not attempted |
| Generic TA combinations (already tried: volume, ATR, candle shape, pivots, isolated RSI) | 🔴 Closed | Do not reopen without new evidence |
| QS-A/BC integration (P3-P6) | 🔴 Closed | Do not reopen |
| QS-A exit/monetization | ⚪ Not this track's problem | Ignore here — belongs to `swing_qs/`, not started, not blocking this track |

**Top-level principle**: *harvest a feature's information value, don't
exhaustively explain it.* If a feature gives a useful clue, capture it. If it
survives a reasonable robustness test, try to turn it into an entry. If it
doesn't, move sideways to a different hypothesis family. The goal is
discovering what KIND of pre-entry information matters, not proving one
particular feature is the final answer.
