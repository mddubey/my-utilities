"""Isolated research only (2026-09-14+). Direct user reframing: the "baseline" (uncapped
3xATR trailing stop) already violates the real practical constraint (cannot hold a
position open beyond ~2-3 weeks) just as much as Family C did, just less obviously --
p90=23 days, max 67-81 days on the daily population. Given a hard MAX_HOLD_DAYS cap is
now mandatory regardless (not optional), the previously-rejected early-exit ideas
(3-day-stall, fixed-N-days-after-arm) need to be re-asked against a DIFFERENT baseline:
not "does this beat an uncapped ride-forever strategy" (the framing that killed them
before, since they were competing against trades that got to run indefinitely), but
"given a 15-trading-day cap is coming regardless, does actively recognizing a stalled
trade and exiting early beat passively riding to the forced cap exit."

Tested across the standard 3-population bracket (daily/intraday/intraday+cutoff, all
freshness<=0.40), per direct instruction to always check all three, no exceptions.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from stop_family_research import load_daily, concentration, VARIANTS

TRIGGER_CLEARANCE = 1.005
MAX_HOLD_DAYS = 15
ARM_R_FRACTION = 0.55
STALL_DAYS = 3


def simulate(daily, i, mechanism, fixed_n=None):
    trigger = daily.iloc[i].high10_prior * TRIGGER_CLEARANCE
    R = backtest.ATR_TRAIL_MULT * daily.iloc[i].atr14
    arm_price = trigger + ARM_R_FRACTION * R

    state = dict(entry_price=trigger, peak_close=trigger, peak_high=trigger, target=None)
    peak_high_since_entry = trigger
    armed, armed_day = False, None
    no_new_high_streak = 0
    exit_price, exit_reason, hold_days = None, None, None

    for j in range(i + 1, len(daily)):
        row = daily.iloc[j]
        hold = j - i
        if row.corp_action_day:
            exit_price, exit_reason, hold_days = state["peak_close"], "corp_action", hold
            break
        if hold >= MAX_HOLD_DAYS:
            exit_price, exit_reason, hold_days = row.Close, "max_hold_cap", hold
            break

        made_new_high = row.High > state["peak_high"]
        state["peak_close"] = max(state["peak_close"], row.Close)
        state["peak_high"] = max(state["peak_high"], row.High)

        fresh_target = backtest.resistance_target(row.Close, row)
        if fresh_target is not None:
            state["target"] = fresh_target if state["target"] is None else max(state["target"], fresh_target)
        hit_resistance = state["target"] is not None and row.Close >= state["target"]

        climax_volume = pd.notna(row.vol_max_run) and row.Volume >= row.vol_max_run
        already_extended = state["peak_close"] >= state["entry_price"] * backtest.CLIMAX_MIN_GAIN_PCT
        day_range = row.High - row.Low
        close_pos = (row.Close - row.Low) / day_range if day_range > 0 else 1.0
        hit_climax = (already_extended and made_new_high and climax_volume
                      and close_pos <= backtest.CLIMAX_WEAK_CLOSE_PCT)

        base_stop = state["peak_close"] - backtest.ATR_TRAIL_MULT * row.atr14
        if state["peak_close"] >= state["entry_price"] * backtest.TRAIL_ENGAGE_PCT:
            stop_level = max(base_stop, row.ema21)
        else:
            stop_level = base_stop
        hit_stop = row.Close < stop_level

        exit_reason_here = "resistance" if hit_resistance else "climax" if hit_climax else "stop" if hit_stop else None

        if not armed and row.Close >= arm_price:
            armed, armed_day = True, hold

        if row.High > peak_high_since_entry:
            peak_high_since_entry = row.High
            no_new_high_streak = 0
        else:
            no_new_high_streak += 1

        if exit_reason_here is None:
            if mechanism == "stall" and armed and no_new_high_streak >= STALL_DAYS:
                exit_reason_here = "stall"
            elif mechanism == "fixed_after_arm" and armed and (hold - armed_day) >= fixed_n:
                exit_reason_here = "fixed_after_arm"

        if exit_reason_here is not None:
            exit_reason, exit_price, hold_days = exit_reason_here, row.Close, hold
            break

    if exit_price is None:
        exit_price, exit_reason, hold_days = daily.iloc[-1].Close, "open_at_end", len(daily) - 1 - i

    return dict(pnl_pct=(exit_price / trigger - 1) * 100, exit_reason=exit_reason, hold_days=hold_days)


VARIANT_DEFS = {
    "ride passively to 15d cap": dict(mechanism="none"),
    "3-day-stall (within cap)": dict(mechanism="stall"),
    "fixed 3d after arm (within cap)": dict(mechanism="fixed_after_arm", fixed_n=3),
    "fixed 5d after arm (within cap)": dict(mechanism="fixed_after_arm", fixed_n=5),
    "fixed 7d after arm (within cap)": dict(mechanism="fixed_after_arm", fixed_n=7),
}

POPS = {
    "daily (n=5213)": pd.read_csv("runs/pop_fresh40_big.csv", parse_dates=["entry_date"]),
    "intraday (n=365)": pd.read_csv("runs/pop_fresh40_small.csv", parse_dates=["entry_date"]),
    "intraday+cutoff (n=298)": pd.read_csv("runs/pop_fresh40_cutoff.csv", parse_dates=["entry_date"]),
}

for pop_name, df in POPS.items():
    print(f"{'=' * 100}\n{pop_name}\n{'=' * 100}")
    for vname, kwargs in VARIANT_DEFS.items():
        rows = []
        for r in df.itertuples():
            daily = load_daily(r.ticker)
            match = daily.index[daily.Date == r.entry_date]
            if len(match) == 0:
                continue
            i = match[0]
            rows.append(simulate(daily, i, **kwargs))
        out = pd.DataFrame(rows)
        wins = out[out.pnl_pct > 0].pnl_pct
        losses = out[out.pnl_pct <= 0].pnl_pct
        wr = len(wins) / len(out) * 100
        exp = (wr / 100) * (wins.mean() if len(wins) else 0) + (1 - wr / 100) * (losses.mean() if len(losses) else 0)
        print(f"  {vname:<34} n={len(out):<6} win={wr:5.1f}%  med={out.pnl_pct.median():+.2f}%  exp={exp:+.3f}%  "
              f"conc={concentration(out.pnl_pct):.1f}%  hold(med/p90/max)={out.hold_days.median():.0f}/{out.hold_days.quantile(0.9):.0f}/{out.hold_days.max():.0f}")
    print()
