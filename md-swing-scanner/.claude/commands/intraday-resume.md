---
allowed-tools: Bash(git log:*), Bash(git status:*), Bash(git diff:*), Bash(cat:*), Bash(tail:*), Bash(head:*), Bash(ls:*), Bash(date:*), Read, Grep
description: Resume the intraday shorts system (intradaygeeks_replica/) in a fresh session — live state first (data freshness, next alarm, latest scan, live log), then current rules and where research left off
---

## Your task

Reconstruct the current state of the **intraday shorts system** in
`/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/intradaygeeks_replica/` before responding to anything
else the user says this session. Do the reads below quietly — don't narrate each file — then give ONE consolidated
orientation summary.

Scope: this skill is for the intraday 1H 34-EMA rejection shorts (live since 2026-10-05). Primed BC, the live swing
system, has its own skill (`/swing-resume`); `short_discovery/` and `pre_breach/` are separate research threads.
Mention them only if git shows uncommitted work there.

Data: all base market data lives under the root `data/` folder, documented in `data/README.md`, with locations in
`data/paths.py`. The scan reads the 5-minute cache (`data/intraday_5m/`) and the daily cache (`data/daily/`). Both
are refreshed by the shared end-of-day run, `eod_checklist.sh`.

### Step 1: Read the memory

- `/Users/mdubey/.claude/projects/-Users-mdubey-workspace-personal-my-utilities/memory/intraday_shorts_project.md`
  in full.
- In `md_swing_scanner_project.md` (same folder), only the entries mentioning `intradaygeeks`. Grep for them and
  read the most recent few. They are history; STRATEGY.md is the current truth.

### Step 2: Read the strategy doc

Read `intradaygeeks_replica/STRATEGY.md` in full. It is the living source of truth:
- section 1: current rules;
- section 2: how to run;
- section 3: what the tests showed;
- section 4: closed, don't re-test;
- section 5: open ideas, including 8a stop-rate filters, 8b telemetry and 8c loose ends.

### Step 3: Check the live state

- `date`: the IST time now, and whether it's an NSE trading day.
- Data freshness: the last date in `data/daily/_NIFTY.csv` and the last 5-min bar in one liquid stock's file in
  `data/intraday_5m/` (e.g. `RELIANCE.csv`, timestamps are UTC; add 5:30 for IST). If either is older than the last
  NSE trading day, the end-of-day run hasn't been done, and the scan will exclude stale stocks.
- `live_watch_log.csv`: all rows. These are real trades and observations; treat them as live data.
- The most recent `alarm_scan_30m_*.csv` files (`ls -t | head`): what the last alarms found.
- `prep/`: whether today's `prep_YYYYMMDD.csv` exists.

### Step 4: Check git state

From the repo root: `git log --oneline -5 -- intradaygeeks_replica data`, then `git status --short intradaygeeks_replica data`.
Remember the repo is PUBLIC. TELEGRAM_CALLS.md, SOURCE_TRANSCRIPT.md, CHARTINK_QUERIES.md, OPEN_QUESTIONS.md and the
chartink JSON must stay uncommitted.

### Step 5: Give ONE consolidated orientation summary, then stop

Structure it as:
- **Live status**, one line each:
  - data freshness (daily and 5-min);
  - the next step due from the trading-day playbook below (plan B: the 10:45 signal taken when standup ends, else
    11:15, else 11:45, one trade a day; never the 10:15 alarm; 12:15 not traded), or `./eod_checklist.sh` after the close;
  - the last scan result;
  - the live log so far: trades, results.
- **Current rules**: a 2-3 line recap of STRATEGY.md section 1.
- **Last closed/decided**: the most recent conclusion, with its exact numbers.
- **Open items**: quote STRATEGY.md section 5's exact wording for the next research step and the loose ends.
- **Uncommitted work / loose ends** from git and memory.

Do NOT start new research, write code, or change anything yet. If the user's first message already says what they
want, fold this orientation into answering it directly. On a trading day, end the summary with the playbook step that
is due now (below) and offer to run it -- the user does not run commands; they ask you to.

### Trading-day playbook (the user asks, you run; plan B adopted 2026-10-04 = one trade a day: the 10:45 signal when standup ends, else 11:15, else 11:45)

The user's day: free 10:15-10:20, standup ~10:20-10:50. Plan B on the 30m backtest (STRATEGY section 1 plan table):
target / stall / stop 40 / 13 / 47, net ~Rs+220 per trade vs Rs+94 for the old 11:15-first plan. The sooner after
10:45 the scan runs, the better (10:50 best; 11:00 still good).

