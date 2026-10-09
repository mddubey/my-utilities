"""STALL ANATOMY under the frozen frame (user, 2026-10-09: 'stalls are the biggest bucket -- what causes them?'). Spec fixed before
running. Population: frozen frame (8j) + current layers (red, Nifty > 200d, stock daily 8>34, gap zone), both candles; also the
plan-B highest-ATR pick (one a day, 10:15 candle). Per trade, walked on h1_cache: MFE = best price reached before the exit, as a
FRACTION of the target distance; hour of the best price; exit price. Stall types (declared):
  went nowhere  : MFE < 25% of the way to target
  out of steam  : MFE >= 50%, and gave back >= half of it by the exit
  out of time   : exit within 25% (of the target distance) of the best price
  other         : the rest
Also: same trades HELD to the day's last candle (stop/target still live) instead of 5 candles; obstacles between entry and target:
previous day's low (PDL), the day's low so far (DL, up to the signal candle), daily PP and S1 (classic, from yesterday).
Rs at fixed Rs1 lakh, net of Rs85. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
exec(open(Path(__file__).resolve().parent / "130_rebaseline_frozen_frame.py").read().split('print(f"base (frozen-frame')[0])
Z = B[B.red & (B.n200 == True) & (B.s8 > B.s34) & (B.gap > -0.25) & (B.gap <= 0.5)].copy()
rows = []
for t, g in Z.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    H, L, C, T = h.High.values, h.Low.values, h.Close.values, h.index; day = T.normalize()
    d = load(t); pv = pd.DataFrame({"pdl": d.Low, "pdh": d.High, "pdc": d.Close}).shift(1)
    for ix, r in g.iterrows():
        k = pd.Timestamp(f"{r.date} {r.hour}")
        if k not in h.index or pd.Timestamp(r.date) not in pv.index: continue
        i = h.index.get_loc(k); e = r.entry; dist = e * r.tp / 100; tgt = e - dist
        res = {}
        for mode in ("5h", "eod"):
            best, bh, px, o = e, 0, None, "stall"
            for j in range(i + 1, len(C)):
                if day[j] != day[i]: px = C[j - 1]; break
                if H[j] >= r.high: px, o = r.high, "stop"; break
                if L[j] < best: best, bh = L[j], j - i
                if L[j] <= tgt: px, o = tgt, "target"; break
                lastbar = j + 1 >= len(C) or day[j + 1] != day[i]
                if (mode == "5h" and j - i >= 5) or lastbar: px = C[j]; break
            res[mode] = (px, o, best, bh)
        px, o, best, bh = res["5h"]; px2, o2, _, _ = res["eod"]
        if px is None or px2 is None: continue
        mfe = (e - best) / dist; giveback = (px - best) / dist
        dl = L[(day == day[i]) & (np.arange(len(L)) <= i)].min()
        p = pv.loc[pd.Timestamp(r.date)]; PP = (p.pdh + p.pdl + p.pdc) / 3; S1 = 2 * PP - p.pdh
        inpath = lambda lv: bool(tgt < lv < e)
        rows.append(dict(ix=ix, hour=r.hour, date=r.date, o=o, rs=(e - px) / e * 1e5 - 85, o2=o2, rs2=(e - px2) / e * 1e5 - 85,
                         mfe=mfe, give=giveback, bh=bh, atrp=r.atrp, PDL=inpath(p.pdl), DL=inpath(dl), PP=inpath(PP), S1=inpath(S1)))
A = pd.DataFrame(rows).set_index("ix")
A["stype"] = np.where(A.o != "stall", A.o, np.where(A.mfe < 0.25, "stall: went nowhere", np.where((A.mfe >= 0.5) & (A.give >= A.mfe / 2), "stall: out of steam",
             np.where(A.give <= 0.25, "stall: out of time", "stall: other"))))


def table(X, title):
    print(f"\n## {title}: {len(X)} trades\n| outcome | share | avg Rs @1L | avg best (frac of target) | median hour of best | if HELD to day end: target / stall / stop % | held avg Rs |\n|---|---|---|---|---|---|---|")
    for s, g in X.groupby("stype"):
        o2 = g.o2
        print(f"| {s} | {len(g)/len(X)*100:.0f}% | {g.rs.mean():+,.0f} | {g.mfe.mean():.2f} | {g.bh.median():.0f} | {(o2=='target').mean()*100:.0f} / {(o2=='stall').mean()*100:.0f} / {(o2=='stop').mean()*100:.0f} | {g.rs2.mean():+,.0f} |")
    print(f"| ALL | 100% | {X.rs.mean():+,.0f} | | | {(X.o2=='target').mean()*100:.0f} / {(X.o2=='stall').mean()*100:.0f} / {(X.o2=='stop').mean()*100:.0f} | {X.rs2.mean():+,.0f} |")
    print(f"\n### obstacles between entry and target ({title})\n| level in path | share of trades | target % in / out | stall % in / out | stop % in / out | out-of-steam share of stalls in / out | Rs in / out |\n|---|---|---|---|---|---|---|")
    for lv in ("PDL", "DL", "PP", "S1"):
        a, b = X[X[lv]], X[~X[lv]]
        f = lambda g, o: (g.o == o).mean() * 100
        st = lambda g: (g.stype == "stall: out of steam").sum() / max((g.o == "stall").sum(), 1) * 100
        print(f"| {lv} | {len(a)/len(X)*100:.0f}% | {f(a,'target'):.0f} / {f(b,'target'):.0f} | {f(a,'stall'):.0f} / {f(b,'stall'):.0f} | {f(a,'stop'):.0f} / {f(b,'stop'):.0f} | {st(a):.0f} / {st(b):.0f} | {a.rs.mean():+.0f} / {b.rs.mean():+.0f} |")


table(A, "full stack, both candles")
Bp = A[A.hour == "10:15"].join(Z[["atrp"]], rsuffix="_z")
pick = Bp.sort_values("atrp", ascending=False).groupby("date").head(1)
table(pick, "plan B, highest-ATR pick (one a day)")
