# RQ-OMD-02 — Fast Reversal Quality — Report

2026-10-04 IST. Built per `RQ-OMD-02_PREFLIGHT.md` (all checkpoints/windows frozen before this
run). Raw output: `reversal_quality_output.txt`. Hand-verified 3 real overnight-originated
retracement paths against raw `data/intraday_60m/` CSVs before trusting any aggregate (Rule
#22) — all 3 matched the manual crossing-time calculation exactly (one near-miss on the 100%
checkpoint traced to real tick-level floating-point precision, not a bug).

**This run also caught and fixed the bug described in `RQ-OMD-01_REPORT.md`'s correction note**
(flat `r_T==0` bars silently misclassified as "down" events) and a second, related edge case:
when the 25% retracement checkpoint is crossed in the very first forward bar, "continuation
before reversal" isn't computable from 1H OHLC (no prior bar exists, and a single bar's
High/Low carry no reliable intrabar ordering) — reported as NaN, not a fabricated 0. Both
fixes verified via a `pre_reversal_mfe <= next_mfe` invariant that now holds with zero
violations across 8.36M eligible rows.

## Population

Same panel as the corrected OMD-01: 8,379,394 qualifying events, 2,192 tickers,
2023-10-23 -> 2026-10-01. 7,120,173 intraday-originated, 1,259,221 overnight-originated.

## Headline result: a bigger move mostly STALLS, it doesn't sharply reverse

**Table 1 — retracement reach-rate and median time-to-reach, by bucket x origin (primary
windows, calendar-matched ~1y):**

| group | bucket | n | reach 25% | t@25 | reach 50% | t@50 | reach 75% | t@75 | reach 100% | t@100 |
|---|---|---|---|---|---|---|---|---|---|---|
| intraday | dn_unusual | 89,082 | 89.5% | 1 | 78.7% | 2 | 66.6% | 2 | 53.1% | 3 |
| intraday | dn_elevated | 338,603 | 92.5% | 1 | 86.0% | 1 | 78.7% | 2 | 70.3% | 2 |
| intraday | dn_normal | 1,765,068 | 95.0% | 1 | 93.0% | 1 | 90.6% | 1 | 87.9% | 1 |
| intraday | up_normal | 1,421,560 | 95.0% | 1 | 93.3% | 1 | 91.5% | 1 | 89.3% | 1 |
| intraday | up_elevated | 303,589 | 92.6% | 1 | 86.5% | 1 | 79.9% | 2 | 72.3% | 2 |
| intraday | up_unusual | 119,394 | 88.2% | 1 | 76.6% | 2 | 63.8% | 2 | 50.2% | 3 |
| overnight | dn_unusual | 16,339 | 78.2% | 2 | 61.4% | 5 | 45.9% | 6 | 30.9% | 7 |
| overnight | dn_normal | 260,538 | 91.4% | 1 | 85.7% | 1 | 80.2% | 1 | 74.7% | 2 |
| overnight | up_normal | 290,101 | 94.2% | 1 | 89.8% | 1 | 85.0% | 1 | 79.7% | 2 |
| overnight | up_unusual | 20,566 | 73.0% | 2 | 49.9% | 5 | 31.6% | 7 | 18.7% | 7 |

(dn_elevated/up_elevated overnight rows and full tables in `reversal_quality_output.txt`.)

