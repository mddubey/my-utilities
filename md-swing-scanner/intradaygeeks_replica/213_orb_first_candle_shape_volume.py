"""ORB: did the SELLERS WIN the first candle, and how much of the trading was done in it? (user, 2026-10-13: 'the first candle we found
yesterday, a clear seller won like INOXGREEN vs SHADOWFAX'; 'also how much of the deal was done in the first candle itself').
Spec fixed before running:
  Population: 212's (in-play relvol >= 1 top 20, official open, shorts = red 09:15, longs = green, first break from 09:20), 2026-06-24..10-09.
  Shape of the 09:15 candle (short side; longs mirrored):
    close position pos = (C - L) / (H - L): SELLERS WON <= 1/3 (INOXGREEN 0.23) | MIDDLE 1/3-2/3 (SHADOWFAX 0.52) | TOP > 2/3
    FLUSH = lower wick (C - L) >= body (O - C) (SHADOWFAX 11.65 vs 10.65; INOXGREEN 1.25 vs 4.28 = no)
    overlap check with 200's decisiveness: each split also within body >= 0.5x ATR and < 0.5x ATR.
  'Deal done in the first candle' (known at 09:20): the 09:15 bar's volume (day volume - other bars) as % of the stock's average
    FULL-DAY volume over the prior 20 days: < 5% | 5-10% | 10-20% | >= 20%.
    (201 already did the other reading -- the first candle's RANGE vs ATR: big ones better for shorts, tiny ones worse.)
  Trade: entry at the level (or the gap-through open), stop 10% ATR, fixed 1.5% / 2% target else out at 15:15; also hold to 15:15
  (stop only) for reference. 206 / 212's entry-bar rule. Rs @1k risk, net Rs85 per Rs1 lakh.
  Report: BASELINE row first, then each group: n, win %, Rs, w/o top-10 days, half 1 / half 2.
  Pass for 'sellers won' as a filter = better than baseline in both targets, w/o the top-10 days and in both halves, and still better
  inside both body-size groups."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from orb_common import read5_official
from data.paths import DAILY_DIR
A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
P = A[(A.rv >= 1) & (A["rank"] <= 20)].copy()
EXITS = [1.5, 2.0, None]


def run(d, kb, b0, ep, s, stp, tgt_pct, gapfill):
    if (gapfill and ((b0.High >= stp) if s < 0 else (b0.Low <= stp))) or ((b0.Close >= stp) if s < 0 else (b0.Close <= stp)): return stp
    tgt = None if tgt_pct is None else ep * (1 + s * tgt_pct / 100)
    for b in d[d.index > kb].itertuples():
        if b.hm >= "15:15": return b.Open
        if (b.High >= stp) if s < 0 else (b.Low <= stp): return stp
        if tgt is not None and ((b.Low <= tgt) if s < 0 else (b.High >= tgt)): return tgt
    return d.Close.iloc[-1]


rows = []
for t, g in P.groupby("ticker"):
    m = read5_official(t); m["hm"] = m.index.strftime("%H:%M")
    D = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).sort_index(); avgv = D.Volume.rolling(20).mean().shift(1)
    for _, r in g.iterrows():
        dd = pd.Timestamp(r.date); d = m[m.index.normalize() == dd].copy()
        if len(d) < 70: continue
        s = int(r.side); f = d.iloc[0]; o, h, l, c = f.Open, f.High, f.Low, f.Close; rng = h - l
        if rng <= 0: continue
        lvl = l if s < 0 else h
        a = d[(d.hm >= "09:20") & (d.hm < "15:15")]
        brk = a[(a.Low < lvl) if s < 0 else (a.High > lvl)]
        if not len(brk): continue
        kb = brk.index[0]; b0 = d.loc[kb]; ep = min(lvl, b0.Open) if s < 0 else max(lvl, b0.Open)
        gapfill = (b0.Open <= lvl) if s < 0 else (b0.Open >= lvl); stp = ep * (1 - s * 0.1 * r.atr / 100); risk = 0.1 * r.atr
        pos = (c - l) / rng if s < 0 else (h - c) / rng                       # 0 = closed at the trade-side extreme
        body = abs(c - o); wick = (c - l) if s < 0 else (h - c)
        v915 = D.Volume.get(dd, np.nan) - d.Volume.iloc[1:].sum()
        rec = dict(t=t, date=r.date, side=s, pos=pos, flush=wick >= body, body_atr=body / o * 100 / r.atr,
                   vshare=v915 / avgv.get(dd, np.nan) * 100)
        for x in EXITS:
            px = run(d, kb, b0, ep, s, stp, x, gapfill); ret = s * (px - ep) / ep * 100
            rec[f"x{x}"] = ret / risk * 1000 - 85 * (1000 / (risk / 100)) / 1e5
        rows.append(rec)
X = pd.DataFrame(rows); X.to_csv(HERE / "orb_first_candle_shape.csv", index=False)
X["shape"] = pd.cut(X.pos, [-0.01, 1 / 3, 2 / 3, 1.01], labels=["SELLERS WON (close in the bottom third)", "MIDDLE third", "TOP third"])
X["vol"] = pd.cut(X.vshare, [-1, 5, 10, 20, 1e9], labels=["< 5% of a day", "5-10%", "10-20%", ">= 20%"], right=False)
X["big"] = np.where(X.body_atr >= 0.5, "body >= 0.5 ATR", "body < 0.5 ATR")

print("HAND CHECK:", X[(X.date == "2026-10-09")].head(0).shape, "| INOXGREEN / SHADOWFAX 2026-10-12 are after the data end (2026-10-09);")
print("  by hand: INOXGREEN pos 0.23 -> SELLERS WON, flush no; SHADOWFAX pos 0.52 -> MIDDLE, flush yes")
print(X.sample(3, random_state=5)[["t", "date", "side", "pos", "flush", "body_atr", "vshare"]].round(2).to_string(index=False))


def line(lab, x):
    if len(x) == 0: return f"| {lab} | 0 |"
    out = [lab, str(len(x))]
    for k in EXITS:
        c = f"x{k}"; v = x[c]; top = x.groupby("date")[c].sum().sort_values(ascending=False).head(10).index
        out.append(f"{(v > 0).mean()*100:.0f}% / {v.mean():+.0f} ({v[~x.date.isin(top)].mean():+.0f}) | {v[x.date <= '2026-08-14'].mean():+.0f} / {v[x.date >= '2026-08-17'].mean():+.0f}")
    return "| " + " | ".join(out) + " |"


hdr = ("| group | trades | 1.5%: win / Rs (w/o top-10) | 1.5%: half 1 / 2 | 2%: win / Rs (w/o top-10) | 2%: half 1 / 2 | hold: win / Rs (w/o top-10) | hold: half 1 / 2 |\n"
       "|---|---|---|---|---|---|---|---|")
for sd, sn in ((-1, "SHORTS (red 09:15)"), (1, "LONGS (green 09:15, mirrored: 'sellers won' = buyers won, close in the top third)")):
    G = X[X.side == sd]
    print(f"\n## {sn}: {len(G)} breaks\n\nShape of the first candle\n{hdr}")
    print(line("BASELINE (all)", G))
    for k in G["shape"].cat.categories: print(line(k, G[G["shape"] == k]))
    print(line("FLUSH (wick against the trade >= body)", G[G.flush])); print(line("no flush", G[~G.flush]))
    print(f"\nOverlap with body size (200): shape inside each body group\n{hdr}")
    for bg in ("body >= 0.5 ATR", "body < 0.5 ATR"):
        B = G[G.big == bg]; print(line(f"{bg}: all", B))
        for k in G["shape"].cat.categories: print(line(f"{bg}: {k}", B[B["shape"] == k]))
    print(f"\nHow much of a normal DAY's volume traded in the first 5 minutes\n{hdr}")
    print(line("BASELINE (all)", G))
    for k in G["vol"].cat.categories: print(line(k, G[G["vol"] == k]))
    print(f"median first-candle volume = {G.vshare.median():.1f}% of an average day")
