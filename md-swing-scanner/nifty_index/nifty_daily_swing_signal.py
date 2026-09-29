"""Ad hoc (2026-09-27): pivot away from the intraday-data-starved NIFTY options exploration
toward something the project's daily data can actually support well -- a real SWING-style
signal on NIFTY itself (multi-day hold, not a same-day scalp), using the same spirit as this
project's own validated stock-side Breakout Continuation signal, applied to the index.

Bullish: fresh 10-day high (Close > High.shift(1).rolling(10).max()) while trend-aligned
(Close > SMA50 > SMA200). Bearish (symmetric, testing the PE angle properly this time, on
real 5-year sample size): fresh 10-day low while trend-aligned the other way (Close < SMA50
< SMA200). Forward returns measured Close[event] -> Close[event+k], k=5,10,20 trading days.
No lookahead: the breakout condition and trend filter both use only data through the event
day itself.
"""
import pandas as pd

df = pd.read_csv("../data_cache/_NIFTY.csv")
df["Date"] = pd.to_datetime(df.Date)

df["high10_prior"] = df.High.shift(1).rolling(10).max()
df["low10_prior"] = df.Low.shift(1).rolling(10).min()

bullish = (df.Close > df.high10_prior) & (df.Close > df.sma50) & (df.sma50 > df.sma200)
bearish = (df.Close < df.low10_prior) & (df.Close < df.sma50) & (df.sma50 < df.sma200)

HORIZONS = [5, 10, 20]
n = len(df)


def eval_signal(mask, label, invert=False):
    events = []
    for i in df.index[mask]:
        fwd = {}
        ok = True
        for k in HORIZONS:
            if i + k >= n:
                ok = False
                break
            ret = df.Close.iloc[i + k] / df.Close.iloc[i] - 1
            fwd[k] = -ret if invert else ret
        if not ok:
            continue
        events.append(dict(date=df.Date.iloc[i], **{f"fwd{k}": fwd[k] for k in HORIZONS}))
    ev = pd.DataFrame(events)
    print(f"=== {label}: n={len(ev)} ===")
    if ev.empty:
        print("  no events")
        return ev
    for k in HORIZONS:
        c = f"fwd{k}"
        print(f"  +{k:2d}d: %positive={(ev[c]>0).mean()*100:5.1f}%  median={ev[c].median()*100:+6.2f}%  mean={ev[c].mean()*100:+6.2f}%")
    s = ev["fwd10"].sort_values(ascending=False)
    top10pct_n = max(1, round(len(s) * 0.10))
    share = s.head(top10pct_n).sum() / s.sum() * 100 if s.sum() else float("nan")
    print(f"  concentration check (top10% n={top10pct_n}, share of fwd10 sum): {share:.1f}%")
    print()
    return ev


bull_ev = eval_signal(bullish, "BULLISH: fresh 10d high + trend-aligned (Close>SMA50>SMA200)")
bear_ev = eval_signal(bearish, "BEARISH: fresh 10d low + trend-aligned (Close<SMA50<SMA200) -- returns shown as SHORT P&L (inverted)")

# baseline: all days, same horizons, for comparison
base_events = []
for i in df.index[10:]:
    fwd = {}
    ok = True
    for k in HORIZONS:
        if i + k >= n:
            ok = False
            break
        fwd[k] = df.Close.iloc[i + k] / df.Close.iloc[i] - 1
    if not ok:
        continue
    base_events.append(fwd)
base = pd.DataFrame(base_events)
print(f"=== BASELINE (all days): n={len(base)} ===")
for k in HORIZONS:
    c = k
    print(f"  +{k:2d}d: %positive={(base[c]>0).mean()*100:5.1f}%  median={base[c].median()*100:+6.2f}%  mean={base[c].mean()*100:+6.2f}%")

bull_ev.to_csv("nifty_daily_swing_bullish.csv", index=False)
bear_ev.to_csv("nifty_daily_swing_bearish.csv", index=False)
print()
print("saved: nifty_daily_swing_bullish.csv, nifty_daily_swing_bearish.csv")