**This reconciles with, and sharpens, OMD-01's "unusual moves see weaker continuation"
finding — "weaker continuation" mostly means STALL, not a deep give-back.** Unusual moves
retrace their own size *less often and more slowly* than normal moves do (dn_unusual only
53% ever fully round-trips vs dn_normal's 88%). That's the opposite direction you'd expect if
"weaker continuation" meant "sharper reversal" — it doesn't. A big move mostly just stops
where it is; it rarely gives most of itself back within the next session. **Directly answers
the critic's Question A/B distinction with the depth dimension they asked for**: the dominant
unusual-move outcome is exhaustion/stall at the new level, not a clean, fast, tradeable
reversal. This is a harder number for a "buy puts after a spike" idea than OMD-01's rate alone
suggested — a put needs the stock to actually fall meaningfully, and most unusual up-moves
don't.

## Overnight vs intraday decomposition (the critic's required step)

**Overnight-originated unusual moves are STICKIER (retrace less, slower) than intraday-
originated ones** — overnight up_unusual reaches full round-trip only 18.7% of the time
(median 7 bars when it does) vs intraday up_unusual's 50.2% (median 3 bars). Same pattern on
the down side (30.9% vs 53.1%). Robust across all 3 calendar-matched window pairs (Table 3,
`reversal_quality_output.txt`) and stable 2024-2026 (Table 5).

**This argues against, not for, "this is just overnight reversal"** (the critic's open
Question B) — if the up-fade found in OMD-01 were simply a repackaging of known overnight-to-
intraday reversal, overnight-originated moves should show *more* retracement, not markedly
less. What OMD-01's gap-bar corroboration actually captured was a *small, direction-biased*
shift (enough to flip median sign below 50%), not a deep reversal — fully consistent with this
table's low reach-rates for overnight-originated moves. The two findings don't contradict; a
move can flip sign on net while still rarely giving back half of itself, and that is
specifically what overnight-originated moves do even less than intraday ones.

## Table 4 — F&O-unusual vs F&O-normal (the comparison OMD-01 was missing)

| group | bucket | n | reach 50% | reach 100% |
|---|---|---|---|---|
| F&O intraday | dn_unusual | 9,874 | 73.8% | 51.4% |
| F&O intraday | dn_normal | 201,466 | 92.3% | 86.9% |
| F&O intraday | up_normal | 184,643 | 91.7% | 86.5% |
| F&O intraday | up_unusual | 13,004 | 68.9% | 44.9% |
| non-F&O intraday | dn_unusual | 79,208 | 79.3% | 53.3% |
| non-F&O intraday | up_unusual | 106,390 | 77.5% | 50.8% |

**The unusual-stalls-more-than-normal pattern holds within F&O names too** — this is a real,
not purely compositional, effect (answers the critic's "is this just liquidity/sector
composition" concern directly: no, the same qualitative pattern survives inside the F&O-only
population). **But the F&O-vs-non-F&O gap itself is modest by this metric** (F&O dn_unusual
51.4% vs non-F&O 53.3% full-round-trip — nearly identical), noticeably smaller than the gap
OMD-01's A/B/C/D view showed (42% vs 32-36% combined continuation). That gap looks more
sensitive to the specific 0.5x classification threshold than to a deep structural F&O
difference — worth keeping as a diagnostic caveat, not promoting the F&O angle further on
threshold-based numbers alone.

## What this tells us about the critic's three open questions

- **A. Rate vs economics:** answered directionally — the "reversal" OMD-01 found is mostly a
  stall, not a deep give-back. Pre-reversal continuation (Table 2), where measurable (21-44%
  of cases depending on bucket/origin — the rest cross 25% in the first bar, not measurable
  from 1H OHLC), has a similar median magnitude (~0.8-1.2%) across buckets — no bucket shows a
  dramatically larger "ran further first" pattern than another.
- **B. Overnight confound:** addressed, not fully closed — overnight-originated unusual moves
  are *less* prone to retracement than intraday-originated ones, which argues against (not
  for) the up-fade being a repackaged overnight-reversal effect, but a full mechanism
  attribution would need more than this stock-only data provides.
- **C. Options economics:** still untouched, by design (out of scope for this RQ) — nothing
  here changes the critic's IV/premium caution.

## What this run does NOT do (per spec)

No option data, no IV/premium analysis, no strategy construction, no new threshold
optimization (25/50/75/100% were fixed before this run, not searched), no F&O population
restriction.

## Next-decision options (not decided here)

1. Given the dominant outcome is stall, not deep reversal, the put-after-spike angle looks
   weaker than OMD-01's rate-only view suggested — worth an explicit critic check-in before
   spending more research time on it.
2. The overnight-vs-intraday asymmetry (overnight moves are stickier) is itself a candidate
   observation worth a dedicated look if a trend-persistence angle (not reversal) is ever of
   interest — out of scope for the current discovery thread, noted for later.
3. Close this branch of the options-momentum discovery and move to another market-behaviour
   family, per OMD-01's spec's own framing, if the critic agrees stall-dominance settles the
   question.
