"""1-hour OHLCV bars built from intraday_cache's 5-minute bars.

Bins are anchored at the NSE open (09:15 IST) and never straddle a session, so
the bars line up with what a broker chart or Dhan's 60-minute endpoint shows:
09:15, 10:15, 11:15, 12:15, 13:15, 14:15 and, where the session runs to 15:30, a
15-minute stub at 15:15. Every bar carries `n_bars` (5-min bars actually
aggregated) and `complete` (all expected 5-min bars were present) so downstream
research can see exactly where yfinance left holes instead of silently trusting
a thin bar.

Session close is per ticker and per date. Since the Closing Auction Session
(CAS, 2026-08-03, Phase 1 = F&O names) continuous trading for F&O stocks ends at
15:15; the 15:15-15:35 window is a call auction, reference-only under the OX1
Continuous Trading Rule (FINDINGS.md). For those sessions the day is exactly six
full hourly bins, there is no stub, and any 5-min bar at or after 15:15 is
auction residue and is dropped rather than aggregated.

The whole point of this layer is the swing_qs Stage A question — does the
intermediate timeframe show structure the daily bars aggregate away — so this
module only reshapes data. It computes no swings, no levels, no features.
"""
import argparse
from pathlib import Path

import pandas as pd

from intraday_cache import CACHE_DIR as CACHE_5M_DIR

