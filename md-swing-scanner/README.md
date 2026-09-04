# MD Swing Scanner

A daily swing-trading scanner for the NIFTY 500 stock universe, plus the backtest
infrastructure used to validate it. The universe is deliberately broader than the F&O
subset — `fo_universe.csv` (210 F&O-eligible names) is reserved for the future
options-specific layer, which is hard-constrained to names that actually have options;
the pure-swing scanner isn't. Two independent entry patterns:

- **Breakout Continuation** — an already-trending stock breaking a fresh 10-day high on
  unusual volume (z-score based, not a flat ratio).
- **Coiled Spring / VCP** — Minervini's Volatility Contraction Pattern: a long-term
  Stage-2 uptrend (50/150/200-day MA stack, relative-strength percentile ≥70 vs the
  universe) breaking out of a genuine multi-week, multi-leg tightening base.

Both patterns share an ADX-based market-regime gate (only trade when Nifty is
genuinely trending, ADX≥20) plus a Nifty-above-its-own-200-day-SMA structural filter
(don't go long against a falling broad market). Exits share ONE mechanism now
(`current_stop_level`, 2026-08-30): a pattern-specific base stop (structural low for
VCP, ATR chandelier for Breakout Continuation) that tightens onto the 21-day EMA once
the trade is up `TRAIL_ENGAGE_PCT` — previously only VCP had this second stage,
Breakout Continuation trailed at a flat 3xATR the whole hold. Plus a shared moving
resistance target and a gated climax-top exit for both.

## Current status

As of 2026-09-01, the validated stock-level config (**v28**) backtested over 5 years
(2021-2026) across the full 500-stock NIFTY 500 universe: **n=1430 trades, 65.0% win
rate, median +2.89%/trade, top-10-of-total concentration 10.3%** (v27 was n=924/62.9%/
+2.90%/16.1%; v25 before that was n=677/58.3%/+1.64%/30.7%). v27 = v25 + three changes
(daily pivots replacing weekly, `vcp.LAST_LEG_TOLERANCE=0.40`, `signals.VOL_ZSCORE_WINDOW=8`
— see the v27 entry in git history or `backtest.py`'s comments for the individual
numbers). v28 = v27 + `signals.RSI_MAX=80` (was 68 — Breakout Continuation's own RSI
ceiling, swept in isolation on v28 data rather than inferred from VCP's separate
no-ceiling finding, which was a real methodological correction owed from round 5's
critique; see `signals.py`'s own comment for the full sweep and the same-day-relabel /
scheduling-cascade verification done before adopting it). Caveat worth knowing before
quoting either headline number: part of each jump partly reflects a larger n diluting
a fixed top-10's share (splitting v27's 5yr window in half, each half's own
concentration was 25.8%/31.6%, not as dramatic as the pooled 16.1% suggested), and
part of v28's win-rate gain over v27 specifically is a mix-shift artifact — Breakout
Cont's own win rate (67.9%) and VCP's own (61.7%) barely moved from their
isolated-test values, but Breakout Cont's much bigger share of the combined pool pulls
the blended average toward the stronger pattern. See `FINDINGS.md` for this and other
narrative conclusions that don't map to a single code parameter.

Options layer (`option_backtest.py`/`portfolio.py`, scoped to `fo_universe.csv`):
contract-selection isolation across ATM/ITM × current/next-month expiry, re-run on
v28's swing entries (838 FO-eligible trades), points to **ITM + next-month** as the
strongest candidate — and it gets healthier on the bigger sample (n=562, win 61.6%,
median +18.63%, concentration **32.6%**, down from 77.1% on the earlier, smaller run).
Survival analysis and the capital-efficiency/leverage metric were also re-run on this
bigger set (2026-09-01) — both original findings hold: stop-outs take 1.6-1.75x
longer to resolve than resistance wins, and leverage stays roughly symmetric between
winners and losers (median 9.7x vs 8.6x on ITM+next) — see `FINDINGS.md` for the full
numbers, including a real leverage-metric gotcha (use median, not mean — a few
near-zero-denominator trades produce meaningless three-digit outlier ratios).
`portfolio.py`'s capital-constrained simulator was rewritten (2026-08-31) from
independent per-slot capital splits to one shared cash pool — see its own comments.
Real costs (transaction charges, STT on exercised ITM options, slippage, bid-ask
spread) are NOT modeled anywhere in this layer yet — flagged as a real, unaudited gap,
not confirmed safe. `FINDINGS.md` also covers a scheduler-fragility finding: portfolio-
level P&L rankings between similar-quality contract-selection variants aren't reliable
without tracing which specific trades actually drive the difference — a `portfolio.py`
comparison, on its own, is not sufficient evidence that one rule is really better than
another this close.

