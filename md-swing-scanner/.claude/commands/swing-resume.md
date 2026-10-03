---
allowed-tools: Bash(git log:*), Bash(git status:*), Bash(git diff:*), Bash(cat:*), Bash(tail:*), Bash(head:*), Bash(date:*), Read, Grep
description: Resume the Primed BC live swing system (and its swing research) in a fresh session — live state first (positions, primed list, data freshness, next dashboard step), then where research left off from memory, FINDINGS.md, and git state
---

## Your task

Reconstruct the current state of the MD Swing Scanner project
(`/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner`) before responding to
anything else the user says this session. Do the reads below quietly — don't narrate each
file as you go — then give ONE consolidated orientation summary.

Scope (2026-10-03): this skill is for **Primed BC — the live swing system** (`daily_scan.py`,
`primed_engine.py`, `trader_dashboard.py`, `eod_checklist.sh`) and the swing research around it.
Other folders have their own threads and are only mentioned here if git shows uncommitted work in
them: `intradaygeeks_replica/` (intraday shorts — its own resume skill is planned),
`short_discovery/`, `pre_breach/`.

Data: all base market data and fetchers are being consolidated into the root `data/` folder
(2026-10-03, copy → verify → delete). `data/README.md` is the map of every dataset — where it lives,
how it is fetched, coverage, known gaps. If a path below has moved, follow `data/README.md`.

### Step 1: Read the project memory

Read `/Users/mdubey/.claude/projects/-Users-mdubey-workspace-personal-my-utilities/memory/md_swing_scanner_project.md`
in full. This is the authoritative cross-session log, append-only, dated sections — the
most recent section (bottom of the file) matters most for "what's the current state,"
earlier sections are historical record only.

### Step 2: Read the most recent FINDINGS.md entries

The memory file summarizes; `FINDINGS.md` in the project directory has the exact numbers
and detail behind each summary line. It is large (thousands of lines) — do not read the
whole file. Read its last ~200-300 lines first. If the memory file's most recent section
references a specific research thread (e.g. "RQ-95") whose detail isn't in that tail,
`grep -n "^## " FINDINGS.md` to find the right section and read that range instead.

### Step 3: Check git state

In the project directory, run:
- `git log --oneline -10`
- `git status`
- `git diff --stat` (only if `git status` shows uncommitted changes)

### Step 4: Check the live BC state

These are real trades and real live inputs, not research artifacts. Treat them accordingly (see
the project's own standing data-handling caution around live position/trade data).
- `open_positions.csv` — currently-held trades.
- `trade_journal.csv` — the last ~10 rows (what was actually traded or decided recently,
  including discretionary holds past a system exit).
- `primed_cache.json` — its `date` and ticker count: is today's primed list fresh or stale?
- Data freshness: the last date in the daily cache's `_NIFTY.csv` (`data_cache/`, or its
  `data/` location once moved). If it is older than the last NSE trading day, the end-of-day run
  (`./eod_checklist.sh`) has not been done.
- `date` (IST): which step of the daily workflow is due next — before/during market hours
  `python3 trader_dashboard.py morning`; after the close `./eod_checklist.sh`, then
  `trader_dashboard.py evening` and `night` (README "Daily usage" is the source of truth).

### Step 5: Check the Parking Lot

Read `PARKING_LOT.md` in the project directory in full — this is where deferred
research/implementation items live (things intentionally not done yet, each with
enough context to pick up cold), separate from FINDINGS.md's append-only log of
what's already done. It's short enough to read in full each time.

### Step 6: Give ONE consolidated orientation summary, then stop

Structure it as:
- **Live BC status** — open positions, primed list date/size, data freshness, and the next
  workflow step due now (one line each).
- **Last closed/decided** — the most recent research conclusion or implementation
  change, 1-3 sentences, specific (exact numbers/thresholds, not vague gestures).
- **Open item(s)** — what was explicitly flagged as next/pending. Quote the exact
  framing from memory/FINDINGS.md rather than paraphrasing loosely — an open item's
  precise wording (e.g. a specific RQ number and its exact unresolved question) is
  often load-bearing.
- **Parking lot** — list each item currently in `PARKING_LOT.md` by name (one line
  each — what it is, not the full context), so the user can pick one to resume without
  re-reading the whole file themselves. If they pick one, use that entry's own "next
  step" as the starting point, not a fresh guess.
- **Uncommitted work / loose ends** — anything `git status` or the memory file flags.
- **Real positions** — what's currently open, if anything, from `open_positions.csv`.

Do NOT start new research, write code, or make any changes yet — wait for the user's
actual direction. If the user's first message in this session already states what they
want to do, fold this orientation into responding to that directly rather than making
them wait through a separate "here's where we left off" step before you get to it.
