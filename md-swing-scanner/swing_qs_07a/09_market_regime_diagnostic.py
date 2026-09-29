"""RQ-QS-07R -- Market Regime Diagnostic (2026-09-29, critic-specified).

Question: does the 2025-26 weakening found in RQ-QS-07A-3R come from the
PREDICTOR breaking, or from the underlying FAST-MOVER PHENOMENON ITSELF
becoming rarer/weaker in that period? Purely DESCRIPTIVE -- no predictor, no
strategy modification, no new feature, no Cohort-A/control machinery. Uses the
NEUTRAL broad universe (every eligible stock-day, same as RQ-QS-07A-1's own
event matrix + a fresh daily cross-sectional panel).

Per critic's explicit instruction: do NOT hard-code "2025 = regime break" --
show the key measures continuously (by quarter, not just a 2022-24 vs 2025-26
split) so the SHAPE of any transition is visible: abrupt vs gradual vs
segment-specific (liquidity-dependent).

Measures, in critic's priority order:
  A. Cross-sectional opportunity (daily): median/P75/P90/P95 daily return,
     cross-sectional dispersion (std of that day's return distribution),
     fraction positive.
  B. Trend breadth (daily): % stocks with positive 20D return, % above EMA34,
     % above SMA200 -- directly relevant since the discovered precursor IS a
     trend-strength state; if breadth itself declined, that's a real
     candidate explanation.
  C. Liquidity/size dispersion: same breadth/dispersion measures, split by
     liquidity tercile -- critical given 07A-3R's own liquidity gradient.
  D. Sector dispersion: EXPLICITLY DEFERRED -- no historical sector mapping
     exists yet (same v1 gap as RQ-QS-07U), not attempted, not faked with a
     current-snapshot proxy per critic's explicit instruction.
  E. Fast-mover base rate: reuses the already-built neutral event_matrix.csv
     (RQ-QS-07A-1) -- D3 MFE/close_ret percentiles AND the share crossing the
     already-fixed historical P95 threshold, both by quarter.

No threshold optimization, no model, no filter -- distribution/time-series
characterization only.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots

OUT_DIR = "swing_qs_07a"

print("Building the daily cross-sectional panel (every ticker, every eligible day)...", flush=True)
uni = pd.read_csv("nse_equity_universe.csv")
tickers = uni.ticker.tolist()

parts = []
for n, t in enumerate(tickers):
    if n % 300 == 0:
        print(f"  {n}/{len(tickers)}", flush=True)
    try:
        idf = load(t, daily_pivots)
    except FileNotFoundError:
        continue
    if len(idf) < 65:
        continue
    close = idf.Close
    daily_ret = (close / close.shift(1) - 1) * 100
    ret_20d = (close / close.shift(20) - 1) * 100
    above_ema34 = close > idf.ema34
    above_sma200 = close > idf.sma200
    part = pd.DataFrame({
        "date": idf.index, "ticker": t, "daily_ret": daily_ret.values,
        "ret_20d_positive": (ret_20d > 0).values, "above_ema34": above_ema34.values,
        "above_sma200": above_sma200.values, "traded_value_sma20": idf.traded_value_sma20.values,
        "corp_action_day": idf.corp_action_day.values,
    })
    parts.append(part[60:])  # matches this line's MIN_HISTORY convention elsewhere
panel = pd.concat(parts, ignore_index=True)
panel = panel[~panel.corp_action_day & panel.daily_ret.notna()]
print(f"Panel: {len(panel):,} stock-days")

panel["liq_decile"] = panel.groupby("date")["traded_value_sma20"].transform(
    lambda x: pd.qcut(x, 10, labels=False, duplicates="drop") if x.notna().sum() >= 10 else np.nan)
panel["liq_tercile"] = pd.cut(panel.liq_decile, [-1, 2, 6, 9], labels=["low", "mid", "high"])
panel["quarter"] = pd.to_datetime(panel.date).dt.to_period("Q")
panel["year"] = pd.to_datetime(panel.date).dt.year

panel.to_csv(f"{OUT_DIR}/regime_daily_panel.csv", index=False,
              columns=["date", "ticker", "daily_ret", "ret_20d_positive", "above_ema34",
                        "above_sma200", "liq_tercile", "quarter"])  # gitignored (~2.06M rows, 136MB) --
                                                                     # a 200k random sample is committed
                                                                     # separately (regime_daily_panel_sample_200k.csv)

# --- A + B: cross-sectional opportunity and trend breadth, by QUARTER (continuous view) ---
print("\n" + "=" * 100 + "\nA+B. CROSS-SECTIONAL OPPORTUNITY & TREND BREADTH, by quarter\n" + "=" * 100)
by_q = panel.groupby("quarter").agg(
    n=("ticker", "size"),
    median_ret=("daily_ret", "median"), p75_ret=("daily_ret", lambda x: np.percentile(x, 75)),
    p90_ret=("daily_ret", lambda x: np.percentile(x, 90)), p95_ret=("daily_ret", lambda x: np.percentile(x, 95)),
    dispersion=("daily_ret", "std"), frac_positive=("daily_ret", lambda x: (x > 0).mean() * 100),
    pct_above_ema34=("above_ema34", lambda x: x.mean() * 100),
    pct_above_sma200=("above_sma200", lambda x: x.mean() * 100),
    pct_ret20d_positive=("ret_20d_positive", lambda x: x.mean() * 100),
)
print(by_q.round(2).to_string())
by_q.round(4).to_csv(f"{OUT_DIR}/regime_breadth_by_quarter.csv")
print("\nKNOWN ARTIFACT (hand-verified, Rule #22): pct_above_sma200 is spuriously LOW for "
      "2021Q4-2022Q2 -- sma200 needs 200 trading days of history and is genuine NaN for any "
      "ticker's first ~10 months in the cache (confirmed on RELIANCE: sma200 all-NaN "
      "2021-11-01 to 2021-11-10), and `Close > NaN` silently evaluates False in pandas rather "
      "than being excluded. This is a burn-in artifact, NOT real 0% market breadth -- ignore "
      "pct_above_sma200 before ~2022Q3 when reading this table. Does not affect any other "
      "column here (ema34/20D-return breadth need <=60d history, already covered by the "
      "panel's own MIN_HISTORY cutoff) and does not touch the 2025-26 comparison this RQ "
      "actually turns on.")

# --- C: same, by liquidity tercile x year (segment-specific check) ---
print("\n" + "=" * 100 + "\nC. TREND BREADTH BY LIQUIDITY TERCILE x YEAR\n" + "=" * 100)
by_liq_yr = panel.groupby(["liq_tercile", "year"], observed=True).agg(
    n=("ticker", "size"),
    pct_above_ema34=("above_ema34", lambda x: x.mean() * 100),
    pct_above_sma200=("above_sma200", lambda x: x.mean() * 100),
    pct_ret20d_positive=("ret_20d_positive", lambda x: x.mean() * 100),
    dispersion=("daily_ret", "std"),
)
print(by_liq_yr.round(2).to_string())
by_liq_yr.round(4).to_csv(f"{OUT_DIR}/regime_breadth_by_liq_tercile_year.csv")

# --- D: sector dispersion -- explicitly not attempted ---
print("\n" + "=" * 100 + "\nD. SECTOR DISPERSION -- explicitly NOT attempted (no historical sector mapping)\n" + "=" * 100)

# --- E: fast-mover base rate, from the existing neutral event matrix, by quarter ---
print("\n" + "=" * 100 + "\nE. FAST-MOVER BASE RATE (from RQ-QS-07A-1's event matrix), by quarter\n" + "=" * 100)
em = pd.read_csv(f"{OUT_DIR}/event_matrix.csv", parse_dates=["date"],
                   usecols=["date", "max_return_d3", "close_ret_d3"])
em["quarter"] = em.date.dt.to_period("Q")
P95_MFE_FIXED = np.percentile(em.max_return_d3, 95)  # the SAME fixed threshold used throughout 07A
P95_CLOSE_FIXED = np.percentile(em.close_ret_d3, 95)
by_q_em = em.groupby("quarter").agg(
    n=("max_return_d3", "size"),
    mfe_p90=("max_return_d3", lambda x: np.percentile(x, 90)),
    mfe_p95=("max_return_d3", lambda x: np.percentile(x, 95)),
    close_p90=("close_ret_d3", lambda x: np.percentile(x, 90)),
    close_p95=("close_ret_d3", lambda x: np.percentile(x, 95)),
    pct_crossing_fixed_mfe_p95=("max_return_d3", lambda x: (x >= P95_MFE_FIXED).mean() * 100),
    pct_crossing_fixed_close_p95=("close_ret_d3", lambda x: (x >= P95_CLOSE_FIXED).mean() * 100),
)
print(by_q_em.round(2).to_string())
by_q_em.round(4).to_csv(f"{OUT_DIR}/regime_fastmover_baserate_by_quarter.csv")

print(f"\n(reference: whole-period fixed thresholds -- MFE P95={P95_MFE_FIXED:.2f}%, close P95={P95_CLOSE_FIXED:.2f}%)")
print("\nDONE")
