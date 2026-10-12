"""Do old LEVELS in the path hurt the in-play ORB? (user, 2026-10-11: 'they can't just vanish because it's a different strategy';
spec declared earlier in chat). 175's in-play trades (paper rules: stop order at the 09:15 level, stop 10% ATR from entry, hold to 15:15,
5-min mid rule), shorts + longs, with / without the 09:30 rule. Levels in the trade's direction (below a short's entry, above a long's):
live daily 8-EMA (2/9 x entry + 7/9 x yday EMA8), live daily 34-EMA (2/35 x entry + 33/35 x yday EMA34), 1H EMA34 as of yesterday's close
(no hourly candle has closed at a 09:30 entry), yesterday's low (high for longs), yesterday's close, pivot S1 = 2P - H (R1 = 2P - L),
P = (H+L+C)/3 of yesterday. Distance = |level / entry - 1| %, only levels on the profit side count. Bands declared: nearest level within
0-0.5 / 0.5-1 / 1-2 / > 2% (or none). Also per level type: within 1% vs not. Skip rules 'any level within 0.5%' and '... within 1%':
kept vs removed vs baseline, both halves, w/o top-10 days, and how many +5R trades each removes. Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from orb_common import read5_official  # 2026-10-12: official 09:15 open
from data.paths import INTRADAY_5M_DIR, DAILY_DIR

A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
S = A[(A.rv >= 1) & (A["rank"] <= 20) & A.traded].copy()
LV = ["d8", "d34", "h34", "pdl", "pdc", "piv"]
NAMES = {"d8": "daily 8-EMA (live)", "d34": "daily 34-EMA (live)", "h34": "1H EMA34 (yday close)", "pdl": "yesterday's low / high",
         "pdc": "yesterday's close", "piv": "pivot S1 / R1"}
rows = []
for t, g in S.groupby("ticker"):
    d = load(t); raw = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True)
    e8 = d.Close.ewm(span=8, adjust=False).mean(); e34 = d.Close.ewm(span=34, adjust=False).mean()
    m = read5_official(t)
    day = m.index.normalize(); hk = day + pd.Timedelta("9h15min") + ((m.index - day - pd.Timedelta("9h15min")) // pd.Timedelta("60min")) * pd.Timedelta("60min")
    hc = m.Close.groupby(hk).last(); h34 = hc.ewm(span=34, adjust=False).mean()
    for ix, r in g.iterrows():
        dd = pd.Timestamp(r.date); prev = d.index[d.index < dd]
        if len(prev) == 0: continue
        p = prev[-1]; H, L, C = d.at[p, "High"], d.at[p, "Low"], d.at[p, "Close"]; P = (H + L + C) / 3; e = r.e; s = int(r.side)
        hy = h34[h34.index < dd]
        lv = dict(d8=2 / 9 * e + 7 / 9 * e8[p], d34=2 / 35 * e + 33 / 35 * e34[p], h34=hy.iloc[-1] if len(hy) else np.nan,
                  pdl=L if s < 0 else H, pdc=C, piv=(2 * P - H) if s < 0 else (2 * P - L))
        rec = dict(ix=ix)
        for k, v in lv.items():
            ok = (v < e) if s < 0 else (v > e)
            rec[k] = abs(v / e - 1) * 100 if (ok and v == v) else np.nan
        rows.append(rec)
X = S.join(pd.DataFrame(rows).set_index("ix")); X["near"] = X[LV].min(axis=1)


def row(lab, g, base=None):
    k = g.r1k10mid; R = g.R10mid
    if len(g) == 0: return f"| {lab} | 0 |"
    byd = g.groupby("date").r1k10mid.sum().sort_values(ascending=False); wo = k[~g.date.isin(byd.head(10).index)].mean()
    return (f"| {lab} | {len(g)} | {(g.o10mid == 'stop').mean()*100:.0f}% | {(R > 0).mean()*100:.0f}% | {R.mean():+.2f} | {k.mean():+.0f} | {wo:+.0f} | "
            f"{k[g.date <= '2026-08-14'].mean():+.0f} / {k[g.date >= '2026-08-17'].mean():+.0f} | {(R >= 5).sum()} |")


HD = "| group | trades | stopped | win % | avg R | Rs @1k net | w/o top-10 days | half 1 / half 2 | +5R trades |\n|---|---|---|---|---|---|---|---|---|"
for sd, sn in ((-1, "SHORTS (levels below the entry)"), (1, "LONGS (levels above the entry)")):
    for rule in (False, True):
        G = X[X.side == sd]; G = G[G.et >= "09:30"] if rule else G
        print(f"\n## {sn}, {'09:30 rule' if rule else 'all'}\n### nearest level in the path\n| " + HD[2:])
        print(row("BASELINE", G))
        for lab, msk in (("level within 0-0.5%", G.near <= 0.5), ("0.5-1%", (G.near > 0.5) & (G.near <= 1)), ("1-2%", (G.near > 1) & (G.near <= 2)),
                         ("clear > 2% (or no level)", (G.near > 2) | G.near.isna())):
            print(row(lab, G[msk]))
        print("\n### skip rules\n| " + HD[2:]); print(row("BASELINE", G))
        for x in (0.5, 1.0):
            print(row(f"KEPT: no level within {x}%", G[~(G.near <= x)])); print(row(f"removed: a level within {x}%", G[G.near <= x]))
        print("\n### each level type: within 1% of the entry vs not\n| " + HD[2:])
        for k in LV:
            print(row(f"{NAMES[k]} within 1%", G[G[k] <= 1])); print(row(f"{NAMES[k]} not within 1%", G[~(G[k] <= 1)]))
