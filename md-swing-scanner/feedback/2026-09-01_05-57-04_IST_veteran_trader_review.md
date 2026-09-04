# Veteran Trader Feedback

Scope: discretionary trading-system review, not a new backtest. I read the project
docs, `FINDINGS.md`, and the source paths for stock signals, exits, daily scanning,
options translation, portfolio simulation, and tests.

Standing write rule: future feedback from me should live only in this `feedback/`
folder, as timestamped files.

## Bottom Line

This is much better than a normal retail scanner. The architecture has several
professional instincts: stock edge is separated from options translation, live scan
logic reuses the backtest logic, VCP is modeled as a real base/trend-template setup,
and the project already guards against some common data and lookahead mistakes.

I would still not put normal-size money on it yet.

For stock swings, I would allow only a small pilot after validating live fills. For
options, I would not trade real size until costs, bid-ask/slippage, exercise/STT,
and contract liquidity are explicitly modeled.

Assuming the regime gate eventually opens: that is necessary, not sufficient. The
main unresolved question is whether the trades you can actually execute resemble the
backtest trades closely enough.

## What Is Good

- Separation of concerns is strong: `backtest.py` validates the stock signal, while
  `option_backtest.py` and `portfolio.py` translate it into derivatives mechanics.
- `detect_entry()` and `check_exit()` are shared by backtest, daily scan, and monitor
  flows. This is the right way to avoid live/backtest drift.
- VCP is treated like an actual trader pattern: Stage-2 trend, relative strength,
  multi-leg contraction, breakout volume, and structural stop.
- The regime gate is conceptually sound. Nifty ADX plus Nifty above 200-SMA is a
  defensible "do not fight the tape" filter.
- The project uses median, concentration, split-half checks, and marginal-trade
  quality. That is much better than trusting average return alone.
- The fetch layer has practical safeguards around unsettled same-day Yahoo closes.
  That kind of detail matters in real scanner work.
- Daily scan now marks F&O eligibility. Good stock signals and optionable stock
  signals are not the same universe.
- The tests cover important behavior in pivots, signals, VCP, regime lookup, exits,
  and price-fetching edge cases.

## Money Readiness

My real-money answer:

- Stocks: paper trade immediately; tiny live pilot is acceptable only with strict
  risk caps and journaling.
- Options: research-only for now. Do not deploy real options capital from the current
  numbers alone.
- Never trade `--ignore-regime` output. It is correctly observation-only.
- Treat the first signals after a long regime drought with caution. Reopen phases
  often produce whippy breakouts before leadership is durable.

Pilot sizing I would use: 0.25R to 0.50R of intended normal risk for at least 20-30
live stock signals, comparing actual fills, drawdown, exits, and skipped trades
against the model.

## Hard Blocks Before Serious Capital

### 1. Same-Close Entry Bias

The daily workflow runs after market close, but the backtest enters at the signal
day close. That fill is unavailable if the signal is discovered after close.

For breakout systems this is not a small detail. Next-day open can include the full
gap, spread, first shakeout, or failed continuation.

This is the top item to validate:

- signal at close, enter next open;
- signal at close, enter next-day VWAP proxy if available;
- live 14:45 scan, enter near close;
- skip if next open gaps too far beyond signal close by percent or ATR.

Until this is known, the headline win rate and median are not live-tradable numbers.

### 2. Survivorship Bias

The backtest appears to use the current NIFTY 500 list across the full 2021-2026
period. That creates survivorship bias. Removed, merged, delisted, or badly damaged
stocks are likely absent from older years.

Momentum systems are especially sensitive to this because today's index members are
tilted toward past survivors. This does not kill the project, but it means the
historical stats are probably cleaner than the live opportunity set was.

### 3. Options Execution Is Too Clean

`option_backtest.py` accepts an option row as liquid when open interest is positive
and traded volume is positive. That proves the close is not completely stale; it
does not prove you could enter or exit at that price.

For stock options, this is a major issue. Some contracts print once and then vanish.
The bhavcopy close can be far away from executable bid/ask.

Minimum upgrades before trusting options:

- minimum contracts traded in lots;
- minimum premium turnover;
- minimum open interest in lots;
- no single-print contracts;
- slippage by liquidity bucket;
- exit-before-expiry rule or full exercise-cost model.

I checked current NSE public charge references because this is a real-money issue.
NSE pages updated in April 2026 list STT on sale of an option in securities at 0.15%
and STT on exercised options at 0.15% on intrinsic value. They also list stamp duty
for equity options at 0.003% payable by the buyer and GST on broker services. These
costs are not modeled in the project.

References:

- https://www.nseindia.com/static/products-services/equity-derivatives-securities-transaction-tax
- https://www.nseindia.com/static/invest/first-time-investor-sebi-turnover-fees-stt-other-levies

### 4. No Walk-Forward Proof

The project is honest that parameters were tuned and evaluated on the same broad
window. Split-half checks help, but they are not a replacement for walk-forward.

Required validation:

- train through 2023, test 2024 untouched;
- train through 2024, test 2025 untouched;
- train through 2025, test 2026 untouched;
- no retuning inside the test year.

## Likely Overfitting Or Fragility

- `VOL_ZSCORE_WINDOW=8` is plausible, but exact. Treat it as "short adaptive volume
  window helped", not "8 is the true number".
- `LAST_LEG_TOLERANCE=0.40` is trader-sensible, but still in-sample tuned. The robust
  idea is "some slack helps".
