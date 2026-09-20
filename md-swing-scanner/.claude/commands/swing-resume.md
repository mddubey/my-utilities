---
allowed-tools: Bash(git log:*), Bash(git status:*), Bash(git diff:*), Bash(cat:*), Read, Grep
description: Resume MD Swing Scanner work in a fresh session — reconstructs exactly where things left off from memory, FINDINGS.md, and git state before doing anything else
---

## Your task

Reconstruct the current state of the MD Swing Scanner project
(`/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner`) before responding to
anything else the user says this session. Do the reads below quietly — don't narrate each
file as you go — then give ONE consolidated orientation summary.

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

### Step 4: Check real open positions

Read `open_positions.csv` in the project directory — these are real, currently-held
trades, not research artifacts. Treat them accordingly (see the project's own standing
data-handling caution around live position/trade data).

### Step 5: Give ONE consolidated orientation summary, then stop

Structure it as:
- **Last closed/decided** — the most recent research conclusion or implementation
  change, 1-3 sentences, specific (exact numbers/thresholds, not vague gestures).
- **Open item(s)** — what was explicitly flagged as next/pending. Quote the exact
  framing from memory/FINDINGS.md rather than paraphrasing loosely — an open item's
  precise wording (e.g. a specific RQ number and its exact unresolved question) is
  often load-bearing.
- **Uncommitted work / loose ends** — anything `git status` or the memory file flags.
- **Real positions** — what's currently open, if anything, from `open_positions.csv`.

Do NOT start new research, write code, or make any changes yet — wait for the user's
actual direction. If the user's first message in this session already states what they
want to do, fold this orientation into responding to that directly rather than making
them wait through a separate "here's where we left off" step before you get to it.
