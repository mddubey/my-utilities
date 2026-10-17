"""USER'S STOP RULE: put the stop above the EARLIER wick where the rejection began, not the 11:15 candle's high (user, 2026-10-18: 'if the 09:15 or
10:15 candle already left a wick slightly above, the rejection started there; I am just looking at it late'). Spec fixed before running.
Trades: v1 simplified (241: hourly 11:15 entry, 1% target, out after 5 bars / at the day's last bar, ATR >= 3%, daily 8 not in the path), uptrend set
(the candidate) and all trends shown. Same exit engine as 148 (h1 bars, stop first on a tie).
Stops: BASE = the 10:15 candle high (v1 now). USER = if an earlier high today (the 09:15 hour or earlier in the 10:15 hour... = the day's high before
11:15) sits above the candle high, stop = that high + 0.05%; else the candle high. CAP c = 0.5% / 0.8% of the entry: beyond the cap either SKIP the
trade or FALL BACK to the candle stop. Report per Rs1 lakh AND per Rs1k risk (sized to each version's own stop), target / stall / stop, one a day."""
import sys, os, io, contextlib, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, os.path.dirname(HERE))
import pandas as pd, numpy as np
from data.paths import INTRADAY_60M_DIR
sys.argv = ["x", "0.005"]
with contextlib.redirect_stdout(io.StringIO()): G = runpy.run_path("243_overhead_level_vs_trend.py")
N = G["N"].copy()
cache = {}
def walk(r, stop):
    if r.ticker not in cache:
        h = pd.read_csv(INTRADAY_60M_DIR / f"{r.ticker}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
        cache[r.ticker] = h[~h.index.duplicated()].sort_index()
    h = cache[r.ticker]; H, L, C, T = h.High.values, h.Low.values, h.Close.values, h.index; day = T.normalize()
    k = pd.Timestamp(f"{str(r.date)[:10]} 10:15"); i = h.index.get_loc(k); tgt = r.entry * 0.99; px, o = None, "stall"
    for j in range(i + 1, len(C)):
        if day[j] != day[i]: px = C[j - 1]; break
        if H[j] >= stop: px, o = stop, "stop"; break
        if L[j] <= tgt: px, o = tgt, "target"; break
        if j - i >= 5 or j + 1 >= len(C) or day[j + 1] != day[i]: px = C[j]; break
    ret = (r.entry - px) / r.entry * 100; risk = (stop / r.entry - 1) * 100
    return dict(ret=ret, o=o, risk=risk, rs1L=ret * 1000 - 85, rs1k=(ret - 0.085) / risk * 1000)
rows = []
for _, r in N.iterrows():
    base = walk(r, r.high); earlier = r.dh > r.high * 1.0005; us = r.dh * 1.0005 if earlier else r.high
    user = walk(r, us) if earlier else base
    rows.append(dict(date=r.date, yr=str(r.date)[:4], up=r.up, n200=r.n200, atrp=r.atrp, earlier=earlier, user_risk=(us / r.entry - 1) * 100,
                     **{f"b_{k}": v for k, v in base.items()}, **{f"u_{k}": v for k, v in user.items()}))
X = pd.DataFrame(rows)
assert (X.b_rs1L.round(3) == N.rs1L.values.round(3)).mean() > 0.98, "base must reproduce v1's own results"
def summ(lab, x, p):
    if not len(x): return f"| {lab} | 0 |"
    w = x[f"{p}_o"]; o = x.assign(r=x[f"{p}_rs1k"]).sort_values(["date", "atrp"], ascending=[True, False]).drop_duplicates("date"); eq = o.r.cumsum()
    t10 = x.groupby("date")[f"{p}_rs1k"].sum().nlargest(10).index
    return (f"| {lab} | {len(x)} | {x[f'{p}_risk'].median():.2f}% | {(w=='target').mean()*100:.0f} / {(w=='stall').mean()*100:.0f} / {(w=='stop').mean()*100:.0f}% | "
            f"{x[f'{p}_rs1L'].mean():+.0f} | {x[f'{p}_rs1k'].mean():+.0f} | {x[~x.date.isin(t10)][f'{p}_rs1k'].mean():+.0f} | "
            + " / ".join(f"{x[x.yr == y][f'{p}_rs1k'].mean():+.0f}" for y in ("2024", "2025", "2026")) + f" | {len(o)}, {eq.iloc[-1]:+,.0f}, {(eq - eq.cummax()).min():,.0f} |")
for lab, S in (("UPTREND set (the candidate)", X[X.up]), ("ALL trends", X)):
    print(f"\n### {lab}  (Rs per Rs1k risk = each version sized to its own stop)\n| version | trades | median stop | target / stall / stop | Rs @1L | Rs @1k risk | @1k, top-10 days removed | @1k 2024 / 2025 / 2026 | one a day @1k: trades, total, max DD |\n|---|---|---|---|---|---|---|---|---|")
    print(summ("BASE: candle-high stop (v1 now)", S, "b"))
    for c in (0.5, 0.8):
        ok = ~S.earlier | (S.user_risk <= c)
        print(summ(f"USER, cap {c}%, SKIP beyond the cap", S[ok], "u"))
        F = S.copy(); fb = F.earlier & (F.user_risk > c)
        for k in ("ret", "o", "risk", "rs1L", "rs1k"): F.loc[fb, f"u_{k}"] = F.loc[fb, f"b_{k}"]
        print(summ(f"USER, cap {c}%, FALL BACK to the candle stop beyond the cap", F, "u"))
    E = S[S.earlier]
    print(f"| (trades with an earlier wick above: {len(E)} of {len(S)}; user stop <= 0.5%: {(E.user_risk <= 0.5).sum()}, 0.5-0.8%: {((E.user_risk > 0.5) & (E.user_risk <= 0.8)).sum()}, > 0.8%: {(E.user_risk > 0.8).sum()}) |")
    for c in (0.5, 0.8):
        e = E[E.user_risk <= c]
        print(f"| the trades your rule CHANGES at cap {c}% ({len(e)}): candle stop {e.b_rs1k.mean():+.0f} @1k ({(e.b_o=='stop').mean()*100:.0f}% stopped) -> earlier-wick stop {e.u_rs1k.mean():+.0f} @1k ({(e.u_o=='stop').mean()*100:.0f}% stopped) |")
