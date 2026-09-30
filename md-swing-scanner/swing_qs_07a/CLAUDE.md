# swing_qs_07a — Track B: Reverse-Engineering Short-Horizon Fast Movers

Independent research track, critic's explicit architecture (2026-09-29): **no
dependency on Track A** (`swing_qs/`'s QS-A monetization arc, closed for the
session at RQ-06E — see `swing_qs/CLAUDE.md`'s standing closed result). Don't let
"RQ-07A found feature X" retroactively modify QS-A, and don't let "QS-A has
feature Y" contaminate the RQ-07A winner population — kept strictly separate.

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
complete frozen ledger. Per critic's own next-step pointer: research should
return to QS-A's actual open product problem (exit/monetization, RQ-06's
original unresolved question) using everything learned here as context, not
attempting to make S the answer to it.
