# Pre-Breach Detector — Spec (frozen before any outcome was examined)

Written 2026-09-30 IST, before any outcome column in `panel.csv`, `intraday_features.csv`
or `option_legs.csv` was examined. Scripts 01-03 build features and store outcome columns.
No relationship between a feature and an outcome had been computed when this was written.
This is its own thread. It does not write to the shared `FINDINGS.md`/`PARKING_LOT.md`.
Results go to `pre_breach/FINDINGS.md`.

## 0. What already exists (baseline to beat, not reinvent)

- `live_checkpoint.calibrated_fire_rate(dist_pct)`: a lookup of P(CLOSES above trigger_low by
  EOD | distance at an intraday checkpoint). Its docstring says it is **not** P(touch). The
  2026-09-08 rebuild found that touch overstates real trades by about 2x, uniformly. Values run
  from about 36% (≤0.2%) down to 0.3% (5%+).
- Night-before `quality_score` (range_compression, ema8_dist_pct, atr_trend_15d,
  narrowing_range, dist_to_resistance). Tested 2026-09-04: the top-5% tail lifts the 3-day fire
  rate from 7.2% to 10.5% (a ~1.4x tilt). **Rejected as an entry mechanism.** Recall@5 for
  next-day >5% movers was 9.6%.
- Trigger Velocity (80/20 distance/velocity blend). Real but small, and the lookback window
  was not validated.
- Same-day distance at a checkpoint: Recall@1 60-69%. This is the strongest thing known, and
  it is only available after the open.

## 1. Closed-negative features, not re-proposed (with what would differ if revisited)

| Feature | Status | Re-proposed? |
|---|---|---|
| RVOL@Trigger | RETIRED 2026-09-13 (3 decision tests, never beat Freshness) | **Not re-proposed.** A related but distinct feature is below (F3, RVOL at 09:25). It is measured at a fixed clock time *before* any touch, against the ticker's own same-slot history, and aimed at FIRE rather than win-rate. The one prior hint in its favour is FINDINGS 2026-09-07: within the closest-20% distance band, fire rate went from 18.7% (Q1 volume) to 41.9% (Q4). That was never followed up as its own test. |
| Supply exhaustion / base volume contraction | CLOSED 2026-09-21 | No |
| Breakout-candle geometry family | CLOSED 2026-09-21 | No (and it is breach-candle information anyway) |
| Prior-advance proxy (252d) | CLOSED 2026-09-21 | No |
| Base Count | CLOSED (not operationalizable) | No |
| First-15-min momentum as mover-ranker | Rejected 2026-09-05 (corr with rest-of-day −0.007, mild mean reversion) | F4 below uses the first 5-min bar's state only as a conditional FIRE modifier *given distance*, with a pre-stated expectation that HOLD shows nothing. If F4 shows nothing on FIRE either, it closes again. |
| Hold-vs-reject predictability (proximity, R1/R2, touch-bar volume) | Closed 2026-09-28 (swing_qs item 8, near coin-flip) | The HOLD predictions below are expected to be weak. That is stated up front. |

## 2. Data feasibility (step 3)

| Source | Range | Clock | Notes |
|---|---|---|---|
| `data_cache` daily | 2021-08 → 2026-09-29 | T-1 close, T Open | 134,264 primed candidate-days (base_filters_pass on T-1), 500 tickers, 45% F&O |
| `intraday_cache` 5-min | 2026-06-10 → 2026-09-23 (74 sessions) | 09:20 / 09:25 | 8,360 candidate-days. **The 09:15 bar's Volume is 0 in 97% of rows**, so first-5-min RVOL is not computable. The earliest usable volume is the 09:20-09:25 bar, known at 09:25. |
| `options_cache` bhavcopy | 2022-06 → 2026-09-22 | daily OHLC only | OpnPric = first trade of the day, **not a 09:15 quote**. No intraday option prices. Real spot for pre-2024 files comes from put-call parity (median error 0.22-0.30% vs UndrlygPric on 2024+ dates, p95 < 0.9%). |

Consequences:
- Any **intraday-feature** result (F3, F4) rests on 74 sessions of one regime (Jun-Sep 2026).
  That is enough to see a large effect and not enough for Rule #19 year-by-year robustness.
  At best it is exploratory, whatever it shows.
- The **option test** uses only daily-computable features (T-1 close + T Open), because
  option data is daily. The blind arm's entry is the contract's first trade on T. The touch
  arm's entry is reconstructed with OX1's frozen ATM beta (0.492). Neither is an observed
  09:15-09:20 quote.

## 3. Candidate features (ranked by prior evidence × feasibility)

Literature tiers come from `LITERATURE.md` (filled in from the review):
STUDY = peer-reviewed or SSRN with stated data, PRAC = practitioner with a backtest,
FOLK = repeated without data.

