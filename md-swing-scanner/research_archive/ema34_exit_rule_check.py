"""Isolated research only (2026-09-14). Reconsideration-shortlist item 4 (critic_update_35,
"EMA34-break automatic early-exit"): tested once before on the OLD long-hold strategy
(2026-09-02) and rejected -- real recoveries cost more than the early exits saved. Re-testing
on the CURRENT freshness-conditioned population and the current strategy, per the
noise-vs-structural framing: is this still a bad exit rule now that a lot of the noisy/bad
trades are already filtered out on entry?

Compares two exit rules on the same 467-trade fresh-only population, same entry (trigger
price = high10_prior * 1.005):
  CURRENT rule: backtest.check_exit()'s real production exit logic (stop/target/trailing) --
    reused directly from runs/hourly_ema_support_recheck.csv's swing_pnl_pct, not recomputed.
  NEW rule: exit the first day daily Close closes below daily EMA34 (no stop, no target,
    just this one condition); if never broken, exit at the last available close (same
    fallback convention used elsewhere this session).
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005


def ema34_exit_pnl(daily, i):
    trigger = daily.iloc[i].high10_prior * TRIGGER_CLEARANCE
    exit_price = None
    hold_days = None
    for j in range(i + 1, len(daily)):
        row = daily.iloc[j]
        if row.corp_action_day:
            exit_price = row.Close
            hold_days = j - i
            break
        if row.Close < row.ema34:
            exit_price = row.Close
            hold_days = j - i
            break
    if exit_price is None:
        exit_price = daily.iloc[-1].Close
        hold_days = len(daily) - 1 - i
    return (exit_price / trigger - 1) * 100, hold_days


def concentration(s):
    total = s.sum()
    if not total:
        return float("nan")
    return s.sort_values(ascending=False).head(10).sum() / total * 100


def run():
    df = pd.read_csv("runs/hourly_ema_support_recheck.csv", parse_dates=["entry_date"])
    df = df.dropna(subset=["swing_pnl_pct"]).copy()
    print(f"n = {len(df)}")

    cache = {}
    new_pnl, new_hold = [], []
    for r in df.itertuples():
        if r.ticker not in cache:
            cache[r.ticker] = backtest.load(r.ticker, daily_pivots).reset_index()
        daily = cache[r.ticker]
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0:
            new_pnl.append(None); new_hold.append(None)
            continue
        i = match[0]
        pnl, hold = ema34_exit_pnl(daily, i)
        new_pnl.append(pnl); new_hold.append(hold)

    df["ema34_exit_pnl_pct"] = new_pnl
    df["ema34_exit_hold_days"] = new_hold
    df.to_csv("runs/ema34_exit_rule_check.csv", index=False)

    sub = df.dropna(subset=["ema34_exit_pnl_pct"])
    print(f"n with data = {len(sub)}\n")

    def stats(pnl, label):
        wins = pnl[pnl > 0]
        losses = pnl[pnl <= 0]
        wr = len(wins) / len(pnl) * 100
        exp = (wr / 100) * (wins.mean() if len(wins) else 0) + (1 - wr / 100) * (losses.mean() if len(losses) else 0)
        print(f"  {label:<28} n={len(pnl):<4} win={wr:5.1f}%  med={pnl.median():+.2f}%  "
              f"exp={exp:+.3f}%  conc={concentration(pnl):.1f}%  avg_loss={losses.mean() if len(losses) else 0:+.2f}%")

    print("=== CURRENT exit rule (real check_exit(), stop/target/trailing) ===")
    stats(sub.swing_pnl_pct, "current rule")
    print("\n=== NEW rule: exit on first daily Close < daily EMA34 ===")
    stats(sub.ema34_exit_pnl_pct, "ema34-break exit")
    print(f"\n  avg hold days (ema34 rule): {sub.ema34_exit_hold_days.mean():.1f}")

    print("\n=== Per-trade comparison: which rule wins more often? ===")
    better_new = (sub.ema34_exit_pnl_pct > sub.swing_pnl_pct).sum()
    better_current = (sub.swing_pnl_pct > sub.ema34_exit_pnl_pct).sum()
    tie = len(sub) - better_new - better_current
    print(f"  new rule better: {better_new}  current rule better: {better_current}  tie: {tie}")
    diff = sub.ema34_exit_pnl_pct - sub.swing_pnl_pct
    print(f"  mean per-trade difference (new - current): {diff.mean():+.3f}pp  median: {diff.median():+.3f}pp")


if __name__ == "__main__":
    run()
