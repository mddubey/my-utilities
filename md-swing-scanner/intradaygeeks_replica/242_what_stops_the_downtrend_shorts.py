"""WHAT PULLS PRICE UP INTO THE STOP? (user, 2026-10-18: 'if 61% of downtrend shorts get stopped, what is causing it -- it should show on the chart').
Descriptive. v1 simplified trades (241's NEW: hourly 11:15 entry, candle-high stop, 1% / 15:15; ATR >= 3%, daily 8 not in the path; no gap / branch /
converged rules), Nifty ABOVE its 200d (where uptrend +107 vs downtrend -7). For every STOPPED trade: the top of the rally after entry (max hourly high
from 11:15 to the close) and which chart level it ended at (within 0.15%), checked in this order: daily 8 touch, daily 34, yesterday's close, yesterday's
high, the day's high before entry, 1H EMA8 at entry; also the hour the stop was hit and Nifty's move from 11:15 to that hour's close."""
import sys, os, io, contextlib, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, os.path.dirname(HERE))
import pandas as pd, numpy as np
from data.paths import DAILY_DIR, INTRADAY_60M_DIR, INDEX_INTRADAY_DIR
with contextlib.redirect_stdout(io.StringIO()): G = runpy.run_path("241_v1_simplified.py")
N = G["NEW"].copy(); B = G["B"]; N["ema8"] = N.ix.map(B["ema8"])
N = N[(N.n200 == True)]
NF = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_1h.csv", index_col=0); NF.index = pd.to_datetime(NF.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
NF = NF[~NF.index.duplicated()].sort_index()
rows = []
for _, r in N.iterrows():
    D = pd.Timestamp(str(r.date)[:10])
    d = pd.read_csv(DAILY_DIR / f"{r.ticker}.csv", index_col=0, parse_dates=True).sort_index(); d = d[~d.index.duplicated()].dropna(subset=["Close"])
    p = d[d.index < D]
    if not len(p): continue
    y = p.iloc[-1]; d34 = p.Close.ewm(span=34, adjust=False).mean().iloc[-1]
    h = pd.read_csv(INTRADAY_60M_DIR / f"{r.ticker}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    h = h[~h.index.duplicated()].sort_index(); g = h[h.index.normalize() == D]
    pre = g[g.index < D + pd.Timedelta("11h15min")]; af = g[g.index >= D + pd.Timedelta("11h15min")]
    if not len(af) or not len(pre): continue
    top = af.High.max(); hit = af[af.High >= r.high]
    pp = (y.High + y.Low + y.Close) / 3
    w = p.resample("W-FRI").agg({"High": "max", "Low": "min", "Close": "last"}).dropna()
    w = w[w.index < D - pd.Timedelta(days=D.weekday())]          # last COMPLETED week
    wy = w.iloc[-1]; wpp = (wy.High + wy.Low + wy.Close) / 3
    step = 10 ** np.floor(np.log10(r.entry)) / 2                 # round numbers: 50 for 100-999, 500 for 1000-9999 ...
    rn = np.ceil(r.entry / step) * step
    lv = {"daily 8": r.s8, "daily 34": d34, "yesterday's close": y.Close, "yesterday's high": y.High, "day high before entry": pre.High.max(), "1H EMA8": r.ema8,
          "daily PP": pp, "daily R1": 2 * pp - y.Low, "daily R2": pp + y.High - y.Low, "daily S1": 2 * pp - y.High, "daily S2": pp - (y.High - y.Low),
          "weekly PP": wpp, "weekly R1": 2 * wpp - wy.Low, "weekly S1": 2 * wpp - wy.High, "day open": g.Open.iloc[0], "round number": rn}
    near = [k for k, v in lv.items() if abs(top / v - 1) <= 0.0015]
    above = [k for k, v in lv.items() if r.high < v <= r.entry * 1.02]   # levels sitting between the stop and +2% at entry time
    nh = hit.index[0] if len(hit) else None
    nm = (NF.Close.asof(nh + pd.Timedelta("55min")) / NF.Close.asof(D + pd.Timedelta("11h10min")) - 1) * 100 if nh is not None else np.nan
    rows.append(dict(up=r.up, o=r.o, top_level=near[0] if near else "none of them", **{f"at|{k}": (k in near) for k in lv}, levels_above_stop=len(above), first_above=min(above, key=lambda k: lv[k]) if above else "none",
                     stop_hour=nh.strftime("%H:%M") if nh is not None else "-", nifty_to_stop=nm, rally=(top / r.entry - 1) * 100))
X = pd.DataFrame(rows); X.to_csv("what_stops_downtrend_shorts.csv", index=False)
S = X[X.o == "stop"]
print(f"Nifty above 200d: trades {len(X)} (stops: uptrend {(S.up).sum()}, downtrend {(~S.up).sum()})")
print("\n### Where did the rally that stopped us END? (stopped trades; a rally can end at several levels at once)\n| top of the rally within 0.15% of | uptrend stops | downtrend stops |\n|---|---|---|")
LV = [c[3:] for c in X.columns if c.startswith("at|")]
for k in LV: print(f"| {k} | {S[S.up][f'at|{k}'].mean()*100:.0f}% | {S[~S.up][f'at|{k}'].mean()*100:.0f}% |")
anyl = S[[f"at|{k}" for k in LV]].any(axis=1)
print(f"| at ANY of these | {anyl[S.up].mean()*100:.0f}% | {anyl[~S.up].mean()*100:.0f}% |")
print(f"| at NONE | {(~anyl[S.up]).mean()*100:.0f}% | {(~anyl[~S.up]).mean()*100:.0f}% |")
print("\n### What sat ABOVE the stop at entry (within 2% of the entry) -- all trades, not only stops\n| first level above the stop | uptrend: n / stop % | downtrend: n / stop % |\n|---|---|---|")
for k in sorted(X.first_above.unique(), key=lambda k: -len(X[X.first_above == k])):
    a, b = X[X.up & (X.first_above == k)], X[~X.up & (X.first_above == k)]
    print(f"| {k} | {len(a)} / {(a.o=='stop').mean()*100:.0f}% | {len(b)} / {(b.o=='stop').mean()*100:.0f}% |")
print("\n### When and with what market were they stopped\n| | uptrend stops | downtrend stops |\n|---|---|---|")
print(f"| stopped in the first hour (11:15) | {(S[S.up].stop_hour == '11:15').mean()*100:.0f}% | {(S[~S.up].stop_hour == '11:15').mean()*100:.0f}% |")
print(f"| Nifty rose from 11:15 to the stop hour's close | {(S[S.up].nifty_to_stop > 0).mean()*100:.0f}% | {(S[~S.up].nifty_to_stop > 0).mean()*100:.0f}% |")
print(f"| median Nifty move to the stop | {S[S.up].nifty_to_stop.median():+.2f}% | {S[~S.up].nifty_to_stop.median():+.2f}% |")
print(f"| median rally size after entry | {S[S.up].rally.median():.2f}% | {S[~S.up].rally.median():.2f}% |")
