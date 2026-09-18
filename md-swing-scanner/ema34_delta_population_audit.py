"""RQ-52A Evidence Checklist, Test P1: Delta Population Audit (2026-09-18).
Critic's own framing: "don't ask is EMA34=2 better, ask what NEW trades EMA34=2
creates, and are those trades genuinely better." Isolates the real "Delta"
population (passes base_filters_pass with EMA34_RISING_DAYS_MIN relaxed to 2,
but would have FAILED at the current production value of 9) against "Common"
(passes at both), full multi-year history, single pass (ema34_rising10 is
already a real column -- no need to re-scan per threshold).

Reports, per the critic's own priority list: swing/options win-exp-median-
concentration, freshness overlap (% Fresh, freshness_score<=0.40, this
project's established convention), and REAL fragility rate -- reuses
fragility_margin_check.py's exact definition (winners only, Fragile if
0<day1_pnl<=0.4%, Medium 0.4-0.8%, Robust >0.8%), not the live estimate.

Critic's timestamped prediction (before running): Delta swing exp better by
<0.2%, options meaningfully better (+0.2-0.4%), fragility slightly higher,
~70-80% of Delta already Fresh, ~20-25% more candidates/day.
"""
import warnings
warnings.filterwarnings("ignore")

import sys

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from breakout_failure_confirmation_cost import TRIGGER_CLEARANCE, simulate_swing, simulate_day1
from daily_scan import _fo_tickers
from live_checkpoint import _freshness_score
from research.metrics import expectancy, win_rate, concentration_v2


def gather(tickers, fo, verbose=False):
    original = signals.EMA34_RISING_DAYS_MIN
    signals.EMA34_RISING_DAYS_MIN = 2  # relax to capture the full superset in one pass
    rows = []
    try:
        for n, t in enumerate(tickers):
            if verbose and n % 100 == 0:
                print(f"  {n}/{len(tickers)}", file=sys.stderr)
            try:
                df = backtest.load(t, daily_pivots).reset_index()
            except FileNotFoundError:
                continue
            for i in range(len(df) - 1):
                row = df.iloc[i]
                if row.corp_action_day or pd.isna(row.high10_prior):
                    continue
                if not signals.base_filters_pass(row):
                    continue
                trigger = row.high10_prior * TRIGGER_CLEARANCE
                if row.High < trigger:
                    continue
                group = "Common" if row.ema34_rising10 >= 9 else "Delta"
                fresh = _freshness_score(row)
                rows.append(dict(
                    ticker=t, date=row.Date, group=group, ema34_rising10=row.ema34_rising10,
                    fresh=(fresh is not None and fresh <= 0.40),
                    swing_pnl=simulate_swing(df, i, trigger),
                    day1_pnl=simulate_day1(df, i, trigger) if t in fo else None,
                ))
    finally:
        signals.EMA34_RISING_DAYS_MIN = original
    return pd.DataFrame(rows)


def fragility_label(day1_pnl):
    if pd.isna(day1_pnl) or day1_pnl <= 0:
        return None  # not a winner, fragility undefined
    if day1_pnl <= 0.4:
        return "Fragile"
    if day1_pnl <= 0.8:
        return "Medium"
    return "Robust"


def report(name, d):
    d1 = d.day1_pnl.dropna()
    print(f"\n--- {name} (n={len(d)}) ---")
    print(f"  SWING   win={win_rate(d.swing_pnl):5.1f}%  exp={expectancy(d.swing_pnl):+.3f}%  "
          f"median={d.swing_pnl.median():+.3f}%  conc={concentration_v2(d.swing_pnl):5.1f}%")
    print(f"  OPT     n={len(d1):<6} win={win_rate(d1):5.1f}%  exp={expectancy(d1):+.3f}%  "
          f"median={d1.median():+.3f}%  conc={concentration_v2(d1):5.1f}%")
    print(f"  Freshness overlap: {d.fresh.mean()*100:.1f}% already Fresh (freshness_score<=0.40)")
    winners = d1[d1 > 0]
    labels = winners.apply(fragility_label)
    if len(labels):
        counts = labels.value_counts(normalize=True) * 100
        print(f"  Fragility (real, winners only, n={len(labels)}): "
              f"Fragile={counts.get('Fragile', 0):.1f}%  Medium={counts.get('Medium', 0):.1f}%  Robust={counts.get('Robust', 0):.1f}%")


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    fo = _fo_tickers()
    print("Gathering full population at EMA34_RISING_DAYS_MIN=2 (relaxed), splitting by real ema34_rising10...", file=sys.stderr)
    df = gather(tickers, fo, verbose=True)
    df.to_csv("ema34_delta_population.csv", index=False)
    print(f"\nTotal: n={len(df)}  Common={len(df[df.group=='Common'])}  Delta={len(df[df.group=='Delta'])}")

    report("Common (passes EMA34>=9, current production)", df[df.group == "Common"])
    report("Delta (passes EMA34=2 only, NEW trades)", df[df.group == "Delta"])

    # candidate-count comparison, per the critic's ask
    common_days = df[df.group == "Common"].groupby("date").size()
    all_days = df.groupby("date").size()
    print(f"\nCandidate volume: Common alone avg/day={common_days.mean():.2f}  "
          f"Common+Delta (EMA34=2) avg/day={all_days.mean():.2f}  "
          f"increase={(all_days.mean()/common_days.mean()-1)*100:.1f}%")
