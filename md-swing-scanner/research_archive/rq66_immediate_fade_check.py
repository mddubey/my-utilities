"""RQ-66 Stage 1 (2026-09-19): can breach-time-only, daily-bar features predict which
EMA34=2 Delta trades are about to become "Immediate Fade" trades -- monotonically
worsening through day+3 (close_d1<0, close_d2<close_d1, close_d3<close_d2)?

This is a different, sharper target than RQ-65's True-Unique(15d) label: True-Unique is
an imperfect proxy for "bad trade" (a never-confirming trade can still be a fine swing
that rallies for a week without ever tripping EMA34>=9; an Early trade can dip for two
days before becoming a great winner). Immediate Fade targets the actual trading pain
directly. The label itself uses days+1-3 price (hindsight only, for research); every
candidate feature below must be knowable AT the breach bar, never later -- the already-
rejected "exit if negative at day+1/2" idea used day+1/2 price as a LIVE input, which is
a different (and already falsified) thing from using it to build a hindsight label here.

Stage 1 deliberately stays daily-bar-only (full 5-year universe, large sample) rather
than reaching into the ~70-90-day real intraday cache -- matches this project's own
population-choice convention (big population first, intraday-only refinement later).
Features, in the critic's own priority order, restricted to what's available without
intraday data:
  - vol_zscore       -- production Breakout Volume Z-score (signals.py, BC_VOL_Z_WINDOW=8)
  - body_atr_daily   -- |Close-Open|/ATR14 of the breach day's own daily candle (a daily-
                         bar proxy for live_checkpoint.py's intraday body_atr, which needs
                         the breach bar and isn't available at this sample size)
  - dist_to_trigger_pct -- (Close/trigger - 1) * 100 on the breach day: how far the close
                         finished past the trigger, not just whether it crossed
  - consolidation_days -- production formula, reused directly from live_checkpoint.py
                         (explicitly documented there as "daily-bar only, no live data gap")
"""
import warnings
warnings.filterwarnings("ignore")

import sys

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from breakout_failure_confirmation_cost import TRIGGER_CLEARANCE, simulate_swing, simulate_day1
from live_checkpoint import _consolidation_days
from daily_scan import _fo_tickers
from research.metrics import expectancy, win_rate

FEATURES = ["vol_zscore", "body_atr_daily", "dist_to_trigger_pct", "consolidation_days"]


def gather(tickers, verbose=False):
    fo = _fo_tickers()
    signals.EMA34_RISING_DAYS_MIN = 2
    rows = []
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  {n}/{len(tickers)}", file=sys.stderr)
        try:
            df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        for i in range(3, len(df) - 3):
            row = df.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            if not signals.base_filters_pass(row):
                continue
            trigger = row.high10_prior * TRIGGER_CLEARANCE
            if row.High < trigger:
                continue
            if row.ema34_rising10 >= 9:
                continue  # Delta only

            d1 = (df.iloc[i + 1].Close / trigger - 1) * 100
            d2 = (df.iloc[i + 2].Close / trigger - 1) * 100
            d3 = (df.iloc[i + 3].Close / trigger - 1) * 100
            immediate_fade = d1 < 0 and d2 < d1 and d3 < d2

            body_atr_daily = abs(row.Close - row.Open) / row.atr14 if row.atr14 else None
            dist_to_trigger_pct = (row.Close / trigger - 1) * 100

            rows.append(dict(
                ticker=t, i=i,
                vol_zscore=row.vol_zscore,
                body_atr_daily=body_atr_daily,
                dist_to_trigger_pct=dist_to_trigger_pct,
                consolidation_days=_consolidation_days(df, i),
                immediate_fade=immediate_fade,
                swing_pnl=simulate_swing(df, i, trigger),
                day1_pnl=simulate_day1(df, i, trigger) if t in fo else None,
            ))
    signals.EMA34_RISING_DAYS_MIN = 9
    return pd.DataFrame(rows)


def report(df, n_buckets=4):
    print(f"\nEMA34=2 Delta population, n={len(df)}")
    print(f"Immediate Fade rate (overall): {df.immediate_fade.mean()*100:.1f}%")
    print(f"Baseline SWING:   win={win_rate(df.swing_pnl):.1f}% exp={expectancy(df.swing_pnl):+.3f}%")
    opt = df.dropna(subset=["day1_pnl"])
    print(f"Baseline OPTIONS: win={win_rate(opt.day1_pnl):.1f}% exp={expectancy(opt.day1_pnl):+.3f}% (n={len(opt)})")

    for feat in FEATURES:
        d = df.dropna(subset=[feat]).copy()
        try:
            d["bucket"] = pd.qcut(d[feat], n_buckets, duplicates="drop")
        except ValueError:
            print(f"\n=== {feat}: not enough distinct values to bucket ===")
            continue
        print(f"\n=== {feat} ===")
        for b, g in d.groupby("bucket", observed=True):
            go = g.dropna(subset=["day1_pnl"])
            print(f"  {str(b):<22} n={len(g):<6} fade_rate={g.immediate_fade.mean()*100:5.1f}%  "
                  f"swing win={win_rate(g.swing_pnl):5.1f}%/exp={expectancy(g.swing_pnl):+.3f}%  "
                  f"opt win={win_rate(go.day1_pnl):5.1f}%/exp={expectancy(go.day1_pnl):+.3f}% (n={len(go)})")


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    df = gather(tickers, verbose=True)
    df.to_csv("rq66_immediate_fade.csv", index=False)
    report(df)
