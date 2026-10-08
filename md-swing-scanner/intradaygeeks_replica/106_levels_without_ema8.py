"""Level-in-path re-test WITHOUT the EMA8 rule applied first (user, 2026-10-08: scripts 77-79 tested levels only on the
EMA8-filtered population, which removes most prev-day-low / S1 setups -> population bias). Results only. Spec fixed before running:
  Population: body_below_lines.csv (= double_rejection_cap1e9: current rules, no EMA8 rule, 30m warm-up fixed), price >= Rs100.
  1H 3-year = judge, 30m = check. Levels from the daily cache, yesterday's bar: prev day low (PDL), daily PP, S1, S2.
  "In path" = strictly between the 1% target and the entry (candle close). One at a time, then ANY of the four.
  Groups: ALL (no EMA8 rule) | today (EMA8 < EMA34) | removed: rejected by both | removed: EMA34 only.
  Report n, target / stall / stop %, Rs net (gross - 85 per Rs1 lakh), by year (1H) / month (30m)."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import DAILY_DIR
HERE = Path(__file__).resolve().parent
z = pd.read_csv(HERE / "body_below_lines.csv")
rows = {}
for t, g in z.groupby("ticker"):
    try: d = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True)[["High", "Low", "Close"]].dropna()
    except Exception: continue
    for ix, r in g.iterrows():
        p = d[d.index < pd.Timestamp(r.date)]
        if len(p) < 25: continue
        H, L, C = p.iloc[-1]; pp = (H + L + C) / 3; e, tg = r.qc, r.qc * 0.99
        rows[ix] = {"PDL": tg < L < e, "PP": tg < pp < e, "S1": tg < 2 * pp - H < e, "S2": tg < pp - (H - L) < e}
z = z.join(pd.DataFrame(rows).T.astype(bool), how="inner"); z["ANY"] = z[["PDL", "PP", "S1", "S2"]].any(axis=1)
z.to_csv(HERE / "levels_without_ema8.csv", index=False)


def st(g):
    o = g.out
    return f"{len(g)} / {(o == 'target').mean()*100:.0f} / {(o == 'stall').mean()*100:.0f} / {(o == 'stop').mean()*100:.0f} / {g.ret.mean()*1000 - 85:+.0f}"


for s, nm, per in (("b", "1H 2024-Sep 2026 (judge)", 4), ("a", "30m Jun-Sep 2026 (check)", 7)):
    x = x0 = z[z.set == s]
    groups = [("ALL (no EMA8 rule)", x0), ("today (EMA8 below)", x0[x0.kind.str.startswith("today")]),
              ("removed: rejected by both", x0[x0.kind == "removed: rejected by both"]), ("removed: EMA34 only", x0[x0.kind == "removed: EMA34 only"])]
    print(f"\n## {nm} -- cells: n / target % / stall % / stop % / Rs net")
    print("| group | level | IN the path | NOT in the path |\n|---|---|---|---|")
    for gname, g in groups:
        for lv in ("PDL", "S1", "PP", "S2", "ANY"):
            print(f"| {gname} | {lv} | {st(g[g[lv]])} | {st(g[~g[lv]])} |")
    print(f"\nby period (Rs net), ANY level in path vs clear:")
    for gname, g in groups:
        a = (g[g.ANY].groupby(g[g.ANY].date.str[:per]).ret.mean() * 1000 - 85).round(0).astype(int).to_dict()
        b = (g[~g.ANY].groupby(g[~g.ANY].date.str[:per]).ret.mean() * 1000 - 85).round(0).astype(int).to_dict()
        nb = g[~g.ANY].groupby(g[~g.ANY].date.str[:per]).size().to_dict()
        print(f"  {gname:28s} in path: " + " ".join(f"{k}:{v:+d}" for k, v in a.items()) + " | clear: " + " ".join(f"{k}:{v:+d}(n{nb[k]})" for k, v in b.items()))
