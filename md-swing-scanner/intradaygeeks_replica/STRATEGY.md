# Intraday 34-EMA rejection (shorts): living strategy doc

Last updated: 2026-10-02 (IST), 34-EMA thread closed out (market-direction tests added). Scratch research only, nothing in production uses it.
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

**Trigger: a 30-minute rejection candle** on a 09:15-aligned grid, closing at **10:45, 11:15, 11:45 or 12:15**:
- the candle is red (close below open);
- its high touches or crosses the 1H 34-EMA;
- it closes back below the 1H 34-EMA, and no more than 0.5% below it.

**Checks at the moment of entry:**
- close below the daily 8-EMA;
- the day's high so far has pierced the live daily 8-EMA;
- daily ADX(14) as of yesterday is 25 or below;
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
- One trade at a time, one a day preferred: take the first setup you see. If several show up at once,
  take the one closest to the EMA.

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
and it was the best of several variants tested.

**Fallback version with 3 years of evidence (1H trigger):** the same rules, but with the 1H candle close
as the trigger, at 11:15 and 12:15. With the 2:1 rule and one trade a day it averaged +0.106%
(+0.117% on the unseen Jul 2025 - Sep 2026 period), with a trade on about 59% of days.

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

- The fetch takes a minute or two, so start it a couple of minutes after the alarm time.
- Each run saves `alarm_scan_[30m_]YYYYMMDD_HHMM.csv`.
- **Breadth telemetry** (not a filter): each run prints the share of liquid stocks above yesterday's close. Above 65%
  it says "BULLISH breadth -> be cautious with shorts". The value is also saved in the CSV.
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
8. **When automating, revisit:** (a) half the position at 1% with the rest trailed on 30-min candles (untested);
   (b) the "steadily below VWAP" filter (script 44) using the research's definition: at least 10 of the last 12
   5-min closes below VWAP, at most 1 cross, VWAP falling, with 6- and 24-candle versions as checks.

---

## 6. File index (intradaygeeks_replica/)

| File | What |
|---|---|
| `38_alarm_scan_1h_close.py` | Live / replay alarm scan (default: 30-min trigger) |
| `21_live_bearish_scan.py` | Older 5-min held-rejection scan (superseded) |
| `15_intraday_1h34_daily8.py` | 3-year 1H backtest engine |
| `41_confirmation_length.py`, `43_alarm_times_30m.py` | 30-min trigger tests and alarm timing |
| `live_watch_log.csv`, `channel_calls_live.csv` | Live trade log, graded channel calls |
| `h1_cache/`, `index_1h/` | Yahoo 1H stock and index history |
| `TELEGRAM_CALLS.md` | Full research log |
| `INTRADAY_RESEARCH.md` | Literature and cue research |
