"""Isolated research only (2026-09-14). Reconsideration-shortlist items 1-2 (critic_update_35):
replays the original 2026-09-03 "Exit-strategy comparison: moving resistance vs fixed-R
targets vs trail-only" on the current freshness<=0.40-conditioned population, across the
standard 3-population bracket (feedback_population_choice_for_backtests.md). Original
verdict was "genuine unresolved trade-off, not settled": baseline (moving resistance) is
cleanest (65% win, lowest concentration); 2R/3R have better raw expectancy but only ~50%
of nominal "wins" ever actually reach target, the rest get stopped on the way back down
near breakeven; trail-only has the best raw expectancy (+0.542R) but a near-coin-flip
median (-0.05%) propped up by rare huge winners (24.7% concentration).

Hypothesis being tested: does a cleaner, freshness-conditioned entry population shift the
"~50% reach target" ratio meaningfully, now that a lot of noise-driven reversal trades are
filtered out on entry?

Same entry convention as every other test this session: trigger = high10_prior * 1.005,
R (for the R-multiple metric and the fixed-target variants) = ATR_TRAIL_MULT * atr14 at
entry, matching backtest.py's own definition of the initial stop distance.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005
ATR_TRAIL_MULT = 3.0

daily_cache = {}


def load_daily(ticker):
    if ticker not in daily_cache:
        daily_cache[ticker] = backtest.load(ticker, daily_pivots).reset_index()
    return daily_cache[ticker]


def simulate_variant(daily, i, variant):
    trigger = daily.iloc[i].high10_prior * TRIGGER_CLEARANCE
    R = ATR_TRAIL_MULT * daily.iloc[i].atr14
    if variant == "baseline":
        target, use_resistance = None, True
    elif variant == "2R":
        target, use_resistance = trigger + 2 * R, False
    elif variant == "3R":
        target, use_resistance = trigger + 3 * R, False
    elif variant == "trail_only":
        target, use_resistance = None, False

    state = dict(entry_price=trigger, peak_close=trigger, peak_high=trigger, structural_low=0.0, target=target)
    exit_price, exit_reason_final = None, None
    for j in range(i + 1, len(daily)):
        row = daily.iloc[j]
        if row.corp_action_day:
            exit_price, exit_reason_final = row.Close, "corp_action"
            break
        exit_reason, state = backtest.check_exit("breakout_cont", state, row, use_resistance=use_resistance)
        if exit_reason is not None:
            exit_price, exit_reason_final = row.Close, exit_reason
            break
    if exit_price is None:
        exit_price, exit_reason_final = daily.iloc[-1].Close, "open_at_end"
    pnl_pct = (exit_price / trigger - 1) * 100
    r_multiple = (exit_price - trigger) / R if R else float("nan")
    return pnl_pct, r_multiple, exit_reason_final


def concentration(s):
    total = s.sum()
    if not total:
        return float("nan")
    return s.sort_values(ascending=False).head(10).sum() / total * 100


def stats(df, variant, label):
    pnl = df[f"{variant}_pnl"]
    r = df[f"{variant}_r"]
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    wr = len(wins) / len(pnl) * 100
    mean_r_exp = r.mean()
    print(f"    {label:<12} n={len(pnl):<5} win={wr:5.1f}%  med_pnl={pnl.median():+.2f}%  "
          f"mean_R={mean_r_exp:+.3f}R  conc={concentration(pnl):.1f}%")


POPS = {
    "BIG (full-history, n=5213)": pd.read_csv("runs/pop_fresh40_big.csv", parse_dates=["entry_date"]),
    "SMALL (cache-window, n=365)": pd.read_csv("runs/pop_fresh40_small.csv", parse_dates=["entry_date"]),
    "SMALL+1PM cutoff (n=298)": pd.read_csv("runs/pop_fresh40_cutoff.csv", parse_dates=["entry_date"]),
}

VARIANTS = ["baseline", "2R", "3R", "trail_only"]

for pop_name, pop_df in POPS.items():
    print(f"\n{'=' * 100}\n{pop_name}\n{'=' * 100}")
    rows = []
    for r in pop_df.itertuples():
        daily = load_daily(r.ticker)
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0:
            continue
        i = match[0]
        row = {}
        for v in VARIANTS:
            pnl, rm, reason = simulate_variant(daily, i, v)
            row[f"{v}_pnl"] = pnl
            row[f"{v}_r"] = rm
            row[f"{v}_reason"] = reason
        rows.append(row)
    df = pd.DataFrame(rows)
    for v in VARIANTS:
        stats(df, v, v)

    # decompose 2R "wins": did they hit the real target, or get stopped near breakeven?
    for v in ["2R", "3R"]:
        winners = df[df[f"{v}_pnl"] > 0]
        hit_target = winners[winners[f"{v}_reason"] == "resistance"]
        stopped_above_be = winners[winners[f"{v}_reason"] != "resistance"]
        print(f"    {v} winner breakdown: n={len(winners)}, hit real target={len(hit_target)} "
              f"({len(hit_target)/len(winners)*100:.1f}%, mean_R={hit_target[f'{v}_r'].mean():+.2f}), "
              f"stopped above breakeven={len(stopped_above_be)} ({len(stopped_above_be)/len(winners)*100:.1f}%, "
              f"mean_R={stopped_above_be[f'{v}_r'].mean():+.2f})")

    # trail_only exit-reason breakdown
    to = df.trail_only_reason.value_counts()
    print(f"    trail_only exit reasons: {to.to_dict()}")
