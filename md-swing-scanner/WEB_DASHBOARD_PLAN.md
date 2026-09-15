# MD Swing Scanner — Web Dashboard on Render.com

*Plan only — not implemented yet. Written 2026-09-15 for execution in a future session.*

## Context

The scanner is currently a set of CLI tools run by hand from a laptop (`trader_dashboard.py evening/morning/night`, `daily_scan.py`, `fetch_prices.py`, etc.). The goal: host a lightweight Flask web dashboard on Render.com exposing the three feature groups already in daily use — **live monitor**, **refresh tickers**, **EOD activity** — so they're reachable from a browser at some `xyz.onrender.com` URL instead of requiring SSH/CLI access.

Explicit decisions already made (do not re-litigate these in a future session without being asked):
- **Framework: Flask** (not FastAPI) — named directly.
- **Host: Render.com.**
- **No authentication** — the URL itself is the only access control ("if someone reaches there, reaches there, we'll see"). Do not add a login/password screen unless asked.
- **Scope is strictly the three named feature groups** — this is a wrapping/presentation layer over already-validated logic, not a place to add new trading features, options endpoints, or position/journal-editing forms. (Established project discipline: `detect_entry()`/`check_exit()` in `backtest.py` are the single source of truth precisely so two copies of "what counts as a signal" never drift apart — the web layer must call the *same* functions the CLI tools call, never reimplement scan/checkpoint/monitor logic.)
- **`options_cache/`, `cash_bhav_cache/`, `runs/` do NOT need to exist on the server** — confirmed no live-facing tool touches them. Only `data_cache/` and `intraday_cache/` matter here.

## What already exists (confirmed by direct code reading — reuse, don't reimplement)

| Feature | Function to call | Returns |
|---|---|---|
| EOD activity | `daily_scan.py:322` `scan(tickers, require_regime=True, live=False, cutoff_ist=...)` | `(scan_date, candidates, watchlist, near_miss, live_shortlist)` — candidates/watchlist are already lists of dicts (from `_annotate()`). Pure data, no printing inside it. |
| Live monitor — candidates | `live_checkpoint.py:493` `classify_candidates(tickers, cutoff_ist=None)` | 4-tuple of DataFrames `(pulled_back, kept_going_near, watching, missed)`. Pure data. |
| Live monitor — open positions | `monitor_positions.py:17` `monitor(positions_df)` | **Print-only today — see required code change below.** |
| Refresh tickers — daily bars | `fetch_prices.py:72` `fetch_all(tickers)` | Takes an explicit ticker list (not hardcoded to 500), returns `{'new','updated','current','empty'}` counts. |
| Refresh tickers — intraday | `intraday_cache.py:47` `refresh(tickers=None)` | Writes CSVs directly, no return value, prints progress. |

`trader_dashboard.py` already demonstrates the exact separation-of-concerns pattern to follow: its `run_morning()`/`run_evening()`/`run_night()` call these same functions and only *add* a print layer on top — the web app should do the same thing with an HTTP-response layer instead of print statements.

## Required code change (one, small, additive — do this first)

`monitor_positions.py`'s `monitor(positions_df)` (lines 17-81) currently only `print()`s — every field a web response needs (`stop`, `target`, `days_since_new_high`, `triggered` exit reason + date, `days_held`, `remaining` days before cap) is already computed as a local variable but never returned.

Change: have `monitor()` build a list of per-ticker dicts (one dict per position, same fields already being printed) and **both** print (unchanged CLI behavior — do not break `trader_dashboard.py night` or the standalone script) **and** `return` that list. This is purely additive:
```python
def monitor(positions_df):
    results = []
    for _, pos in positions_df.iterrows():
        ...  # existing logic unchanged
        results.append(dict(ticker=ticker, pattern=pattern, entry_date=..., stop=..., target=..., ...))
        print(f"...")  # existing print statements, unchanged
    return results
```
Run the existing test suite (`python3 -m pytest tests/ -q`, currently 72 passing) after this change — should still be 72/72, nothing else should need to touch this file's tests since behavior is unchanged for the CLI path.

