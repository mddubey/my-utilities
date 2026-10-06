# RQ-EMAPB-02 — Critic-specified research audit (2026-10-04)

Critic's verdict on RQ-EMAPB-01: the confirmation hypothesis is NOT closed. The earlier
"3-bar base -> break of 3-bar high" test (84.5% trigger rate, measured at D3) was one crude,
insufficiently selective implementation, tested at the wrong horizon for the actual product
question (short-horizon, D1, options-sized). Full verbatim critic design kept in the session
log; key fixed guardrails and mechanical definitions actually implemented:

## Fixed guardrails (per critic)
- Same A population: volume-confirmed, >=1.5x `vol_avg10_prior`, 10-day lookback only, 1H
  bars. No change to A, no F&O/liquidity filtering, no Fib ratio optimization.
- D1 (Open/Peak/Close), not D3, is the decision metric. D3 explicitly banned for this batch.
- No stop/exit optimization yet (Track 9) — this is a research audit, not strategy building.

## Mechanical definitions, pre-declared (implementer's choices, surfaced explicitly)
- **Stabilization span** = touch bar + next 2 bars (3 bars total, literature floor of 3-5).
- **Range compression** = span's total width (max High - min Low) <= 0.5x the impulse's own
  height (swing_high - swing_low).
- **ATR/range contraction** = span's average per-bar range <= 0.75x the impulse's own average
  per-bar range (A to peak).
- **Volume contraction** = span's average volume <= 0.75x the impulse's own average volume.
- **Contained** (no breakdown) = bars after the touch don't undercut the touch bar's own Low
  by more than 0.2x the impulse's average bar range.
- **B (stabilized pullback)** = range_compression AND contained.
- **combined_base** (Track 3's full combination, diagnostic only) = range_compression AND
  atr_contraction AND vol_contraction.
- **C1 (early resumption)** = first bar after the span that closes green (Close > Open).
- **C2 (structural confirmation)** = first bar after the span whose High exceeds the span's
  own High.
- **C / "stabilized + resumption"** (Track 2) = B AND C2 occurs.

## Scope cut, flagged explicitly (not silent)
Track 1 (retracement-depth diagnostic) covers all four levels: retest, Fib 38.2/50/61.8%.
The full structural pipeline (Tracks 2-9: B/C classification, component diagnostics,
confirmation-quality comparison, timing cost) runs on the **Fib 50% touch population only**
as the primary pipeline, not all four depths — a scope decision to keep the first pass
achievable, not a claim that Fib 50% is special. Extending to the other three depths is
natural follow-up work if this pass is informative.

## D1 definition
The next full trading session after each anchor point (touch / end of stabilization span /
C1 / C2), using real 1H bars for D1 Open/Peak(intraday max High)/Close/MAE(intraday min Low)
relative to the anchor bar's own Close — not the coarser daily OHLC file.