- The stack of thresholds in `signals.py` increases multiple-comparison risk:
  close near high, volume surge, breakout percent, RSI band, EMA persistence,
  traded value, and 20-day momentum.
- Daily pivots may improve stats by exiting faster. That can be real, but it can
  also cap the biggest trend winners.
- The climax exit fires too rarely to justify much complexity as a hard rule.
- Portfolio-level option results are fragile because a fixed three-slot scheduler
  can admit or reject unrelated later trades after one earlier date changes.
- The Dec 2024 to May 2025 VCP losing patch remains an important unresolved regime.

## R:R And Money Left On The Table

The system is not yet an R-multiple system. `min_rr` defaults to zero, and most
evaluation is percent return, win rate, median, and concentration.

That is useful, but it does not answer whether the strategy earns enough per unit
of risk.

Add these reports:

- initial R: entry minus initial stop;
- realized R at exit;
- MFE in R;
- MAE in R;
- exit efficiency: realized profit divided by MFE;
- giveback before stop exits.

My trading read: full exits at daily pivot resistance probably leave money on the
table in the best trend leaders. They also probably improve hit rate and median.
Both can be true.

The veteran compromise to test:

- take partial profits at first daily pivot or 1R;
- move stop to breakeven or under 8/10/21 EMA after first profit;
- trail the rest with 21 EMA, prior two-day low, or ATR chandelier;
- force full resistance exit only if price closes weak or rejects from the level.

For options, faster profit-taking is more defensible because theta, spreads, and
liquidity decay are real. But even options need room for the occasional convex
winner; selling the entire position at the first pivot may blunt the best payoff.

## Swing-Specific Feedback

- Do not add many more broad filters yet. The stock engine is already filter-heavy.
- Separate gap-up exhaustion from intraday accumulation. A gap that opens high and
  closes flat is not the same as a stock that trends higher through the session.
- Add "extension from 21 EMA or ATR" as a diagnostic. Do not make it a hard gate
  until tested.
- For VCP, check minimum base age. The idea says multi-week base; the implementation
  may still accept compact structures if enough swings appear inside the lookback.
- Add a true volume dry-up check near the pivot. Last-leg average volume falling is
  useful, but the quiet final few days often matter more.
- Track sector leadership. A breakout in a leading group deserves more trust than
  an isolated stock in a weak group.
- Add earnings/event proximity as an annotation at least. For options, this is not
  optional.

## Options-Specific Feedback

- ITM plus next-month is a plausible current hypothesis, not a production rule yet.
- Fixed 5% ITM is not the same as targeting delta. Back out approximate IV and delta
  from premium, strike, spot, time, and rate if possible.
- Avoid holding into expiry unless STT/exercise handling is explicitly part of the
  tested edge.
- A stock stop is not an option risk stop. Slow stock drift can destroy option value
  before the stock stop triggers.
- Add a premium stop or time stop for options: candidates include -35% to -50%
  premium loss, or exit if the stock does not move in favor within 3-5 sessions.
- Use actual next tradable option prices if the stock signal is discovered after
  the close.

## What To Tune Next

Priority order:

1. Entry timing: same close vs next open vs live cutoff.
2. Options costs and slippage, including STT/exercise effects.
3. R-multiple, MFE, MAE, and exit-efficiency reports.
4. Full pivot exit vs partial profit plus runner.
5. Walk-forward validation by year.
6. Survivorship-bias audit using historical constituents or broader NSE history.
7. Breakout Continuation RSI ceiling in isolation: 68, 72, 75, 80.
8. Dec 2024 to May 2025 VCP losing patch by sector, breadth, volatility, and events.
9. Options liquidity thresholds beyond volume greater than zero and OI greater than zero.
10. Gap-up exhaustion filter separate from ordinary high-momentum breakouts.

## What Can Be Simplified

- Demote `climax` from hard exit to alert unless it proves value.
- Consider removing or softening `VOL_SURGE_MIN` if `VOL_ZSCORE_MIN` is the real
  volume confirmation.
- Treat `MOMENTUM_20D_MIN`, `EMA34_RISING_DAYS_MIN`, and `MIN_TRADED_VALUE` as
  candidate-list controls unless they prove edge in current v27 data.
- `oi_buildup_bullish()` is unused. Integrate and test it, or remove it from the
  mental model.
- `support_level()` and `min_rr` are present but inactive by default. Either make
  R:R first-class or stop thinking of the system as R:R-filtered.
- The Pine script is stale against v27: it still refers to v25 and weekly pivots.
  Do not use it for live order management until updated.
- `option_backtest.py` main still points to `runs/trades_v23_recent.csv`, while the
  docs discuss v27 options. That is a reproducibility footgun.
- `daily_scan.py` still has a `v25` warning in `--ignore-regime`; small but worth
  cleaning because stale labels cause trading mistakes.

## How I Would Use It

For stocks:

- trade only regime-approved signals;
- use actual executable fill, not assumed signal close;
- manually check gap behavior, nearby supply, earnings, and sector strength;
- size by R from the actual stop;
- journal every signal, skip, fill, stop move, and exit.

For options:

- trade only F&O names;
- start from ITM plus next-month as a hypothesis;
- reject thin contracts manually even if the script selects them;
- avoid expiry unless modeled;
- size by premium-at-risk, not stock percent risk.

## Final Read

The swing engine is close to pilot-ready. It is not yet proven production-ready.

The options layer is promising research, not live-money-ready.

The next improvement should not be another indicator. It should be making the
simulation behave like a real trader: attainable fills, real option costs, realistic
liquidity, R-multiple reporting, and clean out-of-sample validation.
