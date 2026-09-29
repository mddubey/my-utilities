# research_archive/

104 one-off research scripts (64 archived 2026-09-17, 40 more on 2026-09-29), moved out
of the main project folder to declutter it — **not deleted**. Every one of these is the
reproducible record behind a specific `FINDINGS.md` claim (what was tested, on what
population, with what result), kept exactly as this project's own "isolated research
only" convention requires.

`data/` holds the CSV outputs those scripts wrote (moved 2026-09-29 from the main
folder) plus the real 5-min option price exports (`*_5min_real*.json`,
`*_ox1b_real_check.csv`) used to validate OX1 reconstruction. Scripts reference these by
bare filename, so a re-run writes a fresh copy to the current directory rather than
updating the archived one — that's fine, the archived copy is the record.

Modules deliberately kept in the main folder because they are shared infrastructure,
not one-offs: `breakout_failure_confirmation_cost.py` (imported by ~20 scripts here and
by `swing_qs*/`), `population_builder.py`, `risk_of_ruin.py`, `qs_dashboard.py`,
`qs_trajectory_replay.py`, `resample_1h.py`, `ox1_reconstruction.py`.

Archived scripts that import each other (`ema34_lag_outcome_check`,
`base_filters_threshold_sweep`, `rq_a5_retest_dominance`, `stop_family_research`) live
side by side here, so those imports resolve from the script's own directory.

`monitor_position.py` (singular) is the 2026-09-03 predecessor of the production
`monitor_positions.py`; `fixed_r_sim_scratch.py` still imports the pre-rename
`detect_entry` and will not run without editing — both kept as history only.

**To re-run any archived script**, it needs the project root on `PYTHONPATH` (they
`import backtest`/`signals`/etc., which live one directory up from here):

```
cd /Users/mdubey/workspace/personal/my-utilities/md-swing-scanner
PYTHONPATH=. python3 research_archive/whatever_check.py
```

Running it as `python3 research_archive/whatever_check.py` without `PYTHONPATH=.` will
fail on the first `import` — that's expected, not a sign the script is broken.
