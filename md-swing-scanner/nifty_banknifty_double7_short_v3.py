"""Ad hoc (2026-09-27), v3: real research-driven hypothesis -- a mean-reversion SHORT needs
BOTH a genuine downtrend (SMA200 declining, the v2 fix) AND range-bound/choppy conditions
(ADX < 20, not strongly trending), not just the first alone. Higher-beta Bank Nifty likely
failed v2 because its confirmed downtrends tend to be strongly trending (blow through the
short level) rather than choppy, per real sourced research on mean-reversion needing
range-bound conditions specifically. Tested on BOTH indices together this time, not fit on
one and checked on the other after the fact.
"""
import pandas as pd
import numpy as np


def compute_adx(df, period=14):
    high, low, close = df.High, df.Low, df.Close
    plus_dm = (high.diff()).clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    plus_dm[(plus_dm - minus_dm) <= 0] = 0
    minus_dm[(minus_dm - plus_dm) <= 0] = 0
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return adx


def load_index(path, has_adx=False):
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df.Date)
    df = df.sort_values("Date").reset_index(drop=True)
    if not has_adx:
        df["sma200"] = df.Close.rolling(200).mean()
        df["adx14"] = compute_adx(df)
    df["sma200_20ago"] = df.sma200.shift(20)
    df["sma200_declining"] = df.sma200 < df.sma200_20ago
    df["high7_prior"] = df.High.shift(1).rolling(7).max()
    df["low7_prior"] = df.Low.shift(1).rolling(7).min()
    return df


def simulate_short_v3(df, adx_max):
    n = len(df)
    trades = []
    i = 210
    while i < n:
        row = df.iloc[i]
        if pd.isna(row.high7_prior) or pd.isna(row.sma200_declining) or pd.isna(row.adx14):
            i += 1
            continue
        signal = row.High >= row.high7_prior and row.sma200_declining and row.adx14 < adx_max
        if not signal:
            i += 1
            continue
        entry_price = row.Close
        entry_date = row.Date
        j = i + 1
        exit_price = None
        while j < n:
            r = df.iloc[j]
            l7 = df.Low.shift(1).rolling(7).min().iloc[j]
            if r.Low <= l7:
                exit_price = r.Close
                break
            j += 1
        if exit_price is None:
            i += 1
            continue
        ret = entry_price / exit_price - 1
        trades.append(dict(entry_date=entry_date, adx_at_entry=row.adx14, hold_days=j - i, ret=ret))
        i = j + 1
    return pd.DataFrame(trades)


def report(trades, label):
    print(f"=== {label}: n={len(trades)} ===")
    if trades.empty:
        print("  no trades\n")
        return
    print(f"  win rate: {(trades.ret>0).mean()*100:.1f}%")
    print(f"  median: {trades.ret.median()*100:+.2f}%   mean: {trades.ret.mean()*100:+.2f}%")
    print(f"  cumulative: {trades.ret.sum()*100:+.1f}%")
    print(trades.round(3).to_string(index=False))
    print()


nifty = load_index("data_cache/_NIFTY.csv", has_adx=True)
banknifty = load_index("data_cache/_BANKNIFTY.csv", has_adx=False)

for adx_max in [20, 18]:
    print(f"########## ADX < {adx_max} (range-bound filter) ##########")
    nifty_t = simulate_short_v3(nifty, adx_max)
    bn_t = simulate_short_v3(banknifty, adx_max)
    report(nifty_t, f"NIFTY Double7s SHORT v3 (SMA200 declining + ADX<{adx_max})")
    report(bn_t, f"BANK NIFTY Double7s SHORT v3 (SMA200 declining + ADX<{adx_max})")
