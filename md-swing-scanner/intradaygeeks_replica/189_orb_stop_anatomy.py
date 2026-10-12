"""Anatomy of the in-play ORB's stops (user, 2026-10-11: 'are stops hit in the first 15 min or after the trade went 2-4R our way?').
DESCRIPTIVE only. 175's in-play trades, paper rules (stop order at the level, stop 10% ATR from the executed entry, hold to 15:15),
5-min bars, mid entry-bar rule; shorts + longs, all and with the 09:30 rule. For every STOPPED trade: minutes from entry to the stop,
and the best open profit (MFE, in R) it reached before being stopped. For trades held to the close: MFE vs final R (how much was given
back). Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from orb_common import read5_official  # 2026-10-12: official 09:15 open
from data.paths import INTRADAY_5M_DIR
A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
S = A[(A.rv >= 1) & (A["rank"] <= 20) & A.traded]
rows = []
for t, g in S.groupby("ticker"):
    m = read5_official(t); m["hm"] = m.index.strftime("%H:%M")
    for _, r in g.iterrows():
        d = m[m.index.normalize() == pd.Timestamp(r.date)]; s = int(r.side); lvl = d.iloc[0].Low if s < 0 else d.iloc[0].High
        b0 = d[d.hm == r.et].iloc[0]; e = r.e; sp = 0.1 * r.atr; stp = e * (1 - s * sp / 100); risk = e * sp / 100
        fo = (b0.Open <= lvl) if s < 0 else (b0.Open >= lvl); tc = (b0.High >= stp) if s < 0 else (b0.Low <= stp); cb = (b0.Close >= stp) if s < 0 else (b0.Close <= stp)
        mfe, out, when, final = 0.0, None, None, None
        if (fo and tc) or cb: out, when, final = "stop", 0, -1.0
        else:
            for ts, b in d[d.index > d[d.hm == r.et].index[0]].iterrows():
                if b.hm >= "15:15": out, final = "close", s * (b.Open - e) / risk; break
                if (b.High >= stp) if s < 0 else (b.Low <= stp): out, when, final = "stop", (ts - d[d.hm == r.et].index[0]).total_seconds() / 60, -1.0; break
                mfe = max(mfe, s * ((b.Low if s < 0 else b.High) - e) / risk)
            if out is None: out, final = "close", s * (d.Close.iloc[-1] - e) / risk
        rows.append(dict(side=s, late=r.et >= "09:30", out=out, mins=when, mfe=mfe, final=final))
X = pd.DataFrame(rows)
for sd, sn in ((-1, "SHORTS"), (1, "LONGS")):
    for rule in (False, True):
        G = X[X.side == sd]; G = G[G.late] if rule else G; st = G[G.out == "stop"]; cl = G[G.out == "close"]
        print(f"\n## {sn}, {'09:30 rule' if rule else 'all'}: {len(G)} trades, {len(st)} stopped ({len(st)/len(G)*100:.0f}%), {len(cl)} held to the close")
        print("| stopped within | entry bar | 15 min | 30 min | 1 h | 2 h | 3 h | later |\n|---|---|---|---|---|---|---|---|")
        mm = st.mins
        print("| share of stops | " + " | ".join(f"{x*100:.0f}%" for x in [(mm == 0).mean()] + [((mm > 0) & (mm <= b)).mean() + (mm == 0).mean() for b in (15, 30, 60, 120, 180)]) + f" | {(mm > 180).mean()*100:.0f}% |")
        print("| best open profit before the stop (MFE) | never above 0.5R | 0.5-1R | 1-2R | 2-3R | 3R+ |\n|---|---|---|---|---|---|")
        f = st.mfe
        print(f"| share of stops | {(f < 0.5).mean()*100:.0f}% | {((f >= 0.5) & (f < 1)).mean()*100:.0f}% | {((f >= 1) & (f < 2)).mean()*100:.0f}% | {((f >= 2) & (f < 3)).mean()*100:.0f}% | {(f >= 3).mean()*100:.0f}% |")
        print(f"held to the close: median MFE {cl.mfe.median():.1f}R, median final {cl.final.median():+.1f}R, gave back median {(cl.mfe - cl.final).median():.1f}R; closes that had been >= 3R and finished below 1R: {((cl.mfe >= 3) & (cl.final < 1)).sum()} of {len(cl)}")
