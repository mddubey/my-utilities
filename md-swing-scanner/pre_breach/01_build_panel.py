"""Pre-breach detector, step 3 -- daily candidate-day panel (observational, no gating of
positions: this is a trigger-price counterfactual panel of every primed candidate-day, NOT a
position population -- position-level swing numbers come from population_builder instead).

One row per (ticker, T) where the PRIOR day's row passes base_filters_pass (the real live
primed convention, shortlist_primed() on yesterday's frozen row -- Rule #18, gate on T-1).

Feature clock discipline -- every feature column is tagged by when it is knowable:
  T-1 close : everything computed on rows[i-1] (quality_score parts, freshness, ATR%, CLV...)
  T 09:15   : day-T Open (opening gap, open distance to trigger), Nifty opening gap
Outcome columns (never used as features): touched, gap_through, close_above, ret_* ...

Usage: python3 01_build_panel.py CHUNK NCHUNKS   (writes panel_chunk_{CHUNK}.csv)
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import backtest  # noqa: E402
import primed_engine as pe  # noqa: E402
from signals import base_filters_pass, _freshness_score  # noqa: E402
from live_checkpoint import _quality_features, _consolidation_days  # noqa: E402

OUT = Path(__file__).resolve().parent
REQUIRED = ["ema34", "vol_avg10_prior", "high10_prior", "atr14_60ago",
            "ema34_rising10", "traded_value_sma20", "close_20ago"]


def nifty_gap():
    n = pd.read_csv(ROOT / "data_cache" / "_NIFTY.csv", index_col="Date", parse_dates=True)
    return (n.Open / n.Close.shift(1) - 1) * 100


def build(ticker, fo, ngap):
    df = backtest.load(ticker)
    rows = df.reset_index()
    recs = []
    for i in range(20, len(rows)):
        g = rows.iloc[i - 1]           # gate row = T-1 (live primed convention)
        r = rows.iloc[i]               # day T
        if r.corp_action_day or g.corp_action_day:
            continue
        if g[REQUIRED].isna().any() or not base_filters_pass(g):
            continue
        if pd.isna(r.high10_prior) or pd.isna(g.atr14) or g.atr14 == 0:
            continue
        trig = r.high10_prior * pe.TRIGGER_CLEARANCE   # r.high10_prior uses only T-10..T-1 highs
        q = _quality_features(ticker, rows, i - 1)
        prev_range = g.High - g.Low
        rec = dict(
            ticker=ticker, date=r.Date, fo=ticker in fo, trigger=trig,
            # --- T-1 close features ---
            dist_prev_close_pct=(trig / g.Close - 1) * 100,
            dist_prev_close_atr=(trig - g.Close) / g.atr14,
            atr_pct=g.atr14 / g.Close * 100,
            clv_prev=(g.Close - g.Low) / prev_range if prev_range > 0 else np.nan,
            ret_prev_pct=(g.Close / rows.Close.iloc[i - 2] - 1) * 100,
            vol_ratio_prev=g.Volume / g.vol_avg10_prior if g.vol_avg10_prior else np.nan,
            rsi_prev=g.rsi14, freshness=_freshness_score(g),
            consolidation_days=_consolidation_days(rows, i - 1),
            body_atr_prev=g.body_atr, traded_value_sma20=g.traded_value_sma20,
            **{f"q_{k}": v for k, v in q.items()},
            # --- T 09:15 features ---
            open_=r.Open, gap_pct=(r.Open / g.Close - 1) * 100,
            dist_open_pct=(trig / r.Open - 1) * 100,
            dist_open_atr=(trig - r.Open) / g.atr14,
            nifty_gap_pct=ngap.get(r.Date, np.nan),
            # --- outcomes (T) ---
            high=r.High, low=r.Low, close=r.Close,
            touched=r.High >= trig, gap_through=r.Open >= trig,
            close_above=r.Close >= trig,
            ret_open_close_pct=(r.Close / r.Open - 1) * 100,
            next_open=rows.Open.iloc[i + 1] if i + 1 < len(rows) else np.nan,
            next_date=rows.Date.iloc[i + 1] if i + 1 < len(rows) else pd.NaT,
        )
        recs.append(rec)
    return recs


def main():
    chunk, nchunks = int(sys.argv[1]), int(sys.argv[2])
    tickers = sorted(pd.read_csv(ROOT / "nifty500_universe.csv", header=None)[0])
    fo = set(pd.read_csv(ROOT / "fo_universe.csv", header=None)[0])
    mine = tickers[chunk::nchunks]
    ngap = nifty_gap()
    allrecs, t0 = [], time.time()
    for k, t in enumerate(mine):
        try:
            allrecs += build(t, fo, ngap)
        except FileNotFoundError:
            continue
        if k % 10 == 0:
            print(f"[chunk {chunk}] {k}/{len(mine)} {t} rows={len(allrecs)} {time.time()-t0:.0f}s", flush=True)
    pd.DataFrame(allrecs).to_csv(OUT / f"panel_chunk_{chunk}.csv", index=False)
    print(f"[chunk {chunk}] done rows={len(allrecs)}", flush=True)


if __name__ == "__main__":
    main()
