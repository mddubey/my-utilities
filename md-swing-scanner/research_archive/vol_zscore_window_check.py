"""Isolated research only (2026-09-13). RQ-34, 4th item: does VOL_ZSCORE_WINDOW (currently
8, adopted 2026-08-31 on a joint sweep for both patterns) still hold up as the best window
now that vol_zscore is only usable POST-HOC (as an options-side confidence signal, per the
RSI_MAX/LAST_LEG_TOLERANCE/VCP_VOL_ZSCORE_MIN revalidation) rather than as a live entry gate?
Recomputes vol_zscore with several window lengths (matching signals.py's exact formula:
Volume.shift(1).rolling(WINDOW).mean()/.std(), no lookahead) for both the breakout_cont
(RSI_MAX=80) and VCP (tol=0.4) live-equivalent populations already saved, checking which
window gives the cleanest options-side win-rate discrimination.
"""
import time
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots

WINDOW_CANDIDATES = [30, 32, 34, 35, 36, 38, 40]


def vol_zscore_for_window(df, window):
    vol_prior = df.Volume.shift(1).rolling(window)
    mean = vol_prior.mean()
    std = vol_prior.std()
    return (df.Volume - mean) / std


def check_population(pop_path, label):
    pop = pd.read_csv(pop_path, parse_dates=["entry_date"])
    print(f"\n{'='*20} {label} (n={len(pop)}) {'='*20}")

    cache = {}
    zscores_by_window = {w: [] for w in WINDOW_CANDIDATES}
    t0 = time.time()
    for idx, r in enumerate(pop.itertuples(), 1):
        if idx % 500 == 0 or idx == len(pop):
            print(f"  {idx}/{len(pop)}  ({time.time()-t0:.0f}s elapsed)", flush=True)
        if r.ticker not in cache:
            cache[r.ticker] = backtest.load(r.ticker, daily_pivots).reset_index()
        rows = cache[r.ticker]
        match = rows.index[rows.Date == r.entry_date]
        if len(match) == 0:
            for w in WINDOW_CANDIDATES:
                zscores_by_window[w].append(None)
            continue
        i = match[0]
        for w in WINDOW_CANDIDATES:
            key = (r.ticker, w)
            if key not in cache:
                cache[key] = vol_zscore_for_window(rows, w)
            vz_series = cache[key]
            zscores_by_window[w].append(vz_series.iloc[i] if i < len(vz_series) else None)

    for w in WINDOW_CANDIDATES:
        pop[f"vz_{w}"] = zscores_by_window[w]

    out_path = pop_path.replace(".csv", "_vzwindows.csv")
    pop.to_csv(out_path, index=False)

    print(f"\n  --- correlation(real vol_zscore@window, OPTIONS pnl) ---")
    for w in WINDOW_CANDIDATES:
        sub = pop.dropna(subset=[f"vz_{w}", "opt_pnl_pct"])
        corr = sub[f"vz_{w}"].corr(sub.opt_pnl_pct)
        rank_corr = sub[f"vz_{w}"].rank().corr(sub.opt_pnl_pct.rank())
        hi = sub[sub[f"vz_{w}"] >= 1.5]
        lo = sub[sub[f"vz_{w}"] < 1.5]
        hi_win = (hi.opt_pnl_pct > 0).mean() * 100 if len(hi) else float("nan")
        lo_win = (lo.opt_pnl_pct > 0).mean() * 100 if len(lo) else float("nan")
        print(f"  window={w:<3} n={len(sub):<5} pearson={corr:+.3f}  spearman={rank_corr:+.3f}  "
              f"win@>=1.5: {hi_win:.1f}% (n={len(hi)})  win@<1.5: {lo_win:.1f}% (n={len(lo)})  gap={hi_win-lo_win:+.1f}pp")


if __name__ == "__main__":
    check_population("runs/vcp_live_equiv_tol_0.4.csv", "VCP (tol=0.4)")
