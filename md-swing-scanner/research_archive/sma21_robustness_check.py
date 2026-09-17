"""Isolated research only (2026-09-14+). Critic's explicit ask before promoting SMA21-2%:
a 3x3 robustness grid (activation 2/3/4%, buffer 1/2/3%) around the found-best 3%/2% cell
-- not a search for the maximum, a check for a plateau. If the neighborhood forms a
reasonably broad plateau, the result is trustworthy; if only exactly 3%/2% works, that's
overfitting. Same architecture as sma21_trailing_exit_check.py's D variant (fixed-%
buffer, no ATR anywhere, per the "chuck ATR out" finding) -- only the activation
threshold and buffer size vary here, everything else (entry, pre-engagement stop,
resistance target, climax, MAX_HOLD_DAYS=15 cap) held fixed.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from stop_family_research import load_daily, concentration
from sma21_trailing_exit_check import get_sma21

TRIGGER_CLEARANCE = 1.005
MAX_HOLD_DAYS = 15

ACTIVATIONS = [1.02, 1.03, 1.04]  # +2%, +3%, +4%
BUFFERS = [0.01, 0.02, 0.03]      # 1%, 2%, 3%


def simulate(ticker, daily, i, activation_pct, buffer_pct):
    trigger = daily.iloc[i].high10_prior * TRIGGER_CLEARANCE
    sma21 = get_sma21(ticker, daily)
    state = dict(entry_price=trigger, peak_close=trigger, peak_high=trigger, target=None)
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
        engaged = state["peak_close"] >= state["entry_price"] * activation_pct
        s21 = sma21.iloc[j]

        if not engaged:
            hit_stop = row.Close < base_stop
        elif pd.isna(s21):
            hit_stop = row.Close < max(base_stop, row.ema21)  # fallback if SMA21 undefined this early
        else:
            hit_stop = row.Close < s21 * (1 - buffer_pct)

        if hit_resistance or hit_stop or hit_climax:
            exit_reason = "resistance" if hit_resistance else "climax" if hit_climax else "stop"
            exit_price, hold_days = row.Close, hold
            break

    if exit_price is None:
        exit_price, exit_reason, hold_days = daily.iloc[-1].Close, "open_at_end", len(daily) - 1 - i

    return dict(pnl_pct=(exit_price / trigger - 1) * 100, exit_reason=exit_reason, hold_days=hold_days)


POPS = {
    "daily (n=5213)": pd.read_csv("runs/pop_fresh40_big.csv", parse_dates=["entry_date"]),
    "intraday (n=365)": pd.read_csv("runs/pop_fresh40_small.csv", parse_dates=["entry_date"]),
    "intraday+cutoff (n=298)": pd.read_csv("runs/pop_fresh40_cutoff.csv", parse_dates=["entry_date"]),
}

for pop_name, df in POPS.items():
    print(f"{'=' * 100}\n{pop_name} -- 3x3 activation x buffer grid\n{'=' * 100}")
    print(f"{'activation':<12}{'buffer':<10}{'win%':<8}{'median':<9}{'exp%':<9}{'conc':<8}{'hold(med/p90/max)':<20}")
    for act in ACTIVATIONS:
        for buf in BUFFERS:
            rows = []
            for r in df.itertuples():
                daily = load_daily(r.ticker)
                match = daily.index[daily.Date == r.entry_date]
                if len(match) == 0:
                    continue
                i = match[0]
                rows.append(simulate(r.ticker, daily, i, act, buf))
            out = pd.DataFrame(rows)
            wins = out[out.pnl_pct > 0].pnl_pct
            losses = out[out.pnl_pct <= 0].pnl_pct
            wr = len(wins) / len(out) * 100
            exp = (wr / 100) * (wins.mean() if len(wins) else 0) + (1 - wr / 100) * (losses.mean() if len(losses) else 0)
            hold_str = f"{out.hold_days.median():.0f}/{out.hold_days.quantile(0.9):.0f}/{out.hold_days.max():.0f}"
            print(f"+{int((act-1)*100)}%{'':<8}-{int(buf*100)}%{'':<6}{wr:<8.1f}{out.pnl_pct.median():<9.2f}{exp:<9.3f}{concentration(out.pnl_pct):<8.1f}{hold_str:<20}")
    print()
