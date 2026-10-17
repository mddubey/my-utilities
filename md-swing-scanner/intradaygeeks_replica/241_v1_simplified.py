"""v1 SIMPLIFIED = the accepted filter changes applied TOGETHER (user, 2026-10-17: 'it should be after applying all those filters'). On v1's hourly
trades (10:15 candle red at the 1H EMA34, 11:15 close entry, candle-high stop <= 0.5%, E1 1% target / 15:15, liquid, >= Rs100, doji skip):
  gap zone DROPPED | branch A / B + ATR >= 2% REPLACED by ATR >= 3% | converged skip REPLACED by 'daily 8 touch not between entry and target' |
  uptrend (daily 8 > 34) checked again on top of these. Both Nifty regimes shown; v1 now as the baseline."""
import sys, os, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
P148 = open("148_clean_shape_0915.py").read().replace(" & (B.n200 == True) & (B.s8 > B.s34) & (B.gap > -0.25) & (B.gap <= 0.5)", "")   # Nifty gate / trend / gap removed here; trend + regime handled below
src = open("164_v1_without_nifty200.py").read().replace('src = open(Path(__file__).resolve().parent / "148_clean_shape_0915.py").read()', "src = P148")
assert "(B.gap > -0.25)" not in P148 and "(B.n200 == True)" not in P148, "filter removal failed"
src = src.replace("(((R.ov >= -0.5) & (R.ov < 0)) | ((R.ov >= 0) & (R.atrp >= 3)))", "(R.ov == R.ov)").replace(" & (R.dd >= 0.25)", "").split("\nH = ")[0]
PACK = "--pack-downtrend-stops" in sys.argv; sys.argv = ["x"]; G = {"__file__": os.path.join(HERE, "164_v1_without_nifty200.py"), "P148": P148, "__name__": "x"}
with contextlib.redirect_stdout(io.StringIO()): exec(src, G)
V, B = G["V"], G["B"]
import pandas as pd
V = V[V.ex.str.startswith("E1")].copy()
for c in ("ticker", "entry", "gap", "atrp", "s8", "s34", "high"): V[c] = V.ix.map(B[c])
V["yr"] = V.date.astype(str).str[:4]; V["d8"] = (V.s8 / V.entry - 1) * 100; V["path"] = (V.d8 < 0) & (V.d8 > -1); V["up"] = V.s8 > V.s34
NOW = V[V.up & V.gap.between(-0.25, 0.5, inclusive="right") & (V.atrp >= 2) & (((V.ov >= -0.5) & (V.ov < 0)) | ((V.ov >= 0) & (V.atrp >= 3))) & (V.dd >= 0.25)]
NEW = V[(V.atrp >= 3) & ~V.path]
d = pd.to_datetime(V.date.astype(str).str[:10]); months = (d.max() - d.min()).days / 30.4
def row(lab, x):
    t10 = x.groupby("date").rs1L.sum().nlargest(10).index
    o = x.sort_values(["date", "atrp"], ascending=[True, False]).drop_duplicates("date"); eq = o.rs1L.cumsum()
    return (f"| {lab} | {len(x)} ({len(x)/months:.1f}/mo) | {(x.o=='target').mean()*100:.0f} / {(x.o=='stall').mean()*100:.0f} / {(x.o=='stop').mean()*100:.0f}% | {x.rs1L.mean():+.0f} | "
            f"{x[~x.date.isin(t10)].rs1L.mean():+.0f} | {x[x.n200==True].rs1L.mean():+.0f} ({(x.n200==True).sum()}) / {x[x.n200==False].rs1L.mean():+.0f} ({(x.n200==False).sum()}) | "
            + " / ".join(f"{x[x.yr==y].rs1L.mean():+.0f}" for y in ("2024", "2025", "2026")) + f" | {len(o)} days, {o.rs1L.mean():+.0f}, total {eq.iloc[-1]:+,.0f}, DD {(eq-eq.cummax()).min():,.0f} |")
print("| version | setups | target / stall / stop | net Rs @1L | top-10 days removed | above / below 200d | 2024 / 2025 / 2026 | one a day (highest ATR): days, per trade, total, max DD |")
print("|---|---|---|---|---|---|---|---|")
print(row("v1 NOW", NOW))
print(row("v1 SIMPLIFIED: uptrend + ATR >= 3% + daily 8 not in path (no gap, no branch, no converged skip)", NEW[NEW.up]))
print(row("  same WITHOUT the uptrend filter", NEW))
print(row("  removed by uptrend on top of the simplified set (downtrend stocks)", NEW[~NEW.up]))

if PACK:
    # chart pack (2026-10-17, user): downtrend stocks the uptrend filter removes on top of the simplified set, STOPPED trades, 8 random (fixed seed)
    import numpy as np
    sys.path.insert(0, os.path.dirname(HERE))
    from data.paths import DAILY_DIR, INTRADAY_60M_DIR
    X = NEW[~NEW.up & (NEW.o == "stop")].sample(8, random_state=41).sort_values("date")
    rows = []
    for _, r in X.iterrows():
        D = pd.Timestamp(str(r.date)[:10])
        dd = pd.read_csv(DAILY_DIR / f"{r.ticker}.csv", index_col=0, parse_dates=True).sort_index(); dd = dd[~dd.index.duplicated()].dropna(subset=["Close"])
        p = dd[dd.index < D]; y = p.iloc[-1]; e34 = p.Close.ewm(span=34, adjust=False).mean().iloc[-1]
        h = pd.read_csv(INTRADAY_60M_DIR / f"{r.ticker}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
        h = h[~h.index.duplicated()].sort_index(); c = h[h.index == D + pd.Timedelta("10h15min")]; af = h[(h.index.normalize() == D) & (h.index >= D + pd.Timedelta("11h15min"))]
        hit = af[af.High >= r.high]
        rows.append(dict(n=len(rows) + 1, date=D.strftime("%Y-%m-%d"), ticker=r.ticker, nifty="above" if r.n200 else "below", gap=f"{r.gap:+.2f}%",
                         candle_1015=f"{c.Open.iloc[0]:.2f}/{c.High.iloc[0]:.2f}/{c.Low.iloc[0]:.2f}/{c.Close.iloc[0]:.2f}" if len(c) else "?",
                         ema34_1h=round(r.ema34, 2), entry=round(r.entry, 2), stop=round(r.high, 2), d8=f"{r.s8:.2f} ({r.d8:+.2f}%)",
                         d34=f"{e34:.2f} ({(e34 / r.entry - 1) * 100:+.2f}%)", y_hlc=f"{y.High:.2f}/{y.Low:.2f}/{y.Close:.2f}",
                         stop_hour=hit.index[0].strftime("%H:%M") if len(hit) else "?", day_high_after=round(af.High.max(), 2), day_close=round(af.Close.iloc[-1], 2)))
    A = pd.DataFrame(rows); A.to_csv("chart_review_v1_downtrend_stops.csv", index=False); pd.set_option("display.width", 260); print("\n" + A.to_string(index=False))
