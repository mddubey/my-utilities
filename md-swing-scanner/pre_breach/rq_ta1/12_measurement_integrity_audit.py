"""RQ-OM-00 -- Measurement-Integrity Audit of the canonical touched population (Rule #23).

Audits the EXISTING `pivot_feats.pkl` touched population (rq_pb2/02_pivot_features.py,
n=26,265, BLAST/STALL/FAIL = r5 >=1.5/<=-1.0/between, ATR-normalized, at T+5 close) that
underlies the 6-year baseline, RVOL@Trigger, cum_vol_ratio, dist_open_atr, the 4-feature
family-wise test, touch_vol_ratio and G.1 in rq_ta1/FINDINGS.md, and was reused by
confirmed_day1/RQ-CD1.

No new filters, no removed observations, no redesign -- existing fields (+ one
reconstruction, the structural round-trip check, from raw daily bars, since that isn't
already a stored field) only. Four dimensions, per CLAUDE.md Rule #23:
  1. Trigger-candle sanity (red vs green touch-day candle)
  2. Wick vs close (close_above already exists as a field, never conditioned on)
  3. Gating (verified by source read of 01_build_panel.py -- stated here, not re-derived)
  4. Structural context (round-trip below the touch-day's own Low before T+5)

Usage: python3 12_measurement_integrity_audit.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
import backtest  # noqa: E402

PB2 = Path(__file__).resolve().parent.parent / "rq_pb2"
OUT = Path(__file__).resolve().parent


def dim1_trigger_candle_sanity(X):
    X = X.copy()
    X["red"] = X.close < X.open_
    print("\n=== DIM 1: Trigger-candle sanity (touch-day Close vs Open) ===")
    print(f"red (Close < Open) touches: {X.red.sum()} / {len(X)} = {X.red.mean():.1%}")
    print("\ncls distribution, red vs green touch-day candle:")
    print(pd.crosstab(X.red, X.cls, normalize="index").round(3))
    print("\ncounts:")
    print(pd.crosstab(X.red, X.cls))
    return X


def dim2_wick_vs_close(X):
    print("\n=== DIM 2: Wick vs close (closed back below trigger same day?) ===")
    rejected = ~X.close_above
    print(f"touched intrabar but closed BELOW trigger (give-back): "
          f"{rejected.sum()} / {len(X)} = {rejected.mean():.1%}")
    print("\ncls distribution, close_above True vs False:")
    print(pd.crosstab(X.close_above, X.cls, normalize="index").round(3))
    print("\ncounts:")
    print(pd.crosstab(X.close_above, X.cls))
    print("\nOverlap: red candle AND give-back (both failure modes at once):")
    both = X.red & rejected
    print(f"{both.sum()} / {len(X)} = {both.mean():.1%}")
    return X


def dim3_gating_note():
    print("\n=== DIM 3: Discovery population vs trading constraint ===")
    print("Verified by source read, not re-derived: pre_breach/01_build_panel.py's `build()`")
    print("loops i in range(20, len(rows)) per ticker with no position-state variable at all --")
    print("every day that passes the T-1 gate + has a valid trigger becomes a row, regardless")
    print("of any other touch for that ticker before/after it. panel.csv is explicitly")
    print("documented as 'observational, no gating of positions... NOT a position population.'")
    print("PASS -- this population is genuinely ungated. (Does not mean later consumers of it")
    print("are: confirm the same for any NEW script before assuming inheritance.)")


def dim4_structural_roundtrip(X):
    print("\n=== DIM 4: Structural context -- round-trip below touch-day's own Low before T+5 ===")
    results = []
    tickers = X.ticker.unique()
    for i, tk in enumerate(tickers):
        try:
            d = backtest.load(tk)
        except FileNotFoundError:
            continue
        d = d.reset_index()
        d["Date"] = pd.to_datetime(d["Date"])
        idx = {dt: j for j, dt in enumerate(d["Date"])}
        sub = X[X.ticker == tk]
        for _, row in sub.iterrows():
            j = idx.get(pd.Timestamp(row.date))
            if j is None or j + 5 >= len(d):
                continue
            touch_day_low = d.Low.iloc[j]
            fwd_low = d.Low.iloc[j + 1 : j + 6].min()
            fwd_min_close = d.Close.iloc[j + 1 : j + 6].min()
            results.append(dict(
                ticker=tk, date=row.date, cls=row.cls,
                breached_touch_low=fwd_low < touch_day_low,
                breached_trigger_again=fwd_min_close < row.trigger,
            ))
        if i % 50 == 0:
            print(f"  ... {i}/{len(tickers)} tickers", flush=True)
    R = pd.DataFrame(results)
    print(f"\nmatched {len(R)} / {len(X)} touches to raw daily bars")
    print("\n% that breached the touch-day's own Low at some point in T+1..T+5, by cls:")
    print(R.groupby("cls").breached_touch_low.mean().round(3))
    print("\n% that closed back below the trigger at some point in T+1..T+5, by cls:")
    print(R.groupby("cls").breached_trigger_again.mean().round(3))
    print("\nOverall:")
    print(f"breached_touch_low: {R.breached_touch_low.mean():.1%}")
    print(f"breached_trigger_again: {R.breached_trigger_again.mean():.1%}")
    R.to_csv(OUT / "rq_om00_roundtrip.csv", index=False)
    return R


def main():
    X = pd.read_pickle(PB2 / "pivot_feats.pkl")
    print(f"Population: n={len(X)}, {X.date.min().date()} -> {X.date.max().date()}")
    print(X.cls.value_counts(normalize=True).round(3))
    X = dim1_trigger_candle_sanity(X)
    X = dim2_wick_vs_close(X)
    dim3_gating_note()
    dim4_structural_roundtrip(X)


if __name__ == "__main__":
    main()
