"""RQ-SHOCK: does a sharp single-day drawdown in an otherwise-healthy uptrend tend to
recover, or is it the start of real deterioration -- exploratory, ad hoc (2026-09-24,
user question triggered by RBLBANK's real -3.6% shock day, IRDAI-news-driven, not an
earnings/company-specific event). Full NIFTY 500 universe, full cached history.

Event definition (all prior-day-known / same-day-observed, no lookahead):
  Healthy trend as of day t-1 (BEFORE the shock): Close > SMA200, SMA200 rising over the
  last 20 days, Close > EMA34 -- same "intact long-term uptrend" bar this project already
  uses elsewhere (stage2_trend_breakdown's above_all_smas/sma200_rising, base_filters_pass's
  trend_bullish).
  Shock on day t: same-day return <= -3%, on elevated volume (vol_zscore >= 1.5, VOL_ZSCORE_MIN
  convention from signals.py) -- a real, volume-confirmed shock, not routine noise.

Baseline (comparison population): ALL days meeting the same t-1 healthy-trend condition,
regardless of what day t's return was -- "what does a random day in a healthy uptrend do
next", to see whether the shock population behaves differently from ordinary healthy-trend
days, not just whether it's positive in isolation.

Forward return measured Close[t] -> Close[t+k], k=1,3,5,10,20,40 trading days. Events
deduped per ticker: no second shock counted within 5 trading days of a prior one (avoid
double-counting one real crash's multiple down days).
"""
import pandas as pd
import numpy as np
from backtest import load

SHOCK_RET_MAX = -0.03
VOL_Z_MIN = 1.5
HORIZONS = [1, 3, 5, 10, 20, 40]
COOLDOWN_DAYS = 5

tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()

shock_events = []
baseline_events = []

for t in tickers:
    try:
        df = load(t).reset_index()
    except FileNotFoundError:
        continue
    if len(df) < 260:
        continue
    ret = df.Close.pct_change()
    healthy = (
        (df.Close.shift(1) > df.sma200.shift(1))
        & (df.sma200.shift(1) > df.sma200_20ago.shift(1))
        & (df.Close.shift(1) > df.ema34.shift(1))
    )
    is_shock = healthy & (ret <= SHOCK_RET_MAX) & (df.vol_zscore >= VOL_Z_MIN)

    n = len(df)
    last_shock_i = -999
    for i in range(1, n):
        if not bool(healthy.iloc[i]):
            continue
        fwd = {}
        ok = True
        for k in HORIZONS:
            if i + k >= n:
                ok = False
                break
            fwd[k] = df.Close.iloc[i + k] / df.Close.iloc[i] - 1
        if not ok:
            continue
        rec = dict(ticker=t, date=df.Date.iloc[i], shock_ret=ret.iloc[i],
                   vol_z=df.vol_zscore.iloc[i], **{f"fwd{k}": fwd[k] for k in HORIZONS})
        if bool(is_shock.iloc[i]) and (i - last_shock_i) > COOLDOWN_DAYS:
            shock_events.append(rec)
            last_shock_i = i
        else:
            baseline_events.append(rec)

shock_df = pd.DataFrame(shock_events)
baseline_df = pd.DataFrame(baseline_events)
print(f"n shock events (deduped): {len(shock_df)}")
print(f"n baseline (healthy-trend, non-shock) days: {len(baseline_df)}")
print()

print("=== SHOCK population: forward returns ===")
for k in HORIZONS:
    col = f"fwd{k}"
    pos_pct = (shock_df[col] > 0).mean() * 100
    print(f"  +{k:2d}d: %positive={pos_pct:5.1f}%  median={shock_df[col].median()*100:+6.2f}%  mean={shock_df[col].mean()*100:+6.2f}%")

print()
print("=== BASELINE population (healthy trend, ordinary day): forward returns ===")
for k in HORIZONS:
    col = f"fwd{k}"
    pos_pct = (baseline_df[col] > 0).mean() * 100
    print(f"  +{k:2d}d: %positive={pos_pct:5.1f}%  median={baseline_df[col].median()*100:+6.2f}%  mean={baseline_df[col].mean()*100:+6.2f}%")

print()
print("=== Does the shock get 'recovered' -- fwd return erases the shock-day loss? ===")
for k in HORIZONS:
    col = f"fwd{k}"
    recovered_pct = (shock_df[col] > -shock_df["shock_ret"]).mean() * 100
    print(f"  +{k:2d}d: %where fwd return more than offsets the shock day's loss: {recovered_pct:5.1f}%")

print()
print("=== Concentration check (top-10 events' share of total fwd20 sum, sanity) ===")
s = shock_df["fwd20"].sort_values(ascending=False)
top10_share = s.head(10).sum() / shock_df["fwd20"].sum() * 100 if shock_df["fwd20"].sum() != 0 else float("nan")
print(f"  top-10 / total fwd20 sum: {top10_share:.1f}%  (n={len(shock_df)})")

shock_df.to_csv("rq_shock_drawdown_recovery_events.csv", index=False)
print()
print("saved: rq_shock_drawdown_recovery_events.csv")
