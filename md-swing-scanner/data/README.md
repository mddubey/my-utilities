# data/ — base market data

**Rules**
- **One home.** Every cache of raw exchange or vendor data lives here, once, with one fetcher
  that owns it.
- **Research outputs stay out.** Panels, features, results and reports stay in their project
  folders.
- **Read paths only through `data/paths.py`.** Never hard-code a folder name.
- **Fetchers fetch the full NSE equity universe** (`nse_equity_universe.csv`, ~2,327 names).
  Each project picks its universe at read time.
- **Old paths still work.** Folders that lived elsewhere before 2026-10-03 are symlinks to
  their `data/` home, so old scripts keep running.
- **Not in git.** Everything here is regeneratable and gitignored, except `paths.py`, the
  fetchers and this file.

Coverage below was measured 2026-10-03 IST. Owner = the session or track that maintains the
fetcher.

## Daily refresh (EOD checklist, Part A)

`./eod_checklist.sh` after the close runs **Part A, data** (`data/refresh.sh`, also runnable on its own), then
**Part B, trading** (each live system's EOD routine). Part B runs only if Part A's critical datasets are current.

| step | dataset | fetcher | notes |
|---|---|---|---|
| 1 | `daily/` all NSE equity | `fetch_prices.py --progress` | saves each batch as it arrives; lock file |
| 2 | `daily/_NIFTY.csv` + regime indicators | `market_regime.py` | merges, refuses an empty/short reply |
| 3 | `intraday_5m/` all | `intraday_cache.py` | top-up last 10 days, one retry pass |
| 4 | `index_intraday/` | `data/fetch_index_intraday.py` | merges; Nifty 5m kept beyond Yahoo's 60 days |
| 5 | `intraday_60m/` all | `data/fetch_intraday_60m.py 0 1 10d --topup` | merges last 10 days |
| 6 | health check | `data/check.py` | PASS/WARN/FAIL per dataset vs the latest real NSE session |

- **Session skip:** every step first asks Nifty's 60-min bars for the latest real NSE session
  (`fetch_prices._latest_nifty_session`) and skips stocks that already hold it, so weekend/holiday runs take
  about a minute. A stock counts as current only with the full session (5-min last bar >= 15:10 IST; 60-min >= 14:15,
  since F&O names have no 15:15 stub after the closing auction began 2026-08-03). If the lookup fails, nothing is
  skipped.
- **Critical** (Part B stops if they fail): daily prices for >= 98% of the Nifty 500, and the Nifty regime file.
  The rest are WARN only.
- **Logs:** `data/logs/refresh_YYYYMMDD_HHMM.log` per run; `data/logs/last_check.json` = latest health check.
- **Not refreshed here (by hand):** `nse_fo_bhav/`, `nse_cash_close/`, `nse_bhav/`, `nse_bands/`,
  `nse_corp_actions.csv`. The health check prints their latest file date.

## Quick map

| path constant | folder / file | source | coverage | prices |
|---|---|---|---|---|
| `DAILY_DIR` | `daily/` | Yahoo daily | 2,338 files (incl. `_NIFTY`, `_BANKNIFTY`, `_BREADTH`, `_sectors`); typical start 2021-08-30 → 2026-10-01 | split-adjusted at fetch time; see caveats |
| `INTRADAY_5M_DIR` | `intraday_5m/` | Yahoo 5-min | 2,319 files; start 2026-06-10 (Nifty-500 names) or ~2026-07-09 (rest) → now | split-adjusted at fetch time |
| `INTRADAY_60M_DIR` | `intraday_60m/` | Yahoo native 60-min | 2,266 files; 2023-10-23 → now | split-adjusted at fetch time |
| `INDEX_INTRADAY_DIR` | `index_intraday/` | Yahoo | `_NIFTY_1h`, `_BANKNIFTY_1h`, `_NIFTY_5m_60d` | index levels |
| `NSE_FO_BHAV_DIR` | `nse_fo_bhav/` | NSE F&O bhavcopy | 1,070 sessions, 2022-06-01 → 2026-09-30 | raw contract prices, OI, volume |
| `NSE_CASH_CLOSE_DIR` | `nse_cash_close/` | NSE cash bhavcopy, close only | 351 sparse dates, 2022-08-01 → 2026-09-30 | raw unadjusted close |
| `NSE_BHAV_DIR` | `nse_bhav/` | NSE full cash bhavcopy | 1,203 sessions, 2021-11-22 → 2026-10-01, every equity series | raw unadjusted OHLC + PREVCLOSE + volume |
| `NSE_BANDS_DIR` | `nse_bands/` | NSE `sec_list_DDMMYYYY` | 1,200 sessions, 2021-11-22 → 2026-10-01 | price-band % per symbol |
| `NSE_CORP_ACTIONS_FILE` | `nse_corp_actions.csv` | NSE corporate-actions API | 12,556 rows, ex-dates 2021-11 → 2026-10, equities + SME | n/a |

## daily/ — Yahoo daily OHLCV (owner: production / EOD)

- **Fetcher:** `fetch_prices.py` (incremental), run via `eod_checklist.sh`.
- **Columns:** Date, Open, High, Low, Close, Adj Close, Volume. Index and breadth files are
  prefixed `_`. `backtest.load()` drops Volume = 0 rows and flags
  `corp_action_day` = |close-to-close| > 35%.
- **Caveats:**
  - **Corporate actions are not reliably adjusted.** 49 of the 51 one-day drops > 35% that
    `corp_action_day` removes are unadjusted splits, bonuses or demergers, clustered on
    Jan-1 dates. Smaller ones slip under 35% and look like real crashes. Example: TRENT
    T = 2025-12-31 opens −33.33% in Yahoo but −0.54% at NSE. For anything sensitive to
    single-day moves, cross-check against `nse_bhav/` and `nse_corp_actions.csv`.
  - **Adj Close is unreliable.** Rows were written at different fetch times, so they carry
    different dividend bases.
  - **The session calendar (`_NIFTY.csv`) is missing 5 real NSE sessions:** 2023-11-12
    (Muhurat), 2024-01-20, 2024-03-02, 2024-05-18 and 2026-02-01 (Budget Sunday). NSE's
    PREVCLOSE on the following session reveals them.
  - **Late starts:** 222 tickers' history starts Aug 2026 or later. 166 are genuine new
    listings. 56 (all with listing_date 2026-04-20) are a ~4-month Yahoo gap; `nse_bhav/`
    has those sessions. List: `short_discovery/late_start_tickers.csv`.
  - **Missing rows:** occasional per ticker (e.g. RELIANCE 2026-03-18). Treat T+k as "the
    next k market sessions", not "the next k rows".

## intraday_5m/ — Yahoo 5-minute bars (owner: production)

- **Fetcher:** `intraday_cache.py` (now defaults to the full universe).
- **Coverage:** Nifty-500 names from about 2026-06-10, the rest from about 2026-07-02 / 09.
  Yahoo keeps only about 60 days of 5-min history, so anything not cached is gone.
- **Note:** `resample_1h()` in `resample_1h.py` rebuilds hourly bars from these on demand;
  the old `intraday_cache_1h/` is retired.
- **Timestamps** are tz-aware UTC (03:45 UTC = 09:15 IST). Columns: Open, High, Low, Close, Volume.
- **Refresh:** `eod_checklist.sh` step 2 tops up the last 10 days for every cached stock, with one slower retry pass
  for any that come back empty (Yahoo throttling returns empty frames with no error).
- **Holes:** Yahoo drops some 5-min bars. A full session is 75 bars (09:15-15:25). Count bars per stock-day before
  trusting a day; `resample_1h()` reports `n_bars` / `complete` per hour.
- **Extremes:** Yahoo misses NSE's true day high/low on about 72% of stock-days (median 0.056%, checked against NSE
  bhavcopy, intradaygeeks_replica scripts 22-23). Matters for tight stops; take stop levels from the broker chart.