TZ = "Asia/Kolkata"
SESSION_OPEN = "09:15"
BIN_MINUTES = 60
BAR_MINUTES = 5
FULL_SESSION_MINUTES = 375  # 09:15 -> 15:30
CAS_SESSION_MINUTES = 360   # 09:15 -> 15:15, F&O names from CAS_START
CAS_START = pd.Timestamp("2026-08-03").date()
STUB_START_MINUTE = (FULL_SESSION_MINUTES // BIN_MINUTES) * BIN_MINUTES  # 360 -> 15:15
PROJECT_DIR = Path(__file__).parent
CACHE_1H_DIR = PROJECT_DIR / "intraday_cache_1h"
FO_UNIVERSE = set(pd.read_csv(PROJECT_DIR / "fo_universe.csv", header=None)[0].tolist())

COLUMNS = ["Open", "High", "Low", "Close", "Volume", "n_bars", "expected_bars", "complete",
           "session", "session_close"]
_AGG = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
_STUB_MODES = ("separate", "merge", "drop")


def resample_1h(df, stub="separate", ticker=None, fo=None):
    """df: 5-min OHLCV with a tz-aware DatetimeIndex (UTC as cached, or IST).
    Returns 1H bars indexed by IST bar-open time, plus `session` (date),
    `session_close` ("15:30" or "15:15"), `n_bars`, `expected_bars`, `complete`.

    fo: whether the instrument is in CAS scope (F&O). Explicit value wins; otherwise
    resolved from `ticker` against fo_universe.csv; with neither, treated as not F&O.
    stub: what to do with a 15:15-15:30 tail — "separate" keeps it as its own 3-bar
    bin (chart/Dhan convention), "merge" folds it into the 14:15 bar, "drop" discards it."""
    if stub not in _STUB_MODES:
        raise ValueError(f"stub must be one of {_STUB_MODES}, got {stub!r}")
    if df.empty:
        return _empty_frame()
    in_cas_scope = _resolve_fo(ticker, fo)

    ist = df.tz_convert(TZ).sort_index()
    session = ist.index.normalize()
    minute_of_session = ((ist.index - session).total_seconds() // 60).astype(int) - _open_minute()
    if (minute_of_session < 0).any():
        raise ValueError("bar before session open (09:15 IST) — not NSE cash-session data")
    if (minute_of_session >= FULL_SESSION_MINUTES).any():
        raise ValueError("bar at or after 15:30 IST — not NSE cash-session data")

    session_minutes = pd.Series(
        [_session_minutes(d.date(), in_cas_scope) for d in session], index=ist.index)
    continuous = minute_of_session < session_minutes.to_numpy()

    work = ist.loc[continuous, list(_AGG)].copy()
    work["session"] = session[continuous].tz_localize(None)
    work["session_minutes"] = session_minutes[continuous].to_numpy()
    work["bin_start"] = _bin_start_minute(minute_of_session[continuous], stub)

    grouped = work.groupby(["session", "session_minutes", "bin_start"], sort=True)
    out = grouped.agg(_AGG)
    out["n_bars"] = grouped.size()
    out = out.reset_index()
    if stub == "drop":
        out = out[out.bin_start < STUB_START_MINUTE]
    out["expected_bars"] = [
        _expected_bars(b, m, stub) for b, m in zip(out.bin_start, out.session_minutes)]
    out["complete"] = out.n_bars == out.expected_bars
    out["session_close"] = out.session_minutes.map(_close_label)
    out.index = pd.DatetimeIndex(
        out.session + pd.to_timedelta(out.bin_start + _open_minute(), unit="m"), name="Datetime"
    ).tz_localize(TZ)
    out["session"] = out.session.dt.date
    return out[COLUMNS]


def resample_session_1h(df, stub="separate", ticker=None, fo=None):
    """Same as resample_1h, for callers that already hold a single session's bars."""
    return resample_1h(df, stub=stub, ticker=ticker, fo=fo)


def load_1h(ticker):
    path = CACHE_1H_DIR / f"{ticker}.csv"
    if not path.exists():
        raise FileNotFoundError(f"no 1H cache for {ticker} — run resample_1h.py")
    df = pd.read_csv(path, index_col="Datetime", parse_dates=True)
    df.index = df.index.tz_convert(TZ)
    df["session"] = pd.to_datetime(df.session).dt.date
    return df


def build_cache(tickers=None, stub="separate"):
    """Resample every cached ticker (or the given list) into CACHE_1H_DIR."""
    CACHE_1H_DIR.mkdir(exist_ok=True)
    if tickers is None:
        tickers = sorted(p.stem for p in CACHE_5M_DIR.glob("*.csv"))
    written, skipped = [], []
    for t in tickers:
        src = CACHE_5M_DIR / f"{t}.csv"
        if not src.exists():
            skipped.append((t, "no 5m cache"))
            continue
        five = pd.read_csv(src, index_col="Datetime", parse_dates=True)
        if five.empty:
            skipped.append((t, "empty 5m cache"))
            continue
        try:
            out = resample_1h(five, stub=stub, ticker=t)
        except ValueError as e:
            skipped.append((t, str(e)))
            continue
        out.to_csv(CACHE_1H_DIR / f"{t}.csv")
        written.append(t)
    return written, skipped


def _resolve_fo(ticker, fo):
    if fo is not None:
        return bool(fo)
    return ticker in FO_UNIVERSE if ticker is not None else False


def _session_minutes(session_date, in_cas_scope):
    if in_cas_scope and session_date >= CAS_START:
        return CAS_SESSION_MINUTES
    return FULL_SESSION_MINUTES


def _close_label(session_minutes):
    total = _open_minute() + int(session_minutes)
    return f"{total // 60:02d}:{total % 60:02d}"


def _open_minute():
    h, m = SESSION_OPEN.split(":")
    return int(h) * 60 + int(m)


def _bin_start_minute(minute_of_session, stub):
    starts = (minute_of_session // BIN_MINUTES) * BIN_MINUTES
    if stub == "merge":
        starts = starts.where(starts < STUB_START_MINUTE, STUB_START_MINUTE - BIN_MINUTES)
    return starts


def _expected_bars(bin_start, session_minutes, stub):
    full = BIN_MINUTES // BAR_MINUTES
    stub_bars = max(0, (int(session_minutes) - STUB_START_MINUTE) // BAR_MINUTES)
    if bin_start == STUB_START_MINUTE:
        return stub_bars
    if stub == "merge" and bin_start == STUB_START_MINUTE - BIN_MINUTES:
        return full + stub_bars
    return full


def _empty_frame():
    return pd.DataFrame(columns=COLUMNS, index=pd.DatetimeIndex([], name="Datetime", tz=TZ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the 1H cache from intraday_cache 5-min bars.")
    parser.add_argument("tickers", nargs="*", help="subset of tickers; default = every cached ticker")
    parser.add_argument("--stub", choices=_STUB_MODES, default="separate")
    args = parser.parse_args()
    written, skipped = build_cache(args.tickers or None, stub=args.stub)
    print(f"written {len(written)} tickers to {CACHE_1H_DIR}")
    for t, why in skipped:
        print(f"skipped {t}: {why}")
