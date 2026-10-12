"""Confirmation entries with the stop at the LEVEL (user, 2026-10-11: 'how can confirmation increase stops?'). 186 sized the stop
from each entry (close-entry stop = close + k x ATR, i.e. lower for a short) -> more stops. Here the stop PRICE is the same as C0's:
breakout level x (1 -/+ k x ATR%) beyond the level; R / Rs @1k use the real risk = entry -> stop (bigger for a confirmed entry, so the
position is smaller). Entries C0 touch / C1 first 5-min close beyond / C2 two closes beyond; with and without the 09:30 rule; shorts
and longs; 175's in-play population, 5-min bars. A confirmed entry whose close is already beyond the stop is impossible (stop is on the
other side of the level). Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from orb_common import read5_official  # 2026-10-12: official 09:15 open
from data.paths import INTRADAY_5M_DIR

A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
P = A[(A.rv >= 1) & (A["rank"] <= 20)]
rows = []
for t, g in P.groupby("ticker"):
    m = read5_official(t)
    m["hm"] = m.index.strftime("%H:%M")
    for _, r in g.iterrows():
        d = m[m.index.normalize() == pd.Timestamp(r.date)]
        if len(d) < 70 or d.hm.iloc[0] != "09:15": continue
        s = int(r.side); f = d.iloc[0]; lvl = f.Low if s < 0 else f.High
        after = d[(d.hm >= "09:20") & (d.hm < "15:15")]
        bl = (after.Low < lvl) if s < 0 else (after.High > lvl); bc = ((after.Close < lvl) if s < 0 else (after.Close > lvl)).values
        if not bl.any(): continue
        touch = after[bl].hm.iloc[0]; ent = {}
        k0 = after[bl].index[0]; b0 = d.loc[k0]; ent["C0"] = (k0, min(lvl, b0.Open) if s < 0 else max(lvl, b0.Open), b0)
        if bc.any(): k1 = after.index[np.argmax(bc)]; ent["C1"] = (k1, d.loc[k1].Close, None)
        for i in range(1, len(bc)):
            if bc[i] and bc[i - 1]: ent["C2"] = (after.index[i], d.loc[after.index[i]].Close, None); break
        for c, (k, e, eb) in ent.items():
            rec = dict(date=r.date, side=s, ver=c, late=touch >= "09:30")
            for sm in (0.1, 0.2):
                stp = lvl * (1 - s * sm * r.atr / 100); risk = abs(stp - e) / e * 100   # % from entry to stop (fix 2026-10-11: first run had the sign flipped, C0 came out -573 vs the known +531)
                px, o = None, "close"
                if eb is not None:   # C0 entry bar, 175 mid rule
                    fo = (eb.Open <= lvl) if s < 0 else (eb.Open >= lvl); tc = (eb.High >= stp) if s < 0 else (eb.Low <= stp); cb = (eb.Close >= stp) if s < 0 else (eb.Close <= stp)
                    if (fo and tc) or cb: px, o = stp, "stop"
                if px is None:
                    for _, b in d[d.index > k].iterrows():
                        if b.hm >= "15:15": px = b.Open; break
                        if (b.High >= stp) if s < 0 else (b.Low <= stp): px, o = stp, "stop"; break
                if px is None: px = d.Close.iloc[-1]
                ret = s * (px - e) / e * 100; pos = 1000 / (risk / 100)
                rec.update({f"o{int(sm*100)}": o, f"R{int(sm*100)}": ret / risk, f"k{int(sm*100)}": ret / 100 * pos - 85 * pos / 1e5, f"risk{int(sm*100)}": risk})
            rows.append(rec)
X = pd.DataFrame(rows)
for sd, sn in ((-1, "SHORTS"), (1, "LONGS")):
    for sm in ("10", "20"):
        print(f"\n## {sn}, stop at the LEVEL + {sm}% ATR (same stop price for every entry)\n| entry | 09:30 rule | trades | stopped | win % | risk from entry (median) | avg R | Rs @1k net | w/o top-10 days | half 1 / half 2 |\n|---|---|---|---|---|---|---|---|---|---|")
        for rule in (False, True):
            for c in ("C0", "C1", "C2"):
                g = X[(X.side == sd) & (X.ver == c)]
                if rule: g = g[g.late]
                k = g[f"k{sm}"]; byd = g.groupby("date")[f"k{sm}"].sum().sort_values(ascending=False); wo = k[~g.date.isin(byd.head(10).index)].mean()
                print(f"| {c} | {'yes' if rule else 'no'} | {len(g)} | {(g[f'o{sm}'] == 'stop').mean()*100:.0f}% | {(g[f'R{sm}'] > 0).mean()*100:.0f}% | {g[f'risk{sm}'].median():.2f}% | {g[f'R{sm}'].mean():+.2f} | {k.mean():+.0f} | {wo:+.0f} | {k[g.date <= '2026-08-14'].mean():+.0f} / {k[g.date >= '2026-08-17'].mean():+.0f} |")
