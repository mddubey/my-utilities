"""RQ-64 (final, critic-revised form, 2026-09-18): holding-period trajectory
comparison, Delta Unique vs Common. Not breach/acceptance anatomy -- that was
the first proposal, revised after the direct observation that Unique Delta's
real options edge (63.2% win, day+1-open exit) means entry-through-day+1 is
already working well, which makes a "Delta has bad breach behavior" story less
likely. The cheaper, more direct diagnostic: does Delta's per-day return
trajectory diverge from Common's as the holding period extends (a short-duration
momentum population losing its edge by day 5-10), or does Delta's trajectory
stay strong through day 10-15 while the swing exit still under-extracts it
(an exit-fit problem)?

For each real trade (Common = EMA34>=9; Delta Unique = EMA34=2-only, EMA34>=9
never fires on the same ticker within 3 trading days, per RQ-56's own
definition), tracks close_pct/MFE/MAE at trading-day offsets 0/1/2/3/5/10, plus
% still profitable at each horizon.
"""
import warnings
warnings.filterwarnings("ignore")

import sys

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from breakout_failure_confirmation_cost import TRIGGER_CLEARANCE
from research.metrics import expectancy, win_rate

HORIZONS = [0, 1, 2, 3, 5, 10]


def gather(tickers, verbose=False):
    signals.EMA34_RISING_DAYS_MIN = 2
    common_idx = {}
    delta_candidates = []
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  pass1 {n}/{len(tickers)}", file=sys.stderr)
        try:
            df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        idxs = []
        for i in range(len(df) - 1):
            row = df.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            if not signals.base_filters_pass(row):
                continue
            trigger = row.high10_prior * TRIGGER_CLEARANCE
            if row.High < trigger:
                continue
            if row.ema34_rising10 >= 9:
                idxs.append(i)
            else:
                delta_candidates.append((t, i, df, trigger))
        common_idx[t] = idxs
    signals.EMA34_RISING_DAYS_MIN = 9

    rows = []
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  pass2(common) {n}/{len(tickers)}", file=sys.stderr)
        try:
            df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        for i in common_idx.get(t, []):
            row = df.iloc[i]
            trigger = row.high10_prior * TRIGGER_CLEARANCE
            rows.append(dict(group="Common", **trajectory(df, i, trigger)))

    for t, i, df, trigger in delta_candidates:
        early = any(i < c <= i + 3 for c in common_idx.get(t, []))
        if early:
            continue  # only Unique, per the final scope
        rows.append(dict(group="Unique", **trajectory(df, i, trigger)))

    return pd.DataFrame(rows)


def trajectory(df, i, trigger):
    out = {}
    max_h = min(15, len(df) - i - 1)
    if max_h < 1:
        return {f"close_d{h}": None for h in HORIZONS} | {"mfe": None, "mae": None, "max_h": 0}
    window = df.iloc[i + 1:i + 1 + max_h]
    for h in HORIZONS:
        if h <= max_h:
            out[f"close_d{h}"] = (window.iloc[h - 1].Close / trigger - 1) * 100 if h > 0 else (df.iloc[i].Close / trigger - 1) * 100
        else:
            out[f"close_d{h}"] = None
    out["mfe"] = (window.High.max() / trigger - 1) * 100
    out["mae"] = (window.Low.min() / trigger - 1) * 100
    out["max_h"] = max_h
    return out


def report(df):
    groups = {"Common": df[df.group == "Common"], "Unique (Delta)": df[df.group == "Unique"]}
    groups["Cumulative (Common+Unique, i.e. real EMA34=2 population)"] = df

    for label, g in groups.items():
        print(f"\n=== {label} (n={len(g)}) ===")
        for h in HORIZONS:
            col = f"close_d{h}"
            d = g[col].dropna()
            if len(d) == 0:
                continue
            print(f"  Day+{h:<3} n={len(d):<6} mean={d.mean():+.3f}%  median={d.median():+.3f}%  %profitable={((d>0).mean()*100):5.1f}%")
        print(f"  MFE (up to day+15, or fewer if data ends): mean={g.mfe.mean():+.3f}%  median={g.mfe.median():+.3f}%")
        print(f"  MAE (up to day+15, or fewer if data ends): mean={g.mae.mean():+.3f}%  median={g.mae.median():+.3f}%")


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    df = gather(tickers, verbose=True)
    df.to_csv("rq64_holding_trajectory.csv", index=False)
    report(df)
