"""Isolated research only (2026-09-14+). Initial-stop-loss redesign, prompted directly by
the user's discomfort with 3xATR14 as an INITIAL stop and grounded in external research
(critic's summary of Minervini/O'Neil/Turtle/Chandelier conventions -- Chandelier is a
TRAILING mechanism, not designed to answer "how far below the breakout structure is the
thesis actually invalid"). Tests three stop-family candidates against the CURRENT
production stop (Family A at k=3.0, i.e. baseline) on the full breakout_cont population,
keeping every other part of check_exit() (resistance target ratchet, climax exit,
TRAIL_ENGAGE_PCT->EMA21 floor) untouched -- isolates the ONE thing being tested.

Families:
  A. ATR-multiple:        base_stop = peak_close - k * atr14_today          (current = k=3.0)
  B. Fixed percentage:    base_stop = peak_close * (1 - p)
  C. Structural low - buffer: base_stop = structural_low - b * atr14_at_entry
     structural_low := lowest Low over the 20 trading days BEFORE entry (matches
     live_checkpoint.py's CONSOLIDATION_LOOKBACK convention) -- a fixed level, not
     trailing with peak_close, since the whole point is "where does the base become
     invalid", not "how far below the current peak."

Also tracks each trade's full MAE/MFE trajectory (in R-multiples, R fixed at
3*atr14_at_entry as a stable reference regardless of which stop family is under test) for
the follow-up MAE-early-exit-divergence analysis (does an early adverse-excursion
threshold predict eventual failure well enough to cut before the real stop, catching most
losers while sacrificing few winners).
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots
from research.metrics import concentration_v2 as concentration

TRIGGER_CLEARANCE = 1.005
STRUCTURAL_LOOKBACK = 20

daily_cache = {}


def load_daily(ticker):
    if ticker not in daily_cache:
        daily_cache[ticker] = backtest.load(ticker, daily_pivots).reset_index()
    return daily_cache[ticker]


def simulate(daily, i, stop_fn):
    trigger = daily.iloc[i].high10_prior * TRIGGER_CLEARANCE
    atr_entry = daily.iloc[i].atr14
    R_ref = backtest.ATR_TRAIL_MULT * atr_entry  # fixed reference R, regardless of family under test
    lo = max(0, i - STRUCTURAL_LOOKBACK)
    structural_low = daily.iloc[lo:i].Low.min() if i > lo else trigger * 0.9

    state = dict(entry_price=trigger, peak_close=trigger, peak_high=trigger, target=None, days_held=0)
    exit_price, exit_reason, hold_days = None, None, None
    mae_r, mfe_r = 0.0, 0.0

    for j in range(i + 1, len(daily)):
        row = daily.iloc[j]
        if row.corp_action_day:
            exit_price, exit_reason, hold_days = state["peak_close"], "corp_action", j - i
            break

        # 2026-09-17 fix: MAX_HOLD_DAYS=15 cap (wired 2026-09-15) was also missing here --
        # same staleness as the ema21-vs-sma21 fix above, caught in the same pass.
        state["days_held"] += 1
        if state["days_held"] >= backtest.MAX_HOLD_DAYS:
            exit_price, exit_reason, hold_days = row.Close, "max_hold_cap", j - i
            break

        if R_ref:
            mae_r = max(mae_r, (trigger - row.Low) / R_ref)
            mfe_r = max(mfe_r, (row.High - trigger) / R_ref)

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

        base_stop = stop_fn(state, row, atr_entry, structural_low)
        if state["peak_close"] >= state["entry_price"] * backtest.TRAIL_ENGAGE_PCT:
            # 2026-09-17 fix: this was still row.ema21, the pre-2026-09-15 trail --
            # caught by direct user question ("don't we have some sma21 as exit now?").
            # Current production trail (backtest.SMA21_TRAIL_BUFFER_PCT, wired 2026-09-15)
            # is SMA21-2%, not EMA21 -- the original Family A/B/C comparison (and the
            # Family C adoption decision itself) predates this and was never re-verified
            # against it. Falls back to ema21 only if sma21 is NaN, matching
            # vcp_sma21_transfer_check.py's own fallback convention.
            if pd.isna(row.get("sma21")):
                stop_level = max(base_stop, row.ema21)
            else:
                stop_level = max(base_stop, row.sma21 * (1 - backtest.SMA21_TRAIL_BUFFER_PCT))
        else:
            stop_level = base_stop
        hit_stop = row.Close < stop_level

        if hit_resistance or hit_stop or hit_climax:
            exit_reason = "resistance" if hit_resistance else "climax" if hit_climax else "stop"
            exit_price, hold_days = row.Close, j - i
            break

    if exit_price is None:
        exit_price, exit_reason, hold_days = daily.iloc[-1].Close, "open_at_end", len(daily) - 1 - i

    pnl_pct = (exit_price / trigger - 1) * 100
    return dict(pnl_pct=pnl_pct, exit_reason=exit_reason, hold_days=hold_days, mae_r=mae_r, mfe_r=mfe_r)


# ---- stop-family definitions ----
def family_atr(k):
    return lambda state, row, atr_entry, structural_low: state["peak_close"] - k * row.atr14


def family_pct(p):
    return lambda state, row, atr_entry, structural_low: state["peak_close"] * (1 - p)


def family_structural(b):
    return lambda state, row, atr_entry, structural_low: structural_low - b * atr_entry


VARIANTS = {
    "A_current_3.0ATR (baseline)": family_atr(3.0),
    "A_1.0ATR": family_atr(1.0),
    "A_1.5ATR": family_atr(1.5),
    "A_2.0ATR": family_atr(2.0),
    "A_2.5ATR": family_atr(2.5),
    "B_3pct": family_pct(0.03),
    "B_4pct": family_pct(0.04),
    "B_5pct": family_pct(0.05),
    "B_6pct": family_pct(0.06),
    "B_7pct": family_pct(0.07),
    "B_8pct": family_pct(0.08),
    "C_structural_0.00buf": family_structural(0.0),
    "C_structural_0.25buf": family_structural(0.25),
    "C_structural_0.50buf": family_structural(0.50),
    "C_structural_1.00buf": family_structural(1.00),
}


def run():
    df = pd.read_csv("runs/rsi_max_sweep_80.csv", parse_dates=["entry_date"])
    print(f"n = {len(df)}")

    results = {name: [] for name in VARIANTS}
    for idx, r in enumerate(df.itertuples(), 1):
        if idx % 2000 == 0:
            print(f"  {idx}/{len(df)}", flush=True)
        daily = load_daily(r.ticker)
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0:
            continue
        i = match[0]
        for name, stop_fn in VARIANTS.items():
            res = simulate(daily, i, stop_fn)
            res["ticker"] = r.ticker
            res["entry_date"] = r.entry_date
            results[name].append(res)

    for name, rows in results.items():
        out = pd.DataFrame(rows)
        out.to_csv(f"runs/stop_family_{name.split()[0]}.csv", index=False)

    print("\n" + "=" * 120)
    print(f"{'Variant':<28}{'n':<7}{'win%':<8}{'med_win':<10}{'med_loss':<10}{'exp%':<9}{'avg_loss':<10}{'max_loss':<10}{'PF':<7}{'stop%':<8}{'conc':<8}")
    for name, rows in results.items():
        out = pd.DataFrame(rows)
        wins = out[out.pnl_pct > 0].pnl_pct
        losses = out[out.pnl_pct <= 0].pnl_pct
        wr = len(wins) / len(out) * 100
        exp = (wr / 100) * (wins.mean() if len(wins) else 0) + (1 - wr / 100) * (losses.mean() if len(losses) else 0)
        pf = wins.sum() / abs(losses.sum()) if losses.sum() else float("inf")
        stop_pct = (out.exit_reason == "stop").mean() * 100
        print(f"{name:<28}{len(out):<7}{wr:<8.1f}{wins.median() if len(wins) else 0:<10.2f}"
              f"{losses.median() if len(losses) else 0:<10.2f}{exp:<9.3f}"
              f"{losses.mean() if len(losses) else 0:<10.2f}{losses.min() if len(losses) else 0:<10.2f}"
              f"{pf:<7.2f}{stop_pct:<8.1f}{concentration(out.pnl_pct):<8.1f}")


if __name__ == "__main__":
    run()
