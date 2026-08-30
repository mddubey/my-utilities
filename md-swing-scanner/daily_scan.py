"""Run once/day, after refreshing data_cache (`python3 fetch_prices.py`) and the Nifty
regime cache (`python3 market_regime.py`) for today. Scans the full NIFTY 500 universe
(the pure-swing default, see relative_strength.py's UNIVERSE_FILE comment) for a NEW
entry signal as of the latest cached trading day — reuses backtest.py's detect_entry()
directly, so this can never drift from what the validated backtest actually tested."""
import pandas as pd

from backtest import load, detect_entry, resistance_target
from pivots import weekly_pivots


def scan(tickers):
    candidates = []
    scan_date = None
    for ticker in tickers:
        try:
            df = load(ticker, weekly_pivots)
        except FileNotFoundError:
            continue
        rows = df.reset_index()
        if len(rows) == 0:
            continue
        i = len(rows) - 1
        row = rows.iloc[i]
        scan_date = row.Date
        if row.corp_action_day:
            continue  # today's own data looks like a corporate-action glitch — skip
        result = detect_entry(ticker, rows, i)
        if result is None:
            continue
        pattern, structural_low = result
        target = resistance_target(row.Close, row)
        candidates.append(dict(
            ticker=ticker, pattern=pattern, close=row.Close, target=target,
            structural_low=structural_low,
        ))
    return scan_date, candidates


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    scan_date, candidates = scan(tickers)
    print(f"scan date: {scan_date.date() if scan_date is not None else 'no data'}")
    if not candidates:
        print("no candidates today")
    for c in candidates:
        target_str = f"₹{c['target']:.2f}" if c['target'] is not None else "n/a"
        print(f"  {c['ticker']:<14} {c['pattern']:<14} close=₹{c['close']:.2f}  target={target_str}")
