import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
from data.paths import DAILY_DIR

CACHE_DIR = DAILY_DIR
PERIOD = "5y"  # only used for a ticker with no cache yet — everything else fetches
                # incrementally (see fetch_all), since re-pulling 5 years daily for the
                # whole universe was wasteful and fetch_stock_options.py already proved
                # the "skip what's cached" pattern out for the options side

IST = ZoneInfo("Asia/Kolkata")
SAME_DAY_SAFE_HOUR = 16  # NSE closes continuous trading at 15:30 IST, but the OFFICIAL
                          # closing-auction print isn't reliably settled on Yahoo's
                          # backend right away — confirmed directly (2026-08-31): a
                          # fetch run before this hour returned a real-looking (non-
                          # null) Close for "today" that was still wrong, silently
                          # revised by ~1% (AUROPHARMA 1699.30 -> 1717.00, LTF 310.85
                          # -> 321.00) once fetched again later the same day. Since the
                          # cache is purely incremental, that stale value would have
                          # been locked in FOREVER. Before this hour IST, treat today as
                          # not-yet-fetchable at all — same treatment as a future date —
                          # rather than risk caching a value that's still in flux.

CHUNK_SIZE = 25   # 2026-09-29, PARKING_LOT #10: a single yf.download(threads=True) call
CHUNK_PAUSE_SEC = 2  # across the whole universe (up to ~700 tickers) silently dropped 198
                      # of them under Yahoo throttling — no error, no signal, they were
                      # indistinguishable from "genuinely no new data" until hand-checked.
                      # Retrying in sequential chunks of 25 with a 2s pause cleared 100% of
                      # that stuck set in one pass. Same class of failure this project
                      # already hit once before with intraday_cache.py's concurrent
                      # fetches — chunking here generalizes that fix into fetch_all()
                      # itself instead of being a one-off manual retry script every time.


def _now_ist():
    return datetime.now(IST)


def _safe_today():
    """The most recent date it's safe to treat as a genuinely settled close. Equals
    today only at/after SAME_DAY_SAFE_HOUR IST; before that, today doesn't count yet."""
    now = _now_ist()
    today = now.date()
    return today if now.hour >= SAME_DAY_SAFE_HOUR else today - timedelta(days=1)


def _last_cached_date(ticker):
    path = CACHE_DIR / f"{ticker}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, index_col="Date", parse_dates=True)
    return df.index.max() if len(df) else None


def _chunked_download(yf_tickers, chunk_size=CHUNK_SIZE, pause=CHUNK_PAUSE_SEC, progress=False, **dl_kwargs):
    """yf.download in sequential chunks, not one call across the whole batch — see
    CHUNK_SIZE's comment for why. Returns {ticker_without_.NS_suffix: per-ticker
    DataFrame}, using an empty DataFrame for any ticker missing from a chunk's
    response (yfinance drops a ticker from its own MultiIndex entirely rather than
    returning an empty frame for it, in some failure cases — this normalizes both
    to the same 'empty, caller decides what that means' shape).

    progress=True prints a chunk-by-chunk line — for a large one-off fetch (e.g.
    RQ-QS-07U's ~1,600-ticker net-new universe pull) this call runs silently for
    20-40+ minutes otherwise, violating this project's own standing convention that
    any background run over ~30s needs live, unbuffered progress output."""
    out = {}
    total = len(yf_tickers)
    for i in range(0, len(yf_tickers), chunk_size):
        if progress:
            print(f"  fetch chunk {i}-{min(i+chunk_size, total)}/{total}", flush=True)
        chunk = yf_tickers[i:i + chunk_size]
        data = yf.download(chunk, threads=True, progress=False, auto_adjust=False, **dl_kwargs)
        is_multi = isinstance(data.columns, pd.MultiIndex)
        for yft in chunk:
            t = yft[:-3]  # strip ".NS"
            if is_multi:
                out[t] = data[yft] if yft in data.columns.get_level_values(0) else pd.DataFrame()
            else:
                # single-ticker chunk (only possible on the final, shorter chunk) —
                # yfinance doesn't build a MultiIndex for a length-1 request even
                # with group_by="ticker"
                out[t] = data if len(chunk) == 1 else pd.DataFrame()
        if i + chunk_size < len(yf_tickers):
            time.sleep(pause)
    return out