All commands from `intradaygeeks_replica/`. Times IST.

| When | Run | Notes |
|---|---|---|
| 10:15-10:20 (user free), or any time before standup | `python3 38_alarm_scan_1h_close.py --prep` | builds today's candidate list; also flags STALE data (then the EOD run was missed). NEVER trade the 10:15 alarm (script 87: opening noise, turns the plan negative) |
| as soon as standup ends (~10:50, by 11:05: the scan drops the 10:45 candle 20 min after it closes) | `python3 38_alarm_scan_1h_close.py` | judges the 10:45 candle (10:15-10:45 half-hour). ENTER = short now at market. SKIP / DEAD = no 10:45 trade, wait for 11:15. Do NOT rest a limit at the signal close (script 86: worse) |
| 11:16-11:20, only if no trade yet | `python3 38_alarm_scan_1h_close.py` | 11:15 check = the FULL 10:15-11:15 hourly bar, stop = hour high |
| 11:46-11:50, only if still no trade | `python3 38_alarm_scan_1h_close.py` | half-hour check; skips a shallow pullback after a strong green 10:15 hour (printed as "skipped, would otherwise qualify"). Last trade window of the day |
| after 15:30 | `./eod_checklist.sh` (from the repo root) | shared with Primed BC: Part A data + health check, Part B trading |
| after `eod_checklist.sh` | `python3 89_eod_review.py` | EOD REVIEW (continuous improvement): replays the day's alarms (10:50 / 11:16 / 11:46 / 12:16) and logs what EVERY setup would have done -- plan pick, ENTERs not taken, and each skip type (EMA8 zone, chased, dead, green hour, stop > 0.5%) -- to `eod_review_log.csv`, then prints the running summary by category. Report: the day's pick vs what the user actually did, then the summary. `--summary` = summary only. Replaces the manual EMA8-zone telemetry step |

- If the scan prints DATA NOT READY, Yahoo is lagging: wait a minute and run again.
- How to report a scan:
  - summary first: the FIRST COME pick (ticker, entry, stop, stop %, target) and its status;
  - then the full table;
  - then "no setups" plainly if empty.
- Status column: only ENTER is tradeable. DEAD = the stop was already touched. SKIP (2:1 gone) = the stop is now > 0.5%
  above the current price. SKIP (EMA8 0.4-0.6% below) = the user's hard rule (2026-10-04): the 1H EMA8 sits 0.4-0.6%
  under the candle close -- on all setups that zone lost in both data sets (more stops), so the user never takes it; the
  scan already passes FIRST COME to the next ENTER. Target = the user's fill minus 1%.
- TELEMETRY for every skip rule (EMA8 zone, chased, green hour, stop > 0.5%) is automatic: `89_eod_review.py` after the
  EOD run logs each skipped setup's would-be outcome in `eod_review_log.csv`. After ~20 cases per category, compare with
  the ENTERs and the plan picks; a rule is kept, changed or dropped on that live evidence.
- To check a setup on the chart, use `python3 69_snapshot.py TICKER YYYY-MM-DD HH:MM --text`. That's the hourly bars
  plus the checklist, as text. Never open image windows: the user is at work during market hours.
- Pick = FIRST COME (the scan marks it): the setup closest to the 1H EMA34 at the first alarm with an ENTER. Do not
  re-order by ATR, volatility, wick or candle shape (all tested worse or not robust).
- Being underwater soon after entry is normal: 73% of eventual target trades come back to the entry price first.
- After a trade:
  - ask the user for fill price/time and exit;
  - log the outcome as target / stall (out at 15:15 or 5h) / stop, plus the stock's daily ATR, so the live target-hit
    rate can be compared with the backtest (30m plan B: 40% target; 3-yr 1H: ~25%), plus the scan's ema8_below%;
  - append a row to `live_watch_log.csv` (same columns as the existing rows);
  - do not guess fills.
- Keep it simple. Lead with what to do, not statistics. The user is trading live.

Standing rules for this thread:
- Judge everything NET of charges (~Rs85 per Rs 1 lakh MIS round trip until real contract notes replace it).
- A filter is adopted only if it helps in BOTH the 30-min (Jun 2026 on) and the 3-year 1H datasets.
- Thresholds are declared before running.
- Always show baseline, kept and removed side by side, with each month or year.
- Show the user the tables; never "test, log and close" without showing them.
