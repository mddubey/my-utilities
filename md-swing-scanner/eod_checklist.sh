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

echo
echo "== 2/6: refreshing intraday 5m cache (full universe) =="
python3 intraday_cache.py

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