def _recover_safe_today(tickers, safe_today):
    """Narrow single-day re-fetch for tickers whose Close for safe_today came back
    NULL from the main batch request, even though real data exists. Confirmed
    reproducible (2026-09-02): the SAME ticker/date's Close is null when that date
    is the LAST row of a wider multi-day range request, but correct when requested
    as a single-day range on its own — a yfinance/Yahoo quirk (plausibly related to
    how the CAS-settled close gets finalized with a lag — see FINDINGS.md), not
    actually-missing data. Only called for tickers still missing safe_today after
    the main fetch, so this stays cheap in the common case; harmless no-op if
    safe_today genuinely has no data for a ticker (weekend/holiday/newly listed)."""
    if not tickers:
        return {}
    yf_tickers = [f"{t}.NS" for t in tickers]
    dfs = _chunked_download(yf_tickers, start=safe_today.strftime("%Y-%m-%d"), interval="1d",
                              group_by="ticker")
    recovered = {}
    for t in tickers:
        df = dfs.get(t, pd.DataFrame())
        if df.empty:
            continue
        df = df.dropna(subset=["Close"])
        df = df[df.index == safe_today]
        if not df.empty:
            recovered[t] = df
    return recovered


def fetch_all(tickers, progress=False):
    """Returns {'new': [...], 'updated': [...], 'current': [...], 'empty': [...],
    'stale': [...]} — 5 distinct buckets. 'stale' (2026-09-29, PARKING_LOT #10) is
    the honest addition: an existing ticker that's genuinely behind safe_today but
    came back with nothing even after a full retry pass — distinguished from
    'current' (nothing NEW exists because it's already caught up), which a silent
    per-ticker fetch failure used to be indistinguishable from. A caller that wants
    the old, simpler behavior can still just check `not result['stale']` for "did
    everything actually succeed."""
    CACHE_DIR.mkdir(exist_ok=True)
    safe_today = pd.Timestamp(_safe_today())
    last_dates = {t: _last_cached_date(t) for t in tickers}
    new_tickers = [t for t in tickers if last_dates[t] is None]
    existing_tickers = [t for t in tickers if last_dates[t] is not None]
    result = {"new": [], "updated": [], "current": [], "empty": [], "stale": []}

    if new_tickers:
        yf_tickers = [f"{t}.NS" for t in new_tickers]
        dfs = _chunked_download(yf_tickers, period=PERIOD, interval="1d", group_by="ticker", progress=progress)
        need_recovery = []
        for t in new_tickers:
            # dropna(subset=["Close"]), not how="all" — a row fetched while the market's
            # still open (or right at close, before yfinance settles the final print)
            # can have real Open/High/Low/Volume but a still-null Close; how="all" let
            # that row through, and since it's incremental-only, it then poisoned the
            # cache PERMANENTLY (next run's start date skips right past it). Confirmed
            # 2026-08-31: 184/500 tickers had exactly this on 2026-08-28, silently
            # breaking that day's RS-rating calc (relative_strength.py) and any pattern
            # check depending on Close for those tickers, with zero visible error.
            df = dfs.get(t, pd.DataFrame())
            df = df.dropna(subset=["Close"]) if not df.empty else df
            df = df[df.index <= safe_today] if not df.empty else df  # today isn't safe pre-SAME_DAY_SAFE_HOUR
            dfs[t] = df
            if df.empty or df.index.max() < safe_today:
                need_recovery.append(t)  # see _recover_safe_today — a chunk boundary or a
                                          # dropped ticker within a chunk is exactly this shape
        for t, extra in _recover_safe_today(need_recovery, safe_today).items():
            dfs[t] = pd.concat([dfs[t], extra]) if not dfs[t].empty else extra
        # one full retry pass for any NEW ticker still completely empty (a chunk-level
        # drop, not "genuinely no data yet") before accepting it as empty/failed
        still_empty = [t for t in new_tickers if dfs[t].empty]
        if still_empty:
            retry_dfs = _chunked_download([f"{t}.NS" for t in still_empty], period=PERIOD,
                                            interval="1d", group_by="ticker")
            for t in still_empty:
                df = retry_dfs.get(t, pd.DataFrame())
                dfs[t] = df.dropna(subset=["Close"])[lambda d: d.index <= safe_today] if not df.empty else df
        for t in new_tickers:
            df = dfs[t]
            if df.empty:
                result["empty"].append(t)
                continue
            df.to_csv(CACHE_DIR / f"{t}.csv")
            result["new"].append(t)

    if existing_tickers:
        start = min(last_dates[t] for t in existing_tickers) + timedelta(days=1)
        if start.date() > safe_today.date():
            # already fetched through the safe date (or later) — a same-day rerun, OR
            # a rerun before SAME_DAY_SAFE_HOUR with yesterday already cached. Either
            # way nothing NEW can safely exist yet, so skip the network call entirely
            # rather than ask and get an empty (or worse, unsafe) answer back. This
            # does NOT cover weekends/holidays before the first same-day run (start is
            # still <= safe_today then) — telling those apart needs an NSE trading-day
            # calendar, which isn't worth building just to save one wasted API call.
            result["current"].extend(existing_tickers)
        else:
            yf_tickers = [f"{t}.NS" for t in existing_tickers]
            dfs = _chunked_download(yf_tickers, start=start.strftime("%Y-%m-%d"), interval="1d",
                                      group_by="ticker", progress=progress)
            need_recovery = []
            for t in existing_tickers:
                df = dfs.get(t, pd.DataFrame())
                new_df = df.dropna(subset=["Close"]) if not df.empty else df  # see new_tickers branch above
                new_df = new_df[(new_df.index > last_dates[t]) & (new_df.index <= safe_today)] if not new_df.empty else new_df
                dfs[t] = new_df
                # only chase a recovery if this ticker is actually behind safe_today AND
                # didn't already get it — a shared batch start date (the minimum across
                # the whole existing_tickers batch) means even ONE stale ticker widens
                # the request for everyone, so this can affect tickers that were only
                # one day behind too, not just the straggler that caused the wide range
                if last_dates[t] < safe_today and (new_df.empty or new_df.index.max() < safe_today):
                    need_recovery.append(t)
            for t, extra in _recover_safe_today(need_recovery, safe_today).items():
                dfs[t] = pd.concat([dfs[t], extra]) if not dfs[t].empty else extra

            # honest retry pass: a ticker that's genuinely behind safe_today but still came
            # back empty gets ONE more chunked attempt before being called 'stale' rather
            # than silently folded into 'current' — this is the exact bug that hid 198
            # stragglers earlier tonight, fixed at the source instead of worked around again.
            #
            # GATED on any_real_update in this SAME batch, not attempted unconditionally —
            # caught in testing (2026-09-29): a genuine weekend/holiday means EVERY ticker
            # in the batch legitimately has nothing new, and retrying would just relabel
            # correct 'current' results as false-positive 'stale'. The real failure this
            # project hit was a MIXED result (501/702 tickers updated, 198 silently didn't,
            # same batch, same date range) — implausible for a real market-wide non-trading
            # day, since stock-specific halts affecting 28% of the universe at once don't
            # happen. Only chase 'stale' when at least one ticker in this batch DID get
            # real data, which rules out "nobody traded" as the explanation for the rest.
            any_real_update = any(not dfs[t].empty for t in existing_tickers)
            suspect = [t for t in existing_tickers if last_dates[t] < safe_today and dfs[t].empty] if any_real_update else []
            if suspect:
                retry_start = min(last_dates[t] for t in suspect) + timedelta(days=1)
                retry_dfs = _chunked_download([f"{t}.NS" for t in suspect], start=retry_start.strftime("%Y-%m-%d"),
                                                interval="1d", group_by="ticker")
                for t in suspect:
                    df = retry_dfs.get(t, pd.DataFrame())
                    if df.empty:
                        continue
                    df = df.dropna(subset=["Close"])
                    df = df[(df.index > last_dates[t]) & (df.index <= safe_today)]
                    if not df.empty:
                        dfs[t] = df

            for t in existing_tickers:
                new_df = dfs[t]
                if not new_df.empty:
                    new_df.to_csv(CACHE_DIR / f"{t}.csv", mode="a", header=False)
                    result["updated"].append(t)
                elif last_dates[t] < safe_today and any_real_update:
                    result["stale"].append(t)  # behind, others in this batch DID get real data, still nothing — real failure
                else:
                    result["current"].append(t)  # already caught up, or nobody in the batch had anything new (weekend/holiday)

    return result


if __name__ == "__main__":
    # 2026-10-03: fetchers fetch EVERYTHING by default -- the full NSE equity universe
    # (nse_equity_universe.csv, ~2,300 names, plus any Nifty 500 name not in it). Each strategy
    # picks its own universe at read time (daily_scan.py still scans nifty500_universe.csv).
    # `--universe nifty500` restores the old Nifty-500-only pull. See data/README.md.
    import sys
    n500 = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    if "--universe" in sys.argv and sys.argv[sys.argv.index("--universe") + 1] == "nifty500":
        tickers = n500
    else:
        rest = pd.read_csv("nse_equity_universe.csv")["ticker"].tolist()
        tickers = n500 + [t for t in rest if t not in set(n500)]
    result = fetch_all(tickers, progress="--progress" in sys.argv)
    print(f"{len(result['new'])} new, {len(result['updated'])} updated, "
          f"{len(result['current'])} already current, "
          f"{len(result['stale'])} stale (retried, still failed): {result['stale']}, "
          f"{len(result['empty'])} empty/no-data: {result['empty']}")
