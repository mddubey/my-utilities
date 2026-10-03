"""Data health check -- the last step of the EOD data refresh (2026-10-03).

For each dataset: does it hold the latest real NSE session (from Nifty's 60-min bars, see
fetch_prices._latest_nifty_session)? Prints one table and writes data/logs/last_check.json.
Exit code 1 if a CRITICAL dataset fails (what the trading part of the EOD checklist needs:
daily prices for the Nifty 500 and the Nifty regime file), else 0. Non-critical shortfalls are WARN.
Usage: python3 data/check.py"""
import json, sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fetch_prices import _latest_nifty_session, _safe_today, IST  # noqa: E402
from data.paths import (DAILY_DIR, INTRADAY_5M_DIR, INTRADAY_60M_DIR, INDEX_INTRADAY_DIR,  # noqa: E402
                        NSE_FO_BHAV_DIR, NSE_CASH_CLOSE_DIR, NSE_BHAV_DIR, NSE_BANDS_DIR,
                        NSE_CORP_ACTIONS_FILE, last_row_time, holds_full_session)

LOG_DIR = Path(__file__).resolve().parent / "logs"


def share(paths, ok):
    paths = [p for p in paths if p.exists()]
    good = sum(1 for p in paths if ok(p))
    return good, len(paths)


def main():
    session = _latest_nifty_session(pd.Timestamp(_safe_today()))
    source = "Nifty 60m"
    if session is None:   # lookup failed: fall back to the cached Nifty daily file
        session, source = last_row_time(DAILY_DIR / "_NIFTY.csv").normalize(), "cached _NIFTY.csv (lookup failed)"
    n500 = pd.read_csv(ROOT / "nifty500_universe.csv", header=None)[0].tolist()
    allu = pd.read_csv(ROOT / "nse_equity_universe.csv")["ticker"].tolist()
    daily_ok = lambda p: (last_row_time(p) or pd.Timestamp(0)).normalize() >= session

    rows = []
    def add(name, critical, good, total, need):
        pct = good / total * 100 if total else 0
        status = "PASS" if total and pct >= need else ("FAIL" if critical else "WARN")
        rows.append(dict(dataset=name, critical=critical, have=good, of=total, pct=round(pct, 1), need=need, status=status))

    g, t = share([DAILY_DIR / f"{x}.csv" for x in n500], daily_ok); add("daily prices, Nifty 500", True, g, t, 98)
    g, t = share([DAILY_DIR / f"{x}.csv" for x in allu], daily_ok); add("daily prices, all NSE equity", False, g, t, 95)
    g, t = share([DAILY_DIR / "_NIFTY.csv"], daily_ok); add("Nifty daily + regime", True, g, t, 100)
    g, t = share([INTRADAY_5M_DIR / f"{x}.csv" for x in allu], lambda p: holds_full_session(p, session)); add("5-min bars, all", False, g, t, 95)
    g, t = share([INTRADAY_60M_DIR / f"{x}.csv" for x in allu], lambda p: holds_full_session(p, session, "14:15")); add("60-min bars, all", False, g, t, 95)
    g, t = share(sorted(INDEX_INTRADAY_DIR.glob("*.csv")),
                 lambda p: (last_row_time(p) or pd.Timestamp(0, tz="UTC")).tz_convert(IST).normalize().tz_localize(None) >= session)
    add("index intraday (Nifty/BankNifty)", False, g, t, 100)

    print(f"\nDATA HEALTH -- latest NSE session {session.date()} (from {source}), checked {datetime.now(IST):%Y-%m-%d %H:%M} IST")
    print(f"{'dataset':36} {'status':6} {'have':>6} / {'of':<6} {'%':>6}  need")
    for r in rows:
        print(f"{r['dataset'] + (' *' if r['critical'] else ''):36} {r['status']:6} {r['have']:>6} / {r['of']:<6} {r['pct']:>6}  {r['need']}%")
    print("* = critical: the trading part of the EOD checklist stops if it fails")
    manual = {"nse_fo_bhav": NSE_FO_BHAV_DIR, "nse_cash_close": NSE_CASH_CLOSE_DIR, "nse_bhav": NSE_BHAV_DIR, "nse_bands": NSE_BANDS_DIR}
    print("manual datasets (not refreshed here), latest file: " + ", ".join(
        f"{k} {max((p.stem for p in v.glob('*.csv')), default='none')}" for k, v in manual.items())
        + f", nse_corp_actions {'present' if NSE_CORP_ACTIONS_FILE.exists() else 'missing'}")
    LOG_DIR.mkdir(exist_ok=True)
    ok = all(r["status"] != "FAIL" for r in rows)
    (LOG_DIR / "last_check.json").write_text(json.dumps(dict(checked_at=datetime.now(IST).isoformat(timespec="seconds"),
        session=str(session.date()), session_source=source, ok=ok, rows=rows), indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
