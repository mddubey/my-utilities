"""Isolated research only (2026-09-12). Real question: once a stock has already breached
the trigger (live dashboard's "pulled_back"/"kept_going_near" tier), does the live volume
reading AT THAT MOMENT (vol_vs_normal_pct, the same metric live_checkpoint.py already shows)
predict whether the breach HOLDS above the trigger by end of day, vs. reverses? This is the
post-breach analog of the already-solved pre-breach question (calibrated_fire_rate/FIRE_TIERS
in live_checkpoint.py, built 2026-09-08) -- that one predicts "will an unbreached candidate
eventually close above the trigger"; this one asks "given it's ALREADY breached, will THIS
breach hold." No equivalent exists yet for the post-breach case.

Needs real intraday volume-so-far data (not the end-of-day vol_zscore) -- restricted to the
~3-month intraday_cache window for that reason, same constraint as the earlier SL-touch
check. Reuses live_checkpoint.py's own _normal_day_volume_baseline/_elapsed_session_fraction
machinery for a consistent, non-invented metric.
"""
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

import pandas as pd

import backtest
import intraday_cache
from pivots import daily_pivots
from signals import base_filters_pass
from live_checkpoint import _normal_day_volume_baseline, vol_tier

CACHE_DIR = Path("intraday_cache")
TRIGGER_CLEARANCE = 1.005
SESSION_MINUTES = 375.0  # 09:15-15:30


def run():
    tickers = pd.read_csv("fo_universe.csv", header=None)[0].tolist()
    cache_tickers = {p.stem for p in CACHE_DIR.glob("*.csv")}

    results = []
    for t in tickers:
        if t not in cache_tickers:
            continue
        try:
            df = backtest.load(t, daily_pivots)
        except FileNotFoundError:
            continue
        try:
            intraday = intraday_cache.load(t)
        except FileNotFoundError:
            continue
        if intraday.empty:
            continue
        intraday = intraday.copy()
        intraday.index = intraday.index.tz_convert("Asia/Kolkata").tz_localize(None)
        cache_min, cache_max = intraday.index.min().normalize(), intraday.index.max().normalize()

        rows = df.reset_index()
        already_extended_df = (df.Close > df.high10_prior)  # same index as df, so it aligns inside _normal_day_volume_baseline's df.iloc slice
        for i in range(len(rows) - 1):
            row = rows.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            entry_date = row.Date
            if entry_date < cache_min or entry_date > cache_max:
                continue
            if not base_filters_pass(row):
                continue
            trigger_price = row.high10_prior * TRIGGER_CLEARANCE
            if row.High < trigger_price:
                continue  # never breached at all today

            day_bars = intraday[intraday.index.normalize() == entry_date]
            if day_bars.empty:
                continue
            crossed = day_bars[day_bars.High >= trigger_price]
            if crossed.empty:
                continue
            breach_time = crossed.index[0]

            normal_baseline, n_days = _normal_day_volume_baseline(df.iloc[:i + 1], already_extended_df.iloc[:i + 1])
            if not normal_baseline or n_days < 10:
                continue
            vol_so_far = day_bars[day_bars.index <= breach_time].Volume.sum()
            elapsed_min = (breach_time - day_bars.index[0]).total_seconds() / 60.0 + 5  # +5 for the first bar's own width
            frac = min(1.0, max(elapsed_min / SESSION_MINUTES, 0.01))
            expected_normal = normal_baseline * frac
            if not expected_normal:
                continue
            vol_vs_normal_pct = vol_so_far / expected_normal * 100

            confirmed_by_close = row.Close >= trigger_price
            results.append(dict(ticker=t, entry_date=entry_date, vol_vs_normal_pct=vol_vs_normal_pct,
                               vol_tier=vol_tier(vol_vs_normal_pct), confirmed_by_close=confirmed_by_close))

    out = pd.DataFrame(results)
    out.to_csv("runs/breach_hold_volume_check.csv", index=False)
    print(f"n = {len(out)}")
    if out.empty:
        return
    print(f"\noverall hold rate: {out.confirmed_by_close.mean()*100:.1f}%")
    print("\n=== hold rate by live vol_vs_normal_pct QUARTILE ===")
    out["q"] = pd.qcut(out.vol_vs_normal_pct, 4, labels=["Q1 (low)", "Q2", "Q3", "Q4 (high)"])
    print(out.groupby("q", observed=True).confirmed_by_close.agg(["count", "mean"]))
    print("\n=== hold rate by vol_tier (WEAK/NORMAL/GOOD/STRONG) ===")
    print(out.groupby("vol_tier", observed=True).confirmed_by_close.agg(["count", "mean"]))


if __name__ == "__main__":
    run()
