# Quick Swing (QS) Product Definition (v0.2, updated 2026-09-27)

**Naming note**: this file was originally titled "BC Product Definition" from when it
was first drafted — it has always been about the new Quick Swing (QS) product, never
about BC. Corrected here; the content below was never about BC.

## Two products, not one — the biggest architectural clarification this weekend

- **Product A — BC (existing, positional-leaning)**: 10-15 trading day horizon, ATR0
  structural stop + K=2 swing-low trail + max-hold cap. Frozen, not touched by this line.
- **Product B — Quick Swing (QS, this document)**: 3-5 trading day primary objective,
  10-day absolute ceiling. Different stop philosophy (S1b, not S0), different exit
  philosophy (still being built), stock + options-compatible. Do not let QS silently
  inherit Product A's exit mechanics, filters, or assumptions — every integrity bug this
  line has caught (wrong exit engine, position-blocking bias, same-day gate leakage,
  hidden stop definition) came from exactly that failure mode.

## Frozen stop / risk-unit definition (Rule #20 compliance — must be declared before any R-based work)

| Field | Value |
|---|---|
| Initial invalidation | **S1b** — the previous trading day's Low, fully known before the entry day begins (decision-time-safe). Conceptually: "loses the last locally-confirmed demand point before the breakout day." Daily-bar implementation today; may become an intraday-derived level later (parked, see `PARKING_LOT.md` item 8) without changing this conceptual definition. |
| Risk unit (1R) | `(entry_price - initial_stop_price) / entry_price * 100`, where `entry_price` = the N-day-high trigger price (`high_prior * 1.005`). |
| ADR telemetry | `adr_multiple_of_stop` tracked, NOT used as a filter — most QS trades run wider than 1x ADR (79-89%), a real but unresolved gap between Kullamägi's live intraday execution and this daily-bar reconstruction. |

## QS v0.1 Entry Gate — deployable output (2026-09-27)

Entry Discovery has produced a real, deployable entry gate. Full readiness report,
population/tradeability/robustness/execution numbers, and exact gate logic:
**`swing_qs/QS_V01_ENTRY_GATE.md`** — read that file before deploying or extending the
entry side of QS. Summary: raw breakout + `base_duration` + `gap_to_trigger_pct`
(conditional logic, not independent AND), RVOL/breach-time/R1-R2 kept as telemetry only.
Exit remains explicitly undecided — see that file's "Exit" section.

## QS is NOT ready for live deployment (2026-09-28 late, supersedes the "20-30 live
trades" framing below) — replay validation is the next gate, not live trading

The user opened one real AEGISLOG chart and within 30 seconds found a genuine
discomfort (entering near the top of a violent breakout wick) that no backtest had
surfaced — a flag against shipping, not against the research. Honest status: entry
gate provisional (not validated as a finished product), exit unresolved/provisional,
replacement policy tested and closed negative (RQ-QS-02), opportunity occupancy real
but no intervention (RQ-QS-01), body/candle quality is known telemetry with no
intervention, and **trajectory replay has not yet actually been researched at scale**.
A couple of live trades generate better hypotheses than months of backtesting — they
do not validate a strategy. Next step is a replay/dry-run session (20 replayed
candidates, 5 live-paper trades, success measured by quality of observation, not
P&L), per the full brief in `swing_qs/trajectory_replay/REPLAY_BRIEF.md` — currently
awaiting critic's design audit before implementation starts. Do not start building the
replay engine further, and do not trade QS live, until that verdict comes back.

## QS v0.1 gate FROZEN until minimum 20-30 live trades (2026-09-28, critic-specified,
now superseded by the replay-validation gate above — kept for the frozen gate's own
exact definition, which still stands)

Feature Discovery is closed for this line — see `swing_qs/FINDINGS.md`'s Feature
Battle + v0.2 gate-option entries. No further entry filters, exit redesign, threshold
tuning, or literature audits until live telemetry from a real trade batch exists.

**Exact frozen gate — verify against this before citing "the v0.1 gate" anywhere**:
the population is built via `ungated_recipe` (the raw "trigger-price counterfactual"
per `../CLAUDE.md`'s Gate Integrity Rule — `base_filters_pass()`'s trend/EMA34-
persistence/momentum/fragility checks are NOT applied), with exactly one conditional
reject: `NOT (base_duration == 0 AND gap_to_trigger_pct > 2.343)`. This is a disclosed
correction to critic's own "Frozen v0.1" description (which listed trend_bullish +
EMA34 persistence>=2 + base_duration>=1 as if already enforced) — that fuller stack
was tested directly on 2026-09-28 and shows the same Rule #21 pattern as everything
else this weekend: 35.9% of the population discarded for a 0.4-point BLAST-rate gain.
Not adopted. The gate that's actually frozen is the single conditional, nothing more.

## Research roadmap phases (adopted 2026-09-27, critic-specified)

