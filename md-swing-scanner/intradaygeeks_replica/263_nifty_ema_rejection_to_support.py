"""Nifty EMA rejection held to the NEXT SUPPORT, can run over days (2026-10-23, user: "I will book at the next possible support
like we did today"; RESULTS ONLY). Events exactly as 262 (hourly candle opens under the daily 8 / daily 34 / 1H EMA8 / 1H EMA34,
high reaches it, closes red under it; first per level per day; entry = candle close, stop = candle high + 0.05%).
Target = fixed AT ENTRY: the nearest support at least GAP under the entry, booked 0.05% in front of it. Supports known then:
  yesterday's low / close, today's PP / S1 / S2 (yesterday's HLC), daily 8 / 21 / 34 / 50 EMA (yesterday's values), 1H EMA8 / 34
  (previous bar), today's low before the entry candle, the prior 5-day low.
Walk: every later hourly bar, across days, up to the close of the 5th trading day after entry (weekly-expiry cap). A bar that
OPENS through the stop / target exits at its open (gaps count); a bar touching both = stop. GAP pre-declared 0.2%, shown at
0.1 / 0.3 too."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd, numpy as np
from data.paths import DAILY_DIR, INDEX_INTRADAY_DIR

TOUCH, BUF, FRONT, STACK, MAXD = 0.0005, 0.0005, 0.0005, 0.0015, 5
h = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_1h.csv", index_col=0)
h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
h = h[~h.index.duplicated()].sort_index()
h["h8"] = h.Close.ewm(span=8, adjust=False).mean().shift(1)
h["h34"] = h.Close.ewm(span=34, adjust=False).mean().shift(1)
d = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True)
d = d[~d.index.duplicated()].sort_index()
for s in (8, 21, 34, 50): d[f"d{s}"] = d.Close.ewm(span=s, adjust=False).mean().shift(1)
d["yH"], d["yL"], d["yC"] = d.High.shift(1), d.Low.shift(1), d.Close.shift(1)
d["low5"] = d.Low.shift(1).rolling(5).min()
d["above200"] = (d.Close > d.Close.rolling(200).mean()).shift(1)
e20 = d.Close.ewm(span=20, adjust=False).mean(); d["up20"] = (e20 > e20.shift(5)).shift(1)
days = sorted(set(h.index.normalize()))
H = h.reset_index().rename(columns={"index": "ts", "Datetime": "ts"})
H["day"] = H.ts.dt.normalize()
pos = {dd: i for i, dd in enumerate(days)}


def run(GAP):
    ev = []
    for day, g in H.groupby("day"):
        if day not in d.index or len(g) < 6: continue
        dr = d.loc[day]
        if pd.isna(dr.d50) or pd.isna(dr.above200) or pd.isna(dr.low5): continue
        PP = (dr.yH + dr.yL + dr.yC) / 3
        fixed = [dr.yL, dr.yC, PP, 2 * PP - dr.yH, PP - (dr.yH - dr.yL), dr.d8, dr.d21, dr.d34, dr.d50, dr.low5]
        k = pos[day]; last_day = days[min(k + MAXD, len(days) - 1)]
        rows = g.index.tolist()
        for kind in ("d8", "d34", "h8", "h34"):
            for ii, ri in enumerate(rows[:-1]):
                b = H.loc[ri]
                L = dr[kind] if kind[0] == "d" else b[kind]
                if not (b.Open < L and b.High >= L * (1 - TOUCH) and b.Close < L and b.Close < b.Open): continue
                c = b.Close; stop = b.High * (1 + BUF); risk = stop - c
                others = [dr.d8, dr.d34, b.h8, b.h34]
                stacked = sum(abs(x / L - 1) <= STACK for x in others) >= 2
                lowsofar = H.loc[rows[:ii]].Low.min() if ii else np.nan
                sup = [x for x in fixed + [b.h8, b.h34, lowsofar] if x == x and x <= c * (1 - GAP)]
                if not sup: continue
                S = max(sup); tgt = S * (1 + FRONT)
                walk = H[(H.index > ri) & (H.day <= last_day)]
                res = None; mfe = 0.0
                for _, w in walk.iterrows():
                    if w.Open >= stop: res = (w.Open, "stop-gap", w.day); break
                    if w.Open <= tgt: res = (w.Open, "target-gap", w.day); break
                    if w.High >= stop: res = (stop, "stop", w.day); break
                    mfe = max(mfe, (c - w.Low) / c * 100)
                    if w.Low <= tgt: res = (tgt, "target", w.day); break
                if res is None:
                    if not len(walk): continue
                    res = (walk.Close.iat[-1], "time", walk.day.iat[-1])
                px, how, xd = res
                ev.append(dict(date=day.date(), year=day.year, above200=bool(dr.above200), up20=bool(dr.up20), level=kind,
                               hour=b.ts.strftime("%H:%M"), stacked=stacked, entry=c, stop=stop, target=tgt,
                               tgt_dist_pct=(c / tgt - 1) * 100, risk_pct=risk / c * 100, exit=px, how=how,
                               days_held=pos[xd] - k, pct=(c / px - 1) * 100, R=(c - px) / risk, mfe_pct=mfe))
                break
    return pd.DataFrame(ev)


def S(x):
    return pd.Series(dict(n=len(x), tgt_dist=x.tgt_dist_pct.median(), stop_pct=x.risk_pct.median(),
                          target=x.how.str.startswith("target").mean() * 100, stop=x.how.str.startswith("stop").mean() * 100,
                          time=(x.how == "time").mean() * 100, win=(x.R > 0).mean() * 100, avg_pct=x.pct.mean(),
                          avgR=x.R.mean(), days_med=x.days_held.median(), overnight=(x.days_held > 0).mean() * 100)).round(2)


pd.set_option("display.width", 250)
E = run(0.002); E.to_csv(Path(__file__).resolve().parent / "nifty_ema_rejection_to_support_events.csv", index=False)
print("GAP 0.2% | events", len(E), E.date.min(), "..", E.date.max())
print("\nALL"); print(S(E).to_frame().T.to_string(index=False))
for col in ("above200", "year", "up20", "level", "stacked", "hour"):
    print(f"\nBY {col}"); print(E.groupby(col).apply(S).to_string())
print("\nLEVEL x 200d"); print(E.groupby(["level", "above200"]).apply(S).to_string())
for G in (0.001, 0.003):
    X = run(G); print(f"\nROBUSTNESS GAP {G*100:.1f}% -- by 200d"); print(X.groupby("above200").apply(S).to_string())
print("\nLAST 12"); print(E.tail(12)[["date", "level", "hour", "entry", "stop", "target", "how", "exit", "days_held", "pct", "R"]].round(2).to_string(index=False))
