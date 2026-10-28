---
allowed-tools: Bash(git log:*), Bash(git status:*), Bash(git diff:*), Bash(cat:*), Bash(tail:*), Bash(head:*), Bash(ls:*), Bash(date:*), Read, Grep
description: Resume the intraday shorts system (intradaygeeks_replica/) in a fresh session -- live state first (data freshness, the next scan due, the live log), then the current rules and where research left off
---

## Your task

Reconstruct the current state of the **intraday shorts system** in
`/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/intradaygeeks_replica/` before responding to anything
else the user says this session. Do the reads below quietly (don't narrate each file), then give ONE consolidated
orientation summary.

Scope (updated 2026-10-18; trade count updated 2026-10-28): the user trades TWO intraday short setups, judged trade by trade
(no one-trade-a-day rule; flag overtrading only from ~5 trades in a day):
1. **Morning fade** on the 09:21 ORB in-play list, 09:20-09:40, discretionary (the user reads the chart and enters inside
   the bar). The ORB sell-stop breakout itself is NOT traded (too luck-dependent; its edge sits in the 09:20 bar).
2. **Hourly 34 rejection** (the user's name; formerly "v1"): short when the 10:15 hourly candle touches the 1H EMA34 and
   closes red under it -- entered by eye inside the hour from a 10:15 watch list, else at the 11:15 scan.
Primed BC (swing) has its own skill (`/swing-resume`); `short_discovery/`, `pre_breach/`, `telegram_swing_check/` are
separate threads -- mention them only if git shows uncommitted work there.

Data: all base market data lives under the root `data/` folder (`data/README.md`, `data/paths.py`): 5-minute cache
`data/intraday_5m/`, 60-minute `data/intraday_60m/` (= `intradaygeeks_replica/h1_cache`), daily `data/daily/`, index
intraday `data/index_intraday/`. All refreshed by the shared end-of-day run `eod_checklist.sh` (repo root).

### Step 1: Read the memory

- `/Users/mdubey/.claude/projects/-Users-mdubey-workspace-personal-my-utilities/memory/intraday_shorts_project.md`
  in full (the latest entries at the bottom are the current state).
- `feedback_discuss_before_recording.md`, `feedback_results_only_user_decides.md`, `feedback_explain_plan_before_running.md`,
  `feedback_log_discussed_fills.md`, `user_intraday_entry_style.md` in the same folder.

### Step 2: Read the strategy doc

`intradaygeeks_replica/STRATEGY.md` is the source of truth. Read in particular:
- **8k0** (search "HOURLY 34 REJECTION") = the current hourly rules, adopted 2026-10-18;
- **"Discretionary reads checklist"** and the **stop management hard rule** in section 2;
- **"Daily 8 cases at the v1 entry"** (the user's two variations to watch);
- the result rows dated 2026-10-15..18 in section 3 (rows marked SUPERSEDED are wrong -- don't cite them).

### Step 3: Check the live state

- `date`: IST now, and whether it is an NSE trading day.
- Data freshness: the last date in `data/daily/_NIFTY.csv` and the last 5-min bar in `data/intraday_5m/RELIANCE.csv`
  (UTC; add 5:30). If older than the last NSE session, the EOD run was missed.
- `live_watch_log.csv`: all rows (ONE merged log since 2026-10-16; real trades + observations, `traits` / `taken` columns).
- Latest scans: `ls -t orb_scans/ | head -3` and `ls -t v1_scans/ | head -3`; today's prep files in `prep/`
  (`orb_prep_YYYYMMDD.csv`, `v1_prep4_YYYYMMDD.csv`).

### Step 4: Check git state

From the repo root: `git log --oneline -5 -- intradaygeeks_replica data`, then `git status --short intradaygeeks_replica data`.
The repo is PUBLIC: TELEGRAM_CALLS.md, SOURCE_TRANSCRIPT.md, CHARTINK_QUERIES.md, OPEN_QUESTIONS.md and the chartink JSON
stay uncommitted. `116_refinements_plain_touch.py` is an unresolved stray (commit or delete -- ask).

### Step 5: ONE consolidated orientation summary, then stop

- **Live status**, one line each: data freshness; the next step due from the playbook below; the last scan; the live log
  (recent trades and results).
- **Current rules**: 2-3 lines for each setup (below).
- **Open items** from memory / STRATEGY (the parked ideas list at the end of this file).
- **Uncommitted work / loose ends.**
Do NOT start research, write code or change anything yet. On a trading day end with the step due now and offer to run it
-- the user does not run commands; they ask you to.

### Trading-day playbook (the user asks, you run; all commands from `intradaygeeks_replica/`, times IST)

| When | Run | What it gives |
|---|---|---|
| before 09:15 (optional) | `python3 185_orb_inplay_scan.py --prep` | builds the ORB universe; flags STALE data |
| 09:21-09:23 | `python3 185_orb_inplay_scan.py` | the top-20 in-play list + the **FADE LEVELS** table (09:15 O/H/L/C, the nearest 4 levels above the price: 09:15 high, R1, R2, daily 8, yesterday's high / close, STACK flag for two within 0.3%, targets = 09:15 close then 09:15 low for red 09:15 candles). The user scans it by eye; do NOT offer to re-fetch bars at 09:30 -- too slow for a 10-minute trade. The ORB "ARM" picks are info only |
| 10:15-10:20 | `python3 254_1015_watch.py watch` | hourly 34 rejection watch list: liquid, >= Rs100, ATR >= 3%, the 09:15 hour closed at / up to 0.5% under the 1H EMA34 (set up to test the line from below) |
| 10:40-10:45 (when the user asks) | `python3 254_1015_watch.py status` | only the REJECTIONS FORMING (the high went through the line, price back under), with pierce, wicks, a reference stop, the daily-8-in-path flag; the rest counted and dropped |
| 11:16-11:20 (if no trade yet) | `python3 203_v1_scan.py` | (1) normal setups: stop <= 0.5%, pick = highest ATR, 1% target, pierce + vs_nifty telemetry; (2) CLEAN REJECTIONS at any stop (pierce_ok YES = pierce > 0.5% is the one that worked; smallest stop first; 1.5% target; INFO, not a tested rule); (3) "how to read" notes. Nifty below its 200d = bear-phase LIVE TRIAL (setups still tradeable, small rupee risk). `--early` = provisional read before 11:15; `--v1old` = the old rules |
| after 15:30 | `./eod_checklist.sh` (repo root) | data refresh + health check, then Primed BC |

**Report every scan as markdown tables in chat -- never paste raw terminal output.** Summary line first, then the table(s).

**Morning fade cue rules** (the user's own, 2026-10-18 -- discretionary, not backtested):
- with a known level: price reaching it and turning down counts, even mid-bar; two levels stacked = stronger; the daily 8 /
  yesterday's high are the strongest, the 09:15 high alone the weakest (first touches break ~56-60%);
- with no level: a doji / stall at the high, then a bar that is red from its open (no new high first) -- the RBLBANK type;
- never fade a push made of full green 5-min bars (momentum -- PINELABS / WIPRO type); skip if there is no room to the target;
- targets: the 09:15 close (reached ~64% of the time, ~10 min), then the 09:15 low (~46%, ~30 min) on red 09:15 candles;
- stop above the push / spike high, rounded a little beyond; on a gap-down stock yesterday's close above is a magnet.

**Hourly 34 rejection rules** (STRATEGY 8k0): liquid (>= Rs15 lakh / 5-min bar), price >= Rs100, daily ATR >= 3%, any
trend (shown, not filtered); 10:15 candle red, touched the 1H EMA34, closed under it; skip a doji cut by the line; skip when
the daily 8 touch sits between the entry and the 1% target; stop = candle high (or the earlier wick if that still fits in
0.5%), only if <= 0.5%; 1% target, out by 15:15; **trail rule (hard):** at the hour close, if the candle is a confirmed red
rejection and its high + 0.05% is below the stop, move the stop there. Prefer likely-clean rejections (from the 10:15 list).

After a trade: log it in `live_watch_log.csv` from what the user said in chat, marked "as discussed" -- never ask for broker
fills, never record quantity; ask only for what is missing (entry / stop / exit / time). Fill `traits` / `taken`.

Standing rules:
- Judge everything net of ~Rs85 per Rs1 lakh; report win-rate with R / drawdown / streak, per Rs1k risk when stops differ.
- New tests: plain-words spec and thresholds BEFORE running, then the user's go-ahead. Results go to chat as tables; nothing is
  written into STRATEGY.md until it has been hand-checked and discussed with the user (`feedback_discuss_before_recording`).
- Filters must have a chart logic; data-only filters are dropped (2026-10-18 cleanup). Results only -- the user decides.
- Chart packs: date, ticker, entry, stop, 1H EMA34, daily 8 and daily 34 vs entry, outcome -- no clutter (no candle OHLC
  unless asked, no Nifty / gap columns); warn when a split / bonus / demerger makes TradingView prices differ.
- The user's TradingView / Dhan feed can differ from Yahoo; prefer the user's chart numbers.
- Don't suggest a 09:20 order clock. Don't over-read short replies; confirm actions before logging them.

Parked ideas (don't start unprompted): trail test (+1% -> break-even / lock +0.5% / trail 0.5%); hold-to-close vs 1% target on
the normal setups; the 0.2% stop buffer (max 0.7%) -- user leaned yes, not built; the 1H EMA8-above-the-candle lead; the user's
two daily-8 variations; "stacked" levels checked properly (two levels within 0.3%, not one bar crossing several);
CMSINFO-type (green 09:15 shoot-and-reject, short the 10:15 retest) -- ignored by the user.
