"""Ad hoc (2026-09-27, user question re: RBLBANK's Friday pinbar at retested support):
does a daily pinbar/hammer at a recent-low support test show real forward follow-through,
and does Friday-close (weekend gap) behave differently from a mid-week pinbar? Full NIFTY
500 universe, full cached history. Exploratory, not a validated project finding.
"""
import pandas as pd
from backtest import load

HORIZONS = [1, 3, 5, 10]
tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()

events = []
for t in tickers:
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
    event_day = is_pinbar & at_support

    n = len(df)
    for i in range(11, n):
        if not bool(event_day.iloc[i]):
            continue
        fwd = {}
        ok = True
        for k in HORIZONS:
            if i + k >= n:
                ok = False
                break
            fwd[k] = df.Close.iloc[i + k] / df.Close.iloc[i] - 1
        if not ok:
            continue
        dow = df.Date.iloc[i].dayofweek
        events.append(dict(ticker=t, date=df.Date.iloc[i], dow=dow, **{f"fwd{k}": fwd[k] for k in HORIZONS}))

ev = pd.DataFrame(events)
print(f"n pinbar-at-support events: {len(ev)}")
print()
print("=== ALL pinbar-at-support events ===")
for k in HORIZONS:
    c = f"fwd{k}"
    print(f"  +{k}d: %positive={(ev[c]>0).mean()*100:5.1f}%  median={ev[c].median()*100:+6.2f}%  mean={ev[c].mean()*100:+6.2f}%")

print()
print(f"=== FRIDAY pinbar events (n={(ev.dow==4).sum()}) -- weekend-gap follow-through ===")
fri = ev[ev.dow == 4]
for k in HORIZONS:
    c = f"fwd{k}"
    print(f"  +{k}d: %positive={(fri[c]>0).mean()*100:5.1f}%  median={fri[c].median()*100:+6.2f}%  mean={fri[c].mean()*100:+6.2f}%")

print()
print(f"=== NON-FRIDAY pinbar events (n={(ev.dow!=4).sum()}) ===")
nonfri = ev[ev.dow != 4]
for k in HORIZONS:
    c = f"fwd{k}"
    print(f"  +{k}d: %positive={(nonfri[c]>0).mean()*100:5.1f}%  median={nonfri[c].median()*100:+6.2f}%  mean={nonfri[c].mean()*100:+6.2f}%")

print()
s = ev["fwd5"].sort_values(ascending=False)
top10_share = s.head(10).sum() / ev["fwd5"].sum() * 100
print(f"concentration check (top10/total fwd5 sum): {top10_share:.1f}%  n={len(ev)}")
