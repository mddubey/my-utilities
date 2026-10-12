"""ORB + VWAP PULLBACK entry (user, 2026-10-12: 'I entered INOXGREEN on the VWAP rejection, not the candle-low break -- does that work?';
spec declared in chat). In-play stocks (175's relvol >= 1, top 20), OFFICIAL open, SHORTS = red 09:15 candle (longs mirrored, info).
Setup: the 09:15 low breaks (from 09:20) -> a LATER 5-min bar's high reaches VWAP (09:15 volume = day - other bars) before 13:00 ->
that bar or one of the next two CLOSES back below VWAP (rejection). Entry (a) at the rejection bar's close; (b) a stop order at the 09:15
low again after the rejection (the re-break -- what the user did; if the rejection bar already closed below the level, (b) fills at the
level inside that bar). Stops: above the bounce high (max high from the VWAP touch to the rejection) | 10% ATR | 20% ATR from the entry.
Exits: hold to 15:15 | fixed 1.5% | fixed 2% (stop counted first in a bar). Compared with the PLAIN BREAK on the same in-play set (stop
order at the level, 10% ATR, same exits). Rs @1k risk net (Rs85 / lakh). Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from orb_common import read5_official
from data.paths import DAILY_DIR
A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
P = A[(A.rv >= 1) & (A["rank"] <= 20)].copy()


def walk(d, k_after, e, s, stp, tgt_pct):
    tgt = None if tgt_pct is None else e * (1 + s * tgt_pct / 100)
    for _, b in d[d.index > k_after].iterrows():
        if b.hm >= "15:15": return b.Open
        if (b.High >= stp) if s < 0 else (b.Low <= stp): return stp
        if tgt is not None and ((b.Low <= tgt) if s < 0 else (b.High >= tgt)): return tgt
    return d.Close.iloc[-1]


rows = []
for t, g in P.groupby("ticker"):
    m = read5_official(t); m["hm"] = m.index.strftime("%H:%M"); dv = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).Volume
    for _, r in g.iterrows():
        dd = pd.Timestamp(r.date); d = m[m.index.normalize() == dd].copy()
        if len(d) < 70: continue
        s = int(r.side); f = d.iloc[0]; lvl = f.Low if s < 0 else f.High
        v = d.Volume.values.astype(float); v[0] = dv.get(dd, np.nan) - v[1:].sum(); d["vw"] = np.cumsum(((d.High + d.Low + d.Close) / 3).values * v) / np.cumsum(v)
        a = d[(d.hm >= "09:20") & (d.hm < "15:15")]
        brk = a[(a.Low < lvl) if s < 0 else (a.High > lvl)]
        if not len(brk): continue
        kb = brk.index[0]; b0 = d.loc[kb]; ep = min(lvl, b0.Open) if s < 0 else max(lvl, b0.Open)
        rec = dict(date=r.date, side=s, atr=r.atr)
        # plain break, 10% ATR, mid entry-bar rule
        sp = 0.1 * r.atr; stp = ep * (1 - s * sp / 100)
        fo = (b0.Open <= lvl) if s < 0 else (b0.Open >= lvl); tc = (b0.High >= stp) if s < 0 else (b0.Low <= stp); cb = (b0.Close >= stp) if s < 0 else (b0.Close <= stp)
        for x in (None, 1.5, 2.0):
            px = stp if ((fo and tc) or cb) else walk(d, kb, ep, s, stp, x); ret = s * (px - ep) / ep * 100
            rec[f"plain_{x}"] = ret / sp * 1000 - 85 * (1000 / (sp / 100)) / 1e5
        # VWAP pullback after the break
        later = d[(d.index > kb) & (d.hm < "13:00")]
        touch = later[(later.High >= later.vw) if s < 0 else (later.Low <= later.vw)]
        if len(touch):
            kt = touch.index[0]; win = d[d.index >= kt].head(3); rej = win[(win.Close < win.vw) if s < 0 else (win.Close > win.vw)]
            if len(rej):
                kr = rej.index[0]; br = d.loc[kr]; seg = d[(d.index >= kt) & (d.index <= kr)]
                bounce = seg.High.max() if s < 0 else seg.Low.min()
                rec["setup"] = True; rec["t_rej"] = br.hm
                # entry (a): rejection close
                entries = {"a": (kr, br.Close)}
                # entry (b): re-break of the level after the rejection
                # 2026-10-12 fix: the rejection is only known at the bar's close -> if that close is already beyond the level, the earliest
                # real fill is that close (first run filled at the level INSIDE the bar = look-ahead)
                if (br.Close < lvl) if s < 0 else (br.Close > lvl): entries["b"] = (kr, br.Close)
                else:
                    nb = d[(d.index > kr) & (d.hm < "15:15")]; rb = nb[(nb.Low < lvl) if s < 0 else (nb.High > lvl)]
                    if len(rb): bb = d.loc[rb.index[0]]; entries["b"] = (rb.index[0], min(lvl, bb.Open) if s < 0 else max(lvl, bb.Open))
                for en, (ke, e) in entries.items():
                    for sn in ("bounce", "10", "20"):
                        stp = (bounce * (1 + s * -0.0005) if False else bounce) if sn == "bounce" else e * (1 - s * (0.1 if sn == "10" else 0.2) * r.atr / 100)
                        risk = s * (e - stp) * -1 / e * 100 if False else abs(stp - e) / e * 100
                        if risk <= 0 or (s < 0 and stp <= e) or (s > 0 and stp >= e): continue
                        # 2026-10-12 fix: a stop-order fill (entry b after the rejection bar) uses the same entry-bar rule as the plain break
                        eb = d.loc[ke]; in_bar_stop = False
                        if en == "b" and ke != kr:
                            fo_ = (eb.Open <= lvl) if s < 0 else (eb.Open >= lvl); tc_ = (eb.High >= stp) if s < 0 else (eb.Low <= stp); cb_ = (eb.Close >= stp) if s < 0 else (eb.Close <= stp)
                            in_bar_stop = (fo_ and tc_) or cb_
                        for x in (None, 1.5, 2.0):
                            px = stp if in_bar_stop else walk(d, ke, e, s, stp, x); ret = s * (px - e) / e * 100
                            rec[f"{en}_{sn}_{x}"] = ret / risk * 1000 - 85 * (1000 / (risk / 100)) / 1e5
                        rec[f"risk_{en}_{sn}"] = risk
        rows.append(rec)
X = pd.DataFrame(rows)


def row(lab, g, col):
    g = g[g[col].notna()]
    if len(g) == 0: return f"| {lab} | 0 |"
    k = g[col]; byd = g.groupby("date")[col].sum().sort_values(ascending=False)
    return f"| {lab} | {len(g)} | {(k > 0).mean()*100:.0f}% | {k.mean():+.0f} | {k[~g.date.isin(byd.head(10).index)].mean():+.0f} | {k[g.date <= '2026-08-14'].mean():+.0f} / {k[g.date >= '2026-08-17'].mean():+.0f} |"


for sd, sn in ((-1, "SHORTS"), (1, "LONGS (info)")):
    G = X[X.side == sd]; Sx = G[G.get("setup", pd.Series(False, index=G.index)) == True]
    print(f"\n## {sn}: in-play breaks {len(G)} | VWAP pullback + rejection after the break (before 13:00): {len(Sx)} ({len(Sx)/len(G)*100:.0f}%)")
    print("| version | trades | win % | Rs @1k net | w/o top-10 days | half 1 / half 2 |\n|---|---|---|---|---|---|")
    for x, xl in ((None, "hold"), (1.5, "1.5% target"), (2.0, "2% target")):
        print(row(f"PLAIN break, 10% ATR, {xl} (all breaks)", G, f"plain_{x}"))
        print(row(f"  plain break, same stocks that later gave the VWAP setup", Sx, f"plain_{x}"))
        for en, enl in (("a", "rejection close"), ("b", "re-break of the level")):
            for st, stl in (("bounce", "stop above bounce high"), ("10", "stop 10% ATR"), ("20", "stop 20% ATR")):
                print(row(f"VWAP pullback, entry {enl}, {stl}, {xl}", Sx, f"{en}_{st}_{x}"))
    for en in ("a", "b"):
        if f"risk_{en}_bounce" in Sx: print(f"median risk with the bounce-high stop, entry {en}: {Sx[f'risk_{en}_bounce'].median():.2f}%")
