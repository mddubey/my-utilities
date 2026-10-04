# RQ-OMD-01 — Preflight

2026-10-04 IST. **Not run.** Written before any result is seen, per CLAUDE.md's Research
Preflight, "Robustness Before Finding" (predeclare horizons/buckets), and "Logic-first
filters" (cut-offs from stated logic, not data-mined after seeing results).

## 1H candle construction — verified 2026-10-04 against `data/intraday_60m/`

- **Universe with a file:** 2,266 / 2,328 tickers in `nse_equity_universe.csv`.
- **Date range:** 2023-10-23 → 2026-10-01 (not refreshed by the daily EOD run; manual/monthly
  top-up, see `data/README.md`).
- **Bars/day:** 7 nominal, starting 09:15 IST: 09:15, 10:15, 11:15, 12:15, 13:15, 14:15,
  15:15. Confirmed on a random 8-ticker sample — modal row count is exactly 7/day (716/723
  sampled days on one ticker); short days (1–6 bars) exist and are holidays/half-days/
  late-start tickers, not a data defect.
- **15:15 bar is a partial/stub** covering roughly 15:15→15:25/15:30 close, not a full hour.
  For F&O names after 2026-08-03 (closing-auction start) it may include CAS auction residue —
  unverified at bar level, carried over as a caveat from `data/README.md`.
- **09:15 bar is a real (non-flat) candle despite near-zero reported Volume** on 83–93% of
  days in the sample (checked 8 tickers) — Open/High/Low/Close differ from each other, so the
  bar is usable for price, just not for volume-based segmentation. Matches `data/README.md`'s
  documented Yahoo quirk that true intraday high/low is missed on ~72% of stock-days; cross-
  checked 4 tickers x 3 days against `data/daily/` and saw the same small (<1%) O/H/L
  discrepancies already on record, nothing new.
- **Gaps:** holiday sessions are cleanly absent (e.g. 2023-10-24 Diwali Muhurat skipped for
  the sample ticker) — no fabricated bar on non-trading days seen in the sample.
- **Corporate actions:** prices are split-adjusted at fetch time (per `data/README.md`) but
  NOT corp-action/dividend adjusted in a PIT-consistent way, and PREVCLOSE-style jumps can
  still appear. Mitigation below.
- **Timestamps:** stored UTC, converted to Asia/Kolkata for all work here.

None of this contradicts `data/README.md`; it confirms the documented caveats apply the same
way at the 1H granularity. No new defect found that blocks the study.

## Research Preflight (CLAUDE.md, answered before any code)

1. **Population.** Every (ticker, bar) pair in `data/intraday_60m/` for all 2,266 tickers
   with a file — no F&O/Nifty-500/liquidity/technical restriction. F&O membership
   (`fo_universe.csv`, point-in-time via `data/nse_fo_bhav/` listings) is attached as a
   reporting split only, never a filter. Actual counts, date range, bars/ticker and
   completeness are reported from the real files at run time (not assumed from this doc).
2. **Entry/decision clock.** Not applicable in the usual T-1/same-day sense — there is no
   live decision being gated here, only a historical measurement of realized bar-to-bar
   price paths. The only clock discipline that matters: the "prior move" for bar T uses
   only data through T's own close (T is a *completed* bar), and "forward behaviour" uses
   only bars strictly after T. No future information crosses that boundary at any point.
3. **Stop / risk-unit definition.** None. This study reports no R-multiple, no P&L, no
   trade outcome — only raw price-path statistics (returns, MFE, MAE, time-to-move). Rule
   #20 (declare the stop before any R-based analysis) does not apply because there is no
   R-based analysis here; flagged explicitly so it isn't mistaken for an oversight.
4. **Exit engine.** None — deliberately. This is not `primed_engine.py` or `backtest.py`
   territory; it's a pure price-path measurement over `data/intraday_60m/`, independent of
   any position-gating logic. No production exit/entry function is reused or reimplemented.
5. **Comparison unit.** Distributions of forward price-path behaviour (return / MFE / MAE /
   time-to-move / behaviour-type share), conditioned on pre-declared buckets of the prior
   bar's stock-relative move magnitude, reported per horizon. No filter, gate or rule is
   being fit — this produces a map, not a promotable signal (Rule #21 doesn't trigger
   because nothing is proposed as an intervention yet).

