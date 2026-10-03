#!/usr/bin/env bash
# End-of-day checklist -- ONE command after the close, two separate parts (restructured 2026-10-03):
#
#   PART A -- DATA     data/refresh.sh: refresh every dataset that must stay current, then a health check
#                      (data/check.py) that says per dataset whether it holds the latest real NSE session.
#                      Shared by every system; can also be run on its own.
#   PART B -- TRADING  the trading routines that read that data. Runs only if Part A's critical datasets
#                      (daily Nifty 500 prices, Nifty regime file) are current -- a stale scan is worse than none.
#                      Add a new system's EOD routine as its own block here (e.g. intraday shorts prep).
#
# History: 2026-09-03 first version (sequenced standalone scripts); 2026-09-08 added the Nifty regime refresh after
# state_validator.py caught _NIFTY.csv 8 days stale; 2026-10-02 full NSE equity universe; 2026-10-03 data moved to
# data/ (data/README.md), split into the two parts above, and the open-positions step fixed (it looked for
# positions.csv / monitor_position.py, which don't exist, so it silently never ran).
cd "$(dirname "$0")"

echo "################ PART A -- DATA ################"
./data/refresh.sh
if [ $? -ne 0 ]; then
    echo
    echo "PART A FAILED: a critical dataset is not current (see the DATA HEALTH table above and data/logs/)."
    echo "PART B (trading) skipped -- fix the data and re-run ./eod_checklist.sh (fetchers skip what's already current)."
    exit 1
fi

set -e
echo
echo "################ PART B -- TRADING ################"

echo
echo "== Primed BC 1/3: pattern scan =="
python3 daily_scan.py

echo
echo "== Primed BC 2/3: open positions -- fresh stop/target (open_positions.csv) =="
python3 trader_dashboard.py night

echo
echo "== Primed BC 3/3: tomorrow's candidates (+1% trigger watchlist) =="
python3 tomorrow_candidates.py
