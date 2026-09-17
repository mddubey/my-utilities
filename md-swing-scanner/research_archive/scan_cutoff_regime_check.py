"""Isolated research only (2026-09-14). Critic's one blocking check before freezing
SCAN_END_TIME=13:00: does the 9:15-13:00 vs 13:00-close cutoff help consistently across
Nifty up-days / down-days / high-VIX / low-VIX days, or is the earlier aggregate result
hiding a regime-dependent effect? "I don't need a huge study... one afternoon of testing.
If stable, freeze forever."

Reuses the exact fresh-only, intraday-covered population from the original scan-window
test (vwap_and_timeofday_check.csv, breakout_continuation only -- same population, same
caveat about VCP already disclosed in live_checkpoint.py's SCAN_END_TIME comment).
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import yfinance as yf

import backtest
import market_regime
from pivots import daily_pivots
from live_checkpoint import _percentile_from_breaks, RSI_PCT_BREAKS, MOMENTUM_PCT_BREAKS

TRIGGER_CLEARANCE = 1.005
CUTOFF = pd.to_datetime("13:00:00").time()


def freshness(rsi14, mom20):
    if pd.isna(rsi14) or pd.isna(mom20):
        return None
    rsi_pct = _percentile_from_breaks(rsi14, RSI_PCT_BREAKS)
    mom_pct = _percentile_from_breaks(mom20, MOMENTUM_PCT_BREAKS)
    return 0.5 * rsi_pct + 0.5 * mom_pct


def run():
    tod = pd.read_csv("runs/vwap_and_timeofday_check.csv", parse_dates=["entry_date"])
    feat = pd.read_csv("runs/consolidation_and_room.csv", parse_dates=["entry_date"])[
        ["ticker", "entry_date", "yday_rsi14", "yday_momentum_20d"]]
    df = tod.merge(feat, on=["ticker", "entry_date"], how="inner").dropna(subset=["yday_rsi14", "yday_momentum_20d"])
    df["freshness_score"] = df.apply(lambda r: freshness(r.yday_rsi14, r.yday_momentum_20d), axis=1)
    fresh_cut = df.freshness_score.median()
    df = df[df.freshness_score <= fresh_cut].copy()

    bt = pd.to_datetime(df.breach_time)
    df["clock_time"] = bt.dt.time
    df["window"] = df.clock_time.apply(lambda t: "9:15-1PM" if t <= CUTOFF else "1PM-Close")

    print("Computing swing outcomes...")
    cache = {}
    swing_pnl = []
    for _, r in df.iterrows():
        if r.ticker not in cache:
            cache[r.ticker] = backtest.load(r.ticker, daily_pivots).reset_index()
        rows = cache[r.ticker]
        match = rows.index[rows.Date == r.entry_date]
        if len(match) == 0 or match[0] + 1 >= len(rows):
            swing_pnl.append(None)
            continue
        i = match[0]
        trigger = rows.iloc[i].high10_prior * TRIGGER_CLEARANCE
        state = dict(entry_price=trigger, peak_close=trigger, peak_high=trigger, structural_low=0.0, target=None)
        exit_price = None
        for j in range(i + 1, len(rows)):
            row = rows.iloc[j]
            if row.corp_action_day:
                exit_price = state["peak_close"]
                break
            exit_reason, state = backtest.check_exit("breakout_cont", state, row, use_resistance=True)
            if exit_reason is not None:
                exit_price = row.Close
                break
        if exit_price is None:
            exit_price = rows.iloc[-1].Close
        swing_pnl.append((exit_price / trigger - 1) * 100)
    df["swing_pnl_pct"] = swing_pnl

    print("Fetching Nifty and VIX regime data...")
    nifty = market_regime._regime_frame()
    nifty_ret = nifty.Close.pct_change()
    df["nifty_up"] = df.entry_date.map(lambda d: nifty_ret.get(d))

    vix = yf.download("^INDIAVIX", period="1y", interval="1d", progress=False, auto_adjust=False)
    vix.columns = [c[0] if isinstance(c, tuple) else c for c in vix.columns]
    vix_close = vix["Close"]
    vix_median = vix_close.median()
    df["vix_level"] = df.entry_date.map(lambda d: vix_close.get(pd.Timestamp(d)))

    df = df.dropna(subset=["nifty_up", "vix_level"])
    df["regime_nifty"] = df.nifty_up.apply(lambda x: "Nifty up" if x > 0 else "Nifty down")
    df["regime_vix"] = df.vix_level.apply(lambda x: "High VIX" if x >= vix_median else "Low VIX")

    print(f"\nn = {len(df)}  (VIX median split at {vix_median:.2f})\n")

    def stats(sub, col):
        if sub.empty:
            return "n=0"
        win = (sub[col] > 0).mean() * 100
        med = sub[col].median()
        wins = sub[sub[col] > 0][col]
        losses = sub[sub[col] <= 0][col]
        wr = len(wins) / len(sub)
        lr = len(losses) / len(sub)
        exp = wr * (wins.mean() if len(wins) else 0) + lr * (losses.mean() if len(losses) else 0)
        return f"n={len(sub):<3} win {win:5.1f}% med {med:+.2f}% exp {exp:+.3f}%"

    print("=== Regime split: 9:15-1PM vs 1PM-Close, OPTIONS metric (day1_pnl_pct) ===")
    for regime_col, label in [("regime_nifty", "Nifty"), ("regime_vix", "VIX")]:
        for regime_val in df[regime_col].unique():
            sub = df[df[regime_col] == regime_val]
            head = sub[sub.window == "9:15-1PM"]
            tail = sub[sub.window == "1PM-Close"]
            print(f"  {regime_val:<10} 9:15-1PM: {stats(head, 'day1_pnl_pct')}   |   1PM-Close: {stats(tail, 'day1_pnl_pct')}")

    print("\n=== Regime split: 9:15-1PM vs 1PM-Close, SWING metric (check_exit) ===")
    for regime_col, label in [("regime_nifty", "Nifty"), ("regime_vix", "VIX")]:
        for regime_val in df[regime_col].unique():
            sub = df[df[regime_col] == regime_val]
            head = sub[sub.window == "9:15-1PM"]
            tail = sub[sub.window == "1PM-Close"]
            print(f"  {regime_val:<10} 9:15-1PM: {stats(head, 'swing_pnl_pct')}   |   1PM-Close: {stats(tail, 'swing_pnl_pct')}")


if __name__ == "__main__":
    run()
