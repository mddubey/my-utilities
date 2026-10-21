"""R1 poke-and-fade by time of day (2026-10-21, spec agreed in chat; RESULTS ONLY, nothing goes to STRATEGY.md).

Question: a stock's 5-min high reaches daily R1 for the first time today and the bar closes back under R1 -- short at that
bar's close. Does it work at any time of day, and better than poking a plain new day high with no level near?

Event R1:  first 5-min bar (09:20+) whose High >= R1*(1-0.0005), every earlier bar's High below that, Close < R1.
Control:   first bar per stock-day per time bucket that makes a new day high, closes back under the prior day-high,
           with no known level (R1, R2, daily 8 touch, yesterday's high / close) within 0.3% of the poke high.
Trade:     entry = event bar close, stop = event bar high + 0.05%, package (a): stop to entry after +2R (from the next
           bar), out at the 15:10 bar close (15:15). Within a bar the stop is checked before the +2R update.
Universe:  5-min cache (2026-06-10 on), price >= Rs100, prior-5-day median 5-min turnover >= Rs15 lakh.
Stacked:   R1 with the daily 8 touch, yesterday's high or the 09:15 high within 0.3%.
Cost:      ~Rs85 per Rs1 lakh traded, reported per Rs1k risk.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd, numpy as np
from multiprocessing import Pool
from data.paths import INTRADAY_5M_DIR, DAILY_DIR
from orb_common import read5_official

TOUCH, STOP_BUF, STACK, LIQ = 0.0005, 0.0005, 0.003, 15e5
BUCKETS = [("09:20-10:30", "09:20", "10:25"), ("10:30-12:00", "10:30", "11:55"),
           ("12:00-13:30", "12:00", "13:25"), ("13:30-15:00", "13:30", "14:55")]


def bucket(hm):
    for name, a, b in BUCKETS:
        if a <= hm <= b: return name
    return None


def simulate(day, i):
    e = day.Close.iat[i]; stop = day.High.iat[i] * (1 + STOP_BUF); risk = stop - e
    if risk <= 0: return None
    cur, be = stop, False
    for j in range(i + 1, len(day)):
        if day.High.iat[j] >= cur: return e, cur, (e - cur) / risk, "BE" if be else "stop", day.index[j]
        if not be and day.Low.iat[j] <= e - 2 * risk: cur, be = e, True
        if day.index[j].strftime("%H:%M") == "15:10": return e, day.Close.iat[j], (e - day.Close.iat[j]) / risk, "time", day.index[j]
    return e, day.Close.iat[-1], (e - day.Close.iat[-1]) / risk, "time", day.index[-1]


def one(t):
    try:
        m = read5_official(t)
        d = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True)
    except Exception:
        return []
    d["e8"] = d.Close.ewm(span=8, adjust=False).mean()
    m["to"] = m.Close * m.Volume; m["day"] = m.index.normalize()
    med5 = m.groupby("day").to.median()
    out = []
    for day_ts, day in m.groupby("day"):
        if day_ts not in d.index: continue
        k = d.index.get_loc(day_ts)
        if k < 1: continue
        p = d.iloc[k - 1]; H, L, C = p.High, p.Low, p.Close
        PP = (H + L + C) / 3; R1 = 2 * PP - L; R2 = PP + H - L; d8 = p.e8
        prior = med5[med5.index < day_ts].tail(5)
        if len(prior) < 3 or prior.median() < LIQ or day.Open.iat[0] < 100: continue
        if abs(R1 / day.Open.iat[0] - 1) > 0.10: continue          # split / bad-data guard
        hm = day.index.strftime("%H:%M"); h915 = day.High.iat[0]
        levels = [R1, R2, d8, H, C]
        # R1 event
        thr = R1 * (1 - TOUCH)
        for i in range(1, len(day)):
            if hm[i] > "14:55": break
            if day.High.iloc[:i].max() >= thr: break
            if day.High.iat[i] >= thr:
                if day.Close.iat[i] < R1 and bucket(hm[i]):
                    stacked = any(abs(x / R1 - 1) <= STACK for x in (d8, H, h915))
                    s = simulate(day, i)
                    if s: out.append(dict(t=t, date=day_ts.date(), kind="R1", bar=hm[i], bucket=bucket(hm[i]), stacked=stacked,
                                          level=round(R1, 2), poke=day.High.iat[i], bar_open=day.Open.iat[i], entry=s[0], stop=round(day.High.iat[i] * (1 + STOP_BUF), 2),
                                          exit=round(s[1], 2), R=s[2], how=s[3], exit_t=s[4].strftime("%H:%M")))
                break
        # control: plain new day high, no level near, first per bucket
        seen = set(); run = day.High.iat[0]
        for i in range(1, len(day)):
            if hm[i] > "14:55": break
            hi = day.High.iat[i]
            if hi > run:
                b = bucket(hm[i])
                if b and b not in seen and day.Close.iat[i] < run and not any(abs(x / hi - 1) <= STACK for x in levels):
                    seen.add(b); s = simulate(day, i)
                    if s: out.append(dict(t=t, date=day_ts.date(), kind="plain_high", bar=hm[i], bucket=b, stacked=False,
                                          level=round(run, 2), poke=hi, bar_open=day.Open.iat[i], entry=s[0], stop=round(hi * (1 + STOP_BUF), 2),
                                          exit=round(s[1], 2), R=s[2], how=s[3], exit_t=s[4].strftime("%H:%M")))
                run = hi
    return out


def summary(g):
    risk_rs = 1000.0
    cost = 85 * (risk_rs / (g.stop - g.entry)) * g.entry / 1e5
    net = risk_rs * g.R - cost
    daily = net.groupby(g.date).sum().sort_values()
    eq = net.cumsum(); dd = (eq - eq.cummax()).min()
    streak = (g.R <= 0).astype(int).groupby((g.R > 0).cumsum()).sum().max()
    return pd.Series(dict(n=len(g), win=f"{(g.R > 0).mean() * 100:.0f}%", avgR=round(g.R.mean(), 2),
                          net_per_trade=round(net.mean()), net_total=round(net.sum()),
                          wo_top5_days=round(daily.iloc[:-5].sum()) if len(daily) > 5 else np.nan,
                          maxDD=round(dd), worst_streak=int(streak)))


if __name__ == "__main__":
    tick = sorted(p.stem for p in INTRADAY_5M_DIR.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as pool:
        res = []
        for n, r in enumerate(pool.imap_unordered(one, tick, chunksize=20), 1):
            res += r
            if n % 300 == 0: print(f"{n}/{len(tick)}", flush=True)
    ev = pd.DataFrame(res).sort_values(["date", "bar"]).reset_index(drop=True)
    out = Path(__file__).resolve().parent / "r1_poke_fade_events.csv"
    ev.to_csv(out, index=False)
    print("events", len(ev), "dates", ev.date.min(), ev.date.max())
    pd.set_option("display.width", 200)
    print("\nBY KIND"); print(ev.groupby("kind").apply(summary).to_string())
    print("\nBY KIND x TIME BUCKET"); print(ev.groupby(["kind", "bucket"]).apply(summary).to_string())
    print("\nR1: STACKED vs ALONE"); print(ev[ev.kind == "R1"].groupby("stacked").apply(summary).to_string())
    print("\nR1 STACKED x BUCKET"); print(ev[ev.kind == "R1"].groupby(["stacked", "bucket"]).apply(summary).to_string())
    print("\nR1 exits"); print(ev[ev.kind == "R1"].how.value_counts().to_string())
    ev["red"] = ev.entry < ev.bar_open
    print("\nRED event bar only (close < open)"); print(ev.groupby(["kind", "red"]).apply(summary).to_string())
    print("\nR1 RED x BUCKET"); print(ev[(ev.kind == "R1") & ev.red].groupby("bucket").apply(summary).to_string())
    print("\nR1 by month"); print(ev[ev.kind == "R1"].groupby(pd.to_datetime(ev[ev.kind == "R1"].date).dt.to_period("M")).apply(summary).to_string())
