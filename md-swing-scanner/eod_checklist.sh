#!/usr/bin/env bash
# End-of-day checklist (2026-09-03): sequences the existing standalone refresh/scan
# scripts — no logic duplicated here, this is just the order to run them in after
# market close. fetch_prices.py, intraday_cache.py, and daily_scan.py already default
# to the full nifty500_universe.csv when run with no args.
set -e
cd "$(dirname "$0")"

echo "== 1/5: refreshing daily cache (full universe) =="
python3 fetch_prices.py

echo
echo "== 2/5: refreshing intraday 5m cache (full universe) =="
python3 intraday_cache.py

echo
echo "== 3/5: pattern scan =="
python3 daily_scan.py

echo
echo "== 4/5: open positions — fresh stop/target =="
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
echo "== 5/5: tomorrow's candidates (+1% trigger watchlist) =="
python3 tomorrow_candidates.py
