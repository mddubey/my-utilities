# research_archive/

64 one-off research scripts (2026-09-17), moved out of the main project folder to
declutter it — **not deleted**. Every one of these is the reproducible record behind a
specific `FINDINGS.md` claim (what was tested, on what population, with what result),
kept exactly as this project's own "isolated research only" convention requires. Scripts
still in active use this week (still in the main folder, not archived):
`base_filters_threshold_sweep.py`, `fragility_margin_check.py`, `oi_buildup_retest.py`,
`stop_family_research.py`, `vcp_sma21_transfer_check.py`, `min_traded_value_ablation.py`,
`live_equivalent_population.py`, `premium_tolerance_check.py`.

**To re-run any archived script**, it needs the project root on `PYTHONPATH` (they
`import backtest`/`signals`/etc., which live one directory up from here now):

```
cd /Users/mdubey/workspace/personal/my-utilities/md-swing-scanner
PYTHONPATH=. python3 research_archive/whatever_check.py
```

Running it as `python3 research_archive/whatever_check.py` without `PYTHONPATH=.` will
fail on the first `import` — that's expected, not a sign the script is broken.
