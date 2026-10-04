# Intraday 34-EMA rejection (shorts): living strategy doc

Last updated: 2026-10-04 (IST, evening): chart-review session -- pivots (daily/weekly/monthly), pivot x market, candle shape, lower-wick sweep, daily 8-EMA above the stop, rolling-over-after-a-top tested (scripts 72-75); no rule changed, two watch items added (5.8e). Research PAUSED after this; Monday 2026-10-05 goes live on the rules below unchanged. Earlier same day: full-hour candle at 11:15 / 12:15 and the strong-green-hour skip adopted (scripts 68, 70).
Detailed test-by-test log: `TELEGRAM_CALLS.md`. Literature notes: `INTRADAY_RESEARCH.md`.
All returns are % per trade, gross of costs, unless stated.

---

## 1. Current version (what we watch / trade)

**Side:** shorts only. Longs were negative in every variant and in every market regime.

**Universe:** NSE EQ stocks with prior-day 20-day average traded value of at least ₹10 crore (INR).
Your broker must allow intraday (MIS) shorting of the name.

**Levels (the strong ones):**
- 1H 34-EMA, as of the last completed hourly candle. Hourly candles are 09:15-aligned
  (09:15-10:15, 10:15-11:15, ...).
- 1H trend: 1H 8-EMA below the 1H 34-EMA.
- Higher timeframe: the daily 8-EMA as the chart shows it live, which is 2/9 × current price + 7/9 × yesterday's EMA8.

**Trigger: an hourly rejection, checked at the half hour and at the hour close.** Hourly bars are 09:15-aligned.
- **10:45 / 11:45 (half-way):** the hourly bar so far, i.e. the first 30-min candle of the hour.
- **11:15 / 12:15 (hour close): the full hourly bar** (open, high, low of the whole hour). Adopted 2026-10-04 (script 68):
  the rejection is hourly, so the stop must sit above the whole hour, not just its last 30 minutes (KNACK 30 Sep:
  30-min high 179.97 vs hourly high 180.76). 30m set: all setups +0.128% (unchanged); plan 11:15-else-11:45
  +0.120% -> +0.171% per trade. At the hour close this is the same trade as the 3-year 1H set.
- The bar is red (close below open); its high touches or crosses the 1H 34-EMA; it closes back below the 1H 34-EMA,
  no more than 0.5% below it.
