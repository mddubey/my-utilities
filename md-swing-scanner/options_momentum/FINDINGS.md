# options_momentum/FINDINGS.md

Closed/banked conclusions for this track only (separate from the shared project-root
FINDINGS.md, same discipline as `pre_breach/` and `short_discovery/`).

## RQ-OMD-01 — Stock-level fast-move behaviour map (2026-10-04) — CLOSED, mixed

**Hypothesis tested:** does an unusually large stock-relative 1H move get followed by a fast
same-direction continuation, usefully for a long directional option? Full population (2,192
tickers, no F&O/liquidity restriction), `data/intraday_60m/`, 2023-10-23 -> 2026-10-01,
8.83M qualifying bar-events. Full preflight/report: `RQ-OMD-01_PREFLIGHT.md` /
`RQ-OMD-01_REPORT.md`.

**CLOSED-NEGATIVE on the literal hypothesis.** No fast-continuation edge after a large move,
in either direction, at any horizon (1H through next session). If anything the reverse:
continuation rate is *lower* after an unusual move than after a normal-sized one, in both
directions (dn: 36.9% vs 45.4% combined A+D; up: 32.8% vs 40.0%). Don't re-litigate "does a
big move keep moving" under a new name later — this is the answer, checked against 3
pre-declared z-windows, 3 individual years, and an independent gap-bar slice, all agreeing.

**BANKED, positive, different phenomenon:** unusually large **up**-moves fade, monotonically
with move size (next-session continuation rate: up_normal 44.4% > up_elevated 43.3% >
up_unusual 42.1%), robust across all 3 z-windows and all 3 years, and independently
corroborated by gap-bar behaviour (gap-ups fade more than gap-downs at every horizon). Down
side shows the same general asymmetry but is not monotonic (dn_elevated continuation edges
above 50%, unlike dn_unusual/dn_normal) — a real asymmetry, not a mirror image. This is a
fade/reversal signature, not a continuation one — points toward a short-side options angle
(buy puts after an unusual spike), not the long-call-momentum framing RQ-OMD-01 set out to
test. Lines up with the standing long-strategy-regime context
([[project_long_strategy_regime_2025_2026]]).

**Smaller open thread, not yet a finding:** within unusual moves, 19-23% are
"delayed_continuation" (eventually continue after stalling) vs 35-40% genuine stalls. F&O
names (the only ones actually tradable as options) show a meaningfully higher combined
continuation rate (~42%) than non-F&O (~32-36%) after an unusual move. Neither is
characterized yet — would need its own RQ to find out what distinguishes a delayed-
continuation case from a stall, before it's anything more than a base rate (Rule #21: a base
rate is not a gate).

**Known scope limits, not blockers:** gap bars (09:15, overnight+first-hour) were not
z-bucketed against their own history in this pass — reported as one unconditional up/down
split only (see preflight). The 0.5x-of-own-move A/B/C/D threshold is a first-cut
classification for readability; the continuous distributions (Table 1, no threshold
involved) are the primary evidence, and agree in sign with the ABCD summary.
