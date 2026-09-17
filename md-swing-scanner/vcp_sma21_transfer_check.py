"""Isolated research only (2026-09-15). One clean transfer test, per the critic's explicit
instruction after approving the BC wiring: does VCP/Coiled Spring also benefit from
swapping its post-engagement EMA21 floor for the new SMA21-2% mechanism? Everything else
(entry, structural-low initial stop capped at MAX_INITIAL_RISK_PCT, resistance ratchet,
climax exit, MAX_HOLD_DAYS=15 cap) stays exactly as production already has it -- no
re-sweep, no re-optimization, no re-testing Family C for VCP (that was BC-only).

Population: the same VCP live-equivalent set built for the Geometry Audit (RQ-43A) --
runs/vcp_live_equiv_tol_0.4.csv, full history (n=3971) and freshness<=0.40 subset
(n=2048) -- matching what that audit itself reported on, per the critic's own framing of
this as a single clean comparison, not a fresh population-discipline exercise.

Decision rule (critic's, not re-derived here): adopt if candidate is better-or-tied
(architectural simplicity argument), keep VCP as-is only if clearly worse. Not treating
this as a new-edge discovery -- no significance test demanded.

RESULT (2026-09-15): candidate won on expectancy and concentration on BOTH populations
(full pop +4.972%->+5.133%, freshness<=0.40 +2.404%->+2.473%; concentration ties/improves
slightly), win rate down ~1.5-2pp (same "fewer but bigger" trade-off already seen and
accepted for breakout_cont). ADOPTED -- wired into backtest.py's current_stop_level()
(coiled_spring branch now shares the same SMA21-2% post-engagement floor as
breakout_cont). See FINDINGS.md and current_stop_level()'s own docstring for the full
validation trail. This script is kept as the reproducible record of that one test, not
run again as part of any later sweep.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots
from vcp import base_pivot
from live_checkpoint import _percentile_from_breaks, RSI_PCT_BREAKS, MOMENTUM_PCT_BREAKS
from research.metrics import concentration_v1, concentration_v2

TRIGGER_CLEARANCE = 1.005
MAX_INITIAL_RISK_PCT = 0.08

daily_cache = {}


def load_daily(ticker):
    if ticker not in daily_cache:
        daily_cache[ticker] = backtest.load(ticker, daily_pivots).reset_index()
    return daily_cache[ticker]


def freshness(rsi14, mom20):
    if pd.isna(rsi14) or pd.isna(mom20):
        return None
    return 0.5 * _percentile_from_breaks(rsi14, RSI_PCT_BREAKS) + 0.5 * _percentile_from_breaks(mom20, MOMENTUM_PCT_BREAKS)


def simulate(daily, i, trigger, structural_low_capped, mechanism):
    """Manual replica of check_exit()'s real logic (resistance ratchet, climax gate,
    MAX_HOLD_DAYS cap all copied verbatim) -- the ONLY thing that differs by `mechanism`
    is the post-engagement trailing floor, current EMA21 vs candidate SMA21-2%. (At the
    time this test ran, production's current_stop_level() still used EMA21 for VCP --
    this replica is what let the "current" vs "candidate" comparison happen before
    committing to the change.)"""
    state = dict(entry_price=trigger, peak_close=trigger, peak_high=trigger,
                  structural_low=structural_low_capped, target=None, days_held=0)
    exit_price, exit_reason, hold_days = None, None, None

    for j in range(i + 1, len(daily)):
        row = daily.iloc[j]
        hold = j - i
        if row.corp_action_day:
            exit_price, exit_reason, hold_days = state["peak_close"], "corp_action", hold
            break
        state["days_held"] += 1
        if state["days_held"] >= backtest.MAX_HOLD_DAYS:
            exit_price, exit_reason, hold_days = row.Close, "max_hold_cap", hold
            break

        made_new_high = row.High > state["peak_high"]
        state["peak_close"] = max(state["peak_close"], row.Close)
        state["peak_high"] = max(state["peak_high"], row.High)
        day_range = row.High - row.Low
        close_pos = (row.Close - row.Low) / day_range if day_range > 0 else 1.0

        fresh_target = backtest.resistance_target(row.Close, row)
        if fresh_target is not None:
            state["target"] = fresh_target if state["target"] is None else max(state["target"], fresh_target)
        hit_resistance = state["target"] is not None and row.Close >= state["target"]

        climax_volume = pd.notna(row.vol_max_run) and row.Volume >= row.vol_max_run
        already_extended = state["peak_close"] >= state["entry_price"] * backtest.CLIMAX_MIN_GAIN_PCT
        hit_climax = (already_extended and made_new_high and climax_volume
                      and close_pos <= backtest.CLIMAX_WEAK_CLOSE_PCT)

        engaged = state["peak_close"] >= state["entry_price"] * backtest.TRAIL_ENGAGE_PCT
        base_stop = state["structural_low"]
        if not engaged:
            stop_level = base_stop
        elif mechanism == "current":
            stop_level = max(base_stop, row.ema21)
        else:  # candidate
            if pd.isna(row.sma21):
                stop_level = max(base_stop, row.ema21)
            else:
                stop_level = max(base_stop, row.sma21 * (1 - backtest.SMA21_TRAIL_BUFFER_PCT))
        hit_stop = row.Close < stop_level

        if hit_resistance or hit_stop or hit_climax:
            exit_reason = "resistance" if hit_resistance else "climax" if hit_climax else "stop"
            exit_price, hold_days = row.Close, hold
            break

    if exit_price is None:
        exit_price, exit_reason, hold_days = daily.iloc[-1].Close, "open_at_end", len(daily) - 1 - i

    return dict(pnl_pct=(exit_price / trigger - 1) * 100, exit_reason=exit_reason, hold_days=hold_days)


def report(sub, label):
    wins = sub[sub.pnl_pct > 0].pnl_pct
    losses = sub[sub.pnl_pct <= 0].pnl_pct
    wr = len(wins) / len(sub) * 100
    exp = (wr / 100) * (wins.mean() if len(wins) else 0) + (1 - wr / 100) * (losses.mean() if len(losses) else 0)
    print(f"  {label:<10} n={len(sub):<6} win={wr:5.1f}%  med={sub.pnl_pct.median():+.2f}%  exp={exp:+.3f}%  "
          f"conc_v1={concentration_v1(sub.pnl_pct):.1f}%  conc_v2={concentration_v2(sub.pnl_pct):.1f}%  "
          f"hold(med/p90/max)={sub.hold_days.median():.0f}/"
          f"{sub.hold_days.quantile(0.9):.0f}/{sub.hold_days.max():.0f}")


def run():
    df = pd.read_csv("runs/vcp_live_equiv_tol_0.4.csv", parse_dates=["entry_date"])

    rows_by_mech = {"current": [], "candidate": []}
    for idx, r in enumerate(df.itertuples(), 1):
        if idx % 1000 == 0:
            print(f"  {idx}/{len(df)}", flush=True)
        daily = load_daily(r.ticker)
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0:
            continue
        i = match[0]
        row = daily.iloc[i]
        base = base_pivot(daily, i)
        if base is None:
            continue
        pivot, structural_low = base
        trigger = pivot * TRIGGER_CLEARANCE
        structural_low_capped = max(structural_low, trigger * (1 - MAX_INITIAL_RISK_PCT))
        atr_entry = row.atr14
        if not atr_entry or pd.isna(atr_entry):
            continue
        rsi14 = row.get("rsi14", None)
        close_20ago = row.get("close_20ago", None)
        mom20 = ((row.Close / close_20ago - 1) * 100) if close_20ago else None
        freshness_score = freshness(rsi14, mom20)

        for mech in ("current", "candidate"):
            res = simulate(daily, i, trigger, structural_low_capped, mech)
            res["freshness_score"] = freshness_score
            rows_by_mech[mech].append(res)

    print(f"{'=' * 90}\nVCP transfer test: current (EMA21 floor) vs candidate (SMA21-2% floor)\n{'=' * 90}")
    for mech, rows in rows_by_mech.items():
        out = pd.DataFrame(rows)
        print(f"\n--- {mech} ---")
        print("Full population (all freshness):")
        report(out, mech)
        fresh = out.dropna(subset=["freshness_score"])
        fresh = fresh[fresh.freshness_score <= 0.40]
        print(f"Freshness<=0.40 subset:")
        report(fresh, mech)


if __name__ == "__main__":
    run()