- **At 11:45 / 12:15 only: skip a shallow pullback right after a strong green 10:15 hour** (adopted 2026-10-04, user's
  chart logic, script 70): the 10:15 bar green AND closed above the 1H 34-EMA AND our close still above that green bar's
  midpoint = buyers took the level back and are still in charge. Not after the 09:15 opening bar: that bar is gap /
  covering noise that fades, and those setups are fine (30m +Rs179, 1H +Rs93 per trade) vs after a 10:15 bar (30m -17,
  1H -40, 71-83% stopped; small: 6 / 51 trades). A DEEP pullback (below the green bar's midpoint) is the best group
  (failed reclaim: 30m +256, 1H +149) -- keep those. Plan 11:15-else-11:45: +171 -> +179 per trade; 1H 3-yr +117 -> +117.

**Checks at the moment of entry:**
- close below the daily 8-EMA;
- the day's high so far has pierced the live daily 8-EMA;
- daily ADX(14) as of yesterday is 25 or below;
- **the stock normally moves enough to reach 1%:** daily ATR(14) at least 2.56% of price, as of yesterday (added
  2026-10-03: low-range stocks made ~0 in both the 30m and the 3-year 1H data; skipping them lifts the 30m average from
  +0.089% to +0.129% and the 1H from +0.069% to +0.102% per trade, keeping two-thirds of setups);
- close below the session VWAP.

**Risk and exit:**
- Entry: short at the 30-minute candle's close.
- Stop: that candle's high.
- Target: 1% below entry.
- **Reward:risk rule:** skip the trade if the stop is more than 0.5% away (that is, less than 2:1).
- Exit at the target, at the stop, after 5 hours, or at the broker's MIS square-off (about 15:15),
  whichever comes first. An exit after 2.5 hours tested the same.
- **Exit decision (user, 2026-10-02):** a fixed 1% target and a fixed stop, with no trailing while trading by hand.
  A prior-candle trail did worse (script 45). Revisit when automating.
- **One trade a day, first come:** the first alarm with a setup, and at the same alarm the one closest to the EMA.
  No further filter reliably separates better from worse setups once the checklist and the 2:1 rule pass (script 56),
  so the scan lists **every** qualifying setup (user: equal quality -> watch them all on the chart, it's where the next
  improvement will come from) and marks the first-come one as the one-trade-a-day choice.

**Backtest, 5-minute data, Jun 10 - Sep 30 2026, one trade a day:**

| | |
|---|---|
| Days with a trade | 97% |
| Mean per trade | +0.156% |
| Win rate | 47% |
| Median stop | 0.35% |
| By month (Jun / Jul / Aug / Sep) | +0.04 / +0.05 / +0.13 / +0.38 |
| Where the trade comes from | 10:45 alarm 81%, 11:15 alarm 13% |

This is **exploratory**. It covers 4 months of a falling market, September dominates the result,
and it was the best of several variants tested. **The one-trade-a-day number is fragile:** with ~65 trades it moved
to +0.095% with a different tie-break and window (Jul-Sep, smallest stop first). The all-setups average (~+0.07-0.09%
per trade with 2:1) is the more reliable figure.

**Fallback version with 3 years of evidence (1H trigger):** the same rules, but with the 1H candle close
as the trigger, at 11:15 and 12:15. **Corrected 2026-10-03 (script 60):** earlier figures (+0.106% one/day, +0.108%
all setups) were inflated by a position-blocking bias in script 15. Clean: 3.7 setups/day, **+0.069% per trade**
(2024 +0.06, 2025 +0.06, 2026 +0.09); +0.074% at one per stock per day. Other 3-year 1H figures below that came from
script 15's set are overstated by ~0.03-0.04% and should be re-checked on clean data.
**Filters re-checked (script 60):** all six still earn their place in the live 30-min version; "below daily 8-EMA" and
"below VWAP" overlap -- either alone looks removable, both together cost ~0.027%/trade and add 70% more setups.

**Costs:** about 0.06-0.15% per MIS round trip including slippage. The edge sits close to the cost line,
so your actual brokerage and fills decide whether it pays.

---

## 2. How to run

```
cd md-swing-scanner/intradaygeeks_replica
python3 38_alarm_scan_1h_close.py                 # just after 10:45 / 11:15 / 11:45 / 12:15 (30-min trigger)
python3 38_alarm_scan_1h_close.py --tf 60         # old 1H trigger, just after 11:15 / 12:15
python3 38_alarm_scan_1h_close.py --rr 0          # show setups that fail the 2:1 rule too
python3 38_alarm_scan_1h_close.py --replay 2026-10-01 10:45   # replay a past alarm
```

- **Data comes from the end-of-day run.** `eod_checklist.sh` refreshes the daily and 5-min caches for all ~2,300 NSE
  stocks after the close; the scan builds its 1H candles and 34-EMA from that 5-min cache (identical to Yahoo's hourly
  bars, checked). If a stock's cache is behind the previous session the scan excludes it and prints "STALE DATA -- run
  eod_checklist.sh". (Stale daily data once wrongly excluded TANLA on 2026-10-01: ADX read 25.7 instead of 24.0.)
- **Prep (optional, ~6 s, local only):** `python3 38_alarm_scan_1h_close.py --prep` builds the day's candidate list from
  the previous close: 1H trend down, within 3% of the 1H EMA34, daily ADX <= 25 (keeps 98% of real setups, script 59),
  plus a 150-stock breadth sample. Alarm runs build it themselves if it's missing.
- **Alarm runs** fetch live 5-min bars only for those ~400-450 stocks. Replays (`--replay DATE HH:MM`) read the cache
  and take ~13 s. Run 1-2 minutes after each alarm: Yahoo publishes each 5-min bar with a short lag; if many stocks
  are missing the alarm candle's last bar, the scan says "DATA NOT READY -- run again in a minute".
- **Running late is fine (script 57):** up to 20 minutes late costs ~nothing per trade (+0.065-0.075% vs +0.075% on
  time). The scan shows each setup's `status` NOW: **ENTER** (stop not touched and the 2:1 rule still holds from the
  current price), **SKIP** (2:1 gone at this price -- don't chase), or **DEAD** (stop already touched). Target = your
  fill - 1%; the stop stays the candle high. FIRST COME = the first ENTER. Beyond 20 minutes the candle isn't shown.
- **Confirmed candles only (user, 2026-10-03):** running before the candle closes was tested (script 58: ~1 in 3 setups
  judged at 25 min fail by the close, mostly the bounce resuming) and rejected -- it invites confusion and overtrading.
  Run after the alarm; up to 20 minutes late is free (script 57).
- **Breadth** (info only): each run prints the share of the most liquid stocks above yesterday's close. The earlier
  "bullish breadth -> be cautious" warning was dropped (script 61): on clean data the effect flips between periods
  (3-yr 1H: bullish-breadth days weakest on average, not every year; Jun-Sep 2026: bullish-breadth days were the best).
- **Monthly re-check:** `./51_monthly_recheck.sh` tops up the 1H cache, re-runs the 30-min alarm test over all 5m data,
  and writes `rechecks/recheck_YYYY-MM.txt`. To schedule it on the 1st of each month at 18:37:
  `(crontab -l 2>/dev/null; echo "37 18 1 * * $PWD/51_monthly_recheck.sh") | crontab -`
  It only learns anything if the 5m cache keeps growing: run `eod_checklist.sh` daily. For all ~2,300 stocks, the cache
  step needs `intraday_cache.py --universe nse_equity` (on branch `intraday-cache-chunked-download`, not yet on master).
- **Take the stop from your broker's chart.** Yahoo misses the true high or low by a few paise on about 72% of days.
- Check that your chart's hourly candles start at 09:15. If they end at 10:00, the setups won't match.
- Log every trade in `live_watch_log.csv`: yours, the scan's, and the channel's (`channel_calls_live.csv`).
  Include your reason for the trade and your bias for the day, written before 10:15.

---

## 3. What the tests showed

| Question | Result | Script |
|---|---|---|
| Entry timing: earlier or later? | Later is better, up to a 30-min confirmation. EMA cross -0.042%, first 5-min close -0.001%, held 15 min +0.029%, 15-min candle +0.046%, **30-min candle + 2:1 rule +0.086%**, 1H close +0.077% (without the 2:1 rule) | 34, 36, 41 |
| Limit order at the EMA instead of entering at the close? | No. It fills 49% of the time, and the trades that never fill are the best ones (+0.44%), a case of adverse selection | 26, 33 |
| Skip if the close is already far below the EMA? | Yes, a 0.5% cap. A sweep shows a flat region from 0.5 to 1.0%, so it isn't fitted | 37 |
| A 2:1 reward:risk filter? | Yes. Return per 1% of stop rose from 0.10 to 0.25 | 39 |
| How deep should the wick pierce the EMA? | Up to 0.3% above is the most efficient per rupee at risk | (stop distribution) |
| Stop at the EMA instead of at the wick? | No better after costs | 35 |
| The 10:15 setups / first-hour noise? | The first hour is mostly opening noise with wide stops. Weaker over 3 years | 39, 40 |
| Shorts vs longs: is it just the 2026 drawdown? | No. Shorts make the same in Nifty-up and Nifty-down months (+0.093 vs +0.094) | 25, (regime) |
| Does Nifty's direction help? | Nifty's move *during* the trade decides it (70% vs 26% win), but nothing known at entry predicts it: 6 entry cues and 14 Nifty-path patterns all failed | 24, 27, 30 |
| "Stay long if unsure"? | That's a holding rule. Nifty Oct 2021 - Sep 2026: +123% overnight, -42% intraday | (overnight) |
| A full shift to a 30m EMA + 4H 8-EMA? | Worse (+0.035% vs +0.090%) | 42 |
| Is the data the problem? | No. A positive control (end-of-day continuation, t about 6) shows up clearly. Yahoo's missing extremes bias results only slightly | 22, 23, 28 |
| Can losers be separated before entry? | Yes, but only slightly: AUC 0.567 out of sample | 31 |
| A 1:3 fixed target? | No. 3R is rarely reached within the day | 29 |
| Trailing at the prior 5/15/30-min candle instead of the 1% target? | No. +0.021 / +0.045 / +0.067 vs +0.080 for the fixed target; the 5-min trail is stopped out by noise within a median of 15 min | 45 |
| Stock steadily below VWAP (at least 70% of 5-min closes) before entry? | Candidate filter: +0.104 vs +0.057, better in 3 of 4 months (exploratory) | 44 |
| VWAP breadth (large caps holding VWAP) to call Nifty's direction? | No. Correlation +0.06 with Nifty from 10:45 to 15:15 | 44 |
| Do shorts fail on bullish days? (Nifty green/red, 50-day SMA, regimes, 3 years incl. the 2024/25 up years) | No. Nifty green +0.112 vs red +0.109. In a Nifty uptrend (above the 50-day SMA) +0.102 vs downtrend +0.126 | 47, 49 |
| Same-day breadth (share of liquid stocks above yesterday's close) | Shorts are weakest when more than 65% of stocks are up: +0.05 vs +0.18 on bearish-breadth days, ordered in every year. **Does not hold with the 2:1 rule** (smaller sample) | 47 |
| Switch to longs on bullish days? | No. Longs on bullish days -0.021. Every switching rule (breadth or SMA) is worse than shorts-only | 48, 49 |
| Market internals at entry (advance/decline, up-volume, 30-min breadth), 5-min data | No consistent effect; 30-min breadth conflicts with Nifty's own 30-min move | 46 |
| Why shorts and not longs? | Theory with peer-reviewed support: market gains come overnight and fade during the session (Berkman et al. 2012; Lou, Polk & Skouras 2019; Zerodha's Nifty data); individual traders are long-biased, dip buyers (Barber & Odean 2008). Swing longs held overnight do work: +0.171% vs shorts 0.000% on the daily version | (research) |
| His SWING 1H scanner as a trade (52) | Shorts on a red candle with 2:1: +0.091% (every year +), 3.7/day. Longs negative | 52 |
| His RSI reversal scanner as a trade (53) | Shorts with 2:1: RSI>80 +0.102% (0.3/day), RSI>70 +0.093% (2.3/day). Longs ~0 | 53 |
| Combined, one trade/day (34-EMA + SWING + RSI shorts, 2:1) | 96% of days with a trade, +0.112%; 34-EMA alone 59% of days +0.124%; SWING alone 83% +0.120% | (inline, 2026-10-02) |
| His 15m VOLUME STRATEGY sell (54) | All setups with 2:1 +0.085% (ours +0.074% same months); one/day -0.037% vs ours +0.095%. Not adopted | 54 |
| Shorts-only intraday, longs multi-day? | Supported as a strong default for these setups (overnight/intraday research + our data in up and down years), not a law | (research) |
| Daily range filter (ATR >= 2.56% of price) | ADOPTED: low-range stocks ~0 in both sets; 30m +0.089 -> +0.129%, 1H +0.069 -> +0.102% | (2026-10-03) |
| 1H 8-EMA under the short (user's chart read: RAILTEL, AARTIIND, GOLDIAM) | Not a rule. Tested 4 ways, none passes both sets: distance gradient (62); placebo support test -- lows stop at the 8-EMA no more than chance, 26.4% vs 24.1% / 22.3% vs 23.6% (63); "rising 8-EMA reaches my 1% zone" -- with the fresh EMA it is already there in 98-99% of trades (65); 8-EMA holding vs rejecting in the last 2/3/4 hours -- holding is average, REJECTING is best on 30m (Rs184-200 vs Rs129, 51% stopped vs 57%) but mixed on 3-yr 1H (66). A pick ranking by 8-EMA position lost on 1H (Rs90 vs Rs117/trade, script inline). RAILTEL was a 09:15 spike, not a support bounce | 62-66 |
| Breadth at entry (clean data) | Inconsistent: 3-yr bullish days weakest on average, Jun-Sep 2026 bullish days best -> info only | 61 |
| Full hourly bar at the hour-close alarms (11:15 / 12:15) | Adopted. All setups flat (+0.128%); plan 11:15-else-11:45 +0.120 -> +0.171%, stops 58.5 -> 54.7%; 11:15 alone worse, 12:15 better | 68 |
| Strong green hour before, shallow pullback | Adopted as a skip at 11:45 / 12:15 only (after the 10:15 bar); after the 09:15 opening bar those setups are fine. Skipping 'any green' or 'any green above EMA' throws away the best group (deep pullback = failed reclaim) | 70 |
| Stop-rate filters (noise ratio, close position, candle shape) | Closed: they only pick wider stops; stop width doesn't change profit within the 2:1 band | 67 |
| Pivots on the current rules (daily / weekly / monthly: support in path, pivot at the stop, side of PP) | Closed as filters: daily and weekly flip between sets; above monthly PP is better in both but cuts total profit and is not significant on 30m | 72 |
| Skip only if a pivot blocks the target AND the market is up at the alarm (script 73) | Closed: headline points the wrong way in both sets; no version passes both | 73 |
| Daily 8-EMA above our stop (script 74) | Closed: 30m better, 1H worse | 74 |
| Allow EMA8 > EMA34 when the EMA8 is rolling over (T2) | Closed: below average on 1H, hurts the 1H plan | 75 |
| The channel's own calls by side | 68% longs; longs +0.031% vs shorts +0.002% at target 1; the edge is counter-trend on both sides; most calls match none of his public scanners | 50 |

---

## 4. Closed: don't re-test without a new reason

- The long side of this setup.
- ADX above 25 as a filter. ADX of 25 or below helps slightly.
- Nifty-direction entry filters: since-open move, 15/30/60-minute move, 1H trend, pivots, regime.
- Pivot (R1/S1) room as a filter. A sector filter (unstable from quarter to quarter).
- RSI, RVOL, relative strength vs Nifty.
- Entering at the touch, at the EMA cross, or at the first 5-minute close.
- A limit order at the EMA. The EMA as the stop. Fixed 1:3 / 1:4 targets.
- The full 30m-EMA / 4H-EMA structure. The 10:15 30-minute alarm. Alarms from 13:15 on.
- Prior-candle trailing stops for manual trading (5 / 15 / 30 min). VWAP breadth as a Nifty-bias call.
- Daily-chart or 1H-chart entries with a ~1% target and no extra filters (about 0 gross).
- (2026-10-04, scripts 67-71) **Stop-rate filters:** "stop inside the noise" (stop / typical candle range >= 1; the 2:1 cap
  makes this nearly impossible) and "close in the bottom third of the candle" -- both only select wider stops; with a
  fixed 1% target, tight stops get hit more but lose less, so ~56% stopped is built into the setup.
- Favouring the tightest stop as the one-trade pick (closest-to-EMA wins in both sets: 30m Rs+267 vs +204, 1H +117 vs +102).
- Candle shape (body-led / mixed / shooting star) as a rule: skip-mixed helped 30m, not 1H; shooting star best on 30m,
  worst on 1H. Not a rule.
- "Previous hour must close below the EMA" (true rejection only): no better; hurts one-trade-a-day on 1H (+117 -> +74).
- Strong-green-hour setups by Nifty regime (below 50-day avg): looked like a flip, but on 14 / 47 trades -- noise. The
  skip applies always, on logic.
- "Wait for the second signal on the same stock": later setups on the same stock the same day do worse than the first
  in both sets.
- (2026-10-04, script 72) **Pivots, re-tested on the current rules** (old test was on script 15's biased set): daily and
  weekly classic pivots -- S1/S2 in the target path, PP/R1/R2 at the stop (rejection at a pivot), entry above/below PP.
  None helps in both sets; P3, P5, P6 flip direction between 30m and 1H (e.g. above weekly PP: 30m Rs+218 vs +112,
  1H Rs+69 vs +116). Rejection at a pivot stops less (52.7 vs 55.9% / 51.8 vs 57.3%) but reaches the target less too:
  Rs109 vs 159 (30m), 105 vs 110 (1H). Not a quality label. Chart context only.
  Monthly pivots (TradingView Auto shows them on the daily chart; weekly on 1H): entry above last month's PP is better
  in both sets, every month/year (30m Rs159 vs 121, 1H 169 vs 85) but NOT a filter: 30m shuffle p=0.26, 1H p=0.005
  (within-day shuffle p=0.09); keeping only those trades cuts days traded to 52-62% and total profit (30m plan
  Rs11.3k -> 6.5k, 1H Rs57k -> 40k); preferring them as the pick is worse. Candidate quality label for the
  quality x market test only.
- (2026-10-04, script 73) **"Pivot in the way of the target AND market not helping -> skip"** (user's rule; trade by
  default). Obstacle = any weekly (headline) / daily / monthly pivot between entry and the 1% target; market up = Nifty
  above its open (M1) or breadth > 50% (M2) at the alarm. Headline (weekly x Nifty) points the WRONG way in both sets:
  obstacle + market up is the BEST cell on 30m (Rs+330, n=44) and average on 1H (+103, vs obstacle + market down +46).
  Weekly x breadth helps 1H (removed +72 vs kept +114) but not 30m (removed +194). No version passes both sets.
  Likely reason: the market's state AT the alarm doesn't tell you what it does DURING the trade (same as the closed
  Nifty-direction tests).
- (2026-10-04, chart review, inline on obstacle_x_market.csv) **Trigger-candle shape, user's chart reads:** opened above
  the EMA34 (body cross) is NOT worse (30m Rs129 vs 131, 1H 118 vs 94) -- keep body crosses. Major lower wick (> 1/3 of
  range) = more stops in both sets (59 vs 51%, 59 vs 50%) but Rs gap small and months/years disagree (30m: lower-wick
  better in Jun/Aug/Sep). Low pierced the 1H EMA8 and closed above (8-EMA support): no (30m +136 vs +128, 1H +77 vs
  +115). No upper wick looked better in both (+180 vs +119, +159 vs +99) but not every month/year -- watch, not a rule.
- (2026-10-04, script 74) **Live daily 8-EMA sitting above our stop** (user: RELIGARE 24 Aug, VERANDA 19 Sep 2025 rose to
  touch it, took the stop, then fell hard): 30m better (Rs145 vs 109), 1H worse (85 vs 129; 2024/25 worse, 2026 better)
  -> no rule. "Stopped, then fell 1% from entry later that day" is 5-6% of trades whether or not the daily 8-EMA is
  above the stop -- that's the bad-luck share, not explained by the daily 8-EMA.
  Lower-wick sweep (inline): candle closing AT its low lost in both sets (30m n=32 Rs-103, 1H n=70 Rs-32, shuffle
  p 0.007/0.02) but 0-10% wick is the best bucket -> cliff at zero with no logic; watch item, not a rule. Not a cheap-
  stock / tiny-candle artifact (still worse inside every price and candle-range bucket). Effect on the one-a-day plan is
  tiny (30m Rs179 -> 183, 1H 117 -> 123; 1-6 picks change) because the closest-to-EMA pick is rarely one of them.
- (2026-10-04, script 75) **T2 "rolling over after a top"** (EMA8 still above EMA34 but falling 3 hours, SUNDARMFIN 19
  Aug type): 30m Rs126 vs 130 (Sep -38), 1H Rs74 vs 107 (2025 +7); adding it to the plan: 30m +179 -> +186, 1H +117 ->
  +101. Closed: the trend rule stays as is.
- Dropping the 2:1 rule: more trades, fewer stops, less per trade (30m +0.128 -> +0.083%, 1H +0.102 -> +0.090%). Keep 2:1.

---

## 5. Open ideas / next steps

1. **Live log for a few weeks:** run both the 30-min and the 1H versions side by side, plus your own trades
   and the channel's calls. Switch to the 30-min version only if it holds up live.
2. **Your daily bias:** write it down before 10:15 each day, and after 1-2 months test whether it beats 50%.
3. **Real costs:** measure brokerage and slippage from your actual fills.
4. **More 5-minute data:** `intraday_cache` keeps growing. Re-run scripts 41 and 43 monthly to re-check the
   30-min version on new months.
5. **Daily swing version** (heavy candle + weekly 8-EMA touch + ADX above 25, about +0.9%/trade in 2022-26):
   the strongest older lead. It needs a robustness check (neighbouring thresholds, costs, concurrency).
6. **Breadth caution (watch, not a rule yet):** skip shorts when more than 65% of liquid stocks are above yesterday's
   close at the alarm. It held in all 3 years in the base 1H set, but not in the 2:1-rule set. Show breadth in the
   scan output and let the live log decide.
6b. Leads, not findings: gap-up of more than 0.5% leading to a Nifty up-drift (t 2.7, n=73); stock-level
   end-of-day continuation (+0.065%/day, too small for costs alone).
7. A longer intraday Nifty history (from the broker) would make it possible to test Nifty-direction ideas properly.
7b. **Folder cleanup (someday):** 50 numbered scripts are the research trail; only 38, 51 (+11, 43) and 15 are live.
   Deleting them won't remove them from git history; a real cleanup means a deliberate history rewrite or an archive move
   (scripts read each other's outputs from this folder, so paths need fixing). Held local, not committed (public repo):
   TELEGRAM_CALLS.md, SOURCE_TRANSCRIPT.md, CHARTINK_QUERIES.md, OPEN_QUESTIONS.md, the chartink JSON.
8a. **DONE 2026-10-04 (closed, see section 4).** Lower the stop rate (user, 2026-10-03): ~56% of trades stop out (67% in the 17 Sep - 1 Oct practice list; stops cluster by day, e.g. 18 Sep 10/10 stopped; 14 of 38 stops hit within 30 min). Two pre-declared filters to test, both sets, with baseline + kept + removed: (a) stop inside the noise -- stop distance vs the stock's typical 30-min candle range, cut-off 1.0; (b) rejection strength -- where the 30-min candle closed within its range (bottom half / bottom third). Goal: fewer stops without lowering profit per trade.
8b. **Telemetry to add to the live log:** 1H 8-EMA rejecting / holding in the last 3 hours (script 66), to re-test on fresh trades.
8d. **Watch in the live log:** volume of the pullback bar vs the green bar before it (break-and-retest literature: low-volume pullback = pause, heavy = real rejection) -- untested.
8e. **Watch in the live log (2026-10-04 chart review, not rules):** (i) "big red box" trigger candle with no upper wick
   looked better in both sets (30m Rs180 vs 119, 1H 159 vs 99) but not every month/year; (ii) trigger candle closing
   exactly at its low looked worse in both sets (shuffle p 0.007 / 0.02, holds inside price and range buckets) but has
   no logic for why 0% is bad and 5% is the best bucket, and barely changes the one-a-day pick -> yellow flag only;
   (iii) the user's discretionary skips ("looks like support") -- log the reason, compare after 1-2 months.
   **Chart-reading trap:** TradingView/Dhan label candles by START time; the 12:15 alarm judges the candle labeled 11:15.
8c. **Loose ends:** (i) RECONCILED 2026-10-04: Rs+120 = plan '11:15 else 11:45' (65 days); Rs+267 = 'first alarm from 10:45'; different plans, not a bug; (ii) the 1H 34-EMA used for the 11:15 and 12:15 alarms is one hour older than the broker chart (backtest and scan agree; fixing means re-running the main backtest); (iii) Yahoo's real 60m history limit (a 730d request returned data from 2023-10).
8. **When automating, revisit:** (a) half the position at 1% with the rest trailed on 30-min candles (untested);
   (b) the "steadily below VWAP" filter (script 44) using the research's definition: at least 10 of the last 12
   5-min closes below VWAP, at most 1 cross, VWAP falling, with 6- and 24-candle versions as checks.

---

## 6. File index (intradaygeeks_replica/)

| File | What |
|---|---|
| `38_alarm_scan_1h_close.py` | Live / replay alarm scan (half-hour check at 10:45 / 11:45, full hour at 11:15 / 12:15, strong-green-hour skip) |
| `69_snapshot.py` | The 1H chart as it looked at an alarm, text + inline iTerm2 image (`python3 69_snapshot.py KNACK 2026-09-30 11:15`, `--save` for a PNG) |
| `21_live_bearish_scan.py` | Older 5-min held-rejection scan (superseded) |
| `15_intraday_1h34_daily8.py` | 3-year 1H backtest engine |
| `41_confirmation_length.py`, `43_alarm_times_30m.py` | 30-min trigger tests and alarm timing |
| `live_watch_log.csv`, `channel_calls_live.csv` | Live trade log, graded channel calls |
| `h1_cache/`, `index_1h/` | Symlinks (2026-10-03) to `../data/intraday_60m/` and `../data/index_intraday/`: Yahoo 1H stock and index history. Fetchers: `../data/fetch_intraday_60m.py`, `../data/fetch_index_intraday.py`. See `../data/README.md` |
| `TELEGRAM_CALLS.md` | Full research log |
| `INTRADAY_RESEARCH.md` | Literature and cue research |
