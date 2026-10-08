"""Which support levels in the target path are clear losers? (user, 2026-10-08: "don't clutter, but if something is obviously
a loser we don't want to keep it"). Extends 106 with weekly pivots and daily swing lows. Results only. Spec fixed before running:
  Population: levels_without_ema8.csv (current rules, no EMA8 rule, price >= Rs100, 30m warm-up fixed); 1H 3-year = judge,
  30m = check. Levels: daily PDL / PP / S1 / S2 (from 106) + weekly PP / S1 / S2 (last completed Mon-Fri week before the trade
  date) + SW = any daily swing low of the last 60 sessions (low below the 2 days on each side, confirmed by yesterday).
  "In path" = strictly between the 1% target and the entry. Per level: in path vs not, for ALL (no EMA8 rule) and today's trades
  (EMA8 rule), n / target / stop / Rs net, by year (1H) / month (30m). A level counts as an OBVIOUS LOSER only if in-path is
  worse than not-in-path in BOTH sets, in today's trades, and in at least 2 of 3 years on 1H."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import DAILY_DIR
HERE = Path(__file__).resolve().parent
z = pd.read_csv(HERE / "levels_without_ema8.csv")
add = {}
for t, g in z.groupby("ticker"):
    try: d = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True)[["High", "Low", "Close"]].dropna()
    except Exception: continue
    for ix, r in g.iterrows():
        day = pd.Timestamp(r.date); p = d[d.index < day]
        if len(p) < 30: continue
        e, tg = r.qc, r.qc * 0.99; rec = {}
        wk = p[p.index < day - pd.Timedelta(days=day.weekday())]
        if len(wk):
            w = wk[wk.index >= wk.index[-1] - pd.Timedelta(days=wk.index[-1].weekday())]
            H, L, C = w.High.max(), w.Low.min(), w.Close.iloc[-1]; pp = (H + L + C) / 3
            rec.update(wPP=tg < pp < e, wS1=tg < 2 * pp - H < e, wS2=tg < pp - (H - L) < e)
        s = p.Low.tail(60).values
        rec["SW"] = any(tg < s[i] < e for i in range(2, len(s) - 2) if s[i] < min(s[i - 2], s[i - 1], s[i + 1], s[i + 2]))
        add[ix] = rec
z = z.join(pd.DataFrame(add).T.astype(bool), how="inner")
z.to_csv(HERE / "more_levels.csv", index=False)
LV = ["PDL", "S1", "S2", "PP", "wPP", "wS1", "wS2", "SW"]
verdict = {}
for s, nm, per in (("b", "1H 2024-Sep 2026 (judge)", 4), ("a", "30m Jun-Sep 2026 (check)", 7)):
    x = z[z.set == s].copy(); x["p"] = x.date.str[:per]
    print(f"\n## {nm} -- Rs net: level IN the path vs NOT (n in brackets)")
    print("| level | how often in path (all) | all setups, no EMA8 rule: in / not | today's trades (EMA8 rule): in / not | today's trades, in-path minus not, by period |\n|---|---|---|---|---|")
    for lv in LV:
        a_in, a_out = x[x[lv]], x[~x[lv]]; t = x[x.kind.str.startswith("today")]; t_in, t_out = t[t[lv]], t[~t[lv]]
        f = lambda g: f"{g.ret.mean()*1000 - 85:+.0f} ({len(g)})"
        bp = (t_in.groupby("p").ret.mean() - t_out.groupby("p").ret.mean()) * 1000
        print(f"| {lv} | {x[lv].mean()*100:.0f}% | {f(a_in)} / {f(a_out)} | {f(t_in)} / {f(t_out)} | " + " ".join(f"{k[2:] if per == 4 else k[5:]}:{v:+.0f}" for k, v in bp.items()) + " |")
        worse_today = t_in.ret.mean() < t_out.ret.mean()
        verdict.setdefault(lv, []).append((s, worse_today, int((bp < 0).sum()), len(bp)))
print("\nobvious-loser check (in-path worse than not, today's trades): " + "; ".join(
    f"{lv}: 1H {'worse' if v[0][1] else 'not worse'} ({v[0][2]}/{v[0][3]} yrs worse), 30m {'worse' if v[1][1] else 'not worse'} -> {'LOSER' if v[0][1] and v[1][1] and v[0][2] >= 2 else 'no'}"
    for lv, v in verdict.items()))
