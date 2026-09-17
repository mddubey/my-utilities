"""Isolated research only (2026-09-13). RVOL@Trigger final audit (critic response-24 item
#6, left unfinished after update-30): larger population than the n=364/690 quartile pass,
and a real decile sweep instead of quartiles, to determine whether the apparent U-shape
(Q3 peak, Q4 drop) seen in update-28 is real or just quartile-boundary noise.

Uses the FULL vwap_and_timeofday_check.csv pool (n=934, all raw-trigger entries, not
pre-filtered by streak-confirmation) rather than the streak>=3 subset (n=690/692) used in
update-28 -- the larger, unfiltered population the critic asked for. Reports both options
(day+1) and swing (check_exit) outcomes per the standing dual-check rule.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import intraday_cache
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005


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


def clock_time_fraction(by_day, day, t, lookback_days=20):
    days = sorted(d for d in by_day if d < day)[-lookback_days:]
    fracs = []
    for d in days:
        day_bars = by_day[d]
        total = day_bars.Volume.sum()
        if not total:
            continue
        so_far = day_bars[day_bars.index.time <= t].Volume.sum()
        fracs.append(so_far / total)
    if len(fracs) < 5:
        return None
    return pd.Series(fracs).median()


def run():
    pool = pd.read_csv("runs/vwap_and_timeofday_check.csv", parse_dates=["entry_date"])
    cache = {}
    results = []
    for _, r in pool.iterrows():
        if r.ticker not in cache:
            daily = backtest.load(r.ticker, daily_pivots).reset_index()
            try:
                intraday = intraday_cache.load(r.ticker)
            except FileNotFoundError:
                intraday = None
            by_day = {}
            if intraday is not None and not intraday.empty:
                idx = intraday.index.tz_convert("Asia/Kolkata").tz_localize(None)
                intraday = intraday.set_axis(idx)
                by_day = {d: g for d, g in intraday.groupby(intraday.index.normalize())}
            cache[r.ticker] = (daily, by_day)
        daily, by_day = cache[r.ticker]

        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0:
            continue
        i = match[0]
        row = daily.iloc[i]
        trigger = row.high10_prior * TRIGGER_CLEARANCE
        day = pd.Timestamp(r.entry_date).normalize()
        day_bars = by_day.get(day)
        if day_bars is None or day_bars.empty:
            continue
        crossed = day_bars[day_bars.High >= trigger]
        if crossed.empty:
            continue
        bar = crossed.iloc[0]
        t = bar.name.time()

        vol_so_far = day_bars[day_bars.index.time <= t].Volume.sum()
        frac = clock_time_fraction(by_day, day, t)
        if not (frac and frac > 0.05 and pd.notna(row.vol_mean_prior) and row.vol_mean_prior):
            continue
        rvol = (vol_so_far / frac) / row.vol_mean_prior

        swing_out = simulate_swing(daily, i, trigger)
        swing_pnl = (swing_out["exit_price"] / trigger - 1) * 100

        results.append(dict(ticker=r.ticker, entry_date=r.entry_date, rvol_at_trigger=rvol,
                             day1_pnl_pct=r.day1_pnl_pct, swing_pnl_pct=swing_pnl,
                             swing_open=swing_out["open_at_end"]))

    out = pd.DataFrame(results)
    out.to_csv("runs/rvol_trigger_audit.csv", index=False)
    print(f"n = {len(out)}  (vs n=364 in update-28's streak-filtered pass -- larger, unfiltered population)\n")

    corr_opt = out.rvol_at_trigger.corr(out.day1_pnl_pct)
    corr_swing = out.rvol_at_trigger.corr(out.swing_pnl_pct)
    rank_opt = out.rvol_at_trigger.rank().corr((out.day1_pnl_pct > 0).astype(int))
    rank_swing = out.rvol_at_trigger.rank().corr((out.swing_pnl_pct > 0).astype(int))
    print(f"Pearson corr vs day1_pnl_pct: {corr_opt:+.3f}   vs swing_pnl_pct: {corr_swing:+.3f}")
    print(f"rank-corr vs options win: {rank_opt:+.3f}   vs swing win: {rank_swing:+.3f}\n")

    out["decile"] = pd.qcut(out.rvol_at_trigger.rank(method="first"), 10, labels=[f"D{i}" for i in range(1, 11)])
    g = out.groupby("decile", observed=True).agg(
        n=("rvol_at_trigger", "count"),
        rvol_range=("rvol_at_trigger", lambda s: f"{s.min():.2f}-{s.max():.2f}"),
        opt_win=("day1_pnl_pct", lambda s: (s > 0).mean() * 100),
        opt_mean=("day1_pnl_pct", "mean"),
        swing_win=("swing_pnl_pct", lambda s: (s > 0).mean() * 100),
        swing_mean=("swing_pnl_pct", "mean"),
    )
    print("=== decile sweep ===")
    for d in [f"D{i}" for i in range(1, 11)]:
        row = g.loc[d]
        print(f"  {d} (rvol {row.rvol_range}): n={int(row.n):<3} OPTIONS win {row.opt_win:5.1f}% mean {row.opt_mean:+.2f}%   |   "
              f"SWING win {row.swing_win:5.1f}% mean {row.swing_mean:+.2f}%")

    # explicit monotonicity check
    opt_series = g.opt_win.values
    diffs = [opt_series[i+1] - opt_series[i] for i in range(len(opt_series)-1)]
    n_up = sum(1 for d in diffs if d > 0)
    n_down = sum(1 for d in diffs if d < 0)
    print(f"\nmonotonicity check (options win rate across deciles): {n_up} increases, {n_down} decreases "
          f"out of {len(diffs)} steps -- {'looks monotonic' if n_up==0 or n_down==0 else 'NOT monotonic, direction flips'}")


if __name__ == "__main__":
    run()