## Pre-declared parameters (fixed now, not tuned after seeing results)

**Bar universe for "prior move."** Two kinds of bar-to-bar return exist and are **never
pooled** (same discipline as not pooling R1/R2 — mechanically different situations):
- **Intraday bars** (10:15, 11:15, 12:15, 13:15, 14:15, 15:15 close vs the immediately
  prior bar's close, same session): pure intraday momentum, no overnight gap.
- **Gap bar** (09:15 close vs prior session's 15:15 close): overnight gap + first-hour
  move conflated. Reported as its own separate split, not merged into the intraday set.
Primary discovery population = intraday bars only. Gap-bar behaviour is reported
descriptively alongside, clearly labeled.

**Corporate-action exclusion.** Any bar whose return window (prior bar → this bar, or this
bar → forward horizon) falls on a session within 1 trading day of an ex-date in
`data/nse_corp_actions.csv` classified as price-affecting (split/sub-division/bonus/rights/
demerger/scheme/arrangement/amalgamation/consolidation/reduction, per `data/README.md`'s own
classification) is dropped from both the prior-move and forward-outcome calculation for that
ticker-day. Counted and reported, not silently dropped.

**Stock-relative magnitude bucketing (predeclared, Section 4).** For each ticker, at each
bar T, compute a trailing z-score of the bar's intraday log-return against that same ticker's
own trailing distribution of intraday bar returns:
  z_T = (r_T − mean(r over trailing W bars)) / std(r over trailing W bars)
- **W = 252 trading sessions x 6 intraday bars/session = 1,512 bars (~1 trading year)** as
  the primary window — long enough to be a real "historical behaviour" baseline, short
  enough that most of the universe (listed before mid-2024) qualifies for most of the sample.
  (Corrected 2026-10-04: an earlier draft of this doc mislabeled this as "~2 years" — 252
  sessions is 1 year, not 2. Caught before running, per Rule #22's spirit of verifying
  arithmetic before trusting it.)
- **Robustness check, pre-declared per Rule #19 (parameterized-feature corollary) — not
  picked after seeing results:** two materially different nearby windows, W = 504 bars
  (~84 sessions, ~4 months) and W = 3,024 bars (~504 sessions, ~2 trading years, close to the
  full available history), run alongside the primary W and shown side by side, not
  substituted in if the primary result looks weak.
- **Bucket edges on |z|, fixed now:** normal <1, elevated 1–2, unusual >=2. Crossed with
  sign (up/down) = 6 buckets. "Unusually large" in the spec = the two unusual buckets
  (|z|>=2, up and down separately — never pooled, direction is not assumed to behave the
  same).
- Bars before a ticker has W trailing observations are excluded from bucketing (reported as
  a coverage loss, not backfilled or assumed-normal).

**Forward horizons (predeclared, Section 3), never collapsed to one number — cumulative,
growing from T+1, not five disjoint windows:** 1H (bar T+1), 2H (T+1..T+2), 3H (T+1..T+3),
remainder-of-session (T+1..session close), next session (T+1..next session's close, i.e. this
horizon's window is a superset of remainder-of-session's). Cumulative framing chosen over
disjoint segments because the spec's own framing is "map the decay of the phenomenon" as the
look-ahead window grows — a disjoint-segment design would answer a different question
(what happens in segment N alone) than the one asked. Flagged here as a judgment call, not
explicit in the spec text. A corp-action exclusion anywhere inside a given horizon's window
breaks that horizon's walk for that observation (same convention as the swing-completion
pre-mortem's corp_action_day rule); H1/H2/H3 can cross a session boundary near the close
(next bar is simply the next bar in the data), remainder-of-session and next-session cannot
by construction.

**Gap-bar scope, narrowed deliberately:** gap bars get the same r_T + forward-metric pipeline
as intraday bars (so the descriptive split is real, not hand-waved), but are NOT z-bucketed
against their own historical gap distribution in this first pass — that would require a
parallel trailing-window infrastructure sized in gap-bar units (~1/6th as many observations
per unit time) for a split the spec treats as secondary context, not the primary ask. Gap
bars are reported as one unconditional up/down split only. Noted explicitly so it isn't
mistaken for an oversight; can be extended later if gap behaviour turns out to matter.

**Forward metrics per horizon, all directional (signed relative to the initial move's own
direction, so "favorable" always means "same direction as the initial move"):**
- forward return (close-to-close, T to horizon end)
- MFE (best close-to-close point reached intrabar, in the initial move's direction, within
  the horizon)
- MAE (worst point reached against the initial move's direction, within the horizon)
- time-to-MFE / time-to-MAE, in bars
- retention = forward return at horizon end as a fraction of the initial move's own
  magnitude |r_T| (can be negative = reversal beyond start, >1 = outright continuation past
  the original move's size)

**Behaviour classification A/B/C/D (predeclared, Section 5) — one simple, stated rule, not
optimized:**
Defined on the **first short horizon = 2H** (two bars after T) as the "immediate" window,
and **remainder-of-session + next-session horizons combined** as the "delayed" window:
- **A. Immediate continuation:** same-direction forward return at the 2H horizon >= 0.5 x
  |r_T| (retention >= 0.5), AND MAE within that 2H window does not exceed 0.5 x |r_T|
  against the move (continuation wasn't bought back through more than half the original move
  first).
- **B. Immediate reversal:** opposite-direction forward return at the 2H horizon, magnitude
  >= 0.5 x |r_T| (retention <= −0.5).
- **C. Stall:** neither A nor B nor D — |retention| at 2H stays inside (−0.5, 0.5) AND it
  still sits inside that band at the delayed-window horizons too (never breaks out either
  way within the data available).
- **D. Delayed continuation:** fails A and B at 2H (stalls initially), but same-direction
  retention reaches >= 0.5 x |r_T| by the delayed window (remainder-of-session or next
  session).
These four are collectively exhaustive and mutually exclusive by construction; 0.5x is the
single predeclared threshold used everywhere above (no second threshold introduced quietly).
This is explicitly a first-cut, stated classification — not claimed to be the only valid one;
the full continuous distributions (Section 6) are reported as the primary output, with A/B/C/D
as a readable summary layered on top, per the spec's "report the full distribution, don't
reduce to one number" instruction.

## What this run will NOT do (Section 7, reconfirmed)

No entry rule, no stop/target optimization, no strike/DTE selection, no breakout detector, no
F&O filter as a population restriction, no threshold search for "the best" move size, no ML,
no options-strategy backtest. Win-rate-style language is not used anywhere in this RQ's
output — there is no trade, so no win/loss.

## Deliverables

1. `01_verify_1h_construction.py` — formalizes the checks above into a script + saved output
   (so the verification is reproducible, not just this doc's prose).
2. `02_build_panel.py` — builds the full (ticker, bar) panel with prior-move z-score/bucket
   and all forward metrics at all horizons, for all three W windows. Parallelized across
   ticker chunks with live progress output (per standing practice for full-universe runs).
3. `03_behaviour_map.py` — produces the Section 4-6 tables: full distributions by bucket x
   horizon, A/B/C/D shares by bucket, timing-structure tables, gap-bar split shown
   separately, F&O-vs-not split shown separately, and the robustness check across the three
   W windows (Rule #19) before anything is called a candidate finding.
4. `RQ-OMD-01_REPORT.md` — the actual numbers, written only after the above runs and is
   hand-verified on a handful of concrete (ticker, date) examples per Rule #22 before any
   aggregate claim is reported.

## Open implementation choices surfaced here for sign-off (not buried in code)

- W_primary = 1,512 bars (~2y), robustness windows 504 and 3,024 bars — reasonable, but
  arbitrary; flagging before building on it.
- A/B/C/D single threshold = 0.5x the initial move, measured at 2H for "immediate" — a
  judgment call, not derived from data. Easy to re-run at a different multiple since the
  continuous distributions are the primary output regardless.
- Corp-action exclusion window = ±1 trading session around a price-affecting ex-date.
