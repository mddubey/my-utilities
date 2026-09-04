"""Tomorrow Candidates — the +1% intraday trigger watchlist (2026-09-04).

Ranks the "primed" universe (same VCP-base-pivot / base_filters_pass logic as
shortlist_primed() in daily_scan.py) by a 5-feature score, and outputs a trigger
price for each: `high10_prior * 1.01` — the level validated this session (full
trade re-simulation: 69.4% win / +3.97% median / 11.6% concentration vs. the
close-based baseline's 65.0%/+2.89%, see FINDINGS.md's "Same-day intraday
confirmation trigger" section for the full validation).

Score = average of 5 equally-weighted percentile ranks:
  - range_compression (10d range / ATR14, lower = tighter = better)
  - ema8_dist_pct (Close vs 8-EMA, lower = less extended = better)
  - atr_trend_15d (ATR14 vs ATR14 15 days ago, lower = more stable vol = better)
  - narrowing_range (recent 3d range / prior 3d range, higher = first hint of
    expansion after compression = better -- counter-intuitive, verified in the
    precursor discrimination test)
  - dist_to_resistance (Close / high10_prior, higher = closer to actually
    triggering today = better) -- added 2026-09-04 after NAUKRI/NEULANDLAB both
    ranked top-5 on quality while sitting 4.3-4.5% below resistance, unreachable
    that day. This is a FEASIBILITY fix, not a predictive-power fix.

Known open item, not yet applied (critic feedback, response-9.pdf, logged in
FINDINGS.md): a volatility-scaled trigger (`resistance + max(0.6%, 0.35*ATR%)`)
instead of the flat 1% used here -- untested, deliberately deferred.
"""
import sys

import pandas as pd

from backtest import load
from vcp import stage2_trend_template
from signals import base_filters_pass
from daily_scan import base_pivot

TOP_N = 5


def build_candidates(tickers, fo_tickers):
    recs = []
    for t in tickers:
        try:
            df = load(t)
        except FileNotFoundError:
            continue
        rows = df.reset_index()
        if len(rows) == 0:
            continue
        i = len(rows) - 1
        row = rows.iloc[i]
        if row.corp_action_day:
            continue
        on_vcp_path = stage2_trend_template(row, t, row.Date) and base_pivot(rows, i) is not None
        if not (on_vcp_path or base_filters_pass(row)):
            continue
        if pd.isna(row.atr14) or row.atr14 == 0 or i < 15 or pd.isna(row.ema8) or pd.isna(row.high10_prior):
            continue
        range10 = (rows.High.iloc[i - 9:i + 1].max() - rows.Low.iloc[i - 9:i + 1].min())
        range_compression = range10 / row.atr14
        ema8_dist_pct = (row.Close - row.ema8) / row.Close * 100
        atr14_15ago = rows.atr14.iloc[i - 15]
        atr_trend_15d = row.atr14 / atr14_15ago if pd.notna(atr14_15ago) and atr14_15ago else None
        recent3 = (rows.High.iloc[i - 2:i + 1] - rows.Low.iloc[i - 2:i + 1]).mean()
        prior3 = (rows.High.iloc[i - 5:i - 2] - rows.Low.iloc[i - 5:i - 2]).mean()
        narrowing_range = recent3 / prior3 if prior3 else None
        if atr_trend_15d is None or narrowing_range is None:
            continue
        dist_to_resistance = row.Close / row.high10_prior
        recs.append(dict(ticker=t, close=row.Close, high10_prior=row.high10_prior,
                          trigger_price=row.high10_prior * 1.01,
                          on_vcp_path=on_vcp_path, range_compression=range_compression,
                          ema8_dist_pct=ema8_dist_pct, atr_trend_15d=atr_trend_15d,
                          narrowing_range=narrowing_range, dist_to_resistance=dist_to_resistance,
                          is_fo=t in fo_tickers))

    pool = pd.DataFrame(recs)
    if pool.empty:
        return pool
    pool["quality_score"] = (
        (-pool.range_compression).rank(pct=True)
        + (-pool.ema8_dist_pct).rank(pct=True)
        + (-pool.atr_trend_15d).rank(pct=True)
        + (pool.narrowing_range).rank(pct=True)
    ) / 4
    pool["score"] = (pool.quality_score * 4 + pool.dist_to_resistance.rank(pct=True)) / 5
    return pool


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    fo_tickers = set(pd.read_csv("fo_universe.csv", header=None)[0])
    pool = build_candidates(tickers, fo_tickers)

    print(f"primed universe: n={len(pool)}\n")
    if pool.empty:
        sys.exit(0)
    top = pool.sort_values("score", ascending=False).head(TOP_N)
    print(f"TOP {TOP_N} Tomorrow Candidates (quality + feasibility):")
    for _, r in top.iterrows():
        fo_tag = "[F&O]" if r.is_fo else "[NO OPTIONS]"
        to_trigger_pct = (r.trigger_price / r.close - 1) * 100
        print(f"  {r.ticker:12s} {fo_tag:13s} close={r.close:9.2f}  "
              f"TRIGGER={r.trigger_price:9.2f} ({to_trigger_pct:+.2f}% away)  "
              f"score={r.score:.3f} (quality={r.quality_score:.3f})")