| # | Feature | Clock | Predicts | Computable | Evidence |
|---|---|---|---|---|---|
| F1 | Opening distance to trigger, `dist_open_pct` and in ATR units `dist_open_atr` | 09:15 | FIRE | daily, full history | Mechanical (this is the baseline's own variable, re-anchored to the open) |
| F2 | Opening gap `gap_pct` (Open vs T-1 close), *holding open-distance fixed* | 09:15 | HOLD (−) | daily, full history | see LITERATURE §2 (gap/overnight reversal) |
| F3 | Early relative volume `rvol_0925` (09:20 bar vs own prior-20-session same-slot median) | 09:25 | FIRE (+), HOLD (?) | intraday, 74 sessions | see LITERATURE §1/§5 (stocks-in-play) |
| F4 | First-bar state `bar1_clv`, `bar1_ret_pct` (5-min ORB position) | 09:20 | FIRE (+ given distance) | intraday, 74 sessions | see LITERATURE §1 (ORB) |
| F5 | Market opening gap `nifty_gap_pct` | 09:15 | FIRE (+) | daily, full history | see LITERATURE §6 |
| F6 | Volatility-normalized distance (`dist_*_atr` vs `dist_*_pct`), plus `atr_pct` | T-1 / 09:15 | FIRE | daily, full history | Qullamaggie ADR framing (PRAC-CLAIM) |
| F7 | Prior-day attention: `abs(ret_prev_pct)`, `vol_ratio_prev` | T-1 close | HOLD (−) | daily, full history | Berkman et al. 2012 (STUDY, US). **Overlaps F2**, so it is tested as a residual within gap terciles, not stacked |

Added after the literature review, still before any outcome was examined: F7 and P8.
Literature tiers are now filled in (`LITERATURE.md`). F2 = STUDY (Berkman; US; partly
contradicted at index level by Plastun). F3 = PRAC-DATA (Zarattini et al., US, no
slippage, and our proxy is the 2nd 5-minute bar, not the 1st). F4 = PRAC-DATA
(~0.10R gross, about equal to costs). F5 = STUDY at index level (Gao et al.;
Komarov: single-stock intraday momentum ≈ market momentum).

## 4. Falsifiable predictions (written before any test)

FIRE = day-T High ≥ trigger, for candidates that **opened below** the trigger. Gap-through
opens are separated out, because for them the fire question is already answered at 09:15.
HOLD = close_above (daily, full history) and held30 (intraday, 74 sessions), measured among
touchers.

- **P1 (F1/F6).** Opening distance dominates prior-close distance for FIRE: AUC(dist_open)
  − AUC(dist_prev_close) ≥ 0.03 on 2025 and on 2026 separately. ATR-normalized open distance
  beats %-distance by AUC ≥ 0.01. *Falsified if* the gap between them is < 0.01 in either year.
- **P2 (F2).** Among touchers that opened below the trigger, within matched `dist_open_atr`
  terciles, close_above falls by ≥ 5 pp from the lowest to the highest gap-up tercile.
  Gap-through opens have a lower close_above rate than intraday touches. *Falsified if*
  the spread is < 3 pp or has the opposite sign in the majority of distance terciles.
- **P3 (F3).** Within matched `dist_0925` quintiles, the top-rvol quintile's fire rate is
  ≥ 1.5x the bottom quintile's in at least 3 of 5 distance quintiles. For HOLD (held30 among
  touchers) the prediction is **no** gradient (≤ 5 pp), in line with swing_qs item 8.
  *Falsified (FIRE)* if the ratio is < 1.2x in most quintiles.
- **P4 (F4).** Within matched `dist_0920` quintiles, the top-tercile `bar1_clv` fire rate is
  ≥ 1.3x the bottom tercile's. No HOLD gradient (≤ 5 pp). *Falsified* if < 1.1x.
