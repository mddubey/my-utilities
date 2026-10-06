"""RQ-EMAPB-01 step 1 -- for each volume-confirmed, 10-day-lookback A (reused from
swing_qs_bpc/rq_bpc05_a_volume_diagnostics.csv, no lookback-mixing), find the first EMA
touch (decision-time-safe) within a 20-day window, for EMA8/20/50 separately, and measure
the forward price path after the touch vs. a fixed-offset baseline bar. See
RQ-EMAPB-01_SPEC_PREFLIGHT.md for every convention. Usage:
  python3 swing_qs_emapb/01_build_touch_panel.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

from backtest import load, daily_pivots

HERE = os.path.dirname(os.path.abspath(__file__))
EMA_PERIODS = (8, 20, 50)
WINDOW_DAYS = 20
HORIZONS = (1, 3, 5, 10)
BASELINE_OFFSET = 10  # fixed midpoint of the 20-day window, independent of any touch
HOLD_M_LIST = (2, 3)      # consecutive touch-bars required for a "hold" -- robustness split
EXPAND_X_LIST = (1.5, 2.0)  # expansion bar range >= X * hold-phase average range


def forward_metrics(rows, i0, n):
    """Signed (long) forward return/MFE/MAE from rows.iloc[i0]'s Close, over the next n
    trading days -- cumulative growing window [i0+1 .. i0+n], same convention as
    options_momentum/. None if the window runs past the end of data or hits a corp action."""
    end = min(i0 + 1 + n, len(rows))
    if end - (i0 + 1) < n:
        return None
    span = rows.iloc[i0 + 1:end]
    if span.corp_action_day.any():
        return None
    c0 = rows.iloc[i0].Close
    ret = (span.Close.iloc[-1] / c0 - 1) * 100
    mfe = (span.High.max() / c0 - 1) * 100
    mae = (span.Low.min() / c0 - 1) * 100
    return dict(ret=ret, mfe=mfe, mae=mae)


def process_a(rows, ia, meta):
    out = dict(meta)
    n_rows = len(rows)
    end = min(ia + 1 + WINDOW_DAYS, n_rows)
    # stop the window at the first corp-action day, same convention as the rest of this project
    for k in range(ia + 1, end):
        if rows.iloc[k].corp_action_day:
            end = k
            break

    for N in EMA_PERIODS:
        ema = rows.Close.ewm(span=N, adjust=False).mean()
        is_touch = {}
        for k in range(ia + 1, end):
            row_k = rows.iloc[k]
            is_touch[k] = row_k.Low <= ema.iloc[k - 1] and row_k.Close >= ema.iloc[k]
        ks = sorted(is_touch)

        for M in HOLD_M_LIST:
            # first run of >= M consecutive touch-bars
            hold_start = hold_end = None
            run_start = None
            run_len = 0
            for k in ks:
                if is_touch[k]:
                    if run_start is None:
                        run_start = k
                    run_len += 1
                    if run_len >= M:
                        hold_start, hold_end = run_start, k
                        break
                else:
                    run_start, run_len = None, 0

            for X in EXPAND_X_LIST:
                tag = f"ema{N}_hold{M}_x{X}"
                if hold_start is None:
                    out[f"held_{tag}"] = False
                    out[f"expanded_{tag}"] = False
                    continue
                out[f"held_{tag}"] = True
                hold_rows = rows.iloc[hold_start:hold_end + 1]
                hold_avg_range = (hold_rows.High - hold_rows.Low).mean()
                exp_i = None
                for k in range(hold_end + 1, end):
                    row_k = rows.iloc[k]
                    if (row_k.High - row_k.Low) >= X * hold_avg_range and row_k.Close > row_k.Open:
                        exp_i = k
                        break
                out[f"expanded_{tag}"] = exp_i is not None
                out[f"days_to_expand_{tag}"] = (exp_i - ia) if exp_i is not None else None
                if exp_i is not None:
                    for h in HORIZONS:
                        m = forward_metrics(rows, exp_i, h)
                        if m:
                            out[f"{tag}_h{h}_ret"] = m["ret"]
                            out[f"{tag}_h{h}_mfe"] = m["mfe"]
                            out[f"{tag}_h{h}_mae"] = m["mae"]

    # baseline: fixed-offset bar, independent of any touch (same window, same ticker/A)
    base_i = ia + BASELINE_OFFSET
    if base_i < end:
        for h in HORIZONS:
            m = forward_metrics(rows, base_i, h)
            if m:
                out[f"baseline_h{h}_ret"] = m["ret"]
                out[f"baseline_h{h}_mfe"] = m["mfe"]
                out[f"baseline_h{h}_mae"] = m["mae"]
    return out


def main():
    pop = pd.read_csv("swing_qs_bpc/rq_bpc05_a_volume_diagnostics.csv")
    pop = pop[(pop.entry_definition == 10) & (pop.vol_ratio >= 1.5)]
    print(f"Population (10-day lookback only, A volume >= 1.5x): {len(pop):,}", flush=True)

    rows_cache, out_rows = {}, []
    for n, (ticker, grp) in enumerate(pop.groupby("ticker")):
        if n % 100 == 0:
            print(f"{n}/{pop.ticker.nunique()} tickers", flush=True)
        try:
            rows = rows_cache.setdefault(ticker, load(ticker, daily_pivots).reset_index())
        except FileNotFoundError:
            continue
        for r in grp.itertuples():
            ia = int(r.a_entry_i)
            if ia >= len(rows) or str(rows.iloc[ia].Date.date()) != r.a_entry_date:
                continue  # integrity check, same convention as 08_rq04b_anatomy.py
            meta = dict(ticker=ticker, a_entry_i=ia, a_entry_date=r.a_entry_date,
                        vol_ratio=r.vol_ratio)
            out_rows.append(process_a(rows, ia, meta))

    df = pd.DataFrame(out_rows)
    df.to_csv(f"{HERE}/rq_emapb01_panel.csv", index=False)
    print(f"\nSaved {len(df):,} rows -> rq_emapb01_panel.csv", flush=True)
    for N in EMA_PERIODS:
        for M in HOLD_M_LIST:
            for X in EXPAND_X_LIST:
                tag = f"ema{N}_hold{M}_x{X}"
                held = df[f"held_{tag}"].mean() * 100
                expanded_of_held = df.loc[df[f"held_{tag}"], f"expanded_{tag}"].mean() * 100 if df[f"held_{tag}"].any() else 0
                print(f"EMA{N} hold>={M} expand>={X}x: held {held:.1f}% of A's  |  of those, expanded: {expanded_of_held:.1f}%")


if __name__ == "__main__":
    main()
