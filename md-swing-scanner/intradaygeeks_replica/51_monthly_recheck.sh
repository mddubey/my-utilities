#!/usr/bin/env bash
# Monthly re-check of the 30-min trigger short setup (scratch research only).
# Needs the 5m cache to have grown: run eod_checklist.sh daily (its intraday_cache.py step). For the full 2,300-stock
# universe the cache refresh must use `intraday_cache.py --universe nse_equity` (branch intraday-cache-chunked-download).
set -e
cd "$(dirname "$0")"
M=$(date +%Y-%m)
{
  echo "== recheck $M ($(date)) =="
  echo "-- topping up 1H cache (30d) --"
  python3 11_fetch_1h.py 0 1 30d --topup 2>&1 | grep -v -i "warn\|delisted\|failed download" | tail -2
  echo "-- 30-min alarm-time test over all available 5m data --"
  python3 43_alarm_times_30m.py 2>&1 | grep -v -i warn
  echo "-- live log so far --"
  cat live_watch_log.csv 2>/dev/null | wc -l | awk '{print $1-1 " logged trades"}'
} > "rechecks/recheck_$M.txt" 2>&1
echo "wrote rechecks/recheck_$M.txt"