## New files to add

```
app.py                    # Flask app: routes + thin JSON-serialization wrappers
templates/dashboard.html  # single static page, vanilla JS, no build step / no frontend framework
static/dashboard.js       # fetch() calls to the /api/* routes below, renders into simple tables
render.yaml               # Render service definition (see Deployment section)
```

Keep `app.py` genuinely thin — every route body should be ~3-5 lines: call the existing function, shape its return into JSON, done. If a route needs more logic than that, that logic belongs in the underlying module, not in `app.py`.

### Routes

| Route | Method | Wraps | Notes |
|---|---|---|---|
| `/` | GET | — | Serves `dashboard.html` |
| `/api/eod-scan` | GET | `daily_scan.scan()` | Optional `?live=true&cutoff=HH:MM` query params map to `scan()`'s own args |
| `/api/live-checkpoint` | GET | `live_checkpoint.classify_candidates()` | Optional `?cutoff=HH:MM` |
| `/api/positions` | GET | `monitor_positions.monitor()` (post-refactor) | Reads `open_positions.csv` same as today — **read-only**, no add/edit form (out of scope) |
| `/api/refresh/prices` | POST | `fetch_prices.fetch_all()` | See background-job handling below — do not run inline |
| `/api/refresh/intraday` | POST | `intraday_cache.refresh()` | Same |
| `/api/refresh/status` | GET | — | Poll: is a refresh currently running, and what did the last one return |

### Concurrency — real issue, confirmed by code reading, must be handled

None of the underlying functions are safe for concurrent writers today:
- `fetch_prices.fetch_all()` and `intraday_cache.refresh()` both do per-ticker read-modify-write CSV writes with no locking — two overlapping refresh calls can interleave/corrupt a file.
- `daily_scan.py`'s `refresh_primed_cache()` does an unlocked full-file `write_text()` — a refresh racing a scan read is a real (if narrow) torn-read risk.

Since this is a single-operator dashboard (no auth, presumably one person clicking it), the simplest correct fix — do NOT build a job queue or database-backed task system for this:
1. A single module-level `threading.Lock` in `app.py` (e.g. `_refresh_lock`) plus a `_refresh_status = {"running": False, "last_result": None, "last_run_at": None}` dict.
2. `/api/refresh/*` routes: if `_refresh_lock.locked()`, return HTTP 409 ("a refresh is already running") immediately. Otherwise spawn a `threading.Thread` that acquires the lock, runs the real function, stores its result in `_refresh_status`, releases the lock, and return HTTP 202 immediately with a "started" body.
3. `/api/refresh/status` just reads `_refresh_status` — the dashboard's JS polls this every few seconds while a refresh is in flight and stops polling once `running` is false.
4. Run the Render web service with a single worker/thread (`gunicorn --workers 1 --threads 4 app:app` — one worker process so the in-memory lock/status dict is actually shared across all requests; with more than one worker each process gets its own copy and the lock stops working). This single-worker constraint is fine for a personal dashboard with no concurrent users.

### Timing — set frontend expectations accordingly

Only one measured number exists in the codebase: `daily_scan.py`'s own comment — `fetch_live_bars()` for the full 500-ticker universe is "~20-30s measured post-close, cold start ~108s." `fetch_prices.fetch_all()` and `intraday_cache.refresh()` have no measured timing in the code — benchmark both locally before deciding on any HTTP timeout / polling interval. A **full cold-start refetch of all 500 tickers' daily+intraday history (see Deployment note below) could take meaningfully longer than the ~108s single-snapshot number** — do not assume it's the same order of magnitude without actually timing it once.

## Deployment on Render.com

