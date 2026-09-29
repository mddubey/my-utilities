"""Ad hoc (2026-09-27), v2: rebuild the SHORT side of both Connors strategies using the
corrected regime filter found by testing -- SMA200 SLOPE (is the 200-day average itself
declining over the last 20 days), not just Close < SMA200 position. LONG side unchanged
(Close > SMA200 already worked well there). Real, full trade simulation, same exit rules
as nifty_connors_strategies.py.
"""
import pandas as pd

df = pd.read_csv("data_cache/_NIFTY.csv")
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
df["sma200_20ago"] = df.sma200.shift(20)
df["sma200_declining"] = df.sma200 < df.sma200_20ago

n = len(df)


def simulate_rsi2_short_v2():
    trades = []
    i = 35
    while i < n:
        row = df.iloc[i]
        if pd.isna(row.rsi2) or pd.isna(row.sma200_declining):
            i += 1
            continue
        signal = row.rsi2 > 95 and row.sma200_declining
        if not signal:
            i += 1
            continue
        entry_price = row.Close
        entry_date = row.Date
        j = i + 1
        exit_price = None
        while j < n:
            r = df.iloc[j]
            if r.rsi2 < 35 or r.Close < r.sma5:
                exit_price = r.Close
                break
            j += 1
        if exit_price is None:
            i += 1
            continue
        ret = entry_price / exit_price - 1
        trades.append(dict(entry_date=entry_date, exit_date=df.Date.iloc[j], hold_days=j - i, ret=ret))
        i = j + 1
    return pd.DataFrame(trades)


def simulate_double7_short_v2():
    trades = []
    i = 28
    while i < n:
        row = df.iloc[i]
        if pd.isna(row.high7_prior) or pd.isna(row.sma200_declining):
            i += 1
            continue
        signal = row.High >= row.high7_prior and row.sma200_declining
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
    print(f"  cumulative return (sum, uncompounded): {trades.ret.sum()*100:+.1f}%")
    s = trades.ret.sort_values(ascending=False)
    top10pct_n = max(1, round(len(s) * 0.10))
    total = s.sum()
    share = s.head(top10pct_n).sum() / total * 100 if abs(total) > 1e-6 else float("nan")
    print(f"  concentration check (top10% n={top10pct_n}, share of total): {share:.1f}%")
    print(trades.to_string(index=False))
    print()


rsi2_short_v2 = simulate_rsi2_short_v2()
d7_short_v2 = simulate_double7_short_v2()

report(rsi2_short_v2, "RSI(2) SHORT v2 (PE): RSI(2)>95 + SMA200 genuinely declining, exit RSI(2)<35 or Close<SMA5")
report(d7_short_v2, "DOUBLE 7s SHORT v2 (PE): 7d high + SMA200 genuinely declining, exit at 7d low")

rsi2_short_v2.to_csv("nifty_rsi2_short_v2.csv", index=False)
d7_short_v2.to_csv("nifty_double7_short_v2.csv", index=False)
print("saved: nifty_rsi2_short_v2.csv, nifty_double7_short_v2.csv")
