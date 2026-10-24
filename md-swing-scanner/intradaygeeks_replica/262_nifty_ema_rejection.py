"""Nifty EMA rejection vs a blind short, by regime (2026-10-23, user's Nifty PE setups; RESULTS ONLY, nothing to STRATEGY.md).
User's Nifty levels: daily 8 / daily 34 EMA (yesterday's value), 1H EMA8 / 1H EMA34 (previous hourly bar's value).
Event:  first hourly candle of the day per level that OPENS under the level, its high reaches it (>= L - 0.05%), and it
        closes RED back under it. Entry = that candle's close; stop = its high + 0.05% (no cap -- options, premium-sized).
Exits:  (a) hold to the 14:15 candle close (~15:15); (b) fixed target 0.5% under entry (~the user's 100-110 pt PE moves).
        Hourly OHLC: a candle touching both stop and target = stop (worst case).
Blind:  short every day at the 09:15 open, out at the 14:15 candle close.
Splits: year, Nifty vs its 200d SMA (yesterday), 20-day EMA rising vs 5 days before, candle hour, stacked (another of the
        four levels within 0.15%). Spot % and R; costs not modelled (options)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd, numpy as np
from data.paths import DAILY_DIR, INDEX_INTRADAY_DIR

TOUCH, BUF, TGT, STACK = 0.0005, 0.0005, 0.005, 0.0015
h = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_1h.csv", index_col=0)
h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
h = h[~h.index.duplicated()].sort_index()
h["h8"] = h.Close.ewm(span=8, adjust=False).mean().shift(1)
h["h34"] = h.Close.ewm(span=34, adjust=False).mean().shift(1)
d = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True)
d = d[~d.index.duplicated()].sort_index()
d["d8"] = d.Close.ewm(span=8, adjust=False).mean().shift(1)
d["d34"] = d.Close.ewm(span=34, adjust=False).mean().shift(1)
d["above200"] = (d.Close > d.Close.rolling(200).mean()).shift(1)
e20 = d.Close.ewm(span=20, adjust=False).mean()
d["up20"] = (e20 > e20.shift(5)).shift(1)

ev, base = [], []
for day, g in h.groupby(h.index.normalize()):
    if day not in d.index or len(g) < 6 or g.index[0].strftime("%H:%M") != "09:15": continue
    dr = d.loc[day]
    if pd.isna(dr.d34) or pd.isna(dr.above200): continue
    hm = list(g.index.strftime("%H:%M"))
    if "14:15" not in hm: continue
    xi = hm.index("14:15"); xc = g.Close.iat[xi]
    reg = dict(date=day.date(), year=day.year, above200=bool(dr.above200), up20=bool(dr.up20))
    base.append(dict(reg, pct=(g.Open.iat[0] / xc - 1) * 100))
    for kind in ("d8", "d34", "h8", "h34"):
        for i in range(xi):
            L = dr[kind] if kind[0] == "d" else g[kind].iat[i]
            o, hi, c = g.Open.iat[i], g.High.iat[i], g.Close.iat[i]
            if not (o < L and hi >= L * (1 - TOUCH) and c < L and c < o): continue
            others = [dr["d8"], dr["d34"], g["h8"].iat[i], g["h34"].iat[i]]
            stacked = sum(abs(x / L - 1) <= STACK for x in others) >= 2          # itself + at least one more
            stop = hi * (1 + BUF); risk = stop - c; tgt = c * (1 - TGT)
            res_t, mfe = None, 0.0
            for j in range(i + 1, xi + 1):
                mfe = max(mfe, (c - g.Low.iat[j]) / c * 100)
                if res_t is None:
                    if g.High.iat[j] >= stop: res_t = (-1.0, -(stop / c - 1) * 100, "stop")
                    elif g.Low.iat[j] <= tgt: res_t = ((c - tgt) / risk, TGT * 100, "target")
            hold_stop = any(g.High.iat[j] >= stop for j in range(i + 1, xi + 1))
            hold = (-1.0, -(stop / c - 1) * 100) if hold_stop else ((c - xc) / risk, (c / xc - 1) * 100)
            if res_t is None: res_t = ((c - xc) / risk, (c / xc - 1) * 100, "time")
            ev.append(dict(reg, level=kind, hour=hm[i], stacked=stacked, entry=round(c, 1), stop=round(stop, 1),
                           risk_pct=risk / c * 100, hold_R=hold[0], hold_pct=hold[1], t_R=res_t[0], t_pct=res_t[1],
                           t_how=res_t[2], mfe_pct=mfe))
            break                                    # first rejection per level per day
E = pd.DataFrame(ev); B = pd.DataFrame(base)
E.to_csv(Path(__file__).resolve().parent / "nifty_ema_rejection_events.csv", index=False)


def S(x):
    return pd.Series(dict(n=len(x), stop_risk_pct=x.risk_pct.median(), hold_win=(x.hold_R > 0).mean() * 100,
                          hold_avg_pct=x.hold_pct.mean(), hold_avgR=x.hold_R.mean(), tgt_hit=(x.t_how == "target").mean() * 100,
                          tgt_stop=(x.t_how == "stop").mean() * 100, tgt_avg_pct=x.t_pct.mean(), tgt_avgR=x.t_R.mean(),
                          mfe_med_pct=x.mfe_pct.median())).round(2)


def SB(x):
    return pd.Series(dict(days=len(x), win=(x.pct > 0).mean() * 100, avg_pct=x.pct.mean())).round(2)


pd.set_option("display.width", 250)
print("events", len(E), "days", B.shape[0], B.date.min(), "..", B.date.max())
print("\nBY LEVEL"); print(E.groupby("level").apply(S).to_string())
print("\nSTACKED vs ALONE"); print(E.groupby("stacked").apply(S).to_string())
print("\nBY YEAR -- setup"); print(E.groupby("year").apply(S).to_string())
print("BY YEAR -- blind open short"); print(B.groupby("year").apply(SB).to_string())
print("\nBY 200d -- setup"); print(E.groupby("above200").apply(S).to_string())
print("BY 200d -- blind"); print(B.groupby("above200").apply(SB).to_string())
print("\nBY 20d EMA trend -- setup"); print(E.groupby("up20").apply(S).to_string())
print("BY 20d trend -- blind"); print(B.groupby("up20").apply(SB).to_string())
print("\nLEVEL x 200d"); print(E.groupby(["level", "above200"]).apply(S).to_string())
print("\nBY CANDLE HOUR"); print(E.groupby("hour").apply(S).to_string())
print("\nLAST 10 EVENTS"); print(E.tail(10)[["date", "level", "hour", "stacked", "entry", "stop", "hold_pct", "hold_R", "t_how", "t_pct"]].round(2).to_string(index=False))
