# RQ-EMAPB-01 — EMA Pullback After an Impulsive Move

2026-10-04. New sibling research line, separate from `swing_qs_bpc/` (same reason BPC got its
own folder instead of living in `swing_qs/`: different mechanism, different assumptions —
mixing them recreates the confusion the project has already deliberately avoided twice).

## Origin

User, reviewing real TradingView charts (RITES, VEDL, REDINGTON — HINDPETRO did not fit):
after an impulsive, volume-confirmed move, price often pulls back to a fast EMA, prints a
rejection/support candle there (Low touches/dips to the EMA, Close holds above it), and then
bursts again. Confirmed on real data for VEDL (1H) and REDINGTON (daily: a 3-day pullback into
EMA8, Aug 17-19 2026, followed by +8-10% over the next 5 days) before building anything.
Explicitly NOT an EMA8-specific claim — EMA8 is just what the user's chart has by default;
the real claim is "some support level after an impulsive move," tested here via EMA8/20/50 as
a predeclared robustness set.

Literature check (done before building, per standing practice): this is a real, named
strategy family — "buy the EMA pullback in an uptrend." Momentum stocks pull back to a fast
EMA (20 commonly cited, 8 in the user's own convention); slower trends to 50. Standard
definition: daily Low touches the EMA, Close holds above it.

## Research Preflight

1. **Population**: the impulsive move (A) = the already-cleaned, volume-confirmed breakout
   population from RQ-BPC-05, **10-day lookback only** (no lookback-mixing, per the MGL
   lesson — never pool 10/20/40-day definitions into one population again), A's own breakout-
   day volume >= 1.5x `vol_avg10_prior`. Reused directly from
   `swing_qs_bpc/rq_bpc05_a_volume_diagnostics.csv` (10,579 events) — not rebuilt from scratch.
2. **Entry/decision clock**: the "touch" (T) is decision-time-safe — EMA value used for the
   touch check is computed through the PRIOR bar's close only, never including the touch
   bar's own close. Burst is measured strictly after T.
3. **Stop/risk-unit**: none. Descriptive price-path measurement only, same discipline as
   `options_momentum/` — no R-multiple, no P&L, until/unless this becomes a real product
   candidate.
4. **Exit engine**: none — deliberately outside `primed_engine.py`/`backtest.py` territory,
   same reasoning as `options_momentum/`.
5. **Comparison unit**: forward price-path distributions after a touch, vs. a baseline of
   forward price-path distributions from ANY bar in the same post-A window (not just touch
   bars) — so "touching the EMA helped" isn't confused with "the stock was in an uptrend
   anyway." Also EMA8 vs EMA20 vs EMA50 side by side, pre-declared, not picked after seeing
   results.

## Pre-declared definitions (fixed now, not tuned after seeing results)

**Touch (T) — superseded 2026-10-04, single-bar pin bar rejected.** First attempt required a
bullish pin bar (literature wick:body definition) at the touch bar. Rejected after a hand-check
showed our own two confirmed ground-truth examples (VEDL 2025-12-12, REDINGTON 2026-07-30)
do NOT qualify under that filter -- both show a multi-day HOLD at the EMA (REDINGTON: 3
consecutive days with Low below EMA8 and Close above it, Aug 17-19 2026; VEDL 1H: repeated
EMA touches through a session), not a single dramatic rejection candle. A pin bar is a
single-candle concept; what was actually observed is a multi-bar consolidation followed by an
expansion -- a different shape, not a stricter/looser version of the same one.

**Hold-and-Expand (revised definition, used from here on):**
1. **Hold phase**: the first run of >= M consecutive bars (after A, within the 20-day window)
   where EVERY bar independently satisfies the original touch condition
   (`Low <= EMA_N(prior bar)` AND `Close >= EMA_N(same bar)`). M predeclared as a robustness
   split: **M=2** and **M=3**, not tuned after seeing results.
2. **Expansion bar**: the first bar after the hold phase ends whose own `(High - Low)` is
   >= X times the hold phase's own average daily range, AND is an up bar (`Close > Open`).
   X predeclared as a robustness split: **X=1.5** and **X=2.0**.
3. Forward metrics measured from the expansion bar's own Close (same convention as every
   other horizon measurement tonight -- a price-path descriptive, not a live entry rule).
If a hold phase is found but no qualifying expansion bar follows within the window, that is
recorded explicitly as "held, no expansion" -- informative on its own, not dropped silently.

**EMA periods tested, side by side**: 8, 20, 50 (literature-informed: 20 for momentum stocks,
50 for slower trends, 8 per the user's own chart convention) — reported as three parallel
results, never pooled into one (same lookback-mixing lesson as RQ-BPC-05/MGL).

**Burst, measured from T's own Close, cumulative growing horizons**: 1, 3, 5, 10 trading days
— signed forward return, MFE, MAE, same conventions as `options_momentum/`'s horizon ladder.
No single horizon picked in advance as "the" answer.

**Baseline for comparison**: for every A in the population, one bar is drawn from the same
post-A window at a fixed, deterministic offset (the window's midpoint day) regardless of
whether it touched an EMA — same forward-horizon measurement applied, to see whether touching
specifically adds anything over "being in this window at all."

## What this does NOT do

No entry rule, no stop-loss, no profit target, no strike/DTE, no backtest of a strategy, no
threshold optimization (touch/burst definitions fixed above, before any result). Purely
descriptive, same as `options_momentum/`'s RQ-OMD-01/02 discipline.
