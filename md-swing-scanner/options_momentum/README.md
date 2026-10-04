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

- RQ-OMD-01 (stock-level fast-move behaviour map) + RQ-OMD-02 (fast reversal quality): **both
  done and CLOSED, 2026-10-04.** See `RQ-OMD-01_REPORT.md` / `RQ-OMD-02_REPORT.md` /
  `FINDINGS.md`. OMD-01: closed-negative on fast-continuation-as-long-options-basis; banked a
  robust fade-with-move-size pattern instead (both directions, monotonic, multi-window/
  multi-year). Critic verdict: bank the behaviour, not the trade — ordered RQ-OMD-02 as the
  required next step (overnight/intraday decomposition + continuous retracement depth/speed)
  before any options framing. OMD-02: the "fade" is mostly a STALL, not a deep reversal —
  weakens the put-after-spike case rather than strengthening it; overnight-originated moves
  are actually stickier than intraday ones (argues against an overnight-reversal confound);
  F&O-vs-non-F&O gap is modest once properly matched. A real bug (flat `r_T==0` bars
  misclassified as "down" events, caught via an invariant check) was found and fixed during
  OMD-02's build — corrected OMD-01's dn_normal numbers (strengthened the finding) without
  touching anything already sent to the critic. Do not resume this branch without a new
  trigger (critic verdict on OMD-02, or a new hypothesis) — see `FINDINGS.md`.
