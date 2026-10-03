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
  - the next alarm due, with the command (`python3 38_alarm_scan_1h_close.py` from `intradaygeeks_replica/`, run
    1-2 minutes after 10:45 / 11:15 / 11:45 / 12:15 IST; the user's plan is 11:15 first, else 11:45, one trade a
    day), or `./eod_checklist.sh` after the close;
  - the last scan result;
  - the live log so far: trades, results.
- **Current rules**: a 2-3 line recap of STRATEGY.md section 1.
- **Last closed/decided**: the most recent conclusion, with its exact numbers.
- **Open items**: quote STRATEGY.md section 5's exact wording for the next research step and the loose ends.
- **Uncommitted work / loose ends** from git and memory.

Do NOT start new research, write code, run the scan, or change anything yet. Wait for the user's direction. If the
user's first message already says what they want, fold this orientation into answering it directly.

Standing rules for this thread:
- A filter is adopted only if it helps in BOTH the 30-min (Jun 2026 on) and the 3-year 1H datasets.
- Thresholds are declared before running.
- Always show baseline, kept and removed side by side, with each month or year.
- Show the user the tables; never "test, log and close" without showing them.
