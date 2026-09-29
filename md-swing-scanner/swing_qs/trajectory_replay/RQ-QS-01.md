# RQ-QS-01 — Opportunity Cost of Occupancy

**Status**: approved by critic 2026-09-28, bounded deliverable in progress.

## The question

How often does holding an unresolved breakout prevent a later breakout that better
matches the QS product? This measures **quality of portfolio occupancy**, not quality
of a trade — a question neither BC nor QS has asked before. Everything until this RQ
measured "was this trade good"; this measures "did holding this trade cost me a better
one on the same name."

## How it was found

User watched AEGISLOG's real 1h chart and spotted a second, clean pin-bar-reclaim setup
on 2026-09-18 — a full breakout candidate on its own merits. The QS research population
never sees it: AEGISLOG's real 10-day breakout trigger fired 2026-09-09 and (per the
single-position-per-ticker convention every population in this project uses) stayed
"open"/unresolved through the last cached date — no ticker can register a second entry
while an earlier one is still open. That's a simulator convention, not a market truth
(critic's framing) — the backtest silently says "ticker occupied" where a real trader
watching the chart would say "I'd take that second breakout."

One correction found during investigation, worth keeping visible: in the exact AEGISLOG
example, the blocking position (2026-09-09 entry) had *already proven itself* (touched
+0.25R and +0.5R) by 09:15-09:20 on the morning of the 18th, before the pin bar even
formed at 10:00. So this specific instance is "blocked while already a winner," not
"blocked while still ambiguous" — a reminder that Phase 2's classification (below)
matters, not just counting raw blocks.

## Methodology (critic-approved, three-phase)

**Phase 1 — discover blocked opportunities**
1. Raw trigger calendar per ticker: every day `High >= high_prior_N × 1.005` fires,
   ignoring the single-position rule (10D/20D/40D, independent).
2. Cross-reference against the existing `qs_raw_{N}d_full.csv` (entry_date/exit_date
   per taken position) — a raw trigger day falling strictly inside an earlier
   position's `[entry_date, exit_date)` window is a **blocked trigger**.
3. Filter to blocked triggers that independently pass the frozen v0.1 gate
   (`base_duration`/`gap_to_trigger_pct` conditional) — call this trigger **B**, the
   blocking position **A**.

**Phase 2 — classify why B was blocked**, using A's own max-R-so-far as of B's
trigger day:
- `winner` — A already ≥1R by then (good occupancy)
- `proven` — A already ≥0.25R but <1R (reasonable occupancy)
- `unresolved` — A still <0.25R, not stopped (the real opportunity-cost candidate)
- `underwater` — A already meaningfully negative but not yet stopped

**Phase 3 — compare A vs B directly**, both walked forward independently from their own
relevant start point (A from B's block day forward, B from its own entry forward) —
same trajectory-walk machinery as `qs_dashboard.py`/`qs_trajectory_replay.py`, not
reimplemented. Reports: R from block day onward (A) vs R from entry (B), max future R
(both), days to +1R (both), net outcome (both). Classified into four outcomes:

| Outcome | Meaning |
|---|---|
| A wins, B loses | Holding was correct |
| A wins, B wins | Opportunity existed, but holding wasn't wrong |
| A loses, B loses | Nothing gained either way |
| **A stalls, B blasts** | **The one we care about — A consumed capital while B better represented the product** |

## Guardrails (critic-specified, binding)

1. **No overlapping positions simulated** — this measures replacement, not stacking.
   Never simulate holding both A and B at once; the comparison is descriptive
   (side-by-side outcomes), not a portfolio-construction decision.
2. **B is frozen to exactly QS v0.1's gate** — no manual/chart-based judgement on which
   triggers count as "real" candidates. Programmatic gate check only, same formula as
   everywhere else in this project.
3. **Report raw frequency before quality** — tickers with blocked triggers, total
   blocked triggers, how many pass the v0.1 gate, how many are specifically
   `unresolved`-blocked (the actual candidate problem) — reported BEFORE any
   A-vs-B quality comparison, so a rare phenomenon doesn't get oversold.

## Bounded deliverable (do not exceed)

1. Count blocked QS-v0.1 triggers (all three lookbacks).
2. Classify blocker state (winner/proven/unresolved/underwater).
3. Compare blocked trade vs blocking trade from block day onward.
4. Produce Top 25 "A stalled, B blasted" examples with full replay printouts.

No new entry filters. No exit redesign. No threshold tuning. If the Top 25 all look
like AEGISLOG, this is the next major QS research direction. If they don't, the
intuition is falsified cheaply, and that's a fine outcome too.
