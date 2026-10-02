# Pre-Breach Detector: Findings (RQ-PB-1)

Separate thread, started 2026-09-30 IST. It does **not** write to the shared `../FINDINGS.md`,
`../PARKING_LOT.md`, or any production file.

**Files in this folder**
- `SPEC.md`: the predictions, frozen before any outcome was looked at.
- `LITERATURE.md`: sources, tagged by evidence tier.
- Scripts `01`–`06`: the analysis.
- `*_out.txt`: raw output from each script.

## Bottom line

| Question | Answer | Disposition |
|---|---|---|
| Does buying an ATM call blind at the open, on highly ranked primed candidates, beat buying at the real touch? | **No.** Paired against the touch entry on the same candidate-days, the net gain is about 0R per candidate before friction (−0.03 to +0.03R across distance buckets). It is negative in every bucket after friction. This holds at both exits and both beta values tested. | **CLOSED-NEGATIVE** |
| Do daily pre-open features (gap, Nifty gap, prior-day attention, quality_score parts, freshness, CLV…) add anything to FIRE beyond opening distance? | **No.** Out of sample, the combined model improves AUC by +0.001 (2025) and −0.000 (2026). | **CLOSED-NEGATIVE** |
| Do they predict HOLD (holding above the trigger once touched)? | **No.** The gap-fade effect is about 0; the attention effect is under 3pp. | **CLOSED-NEGATIVE** |
| Is opening distance in ATR units better than prior-close distance in %? | **Yes.** AUC improves by about +0.04 in total: +0.02 from anchoring to the open, and a further +0.02 from ATR scaling. Consistent in all 5 years. | Descriptive. A candidate improvement to `calibrated_fire_rate`'s input variable; not built. |
| Does early relative volume (09:20 bar, known at 09:25) predict FIRE? | **Yes, in distance-matched cells.** The upper half fires 8–10pp more often. It adds about +0.01 AUC and does **not** predict HOLD. It **does not improve option R** when used to rank a blind entry. | Exploratory only: 74 sessions, one regime. Real signal, not a usable intervention (Rule #21). |

**Side findings, flagged, nothing changed**
- `primed_engine._new_state` books gap-through-open entries at the trigger price instead of the real opening fill.
  - This affects 1,053 of 10,219 BC v2 trades (10%).
  - It inflates their mean R from +0.079 to +0.152.
  - It inflates the population mean R by about +0.007.
- ATM calls bought at the touch, on the full primed-touch population, are about break-even before friction (+0.02–0.03R per trade) and negative after 5% friction.
  - This depends on the reconstruction: it turns to zero or negative if the true touch fill implies a beta ≥ 0.6.

---

## 1. Literature (full detail in LITERATURE.md)

**Backed by studies**
- Buying an attention stock at the open is costly, because the opening price is inflated and then reverses intraday (Berkman et al. 2012, JFQA; US data).
- Single-stock intraday momentum is mostly market momentum (Komarov 2017; Gao et al. 2018, index level).
- Option spreads are widest at the open, and straddles bleed most in the morning (Da, Goyenko & Zhang 2025; US data).
- NSE stock options have no pre-open auction (NSE circulars, Dec 2025).
- There is one counterpoint: outside the US, momentum accrues intraday (Lou, Polk & Skouras 2019). This data set does not include India.

**Practitioner work with data, but no slippage modelled**
- 5-minute Opening Range Breakout (ORB) plus first-5-minute relative volume (RVOL, "stocks in play"): Zarattini, Barbon & Aziz 2024.
- Almost all of that edge comes from the RVOL filter. It decays for 15- and 30-minute windows.
- An independent replication found the direction of the first candle is worth about 0.10R gross, roughly equal to costs.

**Folklore, or no data found**
- VWAP reclaim or rejection.
- NSE gap-fill percentages.
- O'Neil's breakout-volume rule.
- Any published hold or reject rate after a touch.

Qullamaggie (practitioner claim only) buys at the opening-range high, which means he also waits for a touch; nothing in his method supports buying blind at the open.

## 2. Data used

- **Candidate-days:** 134,264 primed candidate-days, meaning `base_filters_pass` on the T-1 row (the live convention, Rule #18). 500 tickers, 2021-11 to 2026-09.
- **Intraday:** 8,360 of those candidate-days have 5-minute features, covering 74 sessions (2026-06-10 to 09-23).
  - The 09:15 bar reports zero volume in 97% of rows, so RVOL is only computable from the 09:20 bar.
- **Options:** 39,472 real ATM call legs from the bhavcopy, 2022-06 to 2026-09-22.
  - Strikes are chosen using liquidity as of T-1.
  - Prices are unadjusted using the bhavcopy underlying price, or put-call-parity spot before 2024 (median error 0.22–0.30%).
  - The blind fill is the contract's first trade of the day, which is **not** a 09:15 quote.
  - The touch fill is reconstructed with OX1 (open + 0.492 × move from open to trigger).
  - 11.6% of touched days had the reconstructed fill clamped to the day's option range.

## 3. Pre-registered tests versus outcomes (predictions in SPEC.md §4)

| # | Prediction | Result | Verdict |
|---|---|---|---|
| P1 | AUC(open distance) − AUC(prior-close distance) ≥ 0.03 in both 2025 and 2026 | +0.027 (2025), +0.035 (2026); +0.022 to +0.035 across all years | Direction confirmed; 2025 just under the stated bar, well above the falsification level of 0.01 |
| F6 | ATR-scaled open distance beats %-scaled by ≥ 0.01 AUC | +0.018 to +0.021 in every year | **Confirmed** |
| P2 | Gap-fade: close-above rate falls by ≥ 5pp from low-gap to high-gap tercile | −0.1 / +1.7 / −0.7pp. Mixed sign across years. Gap-through opens actually hold *better* (51.5% vs 42.9%) | **Falsified** |
| P3 | RVOL at 09:25: Q5/Q1 fire rate ≥ 1.5x in at least 3 of 5 distance quintiles; no HOLD gradient | 1.83x / 2.39x / 2.69x / 2.50x / 2.00x. held30 by RVOL Q1–Q5: 42.3 / 42.6 / 43.6 / 38.7 / 40.4% | **Confirmed**, with caveats (§4) |
| P4 | First-bar close-location value (CLV, where the bar closed within its range): high/low tercile fire rate ≥ 1.3x | 1.32x / 1.20x / 0.97x / 2.33x (thin) | Inconclusive / weak |
| P5 | Nifty gap up vs down: ≥ 1.3x fire rate | 1.15x (near) / 0.82x / 0.77x | **Falsified** (already inside open distance, as caveated in SPEC.md) |
| P6 | Full daily model beats distance-only by ≥ 0.02 AUC out of sample | +0.001 (2025), −0.000 (2026); top-decile fire rate 69.0 vs 68.4% | **Falsified** |
| P8 | Prior-day attention (Berkman): close-above rate ≥ 4pp lower | −0.8 / −1.0 / −3.1pp | **Falsified** (right direction, too small) |
| P7 | Blind top-decile does **not** beat touch in 2025/2026 | Confirmed. The paired decomposition shows no bucket where it wins after friction | **Confirmed** → CLOSED-NEGATIVE |

**P1 detail: fire AUC for candidates that opened below the trigger**

| Year | n | Fire % | Prior-close distance % | Open distance % | Open distance (ATR) |
|---|---|---|---|---|---|
| 2022 | 25,148 | 20.6 | 0.810 | 0.832 | 0.852 |
| 2023 | 31,007 | 21.2 | 0.806 | 0.830 | 0.851 |
| 2024 | 30,427 | 19.7 | 0.810 | 0.836 | 0.855 |
| 2025 | 23,381 | 19.4 | 0.814 | 0.840 | 0.861 |
| 2026 | 19,830 | 19.0 | 0.812 | 0.847 | 0.865 |

## 4. RVOL at 09:25: checks run before believing it (Rule #22)

- **Not the same as velocity.** Spearman correlation with the 09:20→09:25 move toward the trigger is 0.026. The effect holds within every velocity tercile: 19→22%, 15→33%, 21→39%.
- **Distance confound checked.** In the nearest quintile, high-RVOL names sat slightly closer to the trigger. Split into distance quartiles with matched median distance (for example 1.143% vs 1.130%), the high-RVOL half still fires more: +7.8, +8.3, +10.2 and +8.5pp.
- **Lookback robustness.** Q5/Q1 is about the same with a 10-, 20- or 30-session lookback: 1.8–2.1x, 2.1–2.4x and 2.1–2.7x.
- **Stable by month.** It holds in every month (Jun–Sep 2026). Only 4 months exist, so year-level robustness (Rule #19) is not possible.
- **Leave-one-month-out AUC gain** over distance plus velocity: −0.006 (Jun, n=492), +0.008, +0.008, +0.015.
- **Hand-verified.** 5 of 5 examples match the raw 5-minute bars exactly on distance, RVOL and first-touch time: SHYAMMETL 09-23, SBICARD 07-28, FLUOROCHEM 07-27, TMCV 07-02 and COFORGE 08-14.
- **Not an option intervention.** Among candidates within 1.5% and not yet fired at 09:25, a blind 09:25 entry, top 3 per day, returns:

| Ranking | R per trade |
|---|---|
| Distance only | −0.053 |
| Distance + RVOL | −0.070 |
| Touch arm, same rankings | −0.051 / −0.064 |

  That covers 55 sessions, with exit at the next open.

## 5. The motivating question: blind at the open vs at the touch (real bhavcopy legs)

**Per-trade results, exit at T+1 open, 0% friction, 1R = premium**

| Arm | n | Mean R | Median R | Win >0 % | ≥0.25R % | ≥0.5R % | ≥1R % | Payoff |
|---|---|---|---|---|---|---|---|---|
| Blind, all candidates | 39,141 | +0.009 | −0.039 | 43.4 | 16.6 | 6.5 | 1.5 | 1.40 |
|   of which fired | 8,902 | +0.217 | +0.143 | 68.0 | 38.0 | 18.5 | 5.1 | 2.24 |
|   of which missed | 30,239 | −0.052 | −0.077 | 36.1 | 10.3 | 2.9 | 0.5 | 1.11 |
| Blind, top-decile score | 3,932 | +0.020 | −0.054 | 42.0 | 19.4 | 9.6 | 2.6 | 1.61 |
| Touch, all touchers | 8,902 | +0.033 | −0.015 | 46.8 | 17.3 | 7.3 | 1.8 | 1.53 |

Exit at the day-T close gives the same ordering (blind −0.002, top-decile +0.012, touch +0.020).

**Capital-constrained book, top 3 per day, T+1 open exit, total R per year**

| Year | Blind, 0% | Touch, 0% | Blind, 5% friction | Touch, 5% friction |
|---|---|---|---|---|
| 2022 | +1.4 | +7.3 | −20.2 | −9.8 |
| 2023 | +10.8 | +29.3 | −25.5 | −0.3 |
| 2024 | +4.0 | +23.1 | −32.6 | −8.6 |
| 2025 | +6.0 | +18.0 | −30.8 | −12.8 |
| 2026 | +1.3 | +10.4 | −25.0 | −11.7 |

Maximum drawdown is worse for the blind arm in every year: −7 to −15R, against −4 to −11R for touch. The complete K = 1/3/5 grid is in `options_test_out.txt`.

**Paired decomposition, the right comparison unit (as in RQ-94)**

Switching one candidate-day from touch to blind gains the early-entry discount on fired days and pays the full blind-trade R on missed days. Exit at T+1 open, beta 0.492:

| Open distance | n | Fire % | Early-entry gain when fired | R on missed days | Net per candidate | Net after 5% friction |
|---|---|---|---|---|---|---|
| 0–0.25% | 714 | 79.0 | +0.026 | −0.227 | −0.027 | −0.038 |
| 0.25–0.5% | 1,637 | 66.2 | +0.076 | −0.198 | −0.017 | −0.034 |
| 0.5–1% | 4,424 | 52.2 | +0.132 | −0.173 | −0.013 | −0.037 |
| 1–1.5% | 4,662 | 34.5 | +0.211 | −0.127 | −0.010 | −0.043 |
| 1.5–2% | 4,318 | 23.4 | +0.296 | −0.097 | −0.005 | −0.044 |
| 2–3% | 7,469 | 12.7 | +0.371 | −0.070 | −0.014 | −0.058 |
| 3–5% | 8,823 | 4.0 | +0.550 | +0.009 | +0.031 | −0.017 |
| 5%+ | 6,122 | 0.9 | +0.812 | +0.004 | +0.011 | −0.039 |

**Why it fails.** The gain and the cost cancel almost exactly at every distance, which is the structural argument from SPEC.md §5.
- **Near the trigger:** the stock almost always fires, but the early-entry discount is tiny, and a near miss means the stock faded from the open (about −0.2R).
- **Far from the trigger:** the discount is large, but fires are rare.
- **3–5% bucket:** its small positive number comes from missed days scoring about 0R (generic buy-the-open on stocks well below the trigger), not from the detector. It is negative after friction.
- **Beta 0.6 stress test** (makes touch fills pricier): every net per candidate is within ±0.033 before friction, and all are negative after friction.

**One trap caught.** On liquid contracts only (not pre-declared), blind top-decile beat touch-all (+0.064 vs +0.043).
- That top decile is 53% gap-through opens (blind and touch are identical by construction) plus 47% opens within 0.5% of the trigger, with a 92–97% fire rate.
- It is a **composition effect**: near-open touches are better trades. It is **not** evidence that entering early helps.
- The paired table above removes this effect, and nothing survives.

**Caveats that apply to the whole option test**
- The bhavcopy opening price is the first trade, not a 09:15 quote.
- The touch fill is reconstructed (OX1, validated on only 9 paths).
- Friction at the open is unobserved. The literature says spreads are widest then, which argues for 5%+ friction, not 0%.
- Every one of these makes the blind arm look **better** than it really is, not worse. The negative verdict holds in spite of them.

## 6. Stock side (canonical `build_population` + `primed_engine`)

`build_population(nifty500, backtest.load, bc_v2_recipe, gate_clock="T-1")` gives n = 10,671 trades. 10,219 of them join to the panel; the 452 unmatched are mostly 2021, where the panel needs 20+ bars of history.

**Gap-through fill audit.** The engine enters gap-through opens at the trigger price, but the real fill is the open. The median open is 0.48% above the trigger (p90 3.0%). Re-anchored to the open, with the same stop and risk unit:

| | Mean R | Median R |
|---|---|---|
| Engine | +0.152 | +0.116 |
| Real fill | +0.079 | +0.051 |
| Intraday-touch entries | +0.072 | — |

**Realistic-fill splits at the median**

| Cohort | n | Mean R | Median R | Win >0 % | ≥0.25R % | ≥0.5R % | ≥1R % | Payoff |
|---|---|---|---|---|---|---|---|---|
| Baseline | 10,219 | +0.073 | +0.028 | 52.2 | 35.4 | 22.4 | 8.5 | 1.21 |
| Fire score ≥ median | 5,110 | +0.079 | +0.036 | 52.9 | 36.0 | 22.9 | 8.2 | 1.21 |
| Fire score < median | 5,109 | +0.067 | +0.025 | 51.5 | 34.8 | 21.8 | 8.9 | 1.21 |
| Gap ≥ median | 5,110 | +0.089 | +0.033 | 52.6 | 36.2 | 23.0 | 9.1 | 1.27 |
| Gap < median | 5,109 | +0.056 | +0.026 | 51.8 | 34.6 | 21.7 | 8.0 | 1.16 |

**Gap high/low by year:** 2021 +0.077/+0.076, 2022 −0.003/+0.006, 2023 +0.277/+0.246, 2024 +0.072/+0.035, 2025 +0.008/−0.003, 2026 +0.026/−0.071.

It is not year-stable: 2022 reverses, and 2026 carries most of the spread. Descriptive only.

It also contradicts Berkman on the swing horizon, since gap-ups do not do worse. That is consistent with Lou, Polk & Skouras's non-US finding, but that is my inference, not something tested here.

## 7. Closed items (Rule #17), so they aren't re-run under new names

- **Blind pre-breach ATM call entry at the open** (any ranking by daily features, or by 09:25 RVOL): closed-negative. Reopen only with real intraday option quotes **and** a detector that raises the fire rate in the 1–3% distance zone far above distance alone.
- **Daily pre-open FIRE features beyond open distance:** closed-negative (P6). Covers opening gap, Nifty gap, prior-day return and volume, prior-day CLV, quality_score parts, freshness, consolidation_days, RSI and ATR%.
- **Pre-open HOLD predictors** (gap-fade, Berkman attention): closed-negative (P2, P8). This joins swing_qs item 8 (touch-bar volume, proximity, R1/R2), which already found HOLD near-unpredictable.

## 8. Open items (not done; for the user and critic to decide)

1. **Re-key `calibrated_fire_rate` on ATR-scaled distance.** It is worth about +0.02 AUC for FIRE and would need a rebuild of the P(close-above) table. Not built. `live_checkpoint.py` is production and was not touched.
2. **Use 09:25 RVOL only as a tiebreaker** among tier-3 "watching" candidates at similar distance (which IOC to watch), never for blind entry. It needs more sessions before it can pass Rule #19. As the intraday cache grows, rerun `02_intraday_features.py` and the §4 checks.
3. **`primed_engine` gap-through fill optimism.** About 10% of BC v2 trades have R overstated by about 0.07R (mean). This is a shared-engine question for whoever owns it. Not changed here.
4. **Touch-entry ATM option economics.** They look near break-even gross and negative after friction on the full primed-touch population. This is reconstruction-based and sensitive to beta. It deserves real broker quotes before any conclusion about the standing options convention.

---

# RQ-PB-2: Pre-breakout momentum and why breakouts stall (2026-10-01 IST), exploratory

**Status: logged for later discussion with the user. Nothing here is promoted.**
- Every result is exploratory or descriptive, per Rule #19 and Rule #21.
- No production file was changed by this research.

**Files:** `rq_pb2/` holds scripts 01–05 and their outputs. Run them from the `md-swing-scanner/` root with `PYTHONPATH=.`.

**The user's question.** Breakouts often stall after the breach. Can we capture the momentum *before* the breakout instead, and trade it on stock options? And if not, why does the stall happen?

## A. The stall is real

Population: primed candidate-days (gate on T-1) that opened below the trigger and touched it intraday. n = 26,265 of 131,133 (20.0%), 2021-11 to 2026-09.

Returns are measured from the trigger price, in %.

| Window | Median | % positive |
|---|---|---|
| Open → trigger | +1.34% | — |
| Trigger → same-day close | −0.24% | 42.9% |
| Trigger → T+1 close | −0.24% | 46.1% |
| Trigger → T+3 close | −0.23% | 47.6% |
| Trigger → T+5 close | −0.16% | 48.7% |
| Trigger → T+10 close | +0.24% | 51.2% |

- The trigger → close median is negative in every year from 2021 to 2026.
- After the touch, T+1 to T+5 is a coin flip. Drift turns positive only by T+10.
- This is consistent with the BC finding that ≥1R winners take a median of 8 days.

## B. Entering on the intraday approach before the touch: dead (`01_approach_entry.py`)

**Setup**
- **Data:** 5-minute bars, 78 sessions (2026-06-10 to 09-29), non-gap-through opens only.
- **Signal:** the first 5-minute close within {0.5, 1.0, 1.5}% of the trigger, before any touch, no later than 14:30.
- **Fill:** the next bar's open.
- **"Strong":** cumulative volume ≥ 1.5x this ticker's own median by the same time of day (prior 20 sessions only), with price above VWAP. Defined once and not tuned.
- **Units:** returns are % stock returns. No stop is defined, so there is no R (Rule #20).

**A bug caught by hand-checking (Rule #22)**
- The first version let days that had already touched in the 09:15/09:20 bars through, because the loop started at 09:25. APARINDS on 2026-08-10 exposed it.
- After the fix, 0 of 1,565 events have a touch at or before their signal.
- IIFL, FLUOROCHEM and GALLANTT were checked against the raw 5-minute bars and matched.

**Results, 1.0% zone**

| Cohort | n | Touch % | Entry → EOD mean | EOD median | MAE median | T+5 mean |
|---|---|---|---|---|---|---|
| All | 1,565 | 50.6 | +0.02% | −0.12% | −0.87% | −0.25% |
| Strong | 567 | 60.3 | +0.12% | −0.15% | −1.01% | +0.05% |
| Not strong | 998 | 45.1 | −0.03% | −0.11% | −0.78% | −0.42% |
| Touched (hindsight) | 792 | 100 | +0.82% | +0.65% | −0.59% | +0.47% |
| Missed (hindsight) | 773 | 0 | −0.79% | −0.57% | −1.15% | −0.98% |

**Variant: sell at the trigger touch, otherwise exit at EOD**

| Zone | Mean, strong | Mean, not strong | Win %, strong |
|---|---|---|---|
| 0.5% | −0.10% | −0.10% | 76.1% |
| 1.0% | −0.03% | −0.03% | 65.1% |
| 1.5% | −0.10% | −0.07% | 56.2% |

- The "worst 5%" outcome is worse for the strong cohort (−2.44% vs −1.99% in the 1.0% zone).
- By month the sign flips, with no consistent pattern.

**Verdict.** Strength plus volume is a real signal for whether a stock will touch: about +15pp in every zone, matching RQ-PB-1's RVOL result. It fails as an intervention (Rule #21):
- The gain on a touch is capped at the distance to the trigger, about 0.8%.
- A miss loses about the same.
- Even on touch days, trigger → EOD was −0.10% (median).

**CLOSED-NEGATIVE.**

## C. Literature (web search, 2026-10-01)

Tiers follow RQ-PB-1: STUDY = academic, PRAC-DATA = practitioner with data, PRAC-CLAIM = practitioner claim only.

**Why stalls happen: resting supply at the level (STUDY)**
- **Della Vedova, Grant & Westerholm (JFQA 2022), Finnish clearinghouse data 2004–09:** households sharply increase limit-order selling at and before the 52-week high. On the day of the high, the individual is the seller 58.8% of the time in individual-vs-institution trades.
- **Della Vedova et al. (EFMA 2024), Finnish order-book data 2000–15:**
  - Sell-side depth roughly doubles near the high, and the book is 30% more skewed to the sell side.
  - Price impact falls 30–50%.
  - Liquidity and impact trace a V shape around the high.
- **Kavajecz & Odders-White (RFS 2004, NYSE):** support and resistance levels coincide with peaks in order-book depth, and reversals happen there.
- **Osler (NY Fed, FX):** take-profit orders cluster at chart levels, causing reversals. Stop orders sit beyond the levels, causing acceleration once crossed.

**How the stall resolves (STUDY)**
- **George & Hwang (2004):** stocks near the 52-week high drift higher over 6–12 months, with no reversal. Investors under-react near the anchor.
- **Huddart, Lang & Yetman (Mgmt Sci 2009):** volume spikes when price crosses the old range, then fades. The effect is stronger the longer it has been since the last extreme.

**Options near the high (STUDY)**
- **Driessen, Lin & Van Hemert (Review of Finance 2013):** IV falls as price approaches a high and rises after the breakthrough.
- **Saurav, Agarwalla & Varma (J. Futures Markets 2023, Indian stock options):** approaching the 52-week high, risk-neutral skew and OTM call volume fall while OTM put volume rises. Both reverse after the high is crossed.
- **Choy & Wei (Financial Review 2022, US):** delta-hedged option returns are higher near 52-week extremes.

**Early-entry methods (PRAC-CLAIM, no published data)**
- Pocket pivot (Kacher/Morales) and Minervini's cheat / low-cheat entries.
- Both are entries on daily bars, days *before* the breakout, inside the base, with a stop at nearby support. They avoid the supply zone instead of buying into it.

**PRAC-DATA:** Bulkowski finds that above-average-volume breakouts pull back to the breakout level 74% of the time.

**Caveat.** Nearly all of this literature is about the 52-week high, not a 10-day high. Applying it to a 10-day trigger is inference.

## D. IV around the trigger touch: the reverse of the literature (`04_iv_build.py`, `05_iv_event.py`)

**Setup**
- **IV source:** ATM implied volatility, the average of call and put, from bhavcopy closes. Nearest expiry with ≥ 7 days to expiry, r = 6.5%.
- **Data:** 205,224 ticker-days, 280 F&O stocks, 2022-06 to 2026-09-22.
- **Excess IV:** each ticker's IV minus the cross-sectional median that day. This absorbs market moves and the common monthly expiry roll.
- **Events:** 8,934 touched F&O days, with day 0 = the touch day.
- **Control:** ticker-days matched on 10-day return decile, to separate this from the normal spot–vol relationship.

**Results, excess-IV change vs day −10 (vol points, median)**

| Day | d−5 | d−1 | d0 | d+1 | d+3 | d+5 |
|---|---|---|---|---|---|---|
| Change | +0.15 | +0.48 | +0.63 | +0.45 | +0.31 | +0.29 |

- **Approach leg (d−10 → d−1):** +0.54 vol points above the return-matched control (median). Positive in every year 2022–26.
- **Post-touch leg (d0 → d+3):** −0.32 vs control. Negative in every year.
- **By outcome (evaluation only):** BLAST keeps about +1.4 points, while STALL gives it all back by d+3.

**Hand check.** OBEROIRLTY (2024-04-05) and BANKINDIA (2026-02-24) were recomputed from the raw bhavcopy. The Black-Scholes price at the stored IV matches the option close: about 48.9 vs 48.85, and about 7.0 vs 7.04.

**Verdict**
- Around our 10-day triggers, IV rises slightly into the touch and deflates after it. That is the opposite direction to Driessen et al. and Saurav et al.
- My inference: a 10-day high is too weak an anchor for that effect.
- The size is economically trivial. One vol point is about 3% of premium against 2–4%/day of theta.
- **"Buy cheap vol before the breakout" does not exist here. CLOSED.**

## E. Blast vs stall at the pivot (`02_pivot_features.py`, `03_support_features.py`)

**Outcome definition (pre-declared).** Measured from the trigger, in ATR14 units at T-1, at the T+5 close:
- **BLAST:** ≥ +1.5 ATR.
- **FAIL:** ≤ −1.0 ATR.
- **STALL:** in between.

**Base rates.** n = 26,265. BLAST 18.5%, STALL 55.1%, FAIL 26.5%. T+5 mean +0.10 ATR.

**Hand-checked:** NSLNISP (2025-05-16) and POWERINDIA (2022-01-20), every feature against raw bars.

**Flat: within about 1.5pp of baseline at every pre-declared variant**
- Tests of the level ({0.5, 1, 2}% tolerance, prior 20 days).
- Pivot age.
- Volume dry-up ({3, 5, 10} days vs 50).
- Pocket pivot ({3, 5, 10} days).
- Approach speed ({3, 5, 10} days).
- Distance to daily P, S1, S2 and EMA8/13/21/34.
- Support confluence ({0.5, 1, 1.5} ATR).

Closer support lowers FAIL and BLAST together, which compresses outcomes without improving the mean. My reading: it mostly measures how wide yesterday's range was.

**Overhead room: the only structured feature, same shape at 60, 120 and 250 days.** Trigger vs the highest High over the prior 250 days:

| Room | n | BLAST % | FAIL % | T+5 mean |
|---|---|---|---|---|
| Clear air (≤ 0) | 9,097 | 19.0 | 25.6 | +0.15 |
| 0–2 ATR below the older high | 3,837 | 22.2 | 23.1 | +0.29 |
| 2–5 ATR below | 3,289 | 18.2 | 26.0 | +0.13 |
| > 5 ATR below | 5,678 | 16.7 | 28.1 | −0.02 |

- The 0–2 ATR group has the best BLAST rate in every year 2022–26, but the edge is shrinking: 25.1% vs 13.8% for clear air in 2022, 18.3% vs 15.8% in 2026.
- Rule #21: it moves BLAST about 3.7pp while keeping only 15% of the population. A gate is not justified.

**EMA stack 8 > 13 > 21 > 34.**
- It holds on 90% of touched days, since the primed gate already requires a trend.
- The 10% without it are worse: T+5 mean −0.06 vs +0.12, consistent in every year.
- Removing them lifts the mean only from 0.10 to 0.12, and it overlaps with `ema34_persistence` (swing_qs Feature Battle). Not actionable.

**SAME-DAY TELEMETRY, not promotable: did the touch day's low break S1?**

| | n | BLAST % | FAIL % | T+5 mean |
|---|---|---|---|---|
| Low broke below S1 | 2,919 | 13.1 | 37.7 | −0.43 |
| Low held above S1 | 23,346 | 19.2 | 25.1 | +0.17 |

- FAIL is 33–43% vs 21–28% in every year 2022–26.
- This is partly mechanical, because a deep low on the touch day feeds into the T+5 close.

## F. Overall disposition

- With anything visible before the touch, pre-breakout momentum on BC's 10-day triggers is **not tradable as a long-option strategy**.
- STALL is the base case (55%), and the payoff arrives as slow drift that fights theta.
- No feature known before the touch separates BLAST from STALL by more than about 4pp.
- IV gives no tailwind.

## G. Open items (for discussion with the user, not started)

1. **Order the S1 break against the touch, using the 5-minute data.**
   - If the dip below S1 came before the touch, it's knowable before entry: an entry filter.
   - If it came after, it's a stop.
   - If it's a stop: test the touch-entry ATM option arm (RQ-PB-1 legs) with a stop at S1, about 1.1 ATR below the trigger (median). This is the first concrete "stop + options" structure found in this line of work.
2. **A daily-bar early entry days before the trigger** (pocket pivot / volume dry-up inside the base, stop inside the base). This would be a new product, with its own stop definition (Rule #20) and the Research Preflight. It is the only early-entry form the literature supports.
3. **Option structures that survive a stall** (longer-dated options, or futures). Product question only, untested.
4. **Small production issues spotted this session. Not changed, all display-only:**
   - `tomorrow_candidates.py` (evening view) builds trigger bands from `high10_prior` on the latest row, which excludes that day's own high. `live_checkpoint` fixed the same thing on 2026-09-07 (`high10_effective`). On 2026-10-01 it showed stale bands for 7 of 40 names; on 2026-10-02's list, for 3 of 29.
   - `_fragility_risk` on the live dashboard feeds abs(live close − open)/ATR, so before a touch a **red** candle counts as a "big body" and reads as Robust. DRREDDY flipped between Watch and Robust three times on 2026-10-01. The production gate uses the T-1 row, so it's unaffected.
   - The dashboard hides `fragility_est_pct`, so the narrow 12–26% range isn't visible.

## H. Related real trade (anecdote only, not evidence)

- **Trade:** DRREDDY Oct-27 1220CE on 2026-10-01, discretionary.
- **Thesis:** daily EMA8 support plus the 1H EMA34.
- **Result:** entry 32.5, exited on SL at 27.5. −15.4%, −₹3,125 per lot gross.
- **What went wrong:**
  - The 1H EMA34 had already been lost at entry.
  - At the strike, put IV (27.2%) was above call IV (22.4%).
  - A 20x-volume sell bar broke EMA8 and S1.
  - Nifty broke S2.
- **Backtest of the same setup:** the separate intradaygeeks session tested it on 88,299 trades (2024–26) and found a mean of about 0. See `../intradaygeeks_replica/TELEGRAM_CALLS.md`.
