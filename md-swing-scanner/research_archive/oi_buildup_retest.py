"""Isolated research only (2026-09-17). Re-tests oi_buildup_bullish() -- rejected and
deleted 2026-09-06 -- on the CURRENT, validated methodology. The original rejection
(FINDINGS.md, "Round-12") predates three major architectural changes since:
  1. No freshness conditioning existed yet (raw 679-trade population); freshness<=0.40
     was only adopted 2026-09-14.
  2. Options recipe tested was "ITM+next-month"/"ATM+current-month" -- next-month was
     fully dropped 2026-09-14 (current-month only, ITM or ATM, roll if DTE<10).
  3. Stock exit at the time was the OLD 3xATR chandelier with NO MAX_HOLD_DAYS cap --
     positional-until-stop/target, sometimes 60-80+ day holds. The current mechanism
     (structural_low-1xATR + SMA21-2% trail + MAX_HOLD_DAYS=15) was wired 2026-09-14/15,
     AFTER this rejection was made. The old test's own -71.45%/+21.15% median magnitudes
     only make sense under that old, uncapped hold -- nowhere near day+1-open's typical
     single-digit medians.

oi_buildup_bullish() itself is reconstructed EXACTLY from git history (commit
30f3326^:option_backtest.py, before its 2026-09-06 deletion) -- not re-derived from
memory, to avoid re-testing a subtly different function.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import option_backtest
from pivots import daily_pivots

OI_BUILDUP_WINDOW = 3  # exact original constant, from git history


def oi_buildup_bullish(ticker, date):
    """Reconstructed exactly from git history (30f3326^) -- long buildup (price up AND
    futures OI up) over a trailing OI_BUILDUP_WINDOW-day window."""
    days = [d for d in option_backtest.trading_days() if d <= date]
    if len(days) < OI_BUILDUP_WINDOW:
        return False
    window = days[-OI_BUILDUP_WINDOW:]
    net_oi_chg = 0
    first_price = last_price = None
    for d in window:
        try:
            row = option_backtest.front_month_future(ticker, d)
        except KeyError:
            # exact, known pre-2024 gap (fetch_stock_options_pre2024.py's normalized
            # schema carries no futures OI columns at all) -- caught precisely, not
            # broadly, per the standing lesson from the original 2026-09-06 re-check.
            return None
        if row is None:
            return None  # honest "no data", NOT False -- the exact bug this project
                          # already found and corrected once (silently miscounting
                          # missing data as "buildup absent")
        net_oi_chg += row.ChngInOpnIntrst
        if first_price is None:
            first_price = row.PrvsClsgPric
        last_price = row.ClsPric
    return last_price > first_price and net_oi_chg > 0


daily_cache = {}


def load_daily(ticker):
    if ticker not in daily_cache:
        daily_cache[ticker] = backtest.load(ticker, daily_pivots).reset_index()
    return daily_cache[ticker]


def concentration(s):
    s = s.abs()
    total = s.sum()
    return s.sort_values(ascending=False).head(10).sum() / total * 100 if total else float("nan")


def simulate_swing(ticker, entry_date):
    """Real, CURRENT production stock-side exit -- structural_low-1xATR + SMA21-2%
    trail + MAX_HOLD_DAYS=15, exactly as wired into backtest.py right now."""
    df = load_daily(ticker)
    match = df.index[df.Date == entry_date]
    if len(match) == 0 or match[0] + 1 >= len(df):
        return None
    i = match[0]
    row = df.iloc[i]
    entry_price = row.high10_prior * 1.005
    lo = max(0, i - backtest.STRUCTURAL_LOOKBACK_BC)
    structural_low = df.iloc[lo:i].Low.min() if i > lo else entry_price * 0.9
    state = dict(entry_price=entry_price, peak_close=entry_price, peak_high=row.High,
                 structural_low=structural_low, target=None, days_held=0, atr_entry=row.atr14)
    for j in range(i + 1, len(df)):
        r2 = df.iloc[j]
        if r2.corp_action_day:
            return (state["peak_close"] / entry_price - 1) * 100
        reason, state = backtest.check_exit("breakout_cont", state, r2)
        if reason is not None:
            return (r2.Close / entry_price - 1) * 100
    return (df.iloc[-1].Close / entry_price - 1) * 100


def simulate_option_day1(ticker, entry_date, moneyness):
    """Real premium simulation -- current-month only (the now-adopted convention),
    entry at entry-day option Close, exit at day+1's option Open."""
    df = load_daily(ticker)
    match = df.index[df.Date == entry_date]
    if len(match) == 0 or match[0] + 1 >= len(df):
        return None
    i = match[0]
    entry_price = df.iloc[i].high10_prior * 1.005
    contract = option_backtest.pick_contract(ticker, entry_date, entry_price, moneyness, "current")
    if contract is None:
        return None
    expiry, strike, lot_size = contract
    entry_row = option_backtest.option_row(ticker, entry_date, expiry, strike)
    if entry_row is None or not entry_row.ClsPric or not option_backtest.liquid(entry_row):
        return None
    entry_px = entry_row.ClsPric
    exit_date = df.iloc[match[0] + 1].Date
    exit_row = option_backtest.option_row(ticker, exit_date, expiry, strike)
    if exit_row is None or not exit_row.OpnPric or not option_backtest.liquid(exit_row):
        return None
    exit_px = exit_row.OpnPric
    return (exit_px / entry_px - 1) * 100


