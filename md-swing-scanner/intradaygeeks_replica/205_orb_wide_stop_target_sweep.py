"""WIDE stop (20% ATR) + TARGET SWEEP for the in-play ORB (user, 2026-10-12: 'sweep how far it generally goes; today ~2% was there').
Declared grid, all shown (Rule #19 -- read the shape, not the best cell): targets 0.5 / 0.75 / 1 / 1.25 / 1.5 / 2 / 2.5 / 3% of price, plus
hold to 15:15. Also HOW FAR trades go before the stop: share whose best favourable move (MFE, before any stop) reaches 0.5..3%. In-play
trades on the official open, paper entry (5-min mid entry-bar rule), stop 20% ATR from entry (10% shown for comparison), stop counted
before target in the same bar. Shorts from 09:20 and 09:30, longs from 09:30. Rs @1k risk net. Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from orb_common import read5_official
A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
S = A[(A.rv >= 1) & (A["rank"] <= 20) & A.traded].copy()
TG = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
rows = []
for t, g in S.groupby("ticker"):
    m = read5_official(t); m["hm"] = m.index.strftime("%H:%M")
    for _, r in g.iterrows():
        d = m[m.index.normalize() == pd.Timestamp(r.date)]; f = d.iloc[0]; s = int(r.side); lvl = f.Low if s < 0 else f.High
        k = d.index[d.hm == r.et][0]; b0 = d.loc[k]; e = r.e; after = d[(d.index > k) & (d.hm < "15:15")]; close_px = d[d.hm >= "15:15"].Open.iloc[0] if (d.hm >= "15:15").any() else d.Close.iloc[-1]
        rec = dict(date=r.date, side=s, et=r.et, atr=r.atr)
        for sm in (0.1, 0.2):
            sp = sm * r.atr; risk = e * sp / 100; stp = e - s * risk; pos = 1000 / (sp / 100); chg = 85 * pos / 1e5
            fo = (b0.Open <= lvl) if s < 0 else (b0.Open >= lvl); tc = (b0.High >= stp) if s < 0 else (b0.Low <= stp); cb = (b0.Close >= stp) if s < 0 else (b0.Close <= stp)
            # path: bar-by-bar favourable extreme and stop
            mfe, stop_bar = 0.0, None
            if (fo and tc) or cb: stop_bar = -1
            else:
                for j, (_, b) in enumerate(after.iterrows()):
                    if (b.High >= stp) if s < 0 else (b.Low <= stp): stop_bar = j; break
                    mfe = max(mfe, s * ((b.Low if s < 0 else b.High) - e) / e * 100)
            rec[f"mfe{int(sm*100)}"] = mfe
            for tp in [None] + TG:
                if stop_bar == -1: R = -1.0
                else:
                    R, done = None, False; tgt = None if tp is None else e * (1 + s * tp / 100)   # short: below entry, long: above (fix: first run had it on the wrong side)
                    for j, (_, b) in enumerate(after.iterrows()):
                        if stop_bar is not None and j == stop_bar: R = -1.0; done = True; break
                        if tgt is not None and ((b.Low <= tgt) if s < 0 else (b.High >= tgt)): R = tp / sp; done = True; break
                    if not done: R = s * (close_px - e) / risk
                key = f"{int(sm*100)}_{'hold' if tp is None else tp}"
                rec[f"R{key}"] = R; rec[f"k{key}"] = R * 1000 - chg
        rows.append(rec)
X = pd.DataFrame(rows).sort_values(["date", "et"])


def st(g, key):
    R = g[f"R{key}"]; k = g[f"k{key}"]; byd = g.groupby("date")[f"k{key}"].sum().sort_values(ascending=False)
    lose = (k < 0).astype(int); streak = int(lose.groupby((lose != lose.shift()).cumsum()).sum().max()); eq = k.cumsum()
    return f"{(R > 0).mean()*100:.0f}% | {k.mean():+.0f} | {k[~g.date.isin(byd.head(10).index)].mean():+.0f} | {k[g.date <= '2026-08-14'].mean():+.0f} / {k[g.date >= '2026-08-17'].mean():+.0f} | {streak} | {(eq - eq.cummax()).min():,.0f}"


for lab, msk in (("SHORTS from 09:20", lambda x: x.side < 0), ("SHORTS from 09:30", lambda x: (x.side < 0) & (x.et >= "09:30")), ("LONGS from 09:30", lambda x: (x.side > 0) & (x.et >= "09:30"))):
    G = X[msk(X)]
    print(f"\n## {lab} ({len(G)} trades) -- how far trades get before any stop (share reaching each move)")
    print("| stop | 0.5% | 1% | 1.5% | 2% | 2.5% | 3% | median best move |\n|---|---|---|---|---|---|---|---|")
    for sm in ("20", "10"):
        mf = G[f"mfe{sm}"]
        print(f"| {sm}% ATR | " + " | ".join(f"{(mf >= x).mean()*100:.0f}%" for x in (0.5, 1, 1.5, 2, 2.5, 3)) + f" | {mf.median():.2f}% |")
    for sm in ("20", "10"):
        print(f"\n### {lab}, stop {sm}% ATR (median stop {(G.atr * int(sm) / 100).median():.2f}%)\n| target | win % | Rs @1k net | w/o top-10 days | half 1 / half 2 | worst losing streak | max drawdown Rs |\n|---|---|---|---|---|---|---|")
        print(f"| hold to 15:15 | " + st(G, f"{sm}_hold") + " |")
        for tp in TG: print(f"| {tp}% | " + st(G, f"{sm}_{tp}") + " |")
