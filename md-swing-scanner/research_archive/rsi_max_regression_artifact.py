"""Isolated research only (2026-09-14). RSI_MAX regression-test artifact, critic-requested
(response-2, Decision review 1): a permanent record of RSI_MAX=80 vs RSI_MAX=90 on BOTH
populations, so "why is 90 different from the research notebook" never has to be re-derived.

  Live-equivalent population (base_filters_pass + intraday breach only, no vol_zscore gate,
  the one that actually matches what live_checkpoint.py surfaces) -- old baseline (80) vs
  new production (90). Already computed earlier this session (runs/rsi_max_sweep_80.csv /
  _90.csv from rsi_max_freshness_sweep.py) -- reused here, not recomputed.

  Legacy EOD population (backtest.run()'s own real production methodology: base_filters_pass
  AND breakout_continuation's vol_zscore>=1.5 gate, Close-based confirmation, real in-position
  tracking) -- historical baseline (80, the ORIGINAL validation) vs expected degradation (90,
  documented here for the first time). Uses backtest.run() directly, not a hand-rolled
  approximation, filtered to pattern=="breakout_cont" only, matching the original sweep's own
  scope ("Breakout Cont trades only").
"""
import time
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import signals
from pivots import daily_pivots


def concentration(pnl_series):
    total = pnl_series.sum()
    if not total:
        return float("nan")
    top10 = pnl_series.sort_values(ascending=False).head(10).sum()
    return top10 / total * 100


def legacy_eod_stats(rsi_max, tickers):
    original = signals.RSI_MAX
    signals.RSI_MAX = rsi_max
    t0 = time.time()
    trades = backtest.run(tickers, True, daily_pivots, 0.0)
    signals.RSI_MAX = original
    print(f"  RSI_MAX={rsi_max}: backtest.run() done in {time.time()-t0:.0f}s, {len(trades)} total trades (both patterns)")

    bc = trades[trades.pattern == "breakout_cont"]
    closed = bc[(~bc.open_at_end) & (bc.get("exit_reason") != "corp_action")]
    wins = closed[closed.pnl_pct > 0]
    losses = closed[closed.pnl_pct <= 0]
    win_rate = len(wins) / len(closed) * 100 if len(closed) else float("nan")
    avg_win = wins.pnl_pct.mean() if len(wins) else 0
    avg_loss = losses.pnl_pct.mean() if len(losses) else 0
    expectancy = (win_rate / 100) * avg_win + (1 - win_rate / 100) * avg_loss
    med = closed.pnl_pct.median() if len(closed) else float("nan")
    conc = concentration(closed.pnl_pct)
    return dict(n=len(closed), win_rate=win_rate, median=med, expectancy=expectancy, concentration=conc)


def run():
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()

    print("=== Legacy EOD population (backtest.run(), real vol_zscore-gated methodology) ===")
    legacy_80 = legacy_eod_stats(80, tickers)
    legacy_90 = legacy_eod_stats(90, tickers)

    print("\n=== Live-equivalent population (already computed, reused from rsi_max_sweep_*.csv) ===")
    live_80 = pd.read_csv("runs/rsi_max_sweep_80.csv")
    live_90 = pd.read_csv("runs/rsi_max_sweep_90.csv")

    def live_stats(df):
        wins = df[df.opt_pnl_pct > 0].opt_pnl_pct
        losses = df[df.opt_pnl_pct <= 0].opt_pnl_pct
        wr = len(wins) / len(df) * 100
        exp = (wr / 100) * (wins.mean() if len(wins) else 0) + (1 - wr / 100) * (losses.mean() if len(losses) else 0)
        return dict(n=len(df), win_rate=wr, median=df.opt_pnl_pct.median(), expectancy=exp,
                    concentration=concentration(df.opt_pnl_pct))

    live_80_stats = live_stats(live_80)
    live_90_stats = live_stats(live_90)

    print("\n" + "=" * 100)
    print("FINAL REGRESSION TABLE")
    print("=" * 100)
    print(f"{'Dataset':<28}{'RSI_MAX=80':<38}{'RSI_MAX=90':<38}")

    def fmt(s):
        return f"n={s['n']:<6} win={s['win_rate']:.1f}% med={s['median']:+.2f}% exp={s['expectancy']:+.3f}% conc={s['concentration']:.1f}%"

    print(f"{'Live-equivalent (options)':<28}{fmt(live_80_stats):<38}{fmt(live_90_stats):<38}")
    print(f"{'Legacy EOD (breakout_cont)':<28}{fmt(legacy_80):<38}{fmt(legacy_90):<38}")


if __name__ == "__main__":
    run()
