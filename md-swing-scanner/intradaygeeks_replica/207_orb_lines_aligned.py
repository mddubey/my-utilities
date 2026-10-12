"""Are 'all the lines on the trade's side' genuine? (user, 2026-10-12, after INOXGREEN (all above, short) and NAZARA (all below, long)).
Declared: in-play plain-break trades (official open, 5-min mid rule, 10% ATR stop); at ENTRY, with values known then -- VWAP as of the
previous 5-min bar, 1H EMA8 / EMA34 as of the last COMPLETED hour, live daily 8-EMA (2/9 x entry + 7/9 x yesterday's EMA8).
ALIGNED-3 = VWAP, 1H EMA8 and 1H EMA34 all above the entry (short) / below (long); ALIGNED-4 = also the daily 8-EMA.
Kept vs removed vs baseline, exits hold / 1.5% / 2% target; shorts from 09:20, longs from 09:30 (the corrected preferred clocks) and both
from 09:20. Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from orb_common import read5_official
from backtest import load
from data.paths import DAILY_DIR
A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
S = A[(A.rv >= 1) & (A["rank"] <= 20) & A.traded].copy(); rows = []


def walk(d, k, e, s, stp, tp):
    tgt = None if tp is None else e * (1 + s * tp / 100)
    for _, b in d[d.index > k].iterrows():
        if b.hm >= "15:15": return b.Open
        if (b.High >= stp) if s < 0 else (b.Low <= stp): return stp
        if tgt is not None and ((b.Low <= tgt) if s < 0 else (b.High >= tgt)): return tgt
    return d.Close.iloc[-1]


for t, g in S.groupby("ticker"):
    m = read5_official(t); m["hm"] = m.index.strftime("%H:%M"); dv = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).Volume
    p1 = HERE / "h1_cache" / f"{t}.csv"
    if not p1.exists(): continue
    h = pd.read_csv(p1, index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    dd0 = load(t); e8d = dd0.Close.ewm(span=8, adjust=False).mean()
    for _, r in g.iterrows():
        D = pd.Timestamp(r.date); d = m[m.index.normalize() == D].copy()
        if len(d) < 70: continue
        s = int(r.side); f = d.iloc[0]; lvl = f.Low if s < 0 else f.High
        v = d.Volume.values.astype(float); v[0] = dv.get(D, np.nan) - v[1:].sum(); d["vw"] = np.cumsum(((d.High + d.Low + d.Close) / 3).values * v) / np.cumsum(v)
        k = d.index[d.hm == r.et][0]; e = r.e
        prev = d[d.index < k]; vw = prev.vw.iloc[-1] if len(prev) else d.vw.iloc[0]
        hk = D + pd.Timedelta("9h15min") + ((d.index - D - pd.Timedelta("9h15min")) // pd.Timedelta("60min")) * pd.Timedelta("60min")
        tod = d.Close.groupby(hk).last(); tod = tod[tod.index + pd.Timedelta("60min") <= k]          # completed hours only
        allc = pd.concat([h.Close[h.index < D], tod])
        if len(allc) < 40: continue
        h8 = allc.ewm(span=8, adjust=False).mean().iloc[-1]; h34 = allc.ewm(span=34, adjust=False).mean().iloc[-1]
        py = e8d[e8d.index < D]
        if not len(py): continue
        d8 = 2 / 9 * e + 7 / 9 * py.iloc[-1]
        side_ok = (lambda x: x > e) if s < 0 else (lambda x: x < e)
        b0 = d.loc[k]; sp = 0.1 * r.atr; stp = e * (1 - s * sp / 100); pos = 1000 / (sp / 100)
        fo = (b0.Open <= lvl) if s < 0 else (b0.Open >= lvl); tc = (b0.High >= stp) if s < 0 else (b0.Low <= stp); cb = (b0.Close >= stp) if s < 0 else (b0.Close <= stp)
        rec = dict(date=r.date, side=s, et=r.et, al3=side_ok(vw) and side_ok(h8) and side_ok(h34), n3=int(side_ok(vw)) + int(side_ok(h8)) + int(side_ok(h34)))
        rec["al4"] = rec["al3"] and side_ok(d8)
        for tp in (None, 1.5, 2.0):
            px = stp if ((fo and tc) or cb) else walk(d, k, e, s, stp, tp); rec[f"k{tp}"] = s * (px - e) / e * 100 / sp * 1000 - 85 * pos / 1e5
        rows.append(rec)
X = pd.DataFrame(rows)


def row(lab, g, c):
    if len(g) == 0: return f"| {lab} | 0 |"
    k = g[c]; byd = g.groupby("date")[c].sum().sort_values(ascending=False)
    return f"| {lab} | {len(g)} | {(k > 0).mean()*100:.0f}% | {k.mean():+.0f} | {k[~g.date.isin(byd.head(10).index)].mean():+.0f} | {k[g.date <= '2026-08-14'].mean():+.0f} / {k[g.date >= '2026-08-17'].mean():+.0f} |"


for lab, msk in (("SHORTS from 09:20", lambda x: x.side < 0), ("LONGS from 09:30", lambda x: (x.side > 0) & (x.et >= "09:30")), ("LONGS from 09:20", lambda x: x.side > 0)):
    G = X[msk(X)]
    print(f"\n## {lab}: {len(G)} trades | aligned-3 {G.al3.mean()*100:.0f}% | aligned-4 {G.al4.mean()*100:.0f}%")
    for c, cl in (("kNone", "hold to 15:15"), ("k1.5", "1.5% target"), ("k2.0", "2% target")):
        print(f"\n### exit: {cl}\n| group | trades | win % | Rs @1k net | w/o top-10 days | half 1 / half 2 |\n|---|---|---|---|---|---|")
        print(row("BASELINE", G, c)); print(row("ALIGNED-3 (VWAP + 1H EMA8 + 1H EMA34 on the trade's side)", G[G.al3], c)); print(row("not aligned-3", G[~G.al3], c))
        print(row("ALIGNED-4 (+ daily 8-EMA)", G[G.al4], c))
        for n in (0, 1, 2): print(row(f"  {n} of the 3 lines on the trade's side", G[G.n3 == n], c))
