"""Isolated research only (2026-09-14). Reconsideration-shortlist item 3 (critic_update_35,
"3-day-stall exit (armed at 0.5-0.6R)"): originally adopted as a backtest finding on
2026-09-05 (arm once a trade reaches ~0.5-0.6R, R=ATR_TRAIL_MULT*ATR14 at entry, then exit
after 3 consecutive trading days with no fresh High above the running peak since entry) --
but never actually wired into production check_exit(), and later real-money portfolio
testing found it only helps when capital-constrained (₹1L), loses at ₹2L/₹5L (clips
right-tail winners). Standing decision at the time: no stall on the stock/swing leg.

Shortlist framing: with freshness+timing-cutoff now removing a lot of the noisy/bad
trades on entry, does this reverse (fewer bad trades left to cut, so it may clip more
good trades than bad now) -- direction was explicitly flagged as uncertain, not assumed.

Tested as an OVERLAY (exit at whichever fires first: the real check_exit() logic, or the
stall condition), on the current freshness-conditioned population (n=467, same population
used throughout this session's EMA work) -- matching the same methodology used for the
EMA34-break overlay test (ema34_exit_overlay_check.py).

Arm threshold: 0.55R (mid-plateau per the original 2026-09-05 sweep, not the single best
point, to avoid reading noise as signal). Armed once daily Close >= entry + 0.55*R.
"Fresh high" tracked on daily High vs. the running peak High since entry (initialized to
the trigger/entry price). Once armed, exit at the first day closing a 3rd consecutive
day with no fresh high.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005
ATR_TRAIL_MULT = 3.0
ARM_R_FRACTION = 0.55
STALL_DAYS = 3


def simulate(daily, i, add_stall_overlay):
    trigger = daily.iloc[i].high10_prior * TRIGGER_CLEARANCE
    atr_entry = daily.iloc[i].atr14
    R = ATR_TRAIL_MULT * atr_entry
    arm_price = trigger + ARM_R_FRACTION * R

    state = dict(entry_price=trigger, peak_close=trigger, peak_high=trigger, structural_low=0.0, target=None)
    peak_high_since_entry = trigger
    armed = False
    no_new_high_streak = 0

    exit_price = None
    overlay_fired = False
    for j in range(i + 1, len(daily)):
        row = daily.iloc[j]
        if row.corp_action_day:
            exit_price = state["peak_close"]
            break
        exit_reason, state = backtest.check_exit("breakout_cont", state, row, use_resistance=True)

        if not armed and row.Close >= arm_price:
            armed = True

        if row.High > peak_high_since_entry:
            peak_high_since_entry = row.High
            no_new_high_streak = 0
        else:
            no_new_high_streak += 1

        if exit_reason is None and add_stall_overlay and armed and no_new_high_streak >= STALL_DAYS:
            exit_reason = "stall_overlay"
            overlay_fired = True

        if exit_reason is not None:
            exit_price = row.Close
            break
    if exit_price is None:
        exit_price = daily.iloc[-1].Close
    return (exit_price / trigger - 1) * 100, overlay_fired


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
    baseline_recomputed, overlay_pnl, overlay_fired_l = [], [], []
    for r in df.itertuples():
        if r.ticker not in cache:
            cache[r.ticker] = backtest.load(r.ticker, daily_pivots).reset_index()
        daily = cache[r.ticker]
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0:
            baseline_recomputed.append(None); overlay_pnl.append(None); overlay_fired_l.append(None)
            continue
        i = match[0]
        b_pnl, _ = simulate(daily, i, add_stall_overlay=False)
        o_pnl, fired = simulate(daily, i, add_stall_overlay=True)
        baseline_recomputed.append(b_pnl); overlay_pnl.append(o_pnl); overlay_fired_l.append(fired)

    df["baseline_recomputed"] = baseline_recomputed
    df["stall_overlay_pnl"] = overlay_pnl
    df["stall_overlay_fired"] = overlay_fired_l
    df.to_csv("runs/stall_exit_overlay_check.csv", index=False)

    sub = df.dropna(subset=["stall_overlay_pnl"])
    print(f"n with data = {len(sub)}\n")

    mismatch = (sub.baseline_recomputed - sub.swing_pnl_pct).abs() > 0.01
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
    print("\n=== CURRENT rule + 3-day-stall overlay (arm at 0.55R) ===")
    stats(sub.stall_overlay_pnl, "with stall overlay")

    fired = sub[sub.stall_overlay_fired == True]
    print(f"\noverlay fired (cut earlier than check_exit() would have) on {len(fired)}/{len(sub)} trades ({len(fired)/len(sub)*100:.1f}%)")
    if len(fired):
        print("  Of those, what would the ORIGINAL (no-overlay) rule's outcome have been on those same trades:")
        stats(fired.swing_pnl_pct, "  original outcome (no overlay)")
        stats(fired.stall_overlay_pnl, "  overlay outcome")
        saved_or_cost = (fired.stall_overlay_pnl - fired.swing_pnl_pct).sum()
        print(f"  total pp saved(+)/cost(-) by cutting these {len(fired)} trades early: {saved_or_cost:+.1f}pp")
        better_new = (fired.stall_overlay_pnl > fired.swing_pnl_pct).sum()
        print(f"  overlay better on {better_new}/{len(fired)} of the trades it fired on")


if __name__ == "__main__":
    run()
