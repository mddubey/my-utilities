"""CHART PACK: losing trades of the HOURLY 34 REJECTION as the user would trade it (one a day, highest-ATR pick; 245's O), 8 random STOPPED trades
(fixed seed, picked before looking). Layout the user asked for (2026-10-18): date, ticker, entry 11:15, stop, 1H EMA34, daily 8 and daily 34 (vs entry),
the hour the stop hit, the high after, the close; trend shown as info; a warning when a split / bonus / demerger after the date means TradingView's
(adjusted) prices will differ from ours."""
import sys, os, io, contextlib, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, os.path.dirname(HERE))
import pandas as pd, numpy as np
from data.paths import DAILY_DIR, INTRADAY_60M_DIR
sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()): G = runpy.run_path("245_hourly34_stats.py")
O = G["O"]; N = G["G"]["N"].reset_index(drop=True)
CA = pd.read_csv(os.path.join(os.path.dirname(HERE), "data", "nse_corp_actions.csv"), header=None, names=["t", "s", "d", "p", "x"], dtype=str)
CA = CA[CA.p.str.contains("split|bonus|demerger|Split|Bonus|Demerger", na=False)]; CA["dd"] = pd.to_datetime(CA.d, format="%d-%b-%Y", errors="coerce")
L = O[O.o == "stop"].sample(8, random_state=46).sort_values("date")
rows = []
for idx, r in L.iterrows():
    n = N.loc[idx]; D = pd.Timestamp(str(r.date)[:10]); t = n.ticker
    d = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).sort_index(); d = d[~d.index.duplicated()].dropna(subset=["Close"])
    p = d[d.index < D]; d34 = p.Close.ewm(span=34, adjust=False).mean().iloc[-1]
    h = pd.read_csv(INTRADAY_60M_DIR / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    h = h[~h.index.duplicated()].sort_index(); af = h[(h.index.normalize() == D) & (h.index >= D + pd.Timedelta("11h15min"))]
    stop = n.entry * (1 + r.u_risk / 100); hit = af[af.High >= stop * 0.9999]
    ca = CA[(CA.t == t) & (CA.dd > D)]
    rows.append(dict(n=len(rows) + 1, date=D.strftime("%Y-%m-%d"), ticker=t, trend=("up" if n.up else "down"), entry=round(n.entry, 2), stop=round(stop, 2),
                     ema34_1h=round(n.ema34, 2), d8=f"{n.s8:.2f} ({(n.s8 / n.entry - 1) * 100:+.2f}%)", d34=f"{d34:.2f} ({(d34 / n.entry - 1) * 100:+.2f}%)",
                     stop_hour=hit.index[0].strftime("%H:%M") if len(hit) else "?", high_after=round(af.High.max(), 2), close=round(af.Close.iloc[-1], 2),
                     tv_warning=("; ".join(f"{a.p} {a.d}" for a in ca.itertuples()) if len(ca) else "")))
A = pd.DataFrame(rows); A.to_csv("chart_review_hourly34_losers.csv", index=False); pd.set_option("display.width", 260); print(A.to_string(index=False))
