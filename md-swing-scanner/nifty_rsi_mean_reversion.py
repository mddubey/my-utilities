"""Ad hoc (2026-09-27): real, sourced strategy from online research (RSI(14) mean-reversion
-- buy when RSI crosses back above 30 from oversold, short when RSI crosses back below 70
from overbought; real cited benchmark, SPY 2014-2024: 58% win rate, +6.8% avg winner).
Backtest both CE (bullish) and PE (bearish) sides on real 5-year NIFTY daily data, full
symmetric test as requested. No lookahead: RSI computed causally, signal fires on the day
the cross happens, forward returns measured from that day's Close.
"""
import pandas as pd
import numpy as np

df = pd.read_csv("data_cache/_NIFTY.csv")
df["Date"] = pd.to_datetime(df.Date)

delta = df.Close.diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)
avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
rs = avg_gain / avg_loss
df["rsi14"] = 100 - (100 / (1 + rs))

bullish = (df.rsi14 > 30) & (df.rsi14.shift(1) <= 30)   # crossed back ABOVE 30
bearish = (df.rsi14 < 70) & (df.rsi14.shift(1) >= 70)   # crossed back BELOW 70

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
        events.append(dict(date=df.Date.iloc[i], rsi=df.rsi14.iloc[i], **{f"fwd{k}": fwd[k] for k in HORIZONS}))
    ev = pd.DataFrame(events)
    print(f"=== {label}: n={len(ev)} ===")
    if ev.empty:
        print("  no events\n")
        return ev
    for k in HORIZONS:
        c = f"fwd{k}"
        print(f"  +{k:2d}d: %positive={(ev[c]>0).mean()*100:5.1f}%  median={ev[c].median()*100:+6.2f}%  mean={ev[c].mean()*100:+6.2f}%")
    s = ev["fwd10"].sort_values(ascending=False)
    top10pct_n = max(1, round(len(s) * 0.10))
    total = s.sum()
    share = s.head(top10pct_n).sum() / total * 100 if abs(total) > 1e-6 else float("nan")
    print(f"  concentration check (top10% n={top10pct_n}, share of fwd10 sum, total={total:.1f}%): {share:.1f}%")
    print()
    return ev


bull_ev = eval_signal(bullish, "BULLISH (CE angle): RSI(14) crosses back above 30 from oversold")
bear_ev = eval_signal(bearish, "BEARISH (PE angle): RSI(14) crosses back below 70 from overbought -- returns as SHORT P&L")

base_events = []
for i in df.index[15:]:
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
    print(f"  +{k:2d}d: %positive={(base[k]>0).mean()*100:5.1f}%  median={base[k].median()*100:+6.2f}%  mean={base[k].mean()*100:+6.2f}%")

bull_ev.to_csv("nifty_rsi_bullish.csv", index=False)
bear_ev.to_csv("nifty_rsi_bearish.csv", index=False)
print()
print("saved: nifty_rsi_bullish.csv, nifty_rsi_bearish.csv")
