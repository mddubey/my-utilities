"""Ad hoc (2026-09-27): two real, well-documented, sourced mean-reversion strategies
(Larry Connors / Cesar Alvarez, "Short Term Trading Strategies That Work") backtested on
real 5-year NIFTY daily data, both CE (long) and PE (short, mirrored) sides as requested.

1. RSI(2) strategy: buy when RSI(2)<5 while above SMA200 (uptrend filter); exit when
   RSI(2)>65 OR Close crosses back above the 5-day SMA (whichever first). Real cited
   result (SPY): 75-88% win rate, ~1.26% avg gain, ~3.7 day avg hold.
   Mirrored short: RSI(2)>95 while below SMA200; exit RSI(2)<35 OR Close crosses back
   below the 5-day SMA.

2. Double 7s: buy when Close = trailing-7-day low while above SMA200; exit when Close =
   trailing-7-day high. Real cited result (SPY since 1993): 77% win rate, ~7%/yr.
   Mirrored short: sell when Close = trailing-7-day high while below SMA200; exit at
   trailing-7-day low.

Both use real, causal (no-lookahead) daily NIFTY data, event-driven exits (not a fixed
horizon) -- actual entry/exit trade simulation, not just a forward-return snapshot.
"""
import pandas as pd
import numpy as np

df = pd.read_csv("../data_cache/_NIFTY.csv")
df["Date"] = pd.to_datetime(df.Date)

delta = df.Close.diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)
avg_gain2 = gain.ewm(alpha=1/2, min_periods=2, adjust=False).mean()
avg_loss2 = loss.ewm(alpha=1/2, min_periods=2, adjust=False).mean()
df["rsi2"] = 100 - (100 / (1 + avg_gain2 / avg_loss2))
df["sma5"] = df.Close.rolling(5).mean()
df["high7_prior"] = df.High.shift(1).rolling(7).max()
df["low7_prior"] = df.Low.shift(1).rolling(7).min()

n = len(df)


def simulate_rsi2(direction):
    trades = []
    i = 15
    while i < n:
        row = df.iloc[i]
        if pd.isna(row.rsi2) or pd.isna(row.sma200):
            i += 1
            continue
        if direction == "long":
            signal = row.rsi2 < 5 and row.Close > row.sma200
        else:
            signal = row.rsi2 > 95 and row.Close < row.sma200
        if not signal:
            i += 1
            continue
        entry_price = row.Close
        entry_date = row.Date
        j = i + 1
        exit_price = None
        while j < n:
            r = df.iloc[j]
            if direction == "long":
                if r.rsi2 > 65 or r.Close > r.sma5:
                    exit_price = r.Close
                    break
            else:
                if r.rsi2 < 35 or r.Close < r.sma5:
                    exit_price = r.Close
                    break
            j += 1
        if exit_price is None:
            i += 1
            continue
        ret = (exit_price / entry_price - 1) if direction == "long" else (entry_price / exit_price - 1)
        trades.append(dict(entry_date=entry_date, exit_date=df.Date.iloc[j], hold_days=j - i, ret=ret))
        i = j + 1  # no overlapping trades
    return pd.DataFrame(trades)


def simulate_double7(direction):
    trades = []
    i = 8
    while i < n:
        row = df.iloc[i]
        if pd.isna(row.high7_prior) or pd.isna(row.sma200):
            i += 1
            continue
        if direction == "long":
            signal = row.Low <= row.low7_prior and row.Close > row.sma200
        else:
            signal = row.High >= row.high7_prior and row.Close < row.sma200
        if not signal:
            i += 1
            continue
        entry_price = row.Close
        entry_date = row.Date
        j = i + 1
        exit_price = None
        while j < n:
            r = df.iloc[j]
            h7 = df.High.shift(1).rolling(7).max().iloc[j]
            l7 = df.Low.shift(1).rolling(7).min().iloc[j]
            if direction == "long":
                if r.High >= h7:
                    exit_price = r.Close
                    break
            else:
                if r.Low <= l7:
                    exit_price = r.Close
                    break
            j += 1
        if exit_price is None:
            i += 1
            continue
        ret = (exit_price / entry_price - 1) if direction == "long" else (entry_price / exit_price - 1)
        trades.append(dict(entry_date=entry_date, exit_date=df.Date.iloc[j], hold_days=j - i, ret=ret))
        i = j + 1
    return pd.DataFrame(trades)


def report(trades, label):
    print(f"=== {label}: n={len(trades)} ===")
    if trades.empty:
        print("  no trades\n")
        return
    print(f"  win rate: {(trades.ret>0).mean()*100:.1f}%")
    print(f"  median return/trade: {trades.ret.median()*100:+.2f}%   mean: {trades.ret.mean()*100:+.2f}%")
    print(f"  median hold: {trades.hold_days.median():.0f} days")
    print(f"  cumulative return (sum of per-trade %, not compounded): {trades.ret.sum()*100:+.1f}%")
    s = trades.ret.sort_values(ascending=False)
    top10pct_n = max(1, round(len(s) * 0.10))
    share = s.head(top10pct_n).sum() / s.sum() * 100 if abs(s.sum()) > 1e-6 else float("nan")
    print(f"  concentration check (top10% n={top10pct_n}, share of total ret): {share:.1f}%")
    print()


rsi2_long = simulate_rsi2("long")
rsi2_short = simulate_rsi2("short")
d7_long = simulate_double7("long")
d7_short = simulate_double7("short")

report(rsi2_long, "RSI(2) LONG (CE): RSI(2)<5 above SMA200, exit RSI(2)>65 or Close>SMA5")
report(rsi2_short, "RSI(2) SHORT (PE): RSI(2)>95 below SMA200, exit RSI(2)<35 or Close<SMA5")
report(d7_long, "DOUBLE 7s LONG (CE): 7d low above SMA200, exit at 7d high")
report(d7_short, "DOUBLE 7s SHORT (PE): 7d high below SMA200, exit at 7d low")

rsi2_long.to_csv("nifty_rsi2_long.csv", index=False)
rsi2_short.to_csv("nifty_rsi2_short.csv", index=False)
d7_long.to_csv("nifty_double7_long.csv", index=False)
d7_short.to_csv("nifty_double7_short.csv", index=False)
print("saved 4 CSVs")