The full history of what was tried, what was rejected and why, and every bug found
along the way is recorded as comments directly next to the relevant code (see
`backtest.py`, `signals.py`, `vcp.py`, `pivots.py`, `market_regime.py`, `fetch_prices.py`,
`portfolio.py`) — that's the actual decision log for anything tied to a parameter.
`FINDINGS.md` covers everything else: analysis conclusions that never changed a
parameter (entry-day-momentum vs waiting for a pullback, why big-momentum days skew
toward one pattern, the outside-critique review history), so the repo is self-contained
without relying on any single session's memory.

## Layout

**Data** (all gitignored — regenerated by running the fetch scripts, never committed)
- `nifty500_universe.csv` — the pure-swing universe (500 tickers, NSE's official NIFTY
  500 constituent list, fetched from `nsearchives.nseindia.com`). This IS committed
  (it's a small reference list, not generated output).
- `universe.py` — derives the F&O-eligible subset (`fo_universe.csv`, 210 tickers) from
  an NSE bhavcopy — used only by the options-specific layer.
- `fetch_prices.py` — daily OHLCV per ticker into `data_cache/`. Incremental: a
  ticker with no cache yet gets the full 5-year history, an already-cached ticker only
  fetches and appends days since its own last cached date. Defaults to the NIFTY 500
  list, which already covers the F&O subset too (a strict superset).
- `fetch_stock_options.py` — NSE F&O bhavcopy cache for the options layer (`options_cache/`, ~2.7GB), UDiFF format, 2024-01 onward.
- `fetch_stock_options_pre2024.py` — extends `options_cache/` back to 2022-06 by normalizing NSE's discontinued pre-UDiFF bhavcopy format, which never carried a lot-size column; backfills each ticker's lot size from its earliest 2024+ reference value (position-sizing approximation only, doesn't affect the option's own % return — see the file's own comments).
- `intraday_cache.py` — 5-minute intraday bars (`intraday_cache/`, ~190MB, all 500
  tickers), built 2026-09-02 specifically to survive past yfinance's own rolling
  60-day retention window (confirmed: anything older is rejected outright). Once a
  day ages out of that window it's gone from Yahoo for good unless already saved
  here — `refresh()` is safe to re-run anytime, new tickers get a full 60-day
  backfill, already-cached ones just get a 10-day top-up merged in. Run tickers in
  parallel batches with care: two concurrent `yfinance` fetches triggered rate
  limiting the first time this was built (224 of 500 tickers failed silently until
  retried sequentially) — don't background more than one fetch job at once.
- `market_regime.py` — Nifty ADX/±DI/200-SMA regime data (`data_cache/_NIFTY.csv`).
- `relative_strength.py` — cross-sectional RS percentile rank. `UNIVERSE_FILE` defaults
  to `nifty500_universe.csv` — set it to `fo_universe.csv` only for the options-specific
  layer, since RS is a ranking and which universe it's ranked against genuinely changes
  the result.
- `sectors.py` — ticker→sector classification (`data_cache/_sectors.csv`, via
  yfinance, 499/500 classified), refreshed standalone, not on every scan.
- `sector_strength.py` — sector-level relative strength (same RS methodology as
  `relative_strength.py`, grouped by sector). Feeds `daily_scan.py`'s `sector`/
  `sector_rs` annotation — a ranking signal, not a filter, see its own module comment
  and `FINDINGS.md` for the backtest evidence behind it.
- `runs/` — every backtest/portfolio script writes its output CSVs here (also gitignored — regeneratable, not source).

**Signal logic**
- `signals.py` — indicators (EMA/RSI/ATR/z-score volume) + Breakout Continuation's entry gate.
- `vcp.py` — Stage-2 trend template + multi-contraction base detector + VCP's entry gate.
- `pivots.py` — weekly/daily floor-trader pivots (support/resistance levels).

**Backtest**
- `backtest.py` — the simulator. `detect_entry()` and `check_exit()` are the single
  source of truth for entry/exit logic, shared with the live-use scripts below so the
  two can never quietly drift apart.
- `option_backtest.py` — translates stock signals into real front-month option trades
  (front-month + 5-trading-day expiry-runway buffer, corrected settlement pricing).
- `portfolio.py` — capital-constrained simulation (fixed 3-slot, 1-lot options sizing).

**Daily use** (live, not backtesting — see below)
- `daily_scan.py` — today's new candidate signals.
- `monitor_positions.py` — current stop/target for positions you're actually holding.
- `open_positions.csv` — your real, manually-maintained open positions.

**Tests**
- `tests/` — deterministic unit/integration tests (pytest). Found a real bug in
  `weekly_pivots()` on the first run (see `pivots.py`'s comments) — run these after
  touching any signal/exit logic, before trusting a new backtest number.

## Setup

```
pip install -r requirements.txt
```

## Running the backtest

```
python3 fetch_prices.py       # refresh data_cache/ (incremental — fast after the first run)
python3 market_regime.py      # refresh the Nifty regime cache
python3 backtest.py           # writes runs/trades_v28.csv, prints the summary stats
```

## Daily usage

Run once per day, after market close:

```
python3 fetch_prices.py
python3 market_regime.py
python3 daily_scan.py          # new candidates today
python3 monitor_positions.py   # current stop/target for your open positions
```

`daily_scan.py` scans the full NIFTY 500 universe with the exact same entry logic the backtest
validated. Output is always three sections: **Tradable Today** (gate-respecting, real signals),
**Watchlist — fails only on regime** (pattern fired, only the Nifty ADX/200-SMA gate blocked it —
computed automatically at no extra cost, for observation only, not a validated trade signal), and
**Near-miss — intraday High cleared resistance, Close didn't confirm** (2026-09-03, Breakout
Continuation only — a LOW-WEIGHT ranking signal for a quiet day, see `signals.near_miss_high_
breakout`'s docstring for the full backtest numbers: real but modestly below-average trades,
63.0% win/+2.29% median vs the standard pool's 65.0%/+2.89%).
Checked directly (2026-08-31, both a four-way gate-isolation test and a market-breadth gate
alternative) that loosening the regime gate does NOT rescue the current drought with quality
trades — the watchlist is for keeping an eye on things, not a hint that these are secretly
tradable.

Each row is tagged `[F&O]` or `[NO OPTIONS]` (2026-09-01) — this scanner's universe
(`nifty500_universe.csv`, 500 tickers) is a strict superset of the F&O-eligible list
(`fo_universe.csv`, 210 tickers), so a genuinely good swing signal often shows up on a
name with no options market at all (real case: 3 of a real 6-ticker watchlist were
`[NO OPTIONS]`). Still a real stock trade, just never an options trade.

Each row also annotates TODAY's move specifically (2026-08-31), since close/target alone can hide
how much real room is left: `%chg` (today's move vs prior close), `target=... (X% away)` (room
left to the resistance exit target — real case: a close of 916 against a 917.97 target is only
0.2% away, i.e. basically already arrived), `vol_z` (today's volume z-score, confirms or questions
the move), and a `⚠ already touched/exceeded this target intraday today` flag when the day's own
High already reached the target before closing back below it (checked directly: this is roughly a
wash historically, not a strong red flag on its own — but combined with near-zero room left, it's
still worth knowing).

Two more fields, added 2026-09-01: `stop=₹X` is the actual stop-loss level a fresh entry would
start at today (same `current_stop_level()` logic the backtest and `monitor_positions.py` use —
Minervini's structural-base-low for Coiled Spring, the published Chandelier Exit's 3xATR trail for
Breakout Continuation), needed for position sizing before a trade even exists yet. A `[BOTH]` tag
(plus an explanatory line) marks a candidate that independently clears the OTHER pattern's
condition too, not just the one that actually claimed it — checked directly before adding this:
it is **purely informational**, not a validated confidence signal (win rate identical either way,
65.0%, on the 40 real dual-qualified trades out of 1430 in v28 — see `FINDINGS.md`). Don't use it
to rank candidates against each other.

A third field, added 2026-09-01: `{sector} (sector RS N)` shows the candidate's sector and how
that sector currently ranks (0-100 percentile) against every other sector's trailing relative
strength. Unlike `[BOTH]`, this one IS meant as a ranking signal when choosing between several
same-day candidates — real backtest evidence (see `FINDINGS.md`) shows VCP trades in the top
sector-RS quartile win 68.1% (vs 55-61% in the bottom three) with much healthier concentration.
Still not a hard gate — nothing gets excluded from the list on this basis, same reasoning as
`MOMENTUM_20D_MIN`/`MIN_TRADED_VALUE` staying candidate-list controls rather than proven filters.

A top-level line, added 2026-09-02: `market breadth today: X%` (% of NIFTY 500 above their own
200-SMA) — unlike sector RS, this is one market-wide number for the whole day, not a per-stock
value, so it's printed once rather than per-candidate. Real backtest evidence (`FINDINGS.md`) found
a genuine, monotonic relationship between breadth and how good the WHOLE day's candidate list
tends to be (65.0%/+2.89% median at no filter vs 69.3%/+3.58% at breadth>=80) — read it as "how
much weight to put on today's list overall," not a per-candidate ranking field. Also explicitly not
a hard gate, per the same reasoning as sector RS.

Two more observation-only flags, neither backtest-validated: `--ignore-regime` bypasses
the gate entirely (collapses to a single Tradable Today list, no watchlist split — there's no
gate left to fail on); `--live [--cutoff HH:MM]` (default 14:45 IST) checks a same-day intraday
snapshot instead of waiting for tomorrow's close — two-pass, so only a cheap EOD pre-filter
(`shortlist_primed`, typically ~30/500 tickers) gets an actual intraday fetch, not the full
universe. `monitor_positions.py` reads `open_positions.csv` (columns: `ticker,
entry_date, entry_price, pattern`) — log each real position you take there — and
replays the exact same exit logic from your entry date to today, reporting:

- the current stop and target level (update your real broker orders to match — both
  only ever move in your favor, never loosen),
- whether an exit condition already fired on some earlier day (in case you missed it),
- days since the position's last fresh high — informational only, not a validated
  exit rule, but a useful "is this stalling" data point for your own judgment.

Neither script knows about your actual option contract or its expiry yet — that's the
next layer to build if/when the options-translation step gets revisited.

## Running the tests

```
python3 -m pytest tests/ -v
```

All tests are deterministic — synthetic price series with hand-verified expected
outputs, not dependent on `data_cache/` or network access. Run these before trusting
any change to `signals.py`, `vcp.py`, `pivots.py`, `market_regime.py`, or `backtest.py`.

## Known limitations

- IV-percentile filtering isn't built (no IV column in the bhavcopy; would need a
  Black-Scholes back-out).
- `portfolio.py` has a shared cash pool now (fixed 2026-08-31), but still a fixed
  3-concurrent-position cap and fixed 1-lot-per-trade sizing — no scaling up when more
  capital is available.
- **No real transaction costs modeled anywhere in the options layer**: no brokerage,
  no STT on exercised ITM options, no slippage, no bid-ask spread (the bhavcopy gives
  traded prices, not what you could actually execute at) — flagged by outside review,
  not yet audited. Backtested returns should be read as upper bounds, not expected
  real-money returns, until this is checked.
- **No walk-forward / out-of-sample validation** — every parameter (VCP tolerance,
  volume window, RSI bands, daily pivots) has been tuned and evaluated on the same
  5-year historical window. In-sample robustness has been checked several ways (split-
  half consistency, marginal-trade quality, combined-vs-individual interaction), but
  none of that is a substitute for testing on genuinely unseen future data.
- `daily_scan.py`/`monitor_positions.py` are stock-only; they don't yet account for
  which option contract you'd actually be holding or when it expires.
- The Dec'24-May'25 VCP losing patch (32 trades, 34.4% win vs ~56-61% everywhere else)
  is confirmed real, root cause still unidentified.
- The regime-gate drought (Nifty below its own 200-SMA since 2026-02-26) is unresolved
  — three independent gate-loosening experiments were all rejected as fixes; it's
  candidate-scarcity, not a filter problem.
