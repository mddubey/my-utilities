"""ZERO-TO-HERO ad hoc check (2026-09-27, user's own explicit framing: "a greedy gamble,
not blind, based on some technicals"). NOT a validated project finding, NOT wired into
FINDINGS.md/PARKING_LOT.md on purpose -- dumped into zero_to_hero_observations.md instead,
per direct user instruction. This is exploratory curiosity about a specific high-risk/
high-reward pattern, evaluated honestly, not a recommendation.

Question: buying a fairly-OTM stock CE (close price <= RS_CAP on the day), 0-3 trading
days before that contract's monthly expiry, on a day the stock prints a daily pinbar/
hammer at a retested support level (the RBLBANK 2026-09-25 real case) -- does the setup
show real asymmetric payoff (some fraction of "hero" outcomes with a large multiple)
better than an unconditional baseline of the same cheap-OTM-near-expiry trade taken on
an ORDINARY day (no pinbar-at-support)?

Real data only: pinbar event definition matches rq_pinbar_check.py's proven definition.
Real monthly stock-option expiry calendar (54 dates, verified STO-type rows only, not
guessed). Real bhavcopy ClsPric path from entry day to expiry (or last cached day before
expiry if data runs out), tracking both the MAX path multiple (best-case exit) and the
EXPIRY-DAY multiple (worst-case, held to the end) for every qualifying cheap OTM strike.
"""
import pandas as pd
import glob
import os
from backtest import load

RS_CAP = 2.0          # "fairly OTM, <=2 rs" -- user's own framing
MAX_DAYS_TO_EXPIRY = 3  # "2 days into expiry" ballpark, inclusive of a little slack
OPTIONS_DIR = "options_cache"

# --- Step 1: real monthly stock-option expiry calendar (verified from actual STO rows,
# sampled sparsely, not guessed/computed) ---
files = sorted(glob.glob(f"{OPTIONS_DIR}/*.csv"))
sample = files[::20]
expiry_set = set()
for f in sample:
    df = pd.read_csv(f, usecols=["FinInstrmTp", "XpryDt"])
    expiry_set.update(df[df.FinInstrmTp == "STO"].XpryDt.dropna().unique())
expiries = sorted(pd.to_datetime(e) for e in expiry_set)
print(f"real monthly stock-option expiry calendar: {len(expiries)} dates")

# --- Step 2: pinbar-at-support events, F&O universe only ---
fo_tickers = pd.read_csv("fo_universe.csv", header=None)[0].tolist()

pinbar_events = []       # (ticker, event_date, expiry_date, trading_days_to_expiry)
baseline_events = []     # same but NOT a pinbar day -- comparison population

for t in fo_tickers:
    try:
        df = load(t).reset_index()
    except FileNotFoundError:
        continue
    if len(df) < 30:
        continue
    rng = df.High - df.Low
    body = (df.Close - df.Open).abs()
    lower_wick = df[["Open", "Close"]].min(axis=1) - df.Low
    close_pos = (df.Close - df.Low) / rng
    is_pinbar = (rng > 0) & (lower_wick / rng >= 0.5) & (body / rng <= 0.4) & (close_pos >= 0.7)
    recent_low10 = df.Low.rolling(10).min().shift(1)
    at_support = df.Low <= recent_low10 * 1.005
    pinbar_day = is_pinbar & at_support

    dates = df.Date.tolist()
    for i in range(11, len(df)):
        d = dates[i]
        future_expiries = [e for e in expiries if e >= d]
        if not future_expiries:
            continue
        exp = future_expiries[0]
        # trading days to expiry, counted on THIS ticker's own real trading calendar
        future_dates = [x for x in dates[i:] if x <= exp]
        tdte = len(future_dates) - 1  # 0 = event day is expiry day itself
        if tdte > MAX_DAYS_TO_EXPIRY:
            continue
        rec = (t, d, exp, tdte)
        if bool(pinbar_day.iloc[i]):
            pinbar_events.append(rec)
        else:
            baseline_events.append(rec)

print(f"pinbar-at-support events within {MAX_DAYS_TO_EXPIRY}d of expiry: {len(pinbar_events)}")
print(f"baseline (ordinary day) events within {MAX_DAYS_TO_EXPIRY}d of expiry: {len(baseline_events)} "
      f"(will subsample for comparison)")

import random
random.seed(0)
if len(baseline_events) > len(pinbar_events) * 20:
    baseline_events = random.sample(baseline_events, len(pinbar_events) * 20)


