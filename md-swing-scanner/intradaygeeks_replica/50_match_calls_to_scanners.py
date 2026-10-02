"""Which of the channel's OWN chartink scanners (CHARTINK_QUERIES.md) would have listed each call's stock at the call
time, in the call's direction? Spec fixed 2026-10-02. Data known at the call time only: 1H = last COMPLETED hourly bar
(Yahoo h1_cache); daily = completed days + today's candle so far (from completed 1H bars) and live daily EMAs
(alpha-blend of the call-time price with yesterday's EMA). 15m/30m scanners not testable (no history before Jun 2026).
Buy scanners checked for longs, sell scanners for shorts. Outcome = NSE-graded n_pct_t1 / n_pct_last (08)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from signals import rsi
HERE = Path(__file__).resolve().parent
T = pd.read_csv(HERE / "telegram_clean_first_attempts.csv", parse_dates=["ts"])


def live_ema(prev_ema, p, span): a = 2 / (span + 1); return a * p + (1 - a) * prev_ema


rows = []
for r in T.itertuples():
    t, ts = r.ticker, r.ts.tz_localize(None) if r.ts.tzinfo else r.ts
    s = 1 if r.direction == "long" else -1
    try: d = load(t)
    except Exception: rows.append(dict(i=r.Index)); continue
    hp = HERE / "h1_cache" / f"{t}.csv"
    if not hp.exists(): rows.append(dict(i=r.Index)); continue
    h = pd.read_csv(hp, index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    h = h[(h.Volume > 0) | (h.High != h.Low)]
    hd = h[h.index + pd.Timedelta("60min") <= ts]
    day = ts.normalize(); dd = d[d.index < day]
    if len(hd) < 250 or len(dd) < 210: rows.append(dict(i=r.Index)); continue
    e = {k: hd.Close.ewm(span=k, adjust=False).mean().iloc[-1] for k in (8, 34, 150, 200)}
    b = hd.iloc[-1]; c = b.Close                                       # last completed 1H bar
    today = hd[hd.index.normalize() == day]
    P = r.entry                                                       # call price as the live price
    dO = today.Open.iloc[0] if len(today) else P; dH = max(today.High.max() if len(today) else P, P); dL = min(today.Low.min() if len(today) else P, P)
    de = {k: live_ema(dd.Close.ewm(span=k, adjust=False).mean().iloc[-1], P, k) for k in (8, 150, 200)}
    rs = rsi(dd.Close, 14); r1 = rs.iloc[-1]; rlive = rsi(pd.concat([dd.Close, pd.Series([P], index=[day])]), 14).iloc[-1]
    y, y2 = dd.iloc[-1], dd.iloc[-2]
    o, hi, lo, cl = b.Open, b.High, b.Low, b.Close
    m = {}
    if s == 1:
        m["SWING 1H (34 < price < 8)"] = c > e[34] and c < e[8]
        m["1H 150/200 band"] = c < e[150] and c > e[200]
        m["daily 150/200 band"] = P < de[150] and P > de[200]
        m["1H bullish pinbar"] = cl > o and (hi - cl) < (cl - o) and (o - lo) >= (cl - o)
        m["daily bullish pinbar (so far)"] = P > dO and (dH - P) < (P - dO) and (dO - dL) >= (P - dO)
        m["reversal (RSI<20 yday, break yday high)"] = r1 < 20 and P > y.High and y.Close <= y2.High
        m["oversold 1D (RSI<30)"] = rlive < 30
    else:
        m["SWING 1H (8 < price < 34)"] = c < e[34] and c > e[8]
        m["1H 150/200 band"] = c < e[200] and c > e[150]
        m["daily 150/200 band"] = P < de[200] and P > de[150]
        m["1H bearish pinbar"] = o > cl and (hi - o) > (o - cl) * 2 and (cl - lo) < (o - cl)
        rng = dH - dL
        m["daily bearish pinbar (so far)"] = rng > 0 and (dO - dL) <= rng * 0.4 and (P - dL) <= rng * 0.4 and P > dL and P < de[8]
        m["reversal (RSI>80 yday, break yday low)"] = r1 > 80 and P < y.Low and y.Close >= y2.Low
        m["overbought 1D (RSI>70)"] = rlive > 70
    rows.append(dict(i=r.Index, **{k: bool(v) for k, v in m.items()}))
M = pd.DataFrame(rows).set_index("i"); X = T.join(M)
X["n_matched"] = X[[c for c in M.columns]].fillna(False).sum(axis=1); X.to_csv(HERE / "calls_vs_scanners.csv", index=False)
print(f"calls {len(X)} | evaluable {M.dropna(how='all').shape[0]}\n")
print("| scanner (his own) | side | calls matched | share of that side's calls | win% T1 | mean % (T1) | mean % (last target) |\n|---|---|---|---|---|---|---|")
for sd in ("long", "short"):
    S = X[X.direction == sd]; cols = [c for c in M.columns if S[c].notna().any()]
    for c in cols:
        g = S[S[c] == True]
        if len(g): print(f"| {c} | {sd} | {len(g)} | {len(g)/len(S)*100:.0f}% | {(g.n_pct_t1>0).mean()*100:.0f} | {g.n_pct_t1.mean():+.3f} | {g.n_pct_last.mean():+.3f} |")
    g = S[S.n_matched == 0]; print(f"| (no scanner matched) | {sd} | {len(g)} | {len(g)/len(S)*100:.0f}% | {(g.n_pct_t1>0).mean()*100:.0f} | {g.n_pct_t1.mean():+.3f} | {g.n_pct_last.mean():+.3f} |")
