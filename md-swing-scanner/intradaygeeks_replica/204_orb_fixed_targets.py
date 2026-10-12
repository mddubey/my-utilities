"""FIXED-TARGET exits for the in-play ORB (user, 2026-10-12: 'running full day is not smart, a fixed exit fits me'; declared before
running). 175's in-play trades on the OFFICIAL open (orb_sip.csv), paper entry (stop order at the 09:15 level, 5-min mid entry-bar rule),
stops 10% / 20% of ATR from the entry. Exits: X0 hold to 15:15 | X1 target 1R | X2 2R | X3 3R | X4 1% of price | X5 half at 1R, rest
held to 15:15 | X6 half at 1R, then the rest's stop moves to breakeven (held to 15:15). Conservative: inside one 5-min bar the STOP is
counted before the target; no target fill inside the entry bar. Groups: shorts from 09:20 and from 09:30, longs from 09:30 (+ 09:20).
Report: trades, win %, avg R, Rs @1k net (Rs85 / lakh on the full position), w/o top-10 days, halves, worst losing streak, max
drawdown (Rs, trades in date order), and how often stop and target fell in the same bar. Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from orb_common import read5_official
A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
S = A[(A.rv >= 1) & (A["rank"] <= 20) & A.traded].copy()
EXITS = ["X0", "X1", "X2", "X3", "X4", "X5", "X6"]
rows = []
for t, g in S.groupby("ticker"):
    m = read5_official(t); m["hm"] = m.index.strftime("%H:%M")
    for _, r in g.iterrows():
        d = m[m.index.normalize() == pd.Timestamp(r.date)]; f = d.iloc[0]; s = int(r.side); lvl = f.Low if s < 0 else f.High
        k = d.index[d.hm == r.et][0]; b0 = d.loc[k]; e = r.e; after = d[d.index > k]
        rec = dict(date=r.date, side=s, et=r.et)
        for sm in (0.1, 0.2):
            sp = sm * r.atr; risk = e * sp / 100; stp = e - s * risk; pos = 1000 / (sp / 100); chg = 85 * pos / 1e5
            fo = (b0.Open <= lvl) if s < 0 else (b0.Open >= lvl); tc = (b0.High >= stp) if s < 0 else (b0.Low <= stp); cb = (b0.Close >= stp) if s < 0 else (b0.Close <= stp)
            entry_stop = (fo and tc) or cb
            hit = lambda b, px: (b.Low <= px) if s < 0 else (b.High >= px)          # favourable price reached
            adv = lambda b, px: (b.High >= px) if s < 0 else (b.Low <= px)          # adverse price reached
            def run(target_R=None, target_px=None, half=False, be=False):
                if entry_stop: return -1.0, False
                tgt = target_px if target_px is not None else (e + s * -1 * target_R * risk * -1 if False else (e - s * target_R * risk) if target_R else None)
                if target_px is not None: tgt = target_px
                if target_R is not None: tgt = e - (-s) * target_R * risk if s > 0 else e - target_R * risk
                if s > 0 and target_R is not None: tgt = e + target_R * risk
                if s < 0 and target_R is not None: tgt = e - target_R * risk
                booked, cur_stop, same = None, stp, False
                for _, b in after.iterrows():
                    if b.hm >= "15:15":
                        rest = s * (b.Open - e) / risk
                        return ((booked + rest) / 2 if booked is not None else rest), same
                    if adv(b, cur_stop):
                        if tgt is not None and booked is None and hit(b, tgt): same = True
                        rest = s * (cur_stop - e) / risk
                        return ((booked + rest) / 2 if booked is not None else rest), same
                    if tgt is not None and booked is None and hit(b, tgt):
                        tr = s * (tgt - e) / risk
                        if not half: return tr, same
                        booked = tr
                        if be: cur_stop = e
                rest = s * (d.Close.iloc[-1] - e) / risk
                return ((booked + rest) / 2 if booked is not None else rest), same
            outs = {"X0": run(), "X1": run(1), "X2": run(2), "X3": run(3), "X4": run(target_px=e * (1 + s * 0.01)), "X5": run(1, half=True), "X6": run(1, half=True, be=True)}
            for x, (R, same) in outs.items():
                rec[f"R{int(sm*100)}{x}"] = R; rec[f"k{int(sm*100)}{x}"] = R * 1000 - chg; rec[f"same{int(sm*100)}{x}"] = same
        rows.append(rec)
X = pd.DataFrame(rows).sort_values(["date", "et"])


def stats(g, sm, x):
    R = g[f"R{sm}{x}"]; k = g[f"k{sm}{x}"]; byd = g.groupby("date")[f"k{sm}{x}"].sum().sort_values(ascending=False)
    lose = (k < 0).astype(int); streak = int(lose.groupby((lose != lose.shift()).cumsum()).sum().max())
    eq = k.cumsum(); dd = (eq - eq.cummax()).min()
    return (f"{(R > 0).mean()*100:.0f}% | {R.mean():+.2f} | {k.mean():+.0f} | {k[~g.date.isin(byd.head(10).index)].mean():+.0f} | "
            f"{k[g.date <= '2026-08-14'].mean():+.0f} / {k[g.date >= '2026-08-17'].mean():+.0f} | {streak} | {dd:,.0f} | {g[f'same{sm}{x}'].mean()*100:.0f}%")


NAME = {"X0": "hold to 15:15", "X1": "target 1R", "X2": "target 2R", "X3": "target 3R", "X4": "target 1% of price", "X5": "half at 1R, rest held", "X6": "half at 1R, rest stop to breakeven"}
for lab, msk in (("SHORTS, orders from 09:20", lambda x: (x.side < 0)), ("SHORTS, orders from 09:30", lambda x: (x.side < 0) & (x.et >= "09:30")),
                 ("LONGS, orders from 09:30", lambda x: (x.side > 0) & (x.et >= "09:30")), ("LONGS, orders from 09:20", lambda x: (x.side > 0))):
    G = X[msk(X)]
    for sm in ("10", "20"):
        print(f"\n## {lab}, stop {sm}% ATR ({len(G)} trades)\n| exit | win % | avg R | Rs @1k net | w/o top-10 days | half 1 / half 2 | worst losing streak | max drawdown Rs | stop+target same bar |\n|---|---|---|---|---|---|---|---|---|")
        for x in EXITS: print(f"| {NAME[x]} | " + stats(G, sm, x) + " |")
