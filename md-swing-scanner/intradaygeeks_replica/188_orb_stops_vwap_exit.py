"""Stop placement and VWAP exit for the in-play ORB, literature choices only (user, 2026-10-11: 'take literature's input, keep me in
check, don't overdo'; spec fixed before running). 175's in-play population, 5-min bars, shorts + longs, with / without the 09:30 rule.
Entry + stop (5 rows): C0 stop order at the level with S1 = level -/+ 10% ATR (Zarattini-Barbon-Aziz) | C0 with S4 = other side of
the opening range (the 09:15 candle's high for a short; classic ORB) | C1 first 5-min close beyond with S2 = level -/+ 10% ATR | C1 with
S3 = beyond the confirming candle's high/low (practitioner) | C1 with S4.
Exit (3): X1 hold to 15:15 (paper) | X2 VWAP: out at the next bar's open after a 5-min close back on the wrong side of VWAP (Zarattini-
Aziz VWAP paper) | X3 = X2 but only after the trade has gone >= 0.5R our way. Hard stop always live (stop first in a bar). VWAP with the
09:15 volume = day volume - other bars. Rs @1k net uses the real risk (entry -> stop).
PASS = beats C0+S1+X1 (same side / 09:30 setting) on Rs @1k net in both halves (..08-14 / 08-17..) AND w/o the top-10 days. Results only."""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from orb_common import read5_official  # 2026-10-12: official 09:15 open
from data.paths import INTRADAY_5M_DIR, DAILY_DIR

A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
P = A[(A.rv >= 1) & (A["rank"] <= 20)]
rows, t0 = [], time.time()


def walk(d, k, e, s, stp, mode, vw, eb=None, lvl=None):
    risk = abs(stp - e)
    if eb is not None:   # C0 entry bar: 175's mid rule
        fo = (eb.Open <= lvl) if s < 0 else (eb.Open >= lvl); tc = (eb.High >= stp) if s < 0 else (eb.Low <= stp); cb = (eb.Close >= stp) if s < 0 else (eb.Close <= stp)
        if (fo and tc) or cb: return stp, "stop"
    best, armed, nxt = 0.0, mode == "X2", False
    for ts, b in d[d.index > k].iterrows():
        if b.hm >= "15:15": return b.Open, "close"
        if nxt: return b.Open, "vwap"
        if (b.High >= stp) if s < 0 else (b.Low <= stp): return stp, "stop"
        best = max(best, s * ((b.Low if s < 0 else b.High) - e))
        if mode == "X3" and best >= 0.5 * risk: armed = True
        if mode != "X1" and armed and ((b.Close > vw[ts]) if s < 0 else (b.Close < vw[ts])): nxt = True
    return d.Close.iloc[-1], "close"


for t, g in P.groupby("ticker"):
    m = read5_official(t)
    m["hm"] = m.index.strftime("%H:%M"); dv = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).Volume
    for _, r in g.iterrows():
        dd = pd.Timestamp(r.date); d = m[m.index.normalize() == dd]
        if len(d) < 70 or d.hm.iloc[0] != "09:15": continue
        s = int(r.side); f = d.iloc[0]; lvl = f.Low if s < 0 else f.High; opp = f.High if s < 0 else f.Low
        v = d.Volume.values.astype(float); v[0] = dv.get(dd, np.nan) - v[1:].sum()
        vw = pd.Series(np.cumsum(((d.High + d.Low + d.Close) / 3).values * v) / np.cumsum(v), index=d.index)
        a = d[(d.hm >= "09:20") & (d.hm < "15:15")]
        bl = (a.Low < lvl) if s < 0 else (a.High > lvl); bc = (a.Close < lvl) if s < 0 else (a.Close > lvl)
        if not bl.any(): continue
        late = a[bl].hm.iloc[0] >= "09:30"; atrstop = lvl * (1 - s * 0.1 * r.atr / 100)
        k0 = a[bl].index[0]; b0 = d.loc[k0]; e0 = min(lvl, b0.Open) if s < 0 else max(lvl, b0.Open)
        combos = [("C0+S1 (paper)", k0, e0, atrstop, b0), ("C0+S4 range other side", k0, e0, opp, b0)]
        if bc.any():
            k1 = a[bc].index[0]; c = d.loc[k1]; e1 = c.Close
            combos += [("C1+S2 level+10% ATR", k1, e1, atrstop, None), ("C1+S3 confirm-candle high", k1, e1, c.High if s < 0 else c.Low, None), ("C1+S4 range other side", k1, e1, opp, None)]
        for name, k, e, stp, eb in combos:
            if s * (stp - e) >= 0: continue   # stop must be on the risk side (above entry for a short, below for a long)
            risk = abs(stp - e) / e * 100; pos = 1000 / (risk / 100); rec = dict(date=r.date, side=s, late=late, combo=name, risk=risk)
            for mode in ("X1", "X2", "X3"):
                px, o = walk(d, k, e, s, stp, mode, vw, eb, lvl); ret = s * (px - e) / e * 100
                rec[f"k{mode}"] = ret / 100 * pos - 85 * pos / 1e5; rec[f"R{mode}"] = ret / risk; rec[f"o{mode}"] = o
            rows.append(rec)
X = pd.DataFrame(rows); X.to_csv(HERE / "orb_stops_vwap.csv", index=False)
print(f"{len(X)} rows in {time.time()-t0:.0f}s")


def st(g, x):
    k = g[f"k{x}"]; byd = g.groupby("date")[f"k{x}"].sum().sort_values(ascending=False)
    return k.mean(), k[~g.date.isin(byd.head(10).index)].mean(), k[g.date <= "2026-08-14"].mean(), k[g.date >= "2026-08-17"].mean()


for sd, sn in ((-1, "SHORTS"), (1, "LONGS")):
    for rule in (False, True):
        G = X[X.side == sd]; G = G[G.late] if rule else G
        b = st(G[G.combo == "C0+S1 (paper)"], "X1")
        print(f"\n## {sn}, {'09:30 RULE' if rule else 'no 09:30 rule'} -- Rs @1k net per trade (w/o top-10 days) [half 1 / half 2]")
        print("| entry + stop | trades | risk median | stopped (X1) | win % (X1) | X1 hold to 15:15 | X2 VWAP exit | X3 VWAP after +0.5R | PASS |\n|---|---|---|---|---|---|---|---|---|")
        for c in ("C0+S1 (paper)", "C0+S4 range other side", "C1+S2 level+10% ATR", "C1+S3 confirm-candle high", "C1+S4 range other side"):
            g = G[G.combo == c]; cells, passes = [], []
            for x in ("X1", "X2", "X3"):
                kk = st(g, x); cells.append(f"{kk[0]:+.0f} ({kk[1]:+.0f}) [{kk[2]:+.0f} / {kk[3]:+.0f}]")
                if not (c.startswith("C0+S1") and x == "X1"): passes.append(x if (kk[1] > b[1] and kk[2] > b[2] and kk[3] > b[3]) else None)
            ps = ",".join(p for p in passes if p) or ("base" if c.startswith("C0+S1") else "none")
            print(f"| {c} | {len(g)} | {g.risk.median():.2f}% | {(g.oX1 == 'stop').mean()*100:.0f}% | {(g.RX1 > 0).mean()*100:.0f}% | " + " | ".join(cells) + f" | {ps} |")
