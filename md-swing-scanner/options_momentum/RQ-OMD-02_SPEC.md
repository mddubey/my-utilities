# RQ-OMD-02 — Fast Reversal Quality

Frozen from the critic's verdict on RQ-OMD-01, 2026-10-04. Paraphrased into spec form from
the critic's own wording (see `FINDINGS.md`'s critic-verdict section for the verbatim
reasoning this came from).

## Objective

When an unusually large 1H stock move occurs, is the subsequent reversal itself fast, large
and economically meaningful — and does it remain present once overnight-originated movement
is separated from genuinely intraday-originated movement?

This is the required intermediate step between "a reversal tendency exists" (RQ-OMD-01,
banked) and "there might be an options trade here" — not a jump straight to strategy
construction. Architecture: stock phenomenon -> speed/magnitude -> robustness -> option
translation -> option economics. This RQ covers speed/magnitude and the overnight/intraday
robustness split; option translation/economics are explicitly out of scope here.

## What to measure, for unusual AND normal-sized moves (comparison, not unusual-only), both
directions, intraday-originated and overnight-originated separately:

- Signed subsequent return, MFE, MAE over the same growing horizons as OMD-01 (1H / 2H / 3H /
  rest-of-session / next session) — reuse, don't rebuild.
- **Fraction of the initial move retraced**, as a continuous path measure, not a single
  endpoint snapshot.
- **Time to 25% / 50% / 75% / 100% retracement** — first bar at which the path has given back
  that fraction of the initial move. Pre-declared checkpoints, not optimized.
- **Maximum continuation reached before any reversal begins** (i.e. before the 25%
  retracement checkpoint is first crossed) — distinguishes "ran further first, then gave it
  back" from "reversed immediately."
- Compare throughout against normal-sized moves (not just unusual) — the question is whether
  reversal quality *changes* with move size, same discipline as OMD-01's bucket ladder.
- F&O reported as a split throughout, including the comparison the critic flagged as missing
  from OMD-01: **F&O-unusual vs F&O-normal** (within F&O only), not F&O-unusual vs
  non-F&O-unusual. That is the cut that would actually show an F&O-specific conditional
  effect, if one exists.

## Explicit discipline carried over

- **Do not optimize a reversal threshold.** The 25/50/75/100% checkpoints are fixed,
  round, pre-declared — examine the continuous path first; OMD-01's 0.5x A/B/C/D
  classification stays as a secondary cross-check only, not a thing to re-derive or re-tune.
- No options economics, no IV/premium analysis, no strategy construction — this RQ is
  stock-level only, same as OMD-01's Section 7 boundary.
- No F&O filter as a population restriction — F&O stays a reporting split.

## Why this ordering

If unusual moves show only a shallow, slow retracement (e.g. "3% spike -> median reversal
0.3%, takes 4 hours"), the put-after-spike branch closes here, cheaply, without ever touching
option data. If instead retracement is substantial and reasonably fast, THEN the options-
economics question (does IV/premium already price this in?) becomes worth asking — but not
before.
