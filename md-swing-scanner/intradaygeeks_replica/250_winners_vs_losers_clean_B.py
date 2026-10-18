"""Same 8 features as 249, on GROUP B: the big CLEAN rejections the scan never takes (10:15 red candle touching the 1H 34, lower wick < 10%, upper wick
>= 0.3% of price, stop = candle high > 0.5%; ATR >= 3%, >= Rs100, daily 8 not in the path; 11:15 entry, 1% target, out after 5 bars / day end) (user,
2026-10-18: 'run it on B -- how do I land in the 46% and not the 26%'). Net @1L and @1k risk (wide stops -> per-risk matters). CHAT ONLY."""
import sys, os, io, contextlib, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, os.path.dirname(HERE))
import numpy as np, pandas as pd
from data.paths import INTRADAY_60M_DIR, INDEX_INTRADAY_DIR
sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()): G = runpy.run_path("244_stop_above_earlier_wick.py")
B = G["G"]["B"]; walk = G["walk"]; cache = G["cache"]
b = B[(B.hour == "10:15") & B.red & (B.price_ok == True) & (B.atrp >= 3) & (B.high >= B.ema34) & (B.entry < B.ema34)].copy()
b = b[~((b.s8 < b.entry) & (b.s8 > b.entry * 0.99))]
rg = b.high - b["low"]; lw = (np.minimum(b.open, b.entry) - b["low"]) / rg; uwp = (b.high - np.maximum(b.open, b.entry)) / b.entry * 100
b = b[(lw < 0.10) & (uwp >= 0.3) & ((b.high / b.entry - 1) * 100 > 0.5)].copy()
NF = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_1h.csv", index_col=0); NF.index = pd.to_datetime(NF.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None); NF = NF[~NF.index.duplicated()].sort_index()
rows = []
for ix, r in b.iterrows():
    t = r.ticker; D = pd.Timestamp(str(r.date)[:10])
    if t not in cache:
        h = pd.read_csv(INTRADAY_60M_DIR / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None); cache[t] = h[~h.index.duplicated()].sort_index()
    h = cache[t]; a = h[h.index == D + pd.Timedelta("9h15min")]; c = h[h.index == D + pd.Timedelta("10h15min")]
    pre = h[(h.index.normalize() == D) & (h.index < D + pd.Timedelta("11h15min"))]; prev = h[(h.index.strftime("%H:%M") == "10:15") & (h.index < D)].tail(10)
    nd = NF[NF.index.normalize() == D]; n1 = nd[nd.index == D + pd.Timedelta("10h15min")]
    w = walk(r, r.high); dh = pre.High.max() if len(pre) else np.nan
    rows.append(dict(date=str(r.date)[:10], yr=str(r.date)[:4], o=w["o"], rs1L=w["rs1L"], rs1k=w["rs1k"], stop=(r.high / r.entry - 1) * 100,
        F1=bool(len(a) and a.Close.iloc[0] <= r.ema34), F2=(r.high / r.ema34 - 1) * 100, F3=(1 - r.entry / r.ema34) * 100,
        F4=(n1.Close.iloc[0] / n1.Open.iloc[0] - 1) * 100 if len(n1) else np.nan,
        F5=((r.entry / r.dayopen - 1) - (n1.Close.iloc[0] / nd.Open.iloc[0] - 1)) * 100 if len(n1) and len(nd) else np.nan,
        F6=bool(dh == dh and dh > r.high * 1.005 and dh <= r.high * 1.015), F7=bool((r.ema8 > r.high) and (r.ema8 <= r.high * 1.005)),
        F8=(c.Volume.iloc[0] / prev.Volume.median()) if len(c) and len(prev) >= 5 and prev.Volume.median() > 0 else np.nan, up=bool(r.s8 > r.s34), n200=bool(r.n200)))
X = pd.DataFrame(rows); rng = np.random.default_rng(12)
def side(x): return f"{len(x)} | {x.stop.median():.2f}% | {(x.o=='target').mean()*100:.0f} / {(x.o=='stall').mean()*100:.0f} / {(x.o=='stop').mean()*100:.0f}% | {x.rs1L.mean():+.0f} | {x.rs1k.mean():+.0f} | " + " / ".join(f"{x[x.yr == y].rs1k.mean():+.0f}" for y in ("2024", "2025", "2026"))
def shuffle(m, col="rs1k"):
    ok = ~pd.isna(m).values if m.dtype != bool else np.ones(len(m), bool); r = X[col].values[ok]; mm = m.values[ok].astype(bool); obs = r[mm].mean() - r[~mm].mean()
    sims = np.array([(lambda s: r[s].mean() - r[~s].mean())(rng.permutation(mm)) for _ in range(5000)]); return obs, (np.abs(sims) >= abs(obs)).mean()
print(f"GROUP B: {len(X)} big clean rejections. Baseline: {side(X)}\n")
print("| feature (known at 11:15) | side | n | median stop | target / stall / stop | net @1L | net @1k | @1k 2024 / 2025 / 2026 | difference @1k, shuffle p |\n|---|---|---|---|---|---|---|---|---|")
SPEC = [("F1 09:15 closed at/under the line", X.F1, "yes", "no"), ("F2 A: pierce above the line", X.F2 > X.F2.median(), f"> {X.F2.median():.2f}%", "smaller"),
        ("F3 B: entry below the line (late)", X.F3 > X.F3.median(), f"> {X.F3.median():.2f}%", "nearer"), ("F4 Nifty's 10:15 hour", X.F4 > 0, "up", "down"),
        ("F5 stock vs Nifty since the open", X.F5 < 0, "weaker than Nifty", "stronger"), ("F6 earlier high 0.5-1.5% above the candle", X.F6, "yes", "no"),
        ("F7 1H EMA8 just above the candle high", X.F7, "yes", "no"), ("F8 10:15 hour volume", X.F8 > X.F8.median(), f"above median ({X.F8.median():.2f}x)", "below"),
        ("(info) stock daily uptrend", X.up, "up", "down"), ("(info) Nifty above 200d", X.n200, "above", "below")]
for lab, m, a, z in SPEC:
    obs, p = shuffle(m); print(f"| {lab} | {a} | {side(X[m])} | {obs:+.0f}, p {p:.3f} |"); print(f"| | {z} | {side(X[~m])} | |")
X.to_csv("winners_vs_losers_clean_B.csv", index=False)
