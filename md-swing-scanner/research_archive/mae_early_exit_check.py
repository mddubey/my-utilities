"""Isolated research only (2026-09-14+). MAE-early-exit-threshold analysis, built on the
CURRENT baseline stop (3xATR trailing) specifically -- Family C (structural low) was
rejected on style grounds (real data showed p90=42 days, max=426 days hold, incompatible
with "short-term swings, not months longs"). This tests the original ask directly: can an
early adverse-excursion threshold, checked WHILE a trade is open under the unchanged
baseline rule, catch a meaningful share of eventual losers before the real stop is hit,
without sacrificing too many eventual winners (a few "miracle recovery" losses are
explicitly accepted).

Methodology (grounded in the MAE-divergence approach from established TA practice, not
invented here): for every trade, walk day-by-day under the REAL baseline exit logic,
track the first day (if any) the running adverse excursion from the trigger price
reaches each candidate R-multiple threshold. For each threshold: (1) diagnostic -- of
trades that cross it before their real exit, what fraction were eventually winners
(false positives / miracle recoveries) vs losers (true positives, correctly flagged);
(2) simulate an OVERLAY -- exit at whichever comes first, the real baseline rule or the
threshold breach (at that day's Close) -- and report the net effect on aggregate
win rate/median/expectancy/concentration, same overlay-testing convention used for the
EMA34-break and 3-day-stall overlays earlier this session.

R is fixed at 3*atr14_at_entry (the current baseline's own stop distance), so thresholds
are expressed as a FRACTION of the actual live stop distance -- directly answers "how
much of the full stop distance do we need to reach before it's already predictive."
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005
THRESHOLDS = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

daily_cache = {}


def load_daily(ticker):
    if ticker not in daily_cache:
        daily_cache[ticker] = backtest.load(ticker, daily_pivots).reset_index()
    return daily_cache[ticker]


def simulate_with_tracking(daily, i):
    trigger = daily.iloc[i].high10_prior * TRIGGER_CLEARANCE
    atr_entry = daily.iloc[i].atr14
    R = backtest.ATR_TRAIL_MULT * atr_entry

    state = dict(entry_price=trigger, peak_close=trigger, peak_high=trigger, target=None)
    exit_price, exit_reason, exit_day = None, None, None
    crossing_day = {t: None for t in THRESHOLDS}  # first day index (j) each threshold is reached
    crossing_price = {t: None for t in THRESHOLDS}

    for j in range(i + 1, len(daily)):
        row = daily.iloc[j]
        if row.corp_action_day:
            exit_price, exit_reason, exit_day = state["peak_close"], "corp_action", j
            break

        if R:
            adverse_r = (trigger - row.Low) / R
            for t in THRESHOLDS:
                if crossing_day[t] is None and adverse_r >= t:
                    crossing_day[t] = j
                    crossing_price[t] = row.Close

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

        if hit_resistance or hit_stop or hit_climax:
            exit_reason = "resistance" if hit_resistance else "climax" if hit_climax else "stop"
            exit_price, exit_day = row.Close, j
            break

    if exit_price is None:
        exit_price, exit_reason, exit_day = daily.iloc[-1].Close, "open_at_end", len(daily) - 1

    real_pnl_pct = (exit_price / trigger - 1) * 100

    row_out = dict(real_pnl_pct=real_pnl_pct, exit_day=exit_day)
    for t in THRESHOLDS:
        row_out[f"cross_day_{t}"] = crossing_day[t]
        # overlay pnl: if threshold crossed BEFORE the real exit day, cut there instead
        if crossing_day[t] is not None and crossing_day[t] < exit_day:
            row_out[f"overlay_pnl_{t}"] = (crossing_price[t] / trigger - 1) * 100
        else:
            row_out[f"overlay_pnl_{t}"] = real_pnl_pct
    return row_out


def concentration(s):
    total = s.sum()
    if not total:
        return float("nan")
    return s.sort_values(ascending=False).head(10).sum() / total * 100


def run():
    df = pd.read_csv("runs/rsi_max_sweep_80.csv", parse_dates=["entry_date"])
    print(f"n = {len(df)}")

    rows = []
    for idx, r in enumerate(df.itertuples(), 1):
        if idx % 2000 == 0:
            print(f"  {idx}/{len(df)}", flush=True)
        daily = load_daily(r.ticker)
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0:
            continue
        i = match[0]
        res = simulate_with_tracking(daily, i)
        res["ticker"] = r.ticker
        res["entry_date"] = r.entry_date
        rows.append(res)

    out = pd.DataFrame(rows)
    out.to_csv("runs/mae_early_exit_check.csv", index=False)
    print(f"n with data = {len(out)}\n")

    print("=== Diagnostic: of trades whose MAE crosses threshold T before the real exit, catch-rate vs false-positive-rate ===")
    for t in THRESHOLDS:
        crossed = out[out[f"cross_day_{t}"].notna() & (out[f"cross_day_{t}"] < out.exit_day)]
        if len(crossed) == 0:
            continue
        eventual_losers = (crossed.real_pnl_pct <= 0).sum()
        eventual_winners = (crossed.real_pnl_pct > 0).sum()
        all_losers = (out.real_pnl_pct <= 0).sum()
        catch_rate = eventual_losers / all_losers * 100 if all_losers else float("nan")
        fp_rate = eventual_winners / len(crossed) * 100
        print(f"  T={t}R  n_crossed={len(crossed):<6} eventual_losers={eventual_losers:<6} eventual_winners={eventual_winners:<6}  "
              f"catch-rate(of all losers)={catch_rate:5.1f}%  false-positive-rate(of crossed)={fp_rate:5.1f}%")

    print("\n=== Overlay effect: cut at threshold T (if reached before real exit), vs baseline alone ===")
    baseline_stats = out.real_pnl_pct
    wins = baseline_stats[baseline_stats > 0]; losses = baseline_stats[baseline_stats <= 0]
    wr = len(wins) / len(baseline_stats) * 100
    exp = (wr / 100) * wins.mean() + (1 - wr / 100) * losses.mean()
    print(f"  baseline (no overlay)         win={wr:5.1f}%  med={baseline_stats.median():+.2f}%  exp={exp:+.3f}%  conc={concentration(baseline_stats):.1f}%")
    for t in THRESHOLDS:
        s = out[f"overlay_pnl_{t}"]
        wins = s[s > 0]; losses = s[s <= 0]
        wr = len(wins) / len(s) * 100
        exp = (wr / 100) * (wins.mean() if len(wins) else 0) + (1 - wr / 100) * (losses.mean() if len(losses) else 0)
        print(f"  T={t}R overlay                  win={wr:5.1f}%  med={s.median():+.2f}%  exp={exp:+.3f}%  conc={concentration(s):.1f}%")


if __name__ == "__main__":
    run()
