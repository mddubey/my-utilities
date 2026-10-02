#!/usr/bin/env bash
# End-of-day checklist (2026-09-03): sequences the existing standalone refresh/scan
# scripts — no logic duplicated here, this is just the order to run them in after
# market close. fetch_prices.py, intraday_cache.py, and daily_scan.py already default
# to the full nifty500_universe.csv when run with no args.
#
# 2026-09-08: added step 1b (market_regime.py) after state_validator.py's first
# real run caught _NIFTY.csv silently 8 calendar days stale -- market_regime.py's
# refresh() was always a standalone "run when stale" script, never wired into this
# checklist, so nothing was ever reminding anyone to run it. Today's regime-gate
# answer happened to come out the same either way (Nifty's been under its 200-SMA
# since Feb 26 regardless), but the ADX sub-check alone flipped 15.4->21.7 across
# the same stale/fresh gap -- a real risk on any day closer to a flip, not just a
# theoretical one.
set -e
cd "$(dirname "$0")"

echo "== 1/6: refreshing daily cache (full universe) =="
python3 fetch_prices.py

echo
echo "== 1b/6: refreshing Nifty regime cache =="
python3 market_regime.py

# 2026-10-02: the intraday research scan (intradaygeeks_replica/38_alarm_scan_1h_close.py) reads daily data
# for all ~2,300 NSE equity names, but step 1 only refreshes the Nifty 500 -- the other ~1,800 were going
# stale. Step 1c tops them up through fetch_prices.fetch_all() (same chunked download + retry, incremental,
# so only missing days are fetched). Nothing in daily_scan.py's own scope changes.
echo
echo "== 1c/6: refreshing daily cache for the rest of the NSE equity universe =="
python3 -c "
import pandas as pd, fetch_prices
n500 = set(pd.read_csv('nifty500_universe.csv', header=None)[0])
rest = [t for t in pd.read_csv('nse_equity_universe.csv').ticker if t not in n500]
r = fetch_prices.fetch_all(rest, progress=True)
print(f\"{len(r['new'])} new, {len(r['updated'])} updated, {len(r['current'])} current, {len(r['stale'])} stale, {len(r['empty'])} empty\")
"

# Space out the two big Yahoo pulls (daily ~1,800 + 5m ~2,300 tickers) instead of hitting it back to back.
sleep 60

echo
echo "== 2/6: refreshing intraday 5m cache (full NSE equity universe, ~2,300 tickers) =="
python3 intraday_cache.py --universe nse_equity

echo
echo "== 3/6: pattern scan =="
python3 daily_scan.py

echo
echo "== 4/6: open positions — fresh stop/target =="
if [ -f positions.csv ]; then
    tail -n +2 positions.csv | while IFS=, read -r ticker pattern entry_date entry_price; do
        [ -z "$ticker" ] && continue
        python3 monitor_position.py "$ticker" "$pattern" "$entry_date" "$entry_price"
        echo
    done
else
    echo "  no positions.csv yet — add rows as ticker,pattern,entry_date,entry_price"
fi

echo
echo "== 5/6: tomorrow's candidates (+1% trigger watchlist) =="
python3 tomorrow_candidates.py
