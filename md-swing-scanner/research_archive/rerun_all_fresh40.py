"""Isolated research only (2026-09-14). Master rerun of every EMA/stall/gate test from
today's thread under the newly-adopted population discipline (see memory:
feedback_population_choice_for_backtests.md):
  - freshness cutoff = 0.40 (not median split)
  - daily-bar-only tests get the full 2021-2026 population (runs/pop_fresh40_big.csv, n=5213)
  - every daily-bar test is ALSO bracketed against the small, intraday-cache-window
    population (runs/pop_fresh40_small.csv, n=365) and its 1PM-cutoff-restricted version
    (runs/pop_fresh40_cutoff.csv, n=298)
  - genuinely intraday-only tests (hourly bucket/pin-bar) only have the small/cutoff pair,
    since there is no bigger population with real intraday bars
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
import intraday_cache
import market_regime
from pivots import daily_pivots
from ema34_exit_overlay_check import simulate as ema34_simulate
from stall_exit_overlay_check import simulate as stall_simulate

daily_cache = {}


def load_daily(ticker):
    if ticker not in daily_cache:
        daily_cache[ticker] = backtest.load(ticker, daily_pivots).reset_index()
    return daily_cache[ticker]


def concentration(s):
    total = s.sum()
    if not total:
        return float("nan")
    return s.sort_values(ascending=False).head(10).sum() / total * 100


def wstats(pnl):
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    wr = len(wins) / len(pnl) * 100 if len(pnl) else float("nan")
    exp = (wr / 100) * (wins.mean() if len(wins) else 0) + (1 - wr / 100) * (losses.mean() if len(losses) else 0)
    return wr, pnl.median(), exp, concentration(pnl)


def fmt(label, pnl):
    if len(pnl) < 5:
        print(f"    {label:<26} n={len(pnl):<5} (too thin)")
        return
    wr, med, exp, conc = wstats(pnl)
    print(f"    {label:<26} n={len(pnl):<5} win={wr:5.1f}%  med={med:+.2f}%  exp={exp:+.3f}%  conc={conc:.1f}%")


# ============================================================================
POPS = {
    "BIG (full-history, n=5213)": pd.read_csv("runs/pop_fresh40_big.csv", parse_dates=["entry_date"]),
    "SMALL (cache-window, n=365)": pd.read_csv("runs/pop_fresh40_small.csv", parse_dates=["entry_date", "breach_time"]),
    "SMALL+1PM cutoff (n=298)": pd.read_csv("runs/pop_fresh40_cutoff.csv", parse_dates=["entry_date", "breach_time"]),
}
# unify column names: big pop uses opt_pnl_pct, small pops use day1_pnl_pct
for name, df in POPS.items():
    if "opt_pnl_pct" not in df.columns and "day1_pnl_pct" in df.columns:
        df["opt_pnl_pct"] = df["day1_pnl_pct"]

print("=" * 100)
print("1. DAILY-LEVEL SEARCH (swing-only, daily bars) -- EMA34/SMA50 cascade")
print("=" * 100)
LEVELS = ["ema8", "ema21", "ema34", "sma50", "sma150", "sma200"]
MAX_WINDOW_DAYS = 20
for pop_name, pop_df in POPS.items():
    print(f"\n--- {pop_name} ---")
    results = []
    for r in pop_df.itertuples():
        daily = load_daily(r.ticker)
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0:
            continue
        i = match[0]
        window = daily.iloc[i + 1: i + 1 + MAX_WINDOW_DAYS]
        if window.empty:
            continue
        row = {"swing_pnl_pct": r.swing_pnl_pct}
        for col in LEVELS:
            if col not in window.columns or window[col].isna().all():
                row[col] = None
                continue
            touched = window.Low <= window[col]
            if not touched.any():
                row[col] = "never_touched"
                continue
            after = window.loc[touched.idxmax():]
            broke = (after.Close < after[col]).sum() > 1
            row[col] = "broke" if broke else "held"
        results.append(row)
    out = pd.DataFrame(results)
    for col in ["ema34", "sma50"]:
        nt = out[out[col] == "never_touched"].swing_pnl_pct
        hd = out[out[col] == "held"].swing_pnl_pct
        bk = out[out[col] == "broke"].swing_pnl_pct
        print(f"  {col}:")
        fmt("never_touched", nt)
        fmt("held", hd)
        fmt("broke", bk)

print()
print("=" * 100)
print("2. DAILY PIN-BAR (EMA8/EMA34 touch-bar direction) -- options + swing")
print("=" * 100)


def touch_bar_shape(window, level_col):
    touched = window.Low <= window[level_col]
    if not touched.any():
        return None
    bar = window.loc[touched.idxmax()]
    body = abs(bar.Close - bar.Open)
    bullish = bar.Close > bar.Open
    return bool(bullish)


for pop_name, pop_df in POPS.items():
    print(f"\n--- {pop_name} ---")
    for col in ["ema8", "ema34"]:
        bullish_opt, bearish_opt = [], []
        bullish_swg, bearish_swg = [], []
        for r in pop_df.itertuples():
            daily = load_daily(r.ticker)
            match = daily.index[daily.Date == r.entry_date]
            if len(match) == 0:
                continue
            i = match[0]
            window = daily.iloc[i + 1: i + 1 + MAX_WINDOW_DAYS]
            if window.empty:
                continue
            shape = touch_bar_shape(window, col)
            if shape is None:
                continue
            (bullish_opt if shape else bearish_opt).append(r.opt_pnl_pct)
            (bullish_swg if shape else bearish_swg).append(r.swing_pnl_pct)
        print(f"  daily {col}:")
        fmt("bullish OPTIONS", pd.Series(bullish_opt))
        fmt("bearish OPTIONS", pd.Series(bearish_opt))
        fmt("bullish SWING", pd.Series(bullish_swg))
        fmt("bearish SWING", pd.Series(bearish_swg))

print()
print("=" * 100)
print("3. EMA34-BREAK EXIT OVERLAY (swing-only)")
print("=" * 100)
for pop_name, pop_df in POPS.items():
    print(f"\n--- {pop_name} ---")
    baseline, overlay = [], []
    for r in pop_df.itertuples():
        daily = load_daily(r.ticker)
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0:
            continue
        i = match[0]
        b_pnl, _, _ = ema34_simulate(daily, i, add_ema34_overlay=False)
        o_pnl, _, _ = ema34_simulate(daily, i, add_ema34_overlay=True)
        baseline.append(b_pnl); overlay.append(o_pnl)
    fmt("current rule", pd.Series(baseline))
    fmt("+ EMA34-break overlay", pd.Series(overlay))

print()
print("=" * 100)
print("4. 3-DAY-STALL EXIT OVERLAY (swing-only)")
print("=" * 100)
for pop_name, pop_df in POPS.items():
    print(f"\n--- {pop_name} ---")
    baseline, overlay = [], []
    for r in pop_df.itertuples():
        daily = load_daily(r.ticker)
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0:
            continue
        i = match[0]
        b_pnl, _ = stall_simulate(daily, i, add_stall_overlay=False)
        o_pnl, _ = stall_simulate(daily, i, add_stall_overlay=True)
        baseline.append(b_pnl); overlay.append(o_pnl)
    fmt("current rule", pd.Series(baseline))
    fmt("+ 3-day-stall overlay", pd.Series(overlay))

print()
print("=" * 100)
print("5. NIFTY SMA50-AND GATE REPLAY (options + swing, both legs)")
print("=" * 100)
regime = market_regime._regime_frame()
LOOKBACK = market_regime.NIFTY_ADX_RISING_LOOKBACK


def nifty_state(date):
    pos = regime.index.searchsorted(date, side="right") - 1
    if pos < 0:
        return None, None
    row = regime.iloc[pos]
    above = (not pd.isna(row.sma50)) and (row.Close > row.sma50)
    prior_pos = pos - LOOKBACK
    if prior_pos < 0:
        rising = None
    else:
        prior_sma50 = regime.iloc[prior_pos].sma50
        rising = (not pd.isna(row.sma50)) and (not pd.isna(prior_sma50)) and (row.sma50 >= prior_sma50)
    return above, rising


for pop_name, pop_df in POPS.items():
    print(f"\n--- {pop_name} ---")
    pop_df = pop_df.copy()
    states = pop_df.entry_date.apply(nifty_state)
    pop_df["nifty_above"] = states.apply(lambda x: x[0])
    pop_df["nifty_rising"] = states.apply(lambda x: x[1])
    print("  require_above_sma50:")
    fmt("kept (above) OPTIONS", pop_df[pop_df.nifty_above == True].opt_pnl_pct)
    fmt("removed (below) OPTIONS", pop_df[pop_df.nifty_above == False].opt_pnl_pct)
    fmt("kept (above) SWING", pop_df[pop_df.nifty_above == True].swing_pnl_pct)
    fmt("removed (below) SWING", pop_df[pop_df.nifty_above == False].swing_pnl_pct)
    sub = pop_df.dropna(subset=["nifty_rising"])
    print("  require_sma50_rising:")
    fmt("kept (rising) OPTIONS", sub[sub.nifty_rising == True].opt_pnl_pct)
    fmt("removed (falling) OPTIONS", sub[sub.nifty_rising == False].opt_pnl_pct)
    fmt("kept (rising) SWING", sub[sub.nifty_rising == True].swing_pnl_pct)
    fmt("removed (falling) SWING", sub[sub.nifty_rising == False].swing_pnl_pct)

print()
print("=" * 100)
print("6. HOURLY EMA ACTIONABLE WINDOW (options-only, same-day, real breach_time)")
print("=" * 100)


def hourly_ema(intraday_5m):
    h = intraday_5m.resample("60min", origin="start_day").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    ).dropna(subset=["Close"])
    h["ema8"] = h.Close.ewm(span=8, adjust=False).mean()
    h["ema34"] = h.Close.ewm(span=34, adjust=False).mean()
    return h


def classify_bucket(window):
    if window.empty:
        return None
    touched_ema8 = (window.Low <= window.ema8).any()
    touched_ema34 = (window.Low <= window.ema34).any()
    if not touched_ema8 and not touched_ema34:
        return "never touched"
    if touched_ema34:
        broke = (window.Close < window.ema34).any()
        return "touched EMA34, broke" if broke else "touched EMA34, held"
    return "touched EMA8 only"


intraday_hourly_cache = {}


def get_hourly(ticker):
    if ticker not in intraday_hourly_cache:
        try:
            intraday = intraday_cache.load(ticker)
            idx5 = intraday.index.tz_convert("Asia/Kolkata").tz_localize(None)
            intraday_hourly_cache[ticker] = hourly_ema(intraday.set_axis(idx5))
        except FileNotFoundError:
            intraday_hourly_cache[ticker] = None
    return intraday_hourly_cache[ticker]


for pop_name in ["SMALL (cache-window, n=365)", "SMALL+1PM cutoff (n=298)"]:
    pop_df = POPS[pop_name]
    print(f"\n--- {pop_name} ---")
    buckets = {}
    for r in pop_df.itertuples():
        hourly = get_hourly(r.ticker)
        if hourly is None:
            continue
        entry_ts = r.breach_time
        same_day_end_ts = pd.Timestamp(r.entry_date) + pd.Timedelta(hours=15, minutes=30)
        window = hourly[(hourly.index > entry_ts) & (hourly.index <= same_day_end_ts)]
        b = classify_bucket(window)
        if b is None:
            continue
        buckets.setdefault(b, []).append(r.opt_pnl_pct)
    for b in ["never touched", "touched EMA8 only", "touched EMA34, held", "touched EMA34, broke"]:
        if b in buckets:
            fmt(b, pd.Series(buckets[b]))

print()
print("=" * 100)
print("7. HOURLY EMA8 PIN-BAR (options + swing, same-day window)")
print("=" * 100)


def touch_bar_bullish(window, level_col):
    touched = window.Low <= window[level_col]
    if not touched.any():
        return None
    bar = window.loc[touched.idxmax()]
    return bool(bar.Close > bar.Open)


for pop_name in ["SMALL (cache-window, n=365)", "SMALL+1PM cutoff (n=298)"]:
    pop_df = POPS[pop_name]
    print(f"\n--- {pop_name} ---")
    bull_opt, bear_opt, bull_swg, bear_swg = [], [], [], []
    for r in pop_df.itertuples():
        hourly = get_hourly(r.ticker)
        if hourly is None:
            continue
        entry_ts = r.breach_time
        same_day_end_ts = pd.Timestamp(r.entry_date) + pd.Timedelta(hours=15, minutes=30)
        window = hourly[(hourly.index > entry_ts) & (hourly.index <= same_day_end_ts)]
        shape = touch_bar_bullish(window, "ema8")
        if shape is None:
            continue
        (bull_opt if shape else bear_opt).append(r.opt_pnl_pct)
        (bull_swg if shape else bear_swg).append(r.swing_pnl_pct)
    fmt("bullish OPTIONS", pd.Series(bull_opt))
    fmt("bearish OPTIONS", pd.Series(bear_opt))
    fmt("bullish SWING", pd.Series(bull_swg))
    fmt("bearish SWING", pd.Series(bear_swg))

print()
print("DONE")