def track_contract(ticker, entry_date, expiry, strike):
    """Reads the real bhavcopy for entry_date through expiry, returns (entry_premium,
    max_close_along_path, expiry_or_last_close, n_days_tracked) for this exact CE contract."""
    entry_str = entry_date.strftime("%Y%m%d")
    entry_path = f"{OPTIONS_DIR}/{entry_str}.csv"
    if not os.path.exists(entry_path):
        return None
    edf = pd.read_csv(entry_path)
    row = edf[(edf.TckrSymb == ticker) & (edf.FinInstrmTp == "STO") & (edf.OptnTp == "CE")
              & (edf.XpryDt == expiry.strftime("%Y-%m-%d")) & (edf.StrkPric == strike)]
    if row.empty or row.iloc[0].ClsPric <= 0:
        return None
    entry_premium = float(row.iloc[0].ClsPric)

    all_dates = sorted(pd.to_datetime(os.path.basename(p)[:8], format="%Y%m%d")
                        for p in glob.glob(f"{OPTIONS_DIR}/*.csv"))
    path_dates = [d for d in all_dates if entry_date <= d <= expiry]
    closes = []
    for d in path_dates:
        p = f"{OPTIONS_DIR}/{d.strftime('%Y%m%d')}.csv"
        dd = pd.read_csv(p)
        r = dd[(dd.TckrSymb == ticker) & (dd.FinInstrmTp == "STO") & (dd.OptnTp == "CE")
               & (dd.XpryDt == expiry.strftime("%Y-%m-%d")) & (dd.StrkPric == strike)]
        if not r.empty and r.iloc[0].ClsPric > 0:
            closes.append(float(r.iloc[0].ClsPric))
    if not closes:
        return None
    return entry_premium, max(closes), closes[-1], len(closes)


def run_population(events, label, cap_n=None):
    results = []
    checked_dates = {}
    for (t, d, exp, tdte) in (events[:cap_n] if cap_n else events):
        key = d.strftime("%Y%m%d")
        if key not in checked_dates:
            path = f"{OPTIONS_DIR}/{key}.csv"
            checked_dates[key] = pd.read_csv(path) if os.path.exists(path) else None
        edf = checked_dates[key]
        if edf is None:
            continue
        spot_row = edf[(edf.TckrSymb == t) & (edf.FinInstrmTp == "STF")]
        spot = float(spot_row.iloc[0].UndrlygPric) if not spot_row.empty else None
        chain = edf[(edf.TckrSymb == t) & (edf.FinInstrmTp == "STO") & (edf.OptnTp == "CE")
                    & (edf.XpryDt == exp.strftime("%Y-%m-%d")) & (edf.ClsPric > 0)
                    & (edf.ClsPric <= RS_CAP)]
        if spot is not None:
            chain = chain[chain.StrkPric > spot]
        if chain.empty:
            continue
        strike = chain.sort_values("StrkPric").iloc[0].StrkPric  # cheapest qualifying OTM strike
        r = track_contract(t, d, exp, strike)
        if r is None:
            continue
        entry_premium, max_close, final_close, n_days = r
        results.append(dict(ticker=t, date=d, expiry=exp, strike=strike, tdte=tdte,
                             entry=entry_premium, max_mult=max_close / entry_premium,
                             final_mult=final_close / entry_premium, n_days=n_days))
    res = pd.DataFrame(results)
    print(f"\n=== {label}: n={len(res)} ===")
    if res.empty:
        return res
    for thresh in [2, 3, 5, 10]:
        pct = (res.max_mult >= thresh).mean() * 100
        print(f"  %% reaching >= {thresh}x at SOME point on the path: {pct:.1f}%")
    print(f"  median max_mult (best-case path): {res.max_mult.median():.2f}x")
    print(f"  %% expiring (or last-tracked) at >=1x (i.e. a real gain if held to the end): "
          f"{(res.final_mult>=1).mean()*100:.1f}%")
    print(f"  median final_mult (held to expiry/last tracked day): {res.final_mult.median():.2f}x")
    print(f"  %% expiring worthless or near-zero (final_mult < 0.1): {(res.final_mult<0.1).mean()*100:.1f}%")
    return res


pinbar_res = run_population(pinbar_events, "PINBAR-AT-SUPPORT, cheap OTM CE, <=3 trading days to expiry")
baseline_res = run_population(baseline_events, "BASELINE (ordinary day), cheap OTM CE, <=3 trading days to expiry", cap_n=min(len(baseline_events), 400))

pinbar_res.to_csv("zero_to_hero_pinbar_events.csv", index=False)
baseline_res.to_csv("zero_to_hero_baseline_events.csv", index=False)
print("\nsaved: zero_to_hero_pinbar_events.csv, zero_to_hero_baseline_events.csv")