**The one architectural decision that matters most here**: Render's standard web services have an **ephemeral filesystem** — anything written to disk (i.e., every refreshed `data_cache/`/`intraday_cache/` CSV) is lost on every redeploy, restart, or instance recycle, unless a **Render Disk** (a paid persistent-volume add-on, attaches to one service) is provisioned and mounted at the app's working directory. Without one:
- `fetch_prices.py`'s incremental design (only fetches days since a ticker's last cached date) degenerates into a full 500-ticker/5-year fetch on every cold start, since there's never a "last cached date" to be incremental from — slow, and a real risk of hitting yfinance rate-limiting (HTTP 429s were observed from an unrelated sandboxed environment hitting yfinance earlier this same session — cloud-hosted IPs can get rate-limited more aggressively than a residential one; this hasn't been tested from Render specifically).

**Recommendation: attach a small Render Disk (1GB is generously more than the ~266MB `data_cache`+`intraday_cache` actually need) mounted at the repo's working directory.** This is the only way "refresh tickers" behaves the way it does locally (incremental, fast) rather than re-downloading everything on every restart. If cost is a concern and this gets skipped, explicitly accept the tradeoff: every cold start pays the full historical-fetch cost once, and the "refresh" button's real value is limited to same-session top-ups until the next restart.

Steps:
1. `requirements.txt`: add `flask` and `gunicorn` (nothing else new — no ORM/DB needed, this stays file-based like the rest of the project).
2. `render.yaml` (or manual dashboard config): one `web` service, build command `pip install -r requirements.txt`, start command `gunicorn --workers 1 --threads 4 app:app`, attach the Render Disk from the recommendation above at the working directory (or specifically at `data_cache/` and `intraday_cache/` if Render's disk-mount granularity allows per-path mounts — check Render's current docs at build time, this may have changed).
3. Seed the disk once after first deploy by hitting `/api/refresh/prices` and `/api/refresh/intraday` manually (or, simpler: `git push`ing the already-populated local `data_cache/`+`intraday_cache/` directories to the repo once as a one-time seed, then relying on the disk to persist future refreshes — note this means temporarily un-ignoring them for one commit, or copying them onto the disk out-of-band via Render's shell access; pick whichever is less friction at build time).
4. `nifty500_universe.csv`, `fo_universe.csv`, `trade_journal.csv` are already git-tracked, so they deploy automatically. `open_positions.csv` is gitignored — either commit it too (it's just your own state, low sensitivity) or seed it onto the Render Disk the same way as the caches.

## Explicitly out of scope for this build (do not add unless asked)

- Any authentication/login.
- Editing `open_positions.csv` or `trade_journal.csv` from the web UI (both stay read-only display; you still edit them by hand or via the existing CLI tools).
- Anything touching `options_cache/`, `cash_bhav_cache/`, `option_backtest.py`, or `runs/` — confirmed not part of the live path.
- A job queue / database / websockets — the single-lock + polling approach above is sufficient for one operator.
- A frontend framework/build step — plain HTML + vanilla JS `fetch()` is enough for three read-mostly panels and two buttons.

## Verification (once this is actually implemented)

1. `python3 -m pytest tests/ -q` after the `monitor_positions.py` change — expect 72/72 still passing (no behavior change to the CLI path).
2. Run `python3 app.py` (or `flask run`) locally, hit each `/api/*` route with `curl` and confirm it returns the same data the equivalent CLI command prints (`trader_dashboard.py evening/morning/night`, `daily_scan.py`).
3. Manually trigger `/api/refresh/prices` twice back-to-back (fast) and confirm the second returns HTTP 409, not a corrupted/racing write — this is the concurrency fix actually being tested, not just assumed.
4. Deploy to Render, confirm the dashboard loads at the assigned `*.onrender.com` URL, and — critically — restart the Render service once post-deploy and confirm `data_cache`/`intraday_cache` survived the restart (this is the Render Disk mount actually being tested, not just configured).
