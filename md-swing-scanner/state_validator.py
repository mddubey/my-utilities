"""Pre-flight state validator (2026-09-08) — the critic's proposed 5th integrity
gate ("does today's tool know today's reality?"), built after finding SIX real
live bugs so far, every one of them some version of "the tool didn't actually
have today's real state": stale pivot (high10_prior), missing extension-day
tracking, wrong pullback reference point, unnormalized volume-vs-normal,
unnormalized vol_zscore, and a disk-only RS-rating computation. Catches the
CLASS of problem, not one instance of it — run this BEFORE any live scan and
refuse to proceed on a real failure, instead of discovering the staleness
live, mid-investigation, the way every one of those six bugs actually got
found.

Deliberately scoped to DATA freshness only. The live-WIRING half of the
critic's checklist (volume baseline time-normalized, RS-rating live-aware,
etc.) is now structurally guaranteed by the code itself — daily_scan.py's
scan()/shortlist_primed_live() always thread cutoff_ist/live_closes through
when live=True, so there's nothing left for a separate runtime check to catch
there; the fix IS the check. What's still genuinely fragile is external: did
fetch_prices.py actually finish, recently, for (most of) the universe — that's
an operational fact this validator can check, not something the code can just
assert about itself."""
import json
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).parent / "data_cache"
PRIMED_CACHE_FILE = Path(__file__).parent / "primed_cache.json"
MAX_STALENESS_DAYS = 4  # comfortably covers a long weekend + one holiday


def _last_cached_date(ticker):
    path = CACHE_DIR / f"{ticker}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, usecols=["Date"], parse_dates=["Date"])
    if df.empty:
        return None
    return df.Date.max()


def check_data_cache_freshness(tickers):
    """FAIL if the majority of the universe's cache is stale beyond
    MAX_STALENESS_DAYS — catches a failed/incomplete fetch_prices.py run
    before any live scan trusts that data. This is the exact root cause
    category behind Bug 1 (stale high10_prior): the live tool read a cache
    that was further behind "today" than it assumed."""
    dates = [_last_cached_date(t) for t in tickers]
    dates = [d for d in dates if d is not None]
    if not dates:
        return dict(name="data_cache freshness", passed=False,
                     detail="no cached data found for any ticker at all")
    dates = pd.Series(dates)
    most_common_date = dates.mode().iloc[0]
    staleness = (pd.Timestamp.now().normalize() - most_common_date).days
    n_stale = int((dates < most_common_date).sum())
    passed = staleness <= MAX_STALENESS_DAYS
    detail = (f"most recent cached date across universe: {most_common_date.date()} "
              f"({staleness} calendar days old); {n_stale}/{len(dates)} tickers "
              f"behind that date")
    return dict(name="data_cache freshness", passed=passed, detail=detail)


def check_nifty_regime_freshness():
    """The Nifty regime gate (market_regime.py) reads _NIFTY.csv directly out
    of data_cache — a stale regime read would silently misjudge the ADX/200-
    SMA gate for every single candidate in the scan, not just one ticker, so
    it's checked on its own rather than folded into the universe-wide count."""
    date = _last_cached_date("_NIFTY")
    if date is None:
        return dict(name="Nifty regime cache freshness", passed=False,
                     detail="_NIFTY.csv missing or empty")
    staleness = (pd.Timestamp.now().normalize() - date).days
    passed = staleness <= MAX_STALENESS_DAYS
    return dict(name="Nifty regime cache freshness", passed=passed,
                 detail=f"_NIFTY.csv last date: {date.date()} ({staleness} calendar days old)")


def check_primed_cache_status():
    """Informational only, never fails the gate — reports whether --live is
    about to use a fresh --refresh-primed cache or fall back to yesterday-
    based shortlist_primed(), so a stale-but-still-valid fallback isn't
    mistaken for a bug when it shows up in the report."""
    if not PRIMED_CACHE_FILE.exists():
        return dict(name="primed_cache.json status", passed=True,
                     detail="no cache yet -- --live will fall back to yesterday-based shortlist_primed()")
    try:
        payload = json.loads(PRIMED_CACHE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return dict(name="primed_cache.json status", passed=True,
                     detail="cache unreadable -- --live will fall back to shortlist_primed()")
    is_today = payload.get("date") == str(pd.Timestamp.now().date())
    detail = (f"refreshed {payload.get('refreshed_at')} on {payload.get('date')} "
              f"({'today' if is_today else 'STALE, not today'}) -- "
              f"{'--live will use it' if is_today else '--live will fall back to shortlist_primed()'}")
    return dict(name="primed_cache.json status", passed=True, detail=detail)


def validate(tickers):
    """Runs all checks, returns (ok, results). ok is False only if a REAL
    (non-informational) check failed -- primed_cache status never fails it."""
    results = [
        check_data_cache_freshness(tickers),
        check_nifty_regime_freshness(),
        check_primed_cache_status(),
    ]
    ok = all(r["passed"] for r in results)
    return ok, results


def print_report(results):
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"  [{mark}] {r['name']}: {r['detail']}")
