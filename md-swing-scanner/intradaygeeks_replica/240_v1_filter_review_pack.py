"""v1 FILTER REVIEW PACKS on the HOURLY v1 trades (user, 2026-10-17: 'no 5-min mechanics -- back to the 11:15 hourly; show me the stops each
data-mined filter avoids, maybe something simpler explains them'). For one filter at a time: v1's rules (script 164: 10:15 candle red at the
1H EMA34, entry at the 11:15 close, stop = candle high <= 0.5%, 1% target / 15:15, E1; both Nifty regimes) with ONLY that filter removed;
pack = the trades the filter removes, 6 random STOPS + 4 random TARGETS (fixed seed, picked before looking), with everything needed on the
1H chart: the 10:15 candle, 1H EMA34 / EMA8, entry, stop, daily 8 touch (vs entry), daily 34, yesterday's H / L / C, gap, outcome.
Usage: python3 240_v1_filter_review_pack.py gap | trend | branch | converged"""
import sys, os, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
FILTERS = {"gap": " & (B.gap > -0.25) & (B.gap <= 0.5)", "trend": "(B.s8 > B.s34) & "}
which = sys.argv[1] if len(sys.argv) > 1 else "gap"
P148 = open("148_clean_shape_0915.py").read()
if which in FILTERS: P148 = P148.replace(FILTERS[which], "")
src = open("164_v1_without_nifty200.py").read().replace('src = open(Path(__file__).resolve().parent / "148_clean_shape_0915.py").read()', "src = P148")
if which == "converged":   # drop the converged-lines skip (live daily 8 within 0.25% of the 1H EMA34)
    src = src.replace(" & (R.dd >= 0.25)", "")
if which == "branch":   # drop the branch A / B condition (opened 0-0.5% below the line, or above with ATR >= 3)
    src = src.replace("(((R.ov >= -0.5) & (R.ov < 0)) | ((R.ov >= 0) & (R.atrp >= 3)))", "(R.ov == R.ov)")
src = src.split("\nH = ")[0]; sys.argv = ["x"]
G = {"__file__": os.path.join(HERE, "164_v1_without_nifty200.py"), "P148": P148, "__name__": "x"}
with contextlib.redirect_stdout(io.StringIO()): exec(src, G)
V, B = G["V"], G["B"]
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(HERE))
from data.paths import DAILY_DIR, INTRADAY_60M_DIR
V = V[V.ex.str.startswith("E1")].copy()
for c in ("ticker", "entry", "high", "low", "gap", "atrp", "ema8", "s8", "s34"): V[c] = V.ix.map(B[c])
inside = {"gap": V.gap.between(-0.25, 0.5, inclusive="right"), "trend": V.s8 > V.s34,
          "branch": ((V.ov >= -0.5) & (V.ov < 0)) | ((V.ov >= 0) & (V.atrp >= 3)), "converged": V.dd >= 0.25}[which]
X = V[~inside]; K = V[inside]
net = lambda x: f"{x.rs1L.mean():+.0f}" if len(x) else "-"
print(f"FILTER '{which}': v1 trades with it {len(K)} (net {net(K)} @1L, stop {(K.o=='stop').mean()*100:.0f}%), REMOVED by it {len(X)} "
      f"(net {net(X)}, stop {(X.o=='stop').mean()*100:.0f}%); Nifty above 200d removed {net(X[X.n200 == True])} ({(X.n200 == True).sum()}), below {net(X[X.n200 == False])} ({(X.n200 == False).sum()})")
P = pd.concat([X[X.o == "stop"].sample(min(6, (X.o == "stop").sum()), random_state=31), X[X.o == "target"].sample(min(4, (X.o == "target").sum()), random_state=31)])
P = P.sample(frac=1, random_state=5)
rows = []
for _, r in P.iterrows():
    D = pd.Timestamp(str(r.date)[:10])
    d = pd.read_csv(DAILY_DIR / f"{r.ticker}.csv", index_col=0, parse_dates=True).sort_index(); d = d[~d.index.duplicated()].dropna(subset=["Close"])
    p = d[d.index < D]; y = p.iloc[-1]; e34d = p.Close.ewm(span=34, adjust=False).mean().iloc[-1]
    h = pd.read_csv(INTRADAY_60M_DIR / f"{r.ticker}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    h = h[~h.index.duplicated()].sort_index(); c = h[h.index == D + pd.Timedelta("10h15min")]
    after = h[(h.index.normalize() == D) & (h.index >= D + pd.Timedelta("11h15min"))]
    rows.append(dict(n=len(rows) + 1, date=D.strftime("%Y-%m-%d"), ticker=r.ticker, nifty="above 200d" if r.n200 else "below 200d", gap=f"{r.gap:+.2f}%",
                     candle_1015=f"{c.Open.iloc[0]:.2f}/{c.High.iloc[0]:.2f}/{c.Low.iloc[0]:.2f}/{c.Close.iloc[0]:.2f}" if len(c) else "?",
                     ema34_1h=round(r.ema34, 2), ema8_1h=round(r.ema8, 2), entry_1115=round(r.entry, 2), stop=round(r.high, 2),
                     d8_touch=f"{r.s8:.2f} ({(r.s8 / r.entry - 1) * 100:+.2f}%)", d34=round(e34d, 2), y_hlc=f"{y.High:.2f}/{y.Low:.2f}/{y.Close:.2f}",
                     outcome=r.o, low_after=round(after.Low.min(), 2) if len(after) else np.nan, high_after=round(after.High.max(), 2) if len(after) else np.nan))
A = pd.DataFrame(rows); A.to_csv(f"chart_review_v1_{which}_pack.csv", index=False)
pd.set_option("display.width", 260); print(A.to_string(index=False))
