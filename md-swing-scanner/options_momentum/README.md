# options_momentum — new project track (opened 2026-10-04)

Separate track from Primed BC swing (`swing_qs*`), intraday shorts (`intradaygeeks_replica/`),
short-side discovery (`short_discovery/`) and pre-breach (`pre_breach/`). Keep its FINDINGS/
PARKING_LOT separate from the shared project-root files — same discipline as `pre_breach/`
and `short_discovery/`.

**Goal (long-run):** a long-directional options strategy built on repeatable short-horizon
stock-level fast-move behaviour, if one exists. Not yet a strategy — see RQ-OMD-01.

**Data:** reads only from the root `data/` folder (see `data/README.md` for construction,
coverage and caveats of every dataset) — no project-local cache duplication. Primary dataset
for this track is `data/intraday_60m/` (native Yahoo hourly bars, 2023-10-23 → now, 2,266
tickers). `data/daily/` for broader context. Options legs (`data/nse_fo_bhav/`) are future
work, once/if a stock-level phenomenon is confirmed — RQ-OMD-01 is stock-only by design.

**File convention** (matches `short_discovery/` / `pre_breach/`):
- `RQ-<id>_SPEC.md` — frozen research question as given.
- `RQ-<id>_PREFLIGHT.md` — Research Preflight answers + pre-declared parameters, written
  and agreed *before* any result is seen (CLAUDE.md "Research Preflight" + "Robustness
  Before Finding" + "Logic-first filters" memory).
- `RQ-<id>_REPORT.md` — results, once run.
- `NN_<step>.py` — numbered pipeline scripts.
- `FINDINGS.md` — closed/banked conclusions for this track only.

## Status

- RQ-OMD-01 (stock-level fast-move behaviour map): **done, 2026-10-04.** See
  `RQ-OMD-01_REPORT.md`. Closed-negative on the literal hypothesis (big move -> fast
  continuation, as a long-options basis); surfaced a robust up-move-fade phenomenon instead
  (monotonic with move size, holds across 3 z-windows/3 years/an independent gap-bar slice).
  Logged in `FINDINGS.md`. Next-decision options are listed at the end of the report, not
  decided yet.
