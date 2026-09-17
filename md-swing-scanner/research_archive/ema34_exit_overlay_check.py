"""Isolated research only (2026-09-14). Correction to ema34_exit_rule_check.py: that script
REPLACED the current exit logic with a standalone EMA34-break rule, which isn't the right
test -- the actual question is whether adding EMA34-break as ONE MORE exit condition
alongside the existing stop/target/trailing logic (exit at whichever triggers first)
improves on the current rule alone. Re-simulates day by day using the real check_exit(),
short-circuiting early if daily Close < daily EMA34 fires before check_exit() would have.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005


def simulate(daily, i, add_ema34_overlay):
    trigger = daily.iloc[i].high10_prior * TRIGGER_CLEARANCE
    state = dict(entry_price=trigger, peak_close=trigger, peak_high=trigger, structural_low=0.0, target=None)
    exit_price = None
    hold_days = None
    overlay_fired = False
    for j in range(i + 1, len(daily)):
        row = daily.iloc[j]
        if row.corp_action_day:
            exit_price = state["peak_close"]
            hold_days = j - i
            break
        exit_reason, state = backtest.check_exit("breakout_cont", state, row, use_resistance=True)
        if exit_reason is None and add_ema34_overlay and row.Close < row.ema34:
            exit_reason = "ema34_break_overlay"
            overlay_fired = True
        if exit_reason is not None:
            exit_price = row.Close
            hold_days = j - i
            break
    if exit_price is None:
        exit_price = daily.iloc[-1].Close
        hold_days = len(daily) - 1 - i
    return (exit_price / trigger - 1) * 100, hold_days, overlay_fired


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
    baseline_pnl, overlay_pnl, overlay_hold, overlay_fired_l = [], [], [], []
    for r in df.itertuples():
        if r.ticker not in cache:
            cache[r.ticker] = backtest.load(r.ticker, daily_pivots).reset_index()
        daily = cache[r.ticker]
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0:
            baseline_pnl.append(None); overlay_pnl.append(None); overlay_hold.append(None); overlay_fired_l.append(None)
            continue
        i = match[0]
        b_pnl, _, _ = simulate(daily, i, add_ema34_overlay=False)
        o_pnl, o_hold, fired = simulate(daily, i, add_ema34_overlay=True)
        baseline_pnl.append(b_pnl); overlay_pnl.append(o_pnl); overlay_hold.append(o_hold); overlay_fired_l.append(fired)

    df["baseline_recomputed_pnl"] = baseline_pnl
    df["overlay_pnl_pct"] = overlay_pnl
    df["overlay_hold_days"] = overlay_hold
    df["overlay_fired"] = overlay_fired_l
    df.to_csv("runs/ema34_exit_overlay_check.csv", index=False)

    sub = df.dropna(subset=["overlay_pnl_pct"])
    print(f"n with data = {len(sub)}\n")

    # sanity: baseline_recomputed should match the original swing_pnl_pct (same check_exit logic)
    mismatch = (sub.baseline_recomputed_pnl - sub.swing_pnl_pct).abs() > 0.01
    print(f"sanity check -- recomputed baseline vs original swing_pnl_pct mismatches: {mismatch.sum()} / {len(sub)}\n")

    def stats(pnl, label):
        wins = pnl[pnl > 0]
        losses = pnl[pnl <= 0]
        wr = len(wins) / len(pnl) * 100
        exp = (wr / 100) * (wins.mean() if len(wins) else 0) + (1 - wr / 100) * (losses.mean() if len(losses) else 0)
        print(f"  {label:<32} n={len(pnl):<4} win={wr:5.1f}%  med={pnl.median():+.2f}%  "
              f"exp={exp:+.3f}%  conc={concentration(pnl):.1f}%  avg_loss={losses.mean() if len(losses) else 0:+.2f}%")

    print("=== CURRENT rule alone (no overlay) ===")
    stats(sub.swing_pnl_pct, "current rule")
    print("\n=== CURRENT rule + EMA34-break overlay (exit at whichever fires first) ===")
    stats(sub.overlay_pnl_pct, "with overlay")

    fired = sub[sub.overlay_fired == True]
    not_fired = sub[sub.overlay_fired == False]
    print(f"\noverlay fired (cut earlier than check_exit() would have) on {len(fired)}/{len(sub)} trades ({len(fired)/len(sub)*100:.1f}%)")
    if len(fired):
        print("  Of those, what would the ORIGINAL (no-overlay) rule's outcome have been on those same trades:")
        stats(fired.swing_pnl_pct, "  original outcome (no overlay)")
        stats(fired.overlay_pnl_pct, "  overlay outcome")
        saved_or_cost = (fired.overlay_pnl_pct - fired.swing_pnl_pct).sum()
        print(f"  total pp saved(+)/cost(-) by cutting these {len(fired)} trades early: {saved_or_cost:+.1f}pp")


if __name__ == "__main__":
    run()