- **Closing auction (CAS), F&O names from 2026-08-03:** continuous trading ends 15:15; bars at/after 15:15 are
  auction residue. `resample_1h()` drops them for F&O names; raw reads here do not.

## intraday_60m/ — Yahoo native 60-minute bars (owner: intradaygeeks_replica)

- **Fetcher:** `data/fetch_intraday_60m.py <slice> <n_slices> [period] [--topup]`.
- **Bars:** start 09:15 IST, hourly.
- **Coverage:** 2023-10-23 → now. A "730d" request returned back to 2023-10, so the real
  Yahoo limit is still unclear. Until it's known, treat the existing history as
  irreplaceable.
- **Caveats:** split-adjusted at fetch time, with holes. Check completeness per stock-day
  before using a day.
- **Timestamps** UTC (03:45 UTC = 09:15 IST); the last bar of a day is the 15:15 IST stub. Columns: Open, High,
  Low, Close, Adj Close, Volume.
- **Matches the 5-min cache:** hourly bars rebuilt from `intraday_5m/` were identical to these on the overlap
  (intradaygeeks_replica, 2026-10-03). Use these for history before 2026-06, `intraday_5m/` + `resample_1h()` after.
- **Start dates:** 1,622 stocks from Oct 2023 (mostly 2023-10-23); the rest start later (listing date or first Yahoo data; about 200
  only from Aug 2026, same late-start group as `daily/`).
- **Not refreshed by the EOD run.** Top-up is manual or monthly via `intradaygeeks_replica/51_monthly_recheck.sh`
  (`--topup` merges the last 30 days). Last top-up was uneven: 1,296 files end 2026-09-30, 962 end 2026-10-01.
