#!/usr/bin/env bash
# EOD data refresh -- Part A of eod_checklist.sh (2026-10-03). Can also be run on its own.
# Refreshes every dataset that must stay current, then runs the health check (data/check.py).
# Each step runs on its own: one fetcher failing does not stop the others. Every fetcher skips stocks that
# already hold the latest real NSE session, so weekend/holiday runs take seconds.
# Exit code = the health check's: 1 if a critical dataset (daily Nifty 500 prices, Nifty regime) is not current.
# Log: data/logs/refresh_YYYYMMDD_HHMM.log. Datasets refreshed by hand are listed in data/README.md.
cd "$(dirname "$0")/.."
mkdir -p data/logs
LOG="data/logs/refresh_$(date +%Y%m%d_%H%M).log"
FAILED=()

step() {   # step "label" command...
    local label="$1"; shift
    echo; echo "== data: $label =="
    local t0=$SECONDS
    if "$@"; then echo "   ok ($((SECONDS - t0))s)"; else echo "   FAILED (exit $?, $((SECONDS - t0))s) -- continuing"; FAILED+=("$label"); fi
}

{
    echo "EOD data refresh started $(date '+%Y-%m-%d %H:%M:%S %Z')"
    step "1/5 daily prices, full NSE equity universe" python3 fetch_prices.py --progress
    step "2/5 Nifty daily + regime indicators" python3 market_regime.py
    step "3/5 5-min bars, full universe" python3 intraday_cache.py
    step "4/5 Nifty/BankNifty intraday" python3 data/fetch_index_intraday.py
    step "5/5 60-min bars top-up" python3 data/fetch_intraday_60m.py 0 1 10d --topup
    [ ${#FAILED[@]} -gt 0 ] && echo && echo "steps that failed: ${FAILED[*]}"
    python3 data/check.py
    rc=$?
    echo "EOD data refresh finished $(date '+%Y-%m-%d %H:%M:%S %Z'), health check exit $rc"
    exit $rc
} 2>&1 | grep --line-buffered -v -i "NotOpenSSLWarning\|warnings.warn(" | tee "$LOG"
exit ${PIPESTATUS[0]}
