"""Isolated research only (2026-09-13). Critic update-28 ask #6 (from response-23's state
machine): acceptance as an EXECUTION-STATE variable, not an entry gate. Entry stays exactly
where it already won (raw trigger, immediate, no wait -- per update-27). What changes is
POST-entry stop management: if the trade never shows streak-confirmed acceptance the same
day it fires (state = Rejected), tighten the trailing stop (ATR_TRAIL_MULT 3.0 -> 1.5,
reusing stop_tightening_research.py's monkeypatch pattern); if it does show acceptance
(state = Accepted), leave the stop at the normal, already-validated 3.0x.

Base population: vwap_and_timeofday_check.csv (n=934), entry = raw trigger price for
every trade (no streak filter applied to the population itself -- both Accepted and
Rejected trades are included, unlike pullback_after_streak.csv's already-filtered n=690).
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import intraday_cache
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005
STREAK_THRESHOLD = 3


def first_acceptance_reached(day_bars, trigger, threshold):
    streak = 0
    for close in day_bars.Close:
        if close > trigger:
            streak += 1
            if streak >= threshold:
                return True
        else:
            streak = 0
    return False


def simulate_swing(rows, entry_i, entry_price):
    state = dict(entry_price=entry_price, peak_close=entry_price, peak_high=entry_price,
                 structural_low=0.0, target=None)
    for j in range(entry_i + 1, len(rows)):
        row = rows.iloc[j]
        if row.corp_action_day:
            return dict(exit_price=state["peak_close"], open_at_end=False)
        exit_reason, state = backtest.check_exit("breakout_cont", state, row, use_resistance=True)
        if exit_reason is not None:
            return dict(exit_price=row.Close, open_at_end=False)
    last = rows.iloc[-1]
    return dict(exit_price=last.Close, open_at_end=True)


def run():
    pool = pd.read_csv("runs/vwap_and_timeofday_check.csv", parse_dates=["entry_date"])
    cache = {}
    results = []
    for _, r in pool.iterrows():
        if r.ticker not in cache:
            cache[r.ticker] = (backtest.load(r.ticker, daily_pivots).reset_index(),
                                intraday_cache.load(r.ticker) if True else None)
        rows, intraday = cache[r.ticker]
        match = rows.index[rows.Date == r.entry_date]
        if len(match) == 0 or match[0] + 1 >= len(rows):
            continue
        i = match[0]
        trigger = rows.iloc[i].high10_prior * TRIGGER_CLEARANCE

        idx = intraday.index.tz_convert("Asia/Kolkata").tz_localize(None)
        day_bars = intraday.set_axis(idx)[idx.normalize() == r.entry_date]
        if day_bars.empty:
            continue
        accepted = first_acceptance_reached(day_bars, trigger, STREAK_THRESHOLD)

        backtest.ATR_TRAIL_MULT = 3.0
        out_normal = simulate_swing(rows, i, trigger)
        backtest.ATR_TRAIL_MULT = 1.5
        out_tight = simulate_swing(rows, i, trigger)
        backtest.ATR_TRAIL_MULT = 3.0  # restore

        results.append(dict(
            ticker=r.ticker, entry_date=r.entry_date, accepted=accepted,
            normal_pnl=(out_normal["exit_price"] / trigger - 1) * 100, normal_open=out_normal["open_at_end"],
            tight_pnl=(out_tight["exit_price"] / trigger - 1) * 100, tight_open=out_tight["open_at_end"],
        ))

    out = pd.DataFrame(results)
    out.to_csv("runs/acceptance_state_check.csv", index=False)

    print(f"n = {len(out)}   accepted (streak>=3 same day): {out.accepted.mean()*100:.1f}%\n")

    def stats(sub, col_pnl, col_open, label):
        win = (sub[col_pnl] > 0).mean() * 100
        med = sub[col_pnl].median()
        mean = sub[col_pnl].mean()
        print(f"  {label}: n={len(sub):<4} ({sub[col_open].sum()} open)  win {win:.1f}%  median {med:+.2f}%  mean {mean:+.2f}%")

    print("=== BASELINE: normal 3.0x ATR stop for everyone ===")
    stats(out, "normal_pnl", "normal_open", "all (baseline)")
    stats(out[out.accepted], "normal_pnl", "normal_open", "  accepted subset")
    stats(out[~out.accepted], "normal_pnl", "normal_open", "  rejected subset")

    print("\n=== IF rejected trades ALWAYS got the tighter 1.5x stop instead ===")
    stats(out[~out.accepted], "tight_pnl", "tight_open", "  rejected subset, tightened")

    print("\n=== STATE-DEPENDENT combined: accepted->normal stop, rejected->tight stop ===")
    combined_pnl = out.apply(lambda r: r.normal_pnl if r.accepted else r.tight_pnl, axis=1)
    combined_open = out.apply(lambda r: r.normal_open if r.accepted else r.tight_open, axis=1)
    combo = pd.DataFrame({"pnl": combined_pnl, "open": combined_open})
    win = (combo.pnl > 0).mean() * 100
    print(f"  n={len(combo)} ({combo.open.sum()} open)  win {win:.1f}%  median {combo.pnl.median():+.2f}%  mean {combo.pnl.mean():+.2f}%")
    print(f"\n  vs baseline (all normal stop): win {(out.normal_pnl>0).mean()*100:.1f}%  median {out.normal_pnl.median():+.2f}%  mean {out.normal_pnl.mean():+.2f}%")


if __name__ == "__main__":
    run()