- **CAS:** after 2026-08-03 the 15:15 bar of F&O names may include closing-auction prints (unverified).
- **Moved 2026-10-03** from `intradaygeeks_replica/h1_cache/` (now a symlink).

## index_intraday/ — NIFTY / BANKNIFTY intraday (owner: intradaygeeks_replica)

- **Fetcher:** `data/fetch_index_intraday.py`.
- **Files** (timestamps UTC; measured 2026-10-03):
  - `_NIFTY_1h.csv`, `_BANKNIFTY_1h.csv`: 5,050 bars each, 2023-10-25 → 2026-10-01.
  - `_NIFTY_5m_60d.csv`: 4,423 bars, 2026-07-10 → 2026-10-01. The name is historical: the fetcher now merges into
    it, so it keeps growing past Yahoo's 60-day window. History older than 60 days cannot be re-fetched.
- **Merge, never overwrite:** each run adds new bars to the existing file, so history Yahoo no longer serves is kept.
- **Not refreshed by the EOD run;** run the fetcher when index intraday data is needed.
- **Moved 2026-10-03** from `intradaygeeks_replica/index_1h/` (now a symlink). Daily Nifty/BankNifty live in
  `daily/` (`_NIFTY.csv`, `_BANKNIFTY.csv`).

## nse_fo_bhav/ — NSE F&O bhavcopy (owner: production)

- **Fetchers:** `fetch_stock_options.py` (2024+) and `fetch_stock_options_pre2024.py`.
- **Columns:** TradDt, TckrSymb, XpryDt, StrkPric, OptnTp, prices, OpnIntrst, TtlTradgVol,
  NewBrdLotQty, FinInstrmTp. STO = stock options, IDO = index options, STF/IDF = futures.
- **Point-in-time F&O membership:** stock options listed on date T. Used by
  `short_discovery` from 2022-06-01.

## nse_cash_close/ — NSE cash bhavcopy, close only (owner: production)

- **Fetcher:** `fetch_cash_bhav.py`.
- **What it's for:** real unadjusted spot for option strike selection. Sparse: only the
  dates option research needed.
- **For full OHLC on every session, use `nse_bhav/`.**

## nse_bhav/ — NSE full cash bhavcopy (owner: short_discovery)

- **Fetcher:** `data/fetch_nse_bhav.py [start_yyyy-mm-dd]`. Incremental; legacy archive
  before 2024-07-08, UDiFF after.
- **Contents:** one file per session, every equity series (EQ/BE/BZ/SM/ST/…). Columns:
  ticker, series, open, high, low, close, prevclose, volume.
- **Caveats:**
  - **Prices are raw and never adjusted.**
  - **PREVCLOSE is NOT adjusted on corporate-action ex-dates.** Only 8 of 769 one-day
    drops ≥ 30% show an adjusted PREVCLOSE; EASEMYTRIP's 2022-11-21 split plus 3:1 bonus
    shows PREVCLOSE = the unadjusted prior close. So PREVCLOSE ≠ prior CLOSE does not mean
    a corporate action. What it does flag is a session missing from the calendar (see
    daily/ caveats).
  - Use `nse_corp_actions.csv` for ex-dates.
- **Tickers:** current symbols only. Renamed companies' pre-rename history is under the old
  symbol, which caused about 3% of `short_discovery` panel rows to be "missing".

## nse_bands/ — NSE point-in-time price bands (owner: short_discovery)

- **Fetcher:** `data/fetch_nse_bands.py [start_yyyy-mm-dd]`. Incremental.
- **Columns:** Symbol, Series, Band (2 / 5 / 10 / 20 / 40, or "No Band").
- **Convention (verified by hand):** the file dated D holds bands effective for the NEXT
  session, so band(session d) = file(session d − 1).
  - sec_list_04042025 already shows the changes in eq_band_changes_07042025.
  - AAREYDRUGS locked at −5.01% on 2025-04-07 under its new 5% band.
- **"No Band":** about the F&O names. It agrees with `nse_fo_bhav` stock-option listings on
  99.89% of rows, so it works as a point-in-time F&O proxy before 2022-06.
- **Gaps:** NSE returned empty files for 2021-12-09, 2022-05-10 and 2022-07-12 (not stored).

## nse_corp_actions.csv — NSE corporate actions (owner: short_discovery)

- **Fetcher:** `data/fetch_nse_corp_actions.py [start_yyyy-mm] [end_yyyy-mm]`. Rewrites the
  file; needs the nseindia.com homepage cookie, which the script handles.
- **Columns:** symbol, series, exDate (dd-Mon-yyyy), subject, index (equities | sme).
- **Classifying the subject field:**
  - price-affecting: `split|sub-division|bonus|rights|demerger|scheme|arrangement|
    amalgamation|consolidation|reduction`;
  - dividends: `dividend`;
  - the rest is AGMs, interest payments and buybacks.
- **Map an exDate to a session** as the first calendar session on or after it.