- **P5 (F5).** Within matched `dist_open_atr` terciles, fire rate on Nifty-gap > +0.5% days is
  ≥ 1.3x the rate on Nifty-gap < −0.5% days. *Falsified* if < 1.1x. Pre-registered caveat: most
  of this effect should already be inside `dist_open` (a market gap moves every stock's open),
  so the incremental test is the one that counts.
- **P8 (F7, Berkman).** Among touchers that opened below the trigger, within gap terciles,
  the top prior-day-attention tercile (|ret_prev|) has close_above ≥ 4 pp lower than the
  bottom tercile. *Falsified* if the spread is < 2 pp or reversed in the majority of gap
  terciles.
- **P6 (combined detector).** A logistic model on the daily features (F1+F2+F5+F6 + the
  existing quality_score parts + freshness), trained ≤ 2024 and tested on 2025 and 2026
  separately, improves out-of-sample FIRE AUC over `dist_open_atr` alone by ≥ 0.02 in both
  years. *Falsified* if the gain is < 0.01 in either year. That would mean nothing beyond
  distance adds usable information.

## 5. Options economics — the motivating question

**Prior before testing:** blind-at-open probably loses, and the reason is structural, not a
guess:
- When the open is **close** to the trigger (say ≤ 0.5%), the touch fills at almost the open
  price anyway. Entering early buys at most about 0.5% × delta of premium, which is small.
- When the open is **far** from the trigger, P(fire) is low (the baseline curve is < 10% at
  2%+). The blind buy then pays premium and theta on the 75-90% of days that never fire.
- So the blind entry's edge can only come from days that open far away *and* still fire, and
  those are exactly the low-probability days. A detector would have to raise P(fire) a lot in
  that zone.

**Break-even to beat (computed, not assumed):** blind-arm expectancy per candidate
= P(fire)·E[R | fire, bought at open] + (1 − P(fire))·E[R | miss, bought at open]. The touch
arm takes only the fire days at a worse price. Both are measured directly on real bhavcopy
legs.

**P7.** Blind-open ATM calls on *all* primed F&O candidates have negative mean R at both
exits (E1 = day-T close, E2 = T+1 open). The top-decile-by-detector blind arm does **not**
beat the touch arm's per-trade mean R, or its per-day capital-constrained total, in 2025 and
2026 separately. *This would be falsified* (and the idea promoted to further research) if
the top-decile blind arm beats the touch arm on per-day capital-constrained expectancy at
K=3 in both 2025 and 2026, and also after a 5%-of-premium round-trip friction haircut.

**Verdict on testing:** worth testing. The data to answer it already exists: 4 years of real
option legs, split-safe strike selection, and a validated touch reconstruction. It answers a
question this project has never tested (entering *earlier* than the touch; RQ-37/RQ-94 only
tested entering later). It is cheap. The expected answer is negative, and a clean negative is
a completed outcome (Rule #17).

## 6. Research Preflight — RQ-PB-1 (blind pre-breach option entry)

1. **Population.** Every F&O primed candidate-day: `base_filters_pass` on the T-1 row (the
   live `shortlist_primed` convention, Rule #18), no corp action on T or T-1, 2022-06 →
   2026-09-22. The contract is the front-month ATM CE (rolled if < 5 trading days of runway),
   strike nearest the real day-T open, and it must have been liquid on T-1 (OI > 0, traded)
   and traded on T. **No position blocking**: each candidate-day is an independent 1-day
   option trade. This is not a swing position population, and blocking is a swing-engine
   concept. It is labeled a candidate-day panel, not a gated position population.
2. **Entry clock.** Blind arm: decision at 09:15-09:20 using T-1 close + T Open only; fill =
   the contract's day-T OpnPric (first trade; proxy). Touch arm: only on days the stock
   touched the trigger; fill = OX1 reconstruction at the touch (opt_open + 0.492 × (trigger −
   open)), clamped to the option's day range. Gap-through opens fill at OpnPric in both
   arms (identical by construction).
3. **Stop / 1R (Rule #20).** 1R = the premium paid per contract. A long option's max loss is
   the premium. No intraday stop, because daily option data cannot simulate one. R =
   option exit / entry − 1. This convention is **not comparable** to any stock-side R in the
   project (BC's R is structural-low based). No cross-comparison is drawn.
4. **Exit engine.** Fixed and identical for both arms: E1 = day-T ClsPric (same-day, the
   project's standing "options: same-day exit" conclusion) and E2 = T+1 OpnPric (the gap-up
   exit convention, FINDINGS 2026-09-07). `primed_engine` is **not** this product's exit.
   It is a ≤15-day stock swing engine. Research Preflight Q4 asks whether the engine is right
   for the product being tested, and it isn't. `primed_engine` + `build_population` are
   still used for the one stock-side question where they are the right engine: does the
   detector's pre-open score predict the real swing R of the touch trades it would rank
   (secondary, §7).
5. **Comparison unit.** Whole products per day. (a) Per-trade R stack for blind-all,
   blind-top-decile and touch-all. (b) A per-day capital-constrained book: K = 1/3/5
   positions per day chosen by the pre-open score (blind) or by the same score among that
   day's touchers (touch). Equal premium per position. Reported per year (Rule #16), with
   drawdown and worst losing streak in units of premium.

Friction: bid-ask at the open on stock options is not observable here. Every option result
is reported at 0%, 2% and 5% round-trip-of-premium haircuts.

## 7. Secondary (stock side, canonical engine)

`build_population(nifty500, backtest.load, bc_v2_recipe, gate_clock="T-1")`. The real
touch-entry BC v2 trades are joined on (ticker, entry_date) to the panel's pre-open features.
Question: does the pre-open detector score (or F2 gap) separate the real swing R of trades
that did fire? Report KEPT/REMOVED against the BASELINE, with the full R stack, per year.
Telemetry-only unless it clears Rule #21.