| Phase | Goal |
|---|---|
| Exit Discovery | Understand failure/momentum anatomy. No optimization. **We are here, near the end.** |
| Exit Freeze | Choose 2-3 exit philosophies only, then stop generating new exit features. |
| Entry Discovery | Find entries that naturally fit the frozen exits (structural questions — base quality, breakout candle quality, market regime, retest entries — NOT another Momentum/Fragility/RSI filter hunt). |
| Joint Tuning | Evaluate Entry × Exit pairs together. |

**Discovery Budget rule**: every major subsystem (Exit, Entry, Options, Risk sizing)
gets at most 3 discovery batches before it must freeze — compete the alternatives that
survived, move to the next subsystem. Prevents the exact rabbit-hole this rule was
written in response to. Exit discovery is at its budget limit after the current batch
(F1/MA1/reclaim/LH overlap audit + EX1/EX2/EX3) — no F7, F8, EMA variants, ADR buffers,
or K=3 swings without explicit re-opening.

---

# Original v1 definition (2026-09-26), unchanged below except the title correction above

This document exists because this weekend's research kept violating one guardrail:
**never optimize before defining success.** Every filter promoted and later reversed
this weekend (Volume Quality, Fragility, Sector RS, the trail-cut frontier) was tested
against "does it improve average trade expectancy" without first asking what BC is
actually supposed to catch. This file is the answer to that question, agreed with the
user on 2026-09-26. It is a standing reference, same tier as `FINDINGS.md`/`CLAUDE.md` —
read it before starting any RQ-QS work, and don't silently redefine the product mid-RQ.

The specific numbers below (3-5 sessions, 0.25R) are a **starting point, not a sacred
constant** — the user's own words: "these are not fixed, we find the right place
eventually." Research is allowed to move them, but only explicitly and only through the
same discipline as everything else this weekend (pre-declared, robustness-checked,
never silently re-tuned after seeing results).

## The definition

| Question | Answer |
|---|---|
| **Holding horizon** | 3-5 trading sessions — a real business goal, not a mechanical cap. If BC's actual edge requires materially longer than this to develop, that is itself the finding, not something to route around. |
| **Success** | Meaningful continuation develops quickly after the breakout — a real, felt gain, not a token positive. |
| **Failure — two distinct modes, do not conflate them** | (a) Momentum never develops at all before exit (Type-A / FAKE). (b) Momentum develops, then reverses and gives back before exit without being recognized (the Aegis Logistics pattern). These are different mechanisms and need different research treatments. |
| **Who this is for** | Both the stock swing itself and the options overlay (ATM/ITM, current-month, fast-cut/day+1 style). Options are theta-sensitive, so continuation *speed* matters even more there than for the stock leg alone. |
| **What "win" means** | Meaningful Win = `r_multiple >= 0.25` (≈₹500 profit against ₹2,000 risk) — the user's own stated bar, already adopted project-wide as the reporting headline. |
| **FAST / SLOW / FAKE boundary** | FAST = reaches ≥0.25R within Day 5. SLOW = eventually reaches ≥0.25R, but only after Day 5. FAKE = never reaches ≥0.25R before exit. Tied to Meaningful Win (0.25R), not Quality Win (0.5R) — the user's explicit choice, since 0.25R is already the stated bar for "this felt like a win." |
| **What this is explicitly NOT** | Not a positional, hold-through-the-whole-trend strategy. A genuine multi-week uptrend should be treated as a *sequence* of separate breakout events (Darvas-style — new high, new position), not one long hold spanning multiple highs and lows. |
| **Entry mechanism** | Real intraday IOC at the trigger touch (Primed Gate), not EOD-confirmed next-day entry. Settled, validated by RQ-94 (Primed beats Confirmed historically by +0.157R/trade on the same events) — not open for renegotiation in RQ-QS. |
| **Closest existing methodology** | Kullamägi-style fast rotation / short-horizon Minervini, not O'Neil's slower CAN SLIM-style institutional-trend-riding. Informs what literature to treat as a prior, not a constraint. |

## Labeling rule (ground truth, not entry logic)

For every trade in the honest T-1-gated population:
```
FAST: r_multiple >= 0.25 reached (High-based) by day_idx <= 5
SLOW: r_multiple >= 0.25 reached, but only at day_idx > 5
FAKE: r_multiple >= 0.25 never reached before the real exit
```
This uses the trade's own future to build the label — that is fine, it is ground truth
for research, never a prediction. It becomes a bug only if a label leaks back into
anything that fires before entry. Labels are an analysis output, never entry logic.

## Guardrails for everything built under this definition (RQ-QS)

- `population_builder.py` only — no hand-rolled simulation loops.
- T-1 gate only (Rule #18) — no same-day-EOD features in anything that claims to be
  usable before the fact.
- Real `primed_engine` exit mechanics only — no monkeypatched populations.
- **No feature promotion, no threshold optimization, in Stage 0/1.** The deliverable is
  labeled data and descriptive comparisons — not a filter, not a gate, not a promoted
  candidate. That is a later, separate, explicitly-gated stage.
- Explicitly out of scope until labels exist: new filters, new exits, trail-cutting,
  MAX_HOLD_DAYS changes, Cell C rebuild, options policy changes.
