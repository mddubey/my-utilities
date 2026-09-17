"""Isolated research only (2026-09-13). Runaway vs Pullback prediction (critic response-23,
update-28): instead of predicting acceptance (which requires waiting), predict which trades
"run away" (never revisit the trigger intraday -- the best-quality 21.2% population found in
pullback_after_streak.py) using ONLY features available at or before the breach instant, no
waiting, no hindsight. Label reused from pullback_after_streak.csv (ran_away = NOT pulled_back).

Features: freshness score (RSI+momentum percentile blend, same breakpoints as
live_checkpoint.py), consolidation_days, dist_to_trigger_pct, breach candle close position
(breach_candle_quality.csv), plus two new ones built here per the critic's ask: Body/ATR
expansion ratio on the breach bar, and RVOL@Trigger (implied full-day volume pace vs the
20-day trailing average volume, scaled by the historical clock-time volume fraction -- same
mechanism as live_checkpoint._clock_time_volume_fraction, reimplemented standalone here).
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import intraday_cache
from pivots import daily_pivots
from live_checkpoint import _percentile_from_breaks, RSI_PCT_BREAKS, MOMENTUM_PCT_BREAKS

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


def freshness_score(rsi14, momentum_20d):
    if pd.isna(rsi14) or pd.isna(momentum_20d):
        return None
    rsi_pct = _percentile_from_breaks(rsi14, RSI_PCT_BREAKS)
    mom_pct = _percentile_from_breaks(momentum_20d, MOMENTUM_PCT_BREAKS)
    return 0.5 * rsi_pct + 0.5 * mom_pct


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
    label_pop = pd.read_csv("runs/pullback_after_streak.csv", parse_dates=["entry_date"])
    label_pop = label_pop[label_pop.pulled_back.astype(str).isin(["True", "False"])].copy()
    label_pop["ran_away"] = label_pop["pulled_back"].astype(str) == "False"

    feat_pop = pd.read_csv("runs/consolidation_and_room.csv", parse_dates=["entry_date"])
    candle = pd.read_csv("runs/breach_candle_quality.csv", parse_dates=["entry_date"])[
        ["ticker", "entry_date", "close_pos"]]

    df = label_pop.merge(feat_pop, on=["ticker", "entry_date"], how="left")
    df = df.merge(candle, on=["ticker", "entry_date"], how="left")
    df["freshness_score"] = df.apply(lambda r: freshness_score(r.yday_rsi14, r.yday_momentum_20d), axis=1)

    cache = {}
    body_atr_list, rvol_list, swing_pnl_list, swing_open_list = [], [], [], []
    for _, r in df.iterrows():
        ticker, entry_date = r.ticker, r.entry_date
        if ticker not in cache:
            daily = backtest.load(ticker, daily_pivots).reset_index()
            try:
                intraday = intraday_cache.load(ticker)
            except FileNotFoundError:
                intraday = None
            by_day = {}
            if intraday is not None and not intraday.empty:
                idx = intraday.index.tz_convert("Asia/Kolkata").tz_localize(None)
                intraday = intraday.set_axis(idx)
                by_day = {d: g for d, g in intraday.groupby(intraday.index.normalize())}
            cache[ticker] = (daily, by_day)
        daily, by_day = cache[ticker]

        match = daily.index[daily.Date == entry_date]
        if len(match) == 0:
            body_atr_list.append(None); rvol_list.append(None)
            swing_pnl_list.append(None); swing_open_list.append(None)
            continue
        i = match[0]
        row = daily.iloc[i]
        trigger = row.high10_prior * TRIGGER_CLEARANCE

        swing_out = simulate_swing(daily, i, trigger)
        swing_pnl_list.append((swing_out["exit_price"] / trigger - 1) * 100)
        swing_open_list.append(swing_out["open_at_end"])

        day = pd.Timestamp(entry_date).normalize()
        day_bars = by_day.get(day)
        if day_bars is None or day_bars.empty:
            body_atr_list.append(None); rvol_list.append(None); continue
        crossed = day_bars[day_bars.High >= trigger]
        if crossed.empty:
            body_atr_list.append(None); rvol_list.append(None); continue
        bar = crossed.iloc[0]
        t = bar.name.time()

        body_atr = abs(bar.Close - bar.Open) / row.atr14 if pd.notna(row.atr14) and row.atr14 else None
        body_atr_list.append(body_atr)

        vol_so_far = day_bars[day_bars.index.time <= t].Volume.sum()
        frac = clock_time_fraction(by_day, day, t)
        if frac and frac > 0.05 and pd.notna(row.vol_mean_prior) and row.vol_mean_prior:
            rvol = (vol_so_far / frac) / row.vol_mean_prior
        else:
            rvol = None
        rvol_list.append(rvol)

    df["body_atr"] = body_atr_list
    df["rvol_at_trigger"] = rvol_list
    df["swing_pnl_pct"] = swing_pnl_list
    df["swing_open_at_end"] = swing_open_list
    df.to_csv("runs/runaway_prediction_check.csv", index=False)

    print(f"n = {len(df)}   runaway rate: {df.ran_away.mean()*100:.1f}%")
    print(f"swing still-open at end of data: {df.swing_open_at_end.mean()*100:.1f}% "
          f"(blended into swing win/median below at their current mark, not dropped)\n")

    features = ["freshness_score", "consolidation_days", "dist_to_trigger_pct", "close_pos",
                "body_atr", "rvol_at_trigger"]
    for feat in features:
        sub = df.dropna(subset=[feat, "ran_away"]).copy()
        if len(sub) < 20:
            print(f"=== {feat}: insufficient data (n={len(sub)}) ===\n")
            continue
        try:
            sub["q"] = pd.qcut(sub[feat].rank(method="first"), 4, labels=["Q1", "Q2", "Q3", "Q4"])
        except ValueError:
            print(f"=== {feat}: not enough unique values ===\n")
            continue
        g = sub.groupby("q", observed=True).agg(
            n=("ran_away", "count"),
            runaway_rate=("ran_away", lambda s: s.mean() * 100),
            opt_win=("day1_pnl_pct", lambda s: (s > 0).mean() * 100),
            opt_median=("day1_pnl_pct", "median"),
            swing_win=("swing_pnl_pct", lambda s: (s > 0).mean() * 100),
            swing_median=("swing_pnl_pct", "median"),
        )
        corr_runaway = sub[feat].rank().corr(sub["ran_away"].astype(int))
        corr_opt_win = sub[feat].rank().corr((sub["day1_pnl_pct"] > 0).astype(int))
        corr_swing_win = sub[feat].rank().corr((sub["swing_pnl_pct"] > 0).astype(int))
        print(f"=== {feat} (n={len(sub)}, rank-corr vs ran_away={corr_runaway:.3f}, vs opt_win={corr_opt_win:.3f}, vs swing_win={corr_swing_win:.3f}) ===")
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            row = g.loc[q]
            print(f"  {q}: n={int(row.n):<4} runaway {row.runaway_rate:5.1f}%   OPTIONS win {row.opt_win:5.1f}% med {row['opt_median']:+.2f}%   |   SWING win {row.swing_win:5.1f}% med {row['swing_median']:+.2f}%")
        print()

    print("=== Freshness x Runaway interaction (critic's specific ask) ===")
    sub = df.dropna(subset=["freshness_score", "body_atr"]).copy()
    if len(sub) >= 20:
        sub["fresh_q"] = pd.qcut(sub.freshness_score.rank(method="first"), 2, labels=["Fresh(low)", "Extended(high)"])
        sub["body_q"] = pd.qcut(sub.body_atr.rank(method="first"), 2, labels=["Weak body", "Strong body"])
        piv = sub.groupby(["fresh_q", "body_q"], observed=True)["ran_away"].agg(["mean", "count"])
        piv["mean"] = piv["mean"] * 100
        print(piv)


if __name__ == "__main__":
    run()