def report(sub, col, label):
    if len(sub) < 5:
        print(f"    {label:<24} n={len(sub):<5} (too thin)")
        return
    wins = sub[sub[col] > 0][col]
    losses = sub[sub[col] <= 0][col]
    wr = len(wins) / len(sub) * 100
    exp = (wr / 100) * (wins.mean() if len(wins) else 0) + (1 - wr / 100) * (losses.mean() if len(losses) else 0)
    print(f"    {label:<24} n={len(sub):<5} win={wr:5.1f}%  med={sub[col].median():+.2f}%  "
          f"exp={exp:+.3f}%  conc={concentration(sub[col]):.1f}%")


def run():
    pop = pd.read_csv("runs/pop_fresh40_big.csv", parse_dates=["entry_date"])
    fo_tickers = set(pd.read_csv("fo_universe.csv", header=None)[0])
    n_before = len(pop)
    pop = pop[pop.ticker.isin(fo_tickers)]
    print(f"population (freshness<=0.40, daily): n={n_before} total, "
          f"{n_before - len(pop)} dropped (non-F&O, can never have futures OI), "
          f"n={len(pop)} F&O-scoped")

    rows = []
    n_no_data = 0
    for idx, r in enumerate(pop.itertuples(), 1):
        if idx % 500 == 0:
            print(f"  {idx}/{len(pop)}", flush=True)
        buildup = oi_buildup_bullish(r.ticker, r.entry_date)
        if buildup is None:
            n_no_data += 1
            continue
        swing = simulate_swing(r.ticker, r.entry_date)
        itm_day1 = simulate_option_day1(r.ticker, r.entry_date, "itm")
        atm_day1 = simulate_option_day1(r.ticker, r.entry_date, "atm")
        rows.append(dict(ticker=r.ticker, entry_date=r.entry_date, buildup=buildup,
                          swing_pnl_pct=swing, itm_day1_pct=itm_day1, atm_day1_pct=atm_day1))

    out = pd.DataFrame(rows)
    out.to_csv("runs/oi_buildup_retest.csv", index=False)
    print(f"\nn with real futures OI data = {len(out)}  (no-data/skipped: {n_no_data})")

    for buildup_val, label in [(True, "BUILDUP PRESENT"), (False, "BUILDUP ABSENT")]:
        sub = out[out.buildup == buildup_val]
        print(f"\n=== {label} (n={len(sub)}) ===")
        swing_sub = sub.dropna(subset=["swing_pnl_pct"])
        report(swing_sub, "swing_pnl_pct", "swing (current mechanism)")
        itm_sub = sub.dropna(subset=["itm_day1_pct"])
        report(itm_sub, "itm_day1_pct", "options ITM+current, day1")
        atm_sub = sub.dropna(subset=["atm_day1_pct"])
        report(atm_sub, "atm_day1_pct", "options ATM+current, day1")


if __name__ == "__main__":
    run()
