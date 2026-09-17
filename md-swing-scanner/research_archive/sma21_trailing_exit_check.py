"""Isolated research only (2026-09-14+). Critic's SMA21 standalone trailing-exit family
(their final-revised priority, ahead of another ATR sweep). Explicit architectural
constraint from the critic: keep entry AND the pre-engagement initial stop completely
unchanged -- only replace the EXISTING post-TRAIL_ENGAGE_PCT floor mechanism
(currently max(base_stop, row.ema21), Close<level single-day) with real SMA21 variants.
Resistance target, climax exit, and the now-production MAX_HOLD_DAYS=15 cap are all left
untouched, matching how the critic explicitly separated "initial protection" from "trend
exit" as different jobs.

Variants (critic's own naming):
  A. Close < SMA21 -> exit (closest to current, just EMA->SMA)
  B. Low < SMA21 -> exit (tighter, single low-touch, expected noisier)
  C. Two consecutive closes below SMA21 -> exit (slower, less one-day-shakeout-prone)
  D. Close < SMA21 - 0.5*ATR buffer -> exit

Required metrics per critic's explicit ask: expectancy, median return, average winner,
average loser, win rate, concentration, median/p90/max holding period, MFE captured, and
"short-swing compliance" -- the last one is why hold-period distribution is reported for
every variant, not just headline win/expectancy, given the Family C lesson.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from stop_family_research import load_daily, concentration

TRIGGER_CLEARANCE = 1.005
MAX_HOLD_DAYS = 15
sma21_cache = {}


def get_sma21(ticker, daily):
    if ticker not in sma21_cache:
        sma21_cache[ticker] = daily.Close.rolling(21).mean()
    return sma21_cache[ticker]


def simulate(ticker, daily, i, mechanism):
    trigger = daily.iloc[i].high10_prior * TRIGGER_CLEARANCE
    sma21 = get_sma21(ticker, daily)
    state = dict(entry_price=trigger, peak_close=trigger, peak_high=trigger, target=None)
    exit_price, exit_reason, hold_days = None, None, None
    below_streak = 0

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
        engaged = state["peak_close"] >= state["entry_price"] * backtest.TRAIL_ENGAGE_PCT
        s21 = sma21.iloc[j]

        hit_stop = False
        if not engaged:
            hit_stop = row.Close < base_stop
        else:
            if pd.isna(s21):
                stop_level = max(base_stop, row.ema21)  # fall back to current mechanism if SMA21 undefined
                hit_stop = row.Close < stop_level
            elif mechanism == "current":
                stop_level = max(base_stop, row.ema21)
                hit_stop = row.Close < stop_level
            elif mechanism == "A_close":
                stop_level = max(base_stop, s21)
                hit_stop = row.Close < stop_level
            elif mechanism == "B_low":
                hit_stop = row.Low < s21 and row.Close < s21  # still needs a real stop-price basis: use Low touch, but only actually exit if it's a genuine breach (base_stop also still applies as a floor)
                stop_level = max(base_stop, s21)
                hit_stop = row.Low < stop_level
            elif mechanism == "C_2close":
                below = row.Close < s21
                below_streak = below_streak + 1 if below else 0
                hit_stop = (below_streak >= 2) or (row.Close < base_stop)
            elif mechanism == "D_buffer":
                stop_level = max(base_stop, s21 - 0.5 * row.atr14)
                hit_stop = row.Close < stop_level

        if hit_resistance or hit_stop or hit_climax:
            exit_reason = "resistance" if hit_resistance else "climax" if hit_climax else "stop"
            exit_price, hold_days = row.Close, hold
            break

    if exit_price is None:
        exit_price, exit_reason, hold_days = daily.iloc[-1].Close, "open_at_end", len(daily) - 1 - i

    return dict(pnl_pct=(exit_price / trigger - 1) * 100, exit_reason=exit_reason, hold_days=hold_days)


VARIANTS = ["current", "A_close", "B_low", "C_2close", "D_buffer"]

POPS = {
    "daily (n=5213)": pd.read_csv("runs/pop_fresh40_big.csv", parse_dates=["entry_date"]),
    "intraday (n=365)": pd.read_csv("runs/pop_fresh40_small.csv", parse_dates=["entry_date"]),
    "intraday+cutoff (n=298)": pd.read_csv("runs/pop_fresh40_cutoff.csv", parse_dates=["entry_date"]),
}

for pop_name, df in POPS.items():
    print(f"{'=' * 110}\n{pop_name}\n{'=' * 110}")
    for vname in VARIANTS:
        rows = []
        for r in df.itertuples():
            daily = load_daily(r.ticker)
            match = daily.index[daily.Date == r.entry_date]
            if len(match) == 0:
                continue
            i = match[0]
            rows.append(simulate(r.ticker, daily, i, vname))
        out = pd.DataFrame(rows)
        wins = out[out.pnl_pct > 0].pnl_pct
        losses = out[out.pnl_pct <= 0].pnl_pct
        wr = len(wins) / len(out) * 100
        exp = (wr / 100) * (wins.mean() if len(wins) else 0) + (1 - wr / 100) * (losses.mean() if len(losses) else 0)
        print(f"  {vname:<12} n={len(out):<6} win={wr:5.1f}%  med={out.pnl_pct.median():+.2f}%  "
              f"avg_win={wins.mean() if len(wins) else 0:+.2f}%  avg_loss={losses.mean() if len(losses) else 0:+.2f}%  "
              f"exp={exp:+.3f}%  conc={concentration(out.pnl_pct):.1f}%  "
              f"hold(med/p90/max)={out.hold_days.median():.0f}/{out.hold_days.quantile(0.9):.0f}/{out.hold_days.max():.0f}")
    print()
