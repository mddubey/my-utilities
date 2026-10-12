"""Four literature-backed confirmations on the in-play ORB (user, 2026-10-12: 'go, run A to D'; declared before running). 175's in-play
trades (5-min, mid rule, paper stop 10% / 20% ATR, hold to 15:15), shorts + longs, with and without the 09:30 rule.
A opening candle size: (09:15 high - low) / open as a multiple of daily ATR%: < 0.5 / 0.5-1.5 / > 1.5; KEPT = >= 0.5 (skip small ranges)
B noise boundary (Zarattini et al. 'Beat the Market'): at entry the move from the day's open in the trade direction >= the stock's average
  |close - open| / open at that bar time over the previous 14 days; KEPT = yes
C compression (Crabel): yesterday was NR7 (narrowest range of the last 7 days) OR an inside day (inside the day before); KEPT = yes
D relative move vs Nifty: stock's move from the open to entry in the trade direction minus Nifty's (open of the entry bar) -- Nifty 5-min
  only from 2026-07-10, so D runs on that subset; KEPT = stock moved more our way than Nifty (> 0)
PASS = kept beats baseline on Rs @1k net in both halves (..08-14 / 08-17..) AND w/o the top-10 days. Pairs only of passing ones. Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from data.paths import INTRADAY_5M_DIR, INDEX_INTRADAY_DIR
A0 = pd.read_csv(HERE / "orb_sip.csv"); A0["rank"] = A0.groupby("date").rv.rank(ascending=False, method="first")
S = A0[(A0.rv >= 1) & (A0["rank"] <= 20) & A0.traded].copy(); S["mon"] = S.date.str[:7]
n = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_5m_60d.csv", index_col=0, parse_dates=True); n.index = n.index.tz_convert("Asia/Kolkata").tz_localize(None)
n["day"] = n.index.normalize(); n["hm"] = n.index.strftime("%H:%M"); nopen = n[n.hm == "09:15"].set_index("day").Open
rows = []
for t, g in S.groupby("ticker"):
    d0 = load(t); rng = d0.High - d0.Low
    nr7 = rng.rolling(7).apply(lambda x: float(x[-1] == x.min()), raw=True); inside = (d0.High <= d0.High.shift(1)) & (d0.Low >= d0.Low.shift(1))
    m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
    m["day"] = m.index.normalize(); m["hm"] = m.index.strftime("%H:%M")
    op = m.groupby("day").Open.first(); m["mv"] = (m.Close / m.day.map(op) - 1).abs()
    piv = m.pivot_table(index="day", columns="hm", values="mv"); noise = piv.rolling(14, min_periods=10).mean().shift(1)
    for ix, r in g.iterrows():
        dd = pd.Timestamp(r.date); d = m[m.day == dd]; f = d.iloc[0]; s = int(r.side); prev = d0.index[d0.index < dd]
        A = (f.High - f.Low) / f.Open * 100 / r.atr
        mv = s * (r.e / f.Open - 1) * 100
        nb = noise.at[dd, r.et] * 100 if (dd in noise.index and r.et in noise.columns) else np.nan
        C = bool(nr7.get(prev[-1], 0) == 1 or inside.get(prev[-1], False)) if len(prev) else False
        nb_ = n[(n.day == dd) & (n.hm == r.et)]
        D = mv - s * (nb_.Open.iloc[0] / nopen[dd] - 1) * 100 if (len(nb_) and dd in nopen.index) else np.nan
        rows.append(dict(ix=ix, A=A, B=(mv >= nb) if nb == nb else np.nan, C=C, D=D))
X = S.join(pd.DataFrame(rows).set_index("ix"))


def st(g, sm):
    k = g[f"r1k{sm}mid"]; byd = g.groupby("date")[f"r1k{sm}mid"].sum().sort_values(ascending=False)
    return k.mean(), k[~g.date.isin(byd.head(10).index)].mean(), k[g.date <= "2026-08-14"].mean(), k[g.date >= "2026-08-17"].mean()


def row(lab, g, sm, base=None):
    if len(g) == 0: return f"| {lab} | 0 |", None
    a = st(g, sm); R = g[f"R{sm}mid"]
    ok = "" if base is None else ("PASS" if (a[1] > base[1] and a[2] > base[2] and a[3] > base[3]) else "no")
    return (f"| {lab} | {len(g)} | {(g[f'o{sm}mid'] == 'stop').mean()*100:.0f}% | {(R > 0).mean()*100:.0f}% | {R.mean():+.2f} | {a[0]:+.0f} | {a[1]:+.0f} | {a[2]:+.0f} / {a[3]:+.0f} | {ok} |"), a


KEEP = {"A": lambda x: x.A >= 0.5, "B": lambda x: x.B == True, "C": lambda x: x.C == True, "D": lambda x: x.D > 0}
NAME = {"A": "A opening candle >= 0.5x ATR", "B": "B move beyond normal noise", "C": "C yesterday NR7 / inside day", "D": "D moved more our way than Nifty"}
HD = "| group | trades | stopped | win % | avg R | Rs @1k net | w/o top-10 days | half 1 / half 2 | vs baseline |\n|---|---|---|---|---|---|---|---|---|"
for sm in ("10", "20"):
    for sd, sn in ((-1, "SHORTS"), (1, "LONGS")):
        for rule in (True, False):
            G = X[X.side == sd]; G = G[G.et >= "09:30"] if rule else G
            print(f"\n## {sn}, stop {sm}% ATR, {'09:30 rule (current)' if rule else 'all (from 09:20)'}\n{HD}")
            b_txt, b = row("BASELINE", G, sm); print(b_txt); passed = []
            for k in "ABCD":
                GG = G[G.D.notna()] if k == "D" else (G[G.B.notna()] if k == "B" else G)
                bb = b if k not in "BD" else row("x", GG, sm)[1]
                if k in "BD": print(row(f"  ({k} subset baseline)", GG, sm)[0])
                kt, ka = row(f"{NAME[k]}: KEPT", GG[KEEP[k](GG)], sm, bb); print(kt); print(row(f"{NAME[k]}: removed", GG[~KEEP[k](GG)], sm)[0])
                if "PASS" in kt: passed.append(k)
            print(row("A bands: < 0.5x ATR", G[G.A < 0.5], sm)[0]); print(row("A bands: 0.5-1.5x", G[(G.A >= 0.5) & (G.A <= 1.5)], sm)[0]); print(row("A bands: > 1.5x", G[G.A > 1.5], sm)[0])
            for i in range(len(passed)):
                for j in range(i + 1, len(passed)):
                    p, q = passed[i], passed[j]; GG = G[G.D.notna()] if "D" in (p, q) else G
                    print(row(f"PAIR {p} + {q}", GG[KEEP[p](GG) & KEEP[q](GG)], sm, row("x", GG, sm)[1])[0])
            print(f"passed: {', '.join(passed) or 'none'}")
