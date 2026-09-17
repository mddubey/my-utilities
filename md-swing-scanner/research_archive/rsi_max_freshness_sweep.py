"""Isolated research only (2026-09-13). Does layering freshness (built partly from RSI
itself) on top of the existing base_filters_pass RSI ceiling change where the optimal
RSI_MAX sits? RSI_MAX=80 was validated in isolation (2026-09-01, full v27 500-stock/5yr
backtest, concentration-plateau sweep) before freshness existed. Re-sweeps RSI_MAX
(68/72/75/80/85/90/100) on the SAME full long-history population (not the narrow
intraday-cache window used for most of today's other work, to avoid a regime-specific
overfit), reporting both the raw population at each threshold AND the freshness-top-40%
subset at each threshold -- if freshness already absorbs the RSI ceiling's job, the
freshness-filtered numbers should barely move across RSI_MAX values; if not, they should
still shift, telling us which direction (if any) the original threshold should move.

Reuses live_equivalent_population.py's exact real-gate mechanism (base_filters_pass +
intraday High cross via daily OHLC, no intraday_cache dependency -- full multi-year
history usable), full nifty500 universe to match RSI_MAX's original validation scope.
"""
import time
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from live_checkpoint import _percentile_from_breaks, RSI_PCT_BREAKS, MOMENTUM_PCT_BREAKS

TRIGGER_CLEARANCE = 1.005
RSI_MAX_CANDIDATES = [68, 72, 75, 80, 85, 90, 100]


def freshness(rsi14, mom20):
    if pd.isna(rsi14) or pd.isna(mom20):
        return None
    rsi_pct = _percentile_from_breaks(rsi14, RSI_PCT_BREAKS)
    mom_pct = _percentile_from_breaks(mom20, MOMENTUM_PCT_BREAKS)
    return 0.5 * rsi_pct + 0.5 * mom_pct


def run():
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    print(f"Loading full daily history for {len(tickers)} tickers (cached once, reused across all RSI_MAX values)...")
    cache = {}
    for t in tickers:
        try:
            cache[t] = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
    print(f"loaded {len(cache)} tickers\n")

    def simulate_swing(rows, entry_i, entry_price):
        state = dict(entry_price=entry_price, peak_close=entry_price, peak_high=entry_price,
                      structural_low=0.0, target=None)
        for j in range(entry_i + 1, len(rows)):
            row = rows.iloc[j]
            if row.corp_action_day:
                return state["peak_close"]
            exit_reason, state = backtest.check_exit("breakout_cont", state, row, use_resistance=True)
            if exit_reason is not None:
                return row.Close
        return rows.iloc[-1].Close

    original_rsi_max = signals.RSI_MAX
    results_by_threshold = {}
    n_tickers = len(cache)

    for thresh_idx, rsi_max in enumerate(RSI_MAX_CANDIDATES, 1):
        signals.RSI_MAX = rsi_max
        trades = []
        t0 = time.time()
        for ticker_idx, (t, rows) in enumerate(cache.items(), 1):
            if ticker_idx % 100 == 0 or ticker_idx == n_tickers:
                elapsed = time.time() - t0
                rate = ticker_idx / elapsed if elapsed else 0
                eta = (n_tickers - ticker_idx) / rate if rate else 0
                print(f"    [RSI_MAX {thresh_idx}/{len(RSI_MAX_CANDIDATES)}={rsi_max}] "
                      f"{ticker_idx}/{n_tickers} tickers  ({elapsed:.0f}s elapsed, ~{eta:.0f}s left this threshold)",
                      flush=True)
            for i in range(len(rows) - 1):
                row = rows.iloc[i]
                if row.corp_action_day or pd.isna(row.high10_prior):
                    continue
                trigger = row.high10_prior * TRIGGER_CLEARANCE
                if row.High < trigger:
                    continue
                if not signals.base_filters_pass(row):
                    continue
                day1_open = rows.iloc[i + 1].Open
                opt_pnl = (day1_open / trigger - 1) * 100
                swing_exit = simulate_swing(rows, i, trigger)
                swing_pnl = (swing_exit / trigger - 1) * 100
                yday = rows.iloc[i - 1] if i > 0 else None
                yday_mom20 = ((yday.Close / yday.close_20ago - 1) * 100
                              if yday is not None and pd.notna(yday.close_20ago) and yday.close_20ago else None)
                fscore = freshness(yday.rsi14 if yday is not None else None, yday_mom20)
                trades.append(dict(ticker=t, entry_date=row.Date, opt_pnl_pct=opt_pnl, swing_pnl_pct=swing_pnl,
                                    freshness_score=fscore, rsi14=row.rsi14))
        results_by_threshold[rsi_max] = pd.DataFrame(trades)
        results_by_threshold[rsi_max].to_csv(f"runs/rsi_max_sweep_{rsi_max}.csv", index=False)

    signals.RSI_MAX = original_rsi_max  # restore

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

    def print_both(sub, prefix):
        n, o_win, o_med, o_exp = stats(sub, "opt_pnl_pct")
        _, s_win, s_med, s_exp = stats(sub, "swing_pnl_pct")
        print(f"{prefix} n={n:<7} OPTIONS win {o_win:5.1f}% med {o_med:+.2f}% exp {o_exp:+.3f}%   |   "
              f"SWING win {s_win:5.1f}% med {s_med:+.2f}% exp {s_exp:+.3f}%")

    print("=== RAW population (no freshness applied), by RSI_MAX -- the real eligibility-gate revalidation (RQ-34) ===")
    for rsi_max in RSI_MAX_CANDIDATES:
        sub = results_by_threshold[rsi_max]
        print_both(sub, f"  RSI_MAX={rsi_max:<4}")
        o_conc = concentration(sub, "opt_pnl_pct")
        s_conc = concentration(sub, "swing_pnl_pct")
        print(f"      concentration: OPTIONS top-10={o_conc:.1f}%   SWING top-10={s_conc:.1f}%")

    print("\n=== FRESHNESS TOP-40% subset (fixed relative cut within each threshold's own population) ===")
    for rsi_max in RSI_MAX_CANDIDATES:
        df = results_by_threshold[rsi_max].dropna(subset=["freshness_score"])
        cut = df.freshness_score.quantile(0.40)
        sub = df[df.freshness_score <= cut]
        print_both(sub, f"  RSI_MAX={rsi_max:<4}")

    print("\n=== Marginal trades unlocked between adjacent thresholds ===")
    for lo, hi in zip(RSI_MAX_CANDIDATES, RSI_MAX_CANDIDATES[1:]):
        df_lo = results_by_threshold[lo]
        df_hi = results_by_threshold[hi]
        key_lo = set(zip(df_lo.ticker, df_lo.entry_date))
        marginal = df_hi[~df_hi.apply(lambda r: (r.ticker, r.entry_date) in key_lo, axis=1)]
        if marginal.empty:
            print(f"  {lo}->{hi}: no marginal trades")
            continue
        print_both(marginal, f"  {lo}->{hi}: {len(marginal)} new, ALL:")
        marginal_f = marginal.dropna(subset=["freshness_score"])
        if not marginal_f.empty:
            cut = df_hi.freshness_score.quantile(0.40)
            marg_fresh = marginal_f[marginal_f.freshness_score <= cut]
            if len(marg_fresh):
                print_both(marg_fresh, f"        of those, freshness-top-40% ({len(marg_fresh)}):")


if __name__ == "__main__":
    run()
