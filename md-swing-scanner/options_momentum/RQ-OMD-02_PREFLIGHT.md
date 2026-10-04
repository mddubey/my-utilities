# RQ-OMD-02 — Preflight

2026-10-04 IST. **Not run.** Design is the critic's own (`RQ-OMD-02_SPEC.md`); this doc
freezes the implementation details the critic's text left open, before any result is seen.

## Research Preflight (CLAUDE.md)

1. **Population.** Same as OMD-01: every (ticker, bar) in `data/intraday_60m/` for all 2,192
   usable tickers, no F&O/liquidity/Nifty-500 restriction. F&O is a reporting split.
2. **Entry/decision clock.** Same as OMD-01 — historical path measurement, not a live
   decision. "Prior move" uses data through T's close; "subsequent path" uses only bars
   strictly after T.
3. **Stop/risk-unit definition.** None — still no R-multiple, no P&L, no trade outcome. Pure
   price-path statistics, now including retracement depth/timing.
4. **Exit engine.** None, same as OMD-01 — deliberately outside `primed_engine.py`/
   `backtest.py` territory.
5. **Comparison unit.** Continuous retracement-depth/speed distributions, conditioned on
   (magnitude bucket x origin [intraday vs overnight] x direction), reported with F&O as a
   split throughout, **critically including the F&O-unusual vs F&O-normal comparison the
   critic flagged as missing from OMD-01** (OMD-01's Table 6 compared F&O-unusual vs
   non-F&O-unusual, the wrong cut). No filter or gate is being fit here either.

## What's reused from OMD-01, unchanged

- `_lib.py` loaders, corp-action exclusion (+-1 session around a price-affecting ex-date),
  cumulative horizon convention (1H/2H/3H/rest-of-session/next-session, growing from T+1).
- The intraday-bar magnitude bucketing (trailing z-score, W=504/1512/3024 bars, |z| edges at
  1/2, crossed with sign) — unchanged, still the primary intraday bucketing.
- h1/h2/h3/eos/next signed return, MFE, MAE, time-to-MFE/MAE — unchanged definitions.
- OMD-01's 0.5x A/B/C/D classification — kept as a secondary cross-check column only, per the
  critic's explicit instruction not to re-derive or re-tune it here.

## New for OMD-02 — implementation choices surfaced for sign-off

**Overnight vs intraday-originated, operationalized** as OMD-01's existing `is_gap` split:
gap bar (09:15, bar_of_day=0) = overnight-originated; bars bar_of_day 1-6 = genuinely
intraday-originated. This is the split OMD-01 already computes but didn't magnitude-bucket —
OMD-02 removes that limitation.

**Gap-bar magnitude bucketing (new).** Same trailing-z-score method as intraday, but on a
gap-bar-only compact series (1 gap bar per session, vs 6 intraday bars per session). To keep
"unusual relative to own history" meaning the same **calendar span** for both origins (not
the same bar count), gap windows are matched to the intraday windows' time span:
  - W_gap = 84 sessions (~4 months, matches intraday W=504)
  - W_gap = 252 sessions (~1 year, matches intraday W=1512, **primary**)
  - W_gap = 504 sessions (~2 years, matches intraday W=3024)
Same |z| edges (1, 2) and sign-crossing as intraday. This is the one genuinely new piece of
infrastructure in this RQ; everything else is new measurement on top of OMD-01's existing
engine.

**Unified magnitude label for the headline tables:** `origin` (intraday / overnight) x
`direction` (up / down) x `magnitude` (normal / elevated / unusual), magnitude taken from
whichever bucketing applies (intraday W=1512 or gap W=252 — the two primary, calendar-matched
windows) — one clean 2x2x3 comparison grid. The other two window pairs (504/84 and 3024/504)
are the pre-declared robustness check, shown for the headline "unusual" cells only, same
pattern as OMD-01's Table 2.

**Retracement search window = the same "next session" cumulative window already computed**
(T+1 through the close of the session immediately following T's session) — the longest
window this engine already builds, so no new window definition is introduced. An observation
whose path never reaches a given retracement checkpoint within that window is marked
"not reached" (censored at the window edge), not imputed as infinite time or dropped. Checked
and reported as its own share (e.g. "38% of unusual up-moves never retrace 50% within the
next session") — a real, informative number per the critic's framing, not a gap to paper
over.

**Retracement crossing detection** uses intrabar High/Low (the adverse-direction extreme),
matching the convention already used for MFE/MAE — not Close-only, since a Close-only check
would miss a real intrabar retracement that closed back favorably.

**"Maximum continuation before any reversal begins"** = the best favorable-direction
excursion (MFE-style, High/Low-based) achieved over bars strictly before the first bar that
crosses the 25% retracement checkpoint. If 25% retracement is never reached within the
window, this equals the already-computed full-window `next_mfe` (no reversal began within
the data available) — explicit, not a silent edge case.

**Comparison breadth, per the critic's "compare against normal-sized moves" + "repeat broad
and F&O only as a split":** all 6 buckets (not unusual-only) x 2 origins x 2 F&O strata,
reported as the full retracement-depth/speed table — this is the direct answer to the
missing F&O-unusual-vs-F&O-normal comparison from OMD-01.

## Deliverables

1. `04_build_reversal_panel.py` — extends OMD-01's panel-building engine (same corp-action
   handling, same horizon ladder) with: gap-bar z-scores/buckets (3 windows), retracement
   checkpoint times (25/50/75/100%) and pre-reversal max continuation, over the next-session
   window. Parallelized, same pattern as `02_build_panel.py`. Rebuilt from raw
   `data/intraday_60m/` (not from OMD-01's saved panel, which doesn't carry raw High/Low).
2. `05_reversal_quality_map.py` — the actual report: retracement depth/speed distributions by
   bucket x origin x direction, F&O-unusual-vs-F&O-normal, robustness across the
   calendar-matched window pairs, year-by-year check. Hand-verify a handful of real
   (ticker, date, bar) retracement paths against raw data before trusting any aggregate
   (Rule #22), same as OMD-01.
3. `RQ-OMD-02_REPORT.md` — results, with an explicit closable "would this branch survive
   contact with option economics" read, per the critic's "kill the branch quickly if the
   numbers are small" framing — still no option data touched, just stating what number would
   or wouldn't be worth the options-economics follow-up.

## What this run will NOT do (per spec, reconfirmed)

No option data, no IV/premium analysis, no strategy construction, no new threshold
optimization (25/50/75/100% are fixed checkpoints, not searched), no F&O population
restriction.
