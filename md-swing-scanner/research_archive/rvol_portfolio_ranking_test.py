"""Isolated research only (2026-09-13). The critic's proposed final RVOL@Trigger
experiment (response to update-33): NOT a win-rate test -- a capital-allocation/portfolio-
ranking test. For every historical day with multiple already-fired candidates, and a fixed
cap on how many can receive capital (2 or 3), does ranking by Freshness+RVOL pick a better
portfolio than ranking by Freshness alone? Retirement rule (critic's own words): if
Freshness+RVOL does not outperform Freshness-only, RVOL leaves the production roadmap
completely.

Uses the intraday-covered pool (vwap_and_timeofday_check.csv, n=934) since RVOL@Trigger
requires real intraday bars -- a real, disclosed limitation: this restricts the test to the
~3-4 month intraday-cache window, not the full 5-year history, so the number of
multi-candidate days is inherently thin. Reported honestly, not smoothed over.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import intraday_cache
from pivots import daily_pivots
from live_checkpoint import _percentile_from_breaks, RSI_PCT_BREAKS, MOMENTUM_PCT_BREAKS

TRIGGER_CLEARANCE = 1.005
CAPS = [2, 3]


def freshness(rsi14, mom20):
    if pd.isna(rsi14) or pd.isna(mom20):
        return None
    rsi_pct = _percentile_from_breaks(rsi14, RSI_PCT_BREAKS)
    mom_pct = _percentile_from_breaks(mom20, MOMENTUM_PCT_BREAKS)
    return 0.5 * rsi_pct + 0.5 * mom_pct


def normal_day_volume_baseline(df, already_extended, lookback=25):
    tail_vol = df.Volume.tail(lookback)
    tail_ext = already_extended.tail(lookback)
    normal = tail_vol[~tail_ext]
    if normal.empty:
        return None
    return normal.median()


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
    tod = pd.read_csv("runs/vwap_and_timeofday_check.csv", parse_dates=["entry_date"])
    feat = pd.read_csv("runs/consolidation_and_room.csv", parse_dates=["entry_date"])[
        ["ticker", "entry_date", "yday_rsi14", "yday_momentum_20d", "dist_to_trigger_pct"]]
    df = tod.merge(feat, on=["ticker", "entry_date"], how="left")
    df["freshness_score"] = df.apply(lambda r: freshness(r.yday_rsi14, r.yday_momentum_20d), axis=1)

    cache = {}
    rvol_list = []
    for _, r in df.iterrows():
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
            rvol_list.append(None)
            continue
        i = match[0]
        row = daily.iloc[i]
        trigger = row.high10_prior * TRIGGER_CLEARANCE
        day = pd.Timestamp(r.entry_date).normalize()
        day_bars = by_day.get(day)
        if day_bars is None or day_bars.empty:
            rvol_list.append(None)
            continue
        crossed = day_bars[day_bars.High >= trigger]
        if crossed.empty:
            rvol_list.append(None)
            continue
        bar = crossed.iloc[0]
        t = bar.name.time()
        hist = daily.iloc[:i]
        already_ext = hist.Close > hist.high10_prior
        normal_baseline = normal_day_volume_baseline(hist, already_ext)
        if not normal_baseline:
            rvol_list.append(None)
            continue
        vol_so_far = day_bars[day_bars.index.time <= t].Volume.sum()
        frac = clock_time_fraction(by_day, day, t)
        if not (frac and frac > 0.05):
            rvol_list.append(None)
            continue
        rvol_list.append((vol_so_far / frac) / normal_baseline)
    df["rvol_at_trigger"] = rvol_list

    print(f"n = {len(df)}   with freshness = {df.freshness_score.notna().sum()}   "
          f"with RVOL = {df.rvol_at_trigger.notna().sum()}   with distance = {df.dist_to_trigger_pct.notna().sum()}\n")

    day_counts = df.groupby("entry_date").size()
    print("Distribution of candidates per day:")
    print(day_counts.value_counts().sort_index())
    print(f"\ndays with >1 candidate: {(day_counts > 1).sum()} / {len(day_counts)}")

    complete = df.dropna(subset=["freshness_score", "rvol_at_trigger", "dist_to_trigger_pct", "day1_pnl_pct"]).copy()
    print(f"\nn with ALL fields present (freshness+RVOL+distance+outcome) = {len(complete)}")
    multi_days = complete.groupby("entry_date").filter(lambda g: len(g) > 1)
    print(f"of those, on days with >1 simultaneous candidate: {len(multi_days)} trades across "
          f"{multi_days.entry_date.nunique()} days")

    def rank_asc(s):  # lower raw value = better
        return s.rank(ascending=True, pct=True)

    def rank_desc(s):  # higher raw value = better
        return s.rank(ascending=False, pct=True)

    strategies = {
        "Freshness only": lambda g: rank_asc(g.freshness_score),
        "Freshness + RVOL": lambda g: (rank_asc(g.freshness_score) + rank_desc(g.rvol_at_trigger)) / 2,
        "Freshness + Distance": lambda g: (rank_asc(g.freshness_score) + rank_desc(g.dist_to_trigger_pct)) / 2,
        "Freshness + RVOL + Distance": lambda g: (rank_asc(g.freshness_score) + rank_desc(g.rvol_at_trigger) + rank_desc(g.dist_to_trigger_pct)) / 3,
    }

    for cap in CAPS:
        print(f"\n=== Capital cap = {cap} positions/day ===")
        for name, score_fn in strategies.items():
            selected = []
            for date, g in complete.groupby("entry_date"):
                if len(g) <= cap:
                    selected.append(g)
                    continue
                score = score_fn(g)
                top = g.loc[score.nsmallest(cap).index]
                selected.append(top)
            picked = pd.concat(selected)
            win = (picked.day1_pnl_pct > 0).mean() * 100
            med = picked.day1_pnl_pct.median()
            mean = picked.day1_pnl_pct.mean()
            print(f"  {name:<30} n={len(picked):<5} win {win:5.1f}%  median {med:+.2f}%  mean {mean:+.2f}%")


if __name__ == "__main__":
    run()
