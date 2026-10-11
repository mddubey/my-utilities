"""When to start placing orders: 09:20 (paper) / 09:30 (user's rule) / 09:45 / 10:00 (user, 2026-10-11: 'is 09:30 enough to settle?';
nearby settings declared together, Rule #19). Each version SKIPS a stock whose level was first touched before its start time.
175's in-play trades, paper stop (10% ATR from entry, also 20%), hold to 15:15, 5-min mid entry-bar rule; shorts + longs. Also the
share of stops that land within 15 min of entry, per version. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import pandas as pd
HERE = Path(__file__).resolve().parent
src = open(HERE / "189_orb_stop_anatomy.py").read().split("X = pd.DataFrame(rows)")[0].replace("rows.append(dict(side=s,", "rows.append(dict(date=r.date, et=r.et, side=s,")
exec(src); X = pd.DataFrame(rows)
A2 = S.set_index(["ticker", "date"]) if False else None
T = S.reset_index(drop=True)
for sd, sn in ((-1, "SHORTS"), (1, "LONGS")):
    for sm in ("10", "20"):
        print(f"\n## {sn}, stop {sm}% ATR -- Rs @1k net per trade\n| orders from | trades | days with a trade | stopped | win % | avg R | Rs @1k net | w/o top-10 days | half 1 / half 2 | stops within 15 min of entry (10% stop) |\n|---|---|---|---|---|---|---|---|---|---|")
        for st in ("09:20", "09:30", "09:45", "10:00"):
            g = T[(T.side == sd) & (T.et >= st)]; k = g[f"r1k{sm}mid"]; R = g[f"R{sm}mid"]
            byd = g.groupby("date")[f"r1k{sm}mid"].sum().sort_values(ascending=False); wo = k[~g.date.isin(byd.head(10).index)].mean()
            xx = X[(X.side == sd) & (X.et >= st) & (X.out == "stop")]
            print(f"| {st}{' (paper)' if st == '09:20' else ''} | {len(g)} | {g.date.nunique()} | {(g[f'o{sm}mid'] == 'stop').mean()*100:.0f}% | {(R > 0).mean()*100:.0f}% | {R.mean():+.2f} | {k.mean():+.0f} | {wo:+.0f} | {k[g.date <= '2026-08-14'].mean():+.0f} / {k[g.date >= '2026-08-17'].mean():+.0f} | {(xx.mins <= 15).mean()*100:.0f}% |")
