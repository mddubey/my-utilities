"""'Mechanical core' checks (2026-10-02). Spec fixed before running. 5m data Jun 10 - Sep 30 2026.
Basket = 50 largest Nifty-500 names by 20d traded value as of 2026-06-09 (proxy for Nifty 50; no constituent list).
(a) DAY BIAS from VWAP-holding breadth at 10:45 (and 11:15): share of basket stocks whose 5m closes since 09:45 were
    above their session VWAP >= 80% of the time. Bullish >= 70%, bearish <= 30%, else mixed. Outcome: real Nifty 5m
    (Yahoo, Jul 10 - Oct 1) decision -> 15:15, and equal-weight basket decision -> 15:15 (all days).
(b) Our 30m shorts (43's set: alarms 10:45-12:15, 2:1 rule): 'steadily below VWAP' = >= 70% of 5m closes since 09:15
    below VWAP before entry; 'choppy' = >= 4 VWAP crosses (5m close side changes) before entry. Also split by (a)'s bias."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
HERE = Path(__file__).resolve().parent; M5 = HERE.parent / "intraday_cache"


def read(p):
    x = pd.read_csv(p, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[(x.Volume > 0) | (x.High != x.Low)]


def vw_frame(x):
    day = x.index.normalize(); tp = (x.High + x.Low + x.Close) / 3
    vw = (tp * x.Volume).groupby(day).cumsum() / x.Volume.groupby(day).cumsum().replace(0, np.nan)
    return pd.DataFrame({"c": x.Close, "vw": vw, "day": day})


u500 = pd.read_csv(HERE.parent / "nifty500_universe.csv", header=None)[0].tolist()
tv = {}
for t in u500:
    try: d = load(t); tv[t] = d.traded_value_sma20.loc[:"2026-06-09"].iloc[-1]
    except Exception: pass
basket = sorted(tv, key=lambda k: -tv[k])[:50]
print("basket (top 50 by traded value):", ", ".join(basket[:12]), "...")
B = {}
for t in basket:
    p = M5 / f"{t}.csv"
    if p.exists(): B[t] = vw_frame(read(p))
rows = []
for day in sorted(set.intersection(*[set(f.day.unique()) for f in B.values()])):
    for dec in ("10:45", "11:15"):
        dts = pd.Timestamp(f"{day:%Y-%m-%d} {dec}"); hold, rets = [], []
        for t, f in B.items():
            g = f[f.day == day]
            if len(g) < 70: continue
            w = g[(g.index >= day + pd.Timedelta("9h45min")) & (g.index + pd.Timedelta("5min") <= dts)]
            if len(w) < 6: continue
            hold.append((w.c > w.vw).mean())
            at = g[g.index + pd.Timedelta("5min") <= dts].c.iloc[-1]; end = g[g.index < day + pd.Timedelta("15h15min")].c.iloc[-1]
            rets.append(end / at - 1)
        if len(hold) < 40: continue
        h = np.array(hold); rows.append(dict(day=day, dec=dec, breadth=(h >= 0.8).mean(), below=(h <= 0.2).mean(), basket_ret=np.mean(rets) * 100))
Dy = pd.DataFrame(rows)
Dy["bias"] = np.select([Dy.breadth >= 0.7, Dy.below >= 0.7], ["bullish", "bearish"], "mixed")
n5 = read(HERE / "index_1h" / "_NIFTY_5m_60d.csv")
def nret(r):
    g = n5[n5.index.normalize() == r.day]
    if g.empty: return np.nan
    a = g[g.index + pd.Timedelta("5min") <= pd.Timestamp(f"{r.day:%Y-%m-%d} {r.dec}")]; b = g[g.index < r.day + pd.Timedelta("15h15min")]
    return (b.Close.iloc[-1] / a.Close.iloc[-1] - 1) * 100 if len(a) and len(b) else np.nan
Dy["nifty_ret"] = Dy.apply(nret, axis=1); Dy.to_csv(HERE / "vwap_breadth_bias.csv", index=False)
print(f"\n(a) DAY BIAS from VWAP-holding breadth ({Dy.day.nunique()} days)")
print("| decision | bias | days | Nifty decision->15:15 mean % | Nifty up % of days | n (Nifty) | basket mean % | basket up % |\n|---|---|---|---|---|---|---|---|")
for (dec, b), g in Dy.groupby(["dec", "bias"]):
    n = g.nifty_ret.dropna()
    print(f"| {dec} | {b} | {len(g)} | {n.mean():+.3f} | {(n>0).mean()*100:.0f}% | {len(n)} | {g.basket_ret.mean():+.3f} | {(g.basket_ret>0).mean()*100:.0f}% |")
# (b)
T = pd.read_csv(HERE / "alarm_times_30m.csv", parse_dates=["date", "t_in", "t_out"])
T = T[T.alarm.isin(["10:45", "11:15", "11:45", "12:15"])].copy()
feat = {}
for t, g in T.groupby("ticker"):
    f = vw_frame(read(M5 / f"{t}.csv"))
    for r in g.itertuples():
        w = f[(f.day == r.date) & (f.index + pd.Timedelta("5min") <= r.t_in)]
        side = np.sign(w.c - w.vw)
        feat[r.Index] = ((w.c < w.vw).mean(), int((side.diff().abs() > 0).sum()))
T["below_share"] = [feat.get(i, (np.nan, np.nan))[0] for i in T.index]; T["crosses"] = [feat.get(i, (np.nan, np.nan))[1] for i in T.index]
bias = Dy[Dy.dec == "10:45"].set_index("day").bias; T["day_bias"] = T.date.map(bias)
def line(x, lab):
    if len(x) < 30: print(f"| {lab} | {len(x)} | too few | | |"); return
    m = x.groupby(x.date.dt.month).ret.mean()
    print(f"| {lab} | {len(x)} | {(x.ret>0).mean()*100:.0f} | {x.ret.mean():+.3f} | " + " / ".join(f"{v:+.2f}" for v in m) + " |")
print(f"\n(b) OUR 30m SHORTS (alarms 10:45-12:15, 2:1 rule)\n| group | trades | win% | mean % | Jun / Jul / Aug / Sep |\n|---|---|---|---|---|")
line(T, "BASELINE")
line(T[T.below_share >= 0.7], "steadily below VWAP (>= 70% of closes)"); line(T[T.below_share < 0.7], "not steadily below")
line(T[T.crosses >= 4], "choppy: >= 4 VWAP crosses before entry"); line(T[T.crosses < 4], "< 4 crosses")
for b in ("bearish", "mixed", "bullish"): line(T[T.day_bias == b], f"day bias at 10:45 = {b}")
print(f"\nmedian below-VWAP share {T.below_share.median():.2f}, median crosses {T.crosses.median():.0f}")
