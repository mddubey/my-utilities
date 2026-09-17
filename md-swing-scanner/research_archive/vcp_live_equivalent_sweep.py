"""Isolated research only (2026-09-13). RQ-34 continued: revalidate VCP's LAST_LEG_TOLERANCE
on the live-equivalent population (structural base_pivot() + intraday High crossing the
pivot, no vol_zscore/Close-confirmation gate) instead of the original EOD-confirmed
backtest population. Same "Validation Population Drift" concern as RSI_MAX -- vcp_breakout()
gates on row.vol_zscore >= VCP_VOL_ZSCORE_MIN, an end-of-day-only quantity unknowable at the
moment a live intraday breach would fire, same structural issue as breakout_continuation's
vol_zscore gate.

Reuses base_pivot() directly (the structural, non-volume part of vcp_breakout(), no
lookahead) plus stage2_trend_template()/market_trending() (the real regime/trend gates),
sweeping LAST_LEG_TOLERANCE. VCP_VOL_ZSCORE_MIN itself isn't independently sweepable here in
a live-relevant way -- it can't be checked live at all, same as breakout_continuation's gate
-- so this asks the more honest question: does the STRUCTURAL pattern alone, without any
volume confirmation, still show real edge on the live-equivalent population.
"""
import time
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import vcp
from pivots import daily_pivots
from vcp import stage2_trend_template, base_pivot
from market_regime import market_trending

TRIGGER_CLEARANCE = 1.005
TOLERANCE_CANDIDATES = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0]


def simulate_swing(rows, entry_i, entry_price):
    state = dict(entry_price=entry_price, peak_close=entry_price, peak_high=entry_price,
                  structural_low=0.0, target=None)
    for j in range(entry_i + 1, len(rows)):
        row = rows.iloc[j]
        if row.corp_action_day:
            return state["peak_close"]
        exit_reason, state = backtest.check_exit("coiled_spring", state, row, use_resistance=True)
        if exit_reason is not None:
            return row.Close
    return rows.iloc[-1].Close


def run():
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    print(f"Loading full daily history for {len(tickers)} tickers...")
    cache = {}
    for t in tickers:
        try:
            cache[t] = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
    print(f"loaded {len(cache)} tickers\n")

    original_tol = vcp.LAST_LEG_TOLERANCE
    results_by_tol = {}
    n_tickers = len(cache)

    for tol_idx, tol in enumerate(TOLERANCE_CANDIDATES, 1):
        vcp.LAST_LEG_TOLERANCE = tol
        trades = []
        t0 = time.time()
        for ticker_idx, (t, rows) in enumerate(cache.items(), 1):
            if ticker_idx % 100 == 0 or ticker_idx == n_tickers:
                elapsed = time.time() - t0
                rate = ticker_idx / elapsed if elapsed else 0
                eta = (n_tickers - ticker_idx) / rate if rate else 0
                print(f"    [tol {tol_idx}/{len(TOLERANCE_CANDIDATES)}={tol}] "
                      f"{ticker_idx}/{n_tickers} tickers  ({elapsed:.0f}s elapsed, ~{eta:.0f}s left this threshold)",
                      flush=True)
            for i in range(30, len(rows) - 1):
                row = rows.iloc[i]
                if row.corp_action_day:
                    continue
                if not stage2_trend_template(row, t, row.Date):
                    continue
                if not market_trending(row.Date, require_above_sma200=True):
                    continue
                base = base_pivot(rows, i)
                if base is None:
                    continue
                pivot, structural_low = base
                if row.High < pivot * TRIGGER_CLEARANCE:
                    continue
                trigger = pivot * TRIGGER_CLEARANCE
                day1_open = rows.iloc[i + 1].Open
                opt_pnl = (day1_open / trigger - 1) * 100
                swing_exit = simulate_swing(rows, i, trigger)
                swing_pnl = (swing_exit / trigger - 1) * 100
                trades.append(dict(ticker=t, entry_date=row.Date, opt_pnl_pct=opt_pnl, swing_pnl_pct=swing_pnl))
        results_by_tol[tol] = pd.DataFrame(trades)
        results_by_tol[tol].to_csv(f"runs/vcp_live_equiv_tol_{tol}.csv", index=False)
        print(f"  tol={tol}: n={len(trades)}")

    vcp.LAST_LEG_TOLERANCE = original_tol  # restore

    def stats(sub, col):
        wins = sub[sub[col] > 0][col]
        losses = sub[sub[col] <= 0][col]
        wr = len(wins) / len(sub) if len(sub) else 0
        lr = len(losses) / len(sub) if len(sub) else 0
        exp = wr * (wins.mean() if len(wins) else 0) + lr * (losses.mean() if len(losses) else 0)
        return len(sub), wr * 100, sub[col].median() if len(sub) else float("nan"), exp

    def concentration(sub, col):
        total = sub[col].sum()
        if not total:
            return float("nan")
        top10 = sub[col].sort_values(ascending=False).head(10).sum()
        return top10 / total * 100

    print("\n=== LAST_LEG_TOLERANCE sweep, live-equivalent population (structural + intraday breach, no vol_zscore) ===")
    for tol in TOLERANCE_CANDIDATES:
        sub = results_by_tol[tol]
        if sub.empty:
            print(f"  tol={tol}: n=0")
            continue
        n, o_win, o_med, o_exp = stats(sub, "opt_pnl_pct")
        _, s_win, s_med, s_exp = stats(sub, "swing_pnl_pct")
        o_conc = concentration(sub, "opt_pnl_pct")
        s_conc = concentration(sub, "swing_pnl_pct")
        print(f"  tol={tol:<5} n={n:<6} OPTIONS win {o_win:5.1f}% med {o_med:+.2f}% exp {o_exp:+.3f}% conc {o_conc:5.1f}%   |   "
              f"SWING win {s_win:5.1f}% med {s_med:+.2f}% exp {s_exp:+.3f}% conc {s_conc:5.1f}%")


if __name__ == "__main__":
    run()
