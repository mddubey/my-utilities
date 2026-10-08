"""Research only (user, 2026-10-08): drop the 1H EMA8 < EMA34 rule and instead drop doji signal candles. Spec fixed before running:
  Population: double_rejection_cap1e9.csv (current rules, no trend filter, 30m warm-up fixed), price >= Rs100. Both sets
  (1H 3-year = judge, 30m = check). Open from the logged wick (qo = qh - wick*qc/100), low from the logged close position
  (pos = (qc - low) / (qh - low) -> low = (qc - pos*qh) / (1 - pos)); checked against h1_cache below.
  Doji = body < 5% of the candle's range (Nison; 10% shown as a robustness neighbour).
  Rules: today (EMA8 < EMA34) | no EMA8 rule, no doji (5%) | no EMA8 rule, no doji (10%). n, target / stop %, Rs net, total,
  by year / month, one-a-day plan (closest to EMA34, 30m 10:45/11:15/11:45, 1H 11:15/12:15)."""
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
Y = pd.read_csv(HERE / "double_rejection_cap1e9.csv"); Y = Y[Y.qc >= 100].copy()
Y["qo"] = Y.qh - Y.wick * Y.qc / 100
Y["ql"] = (Y.qc - Y.pos * Y.qh) / (1 - Y.pos)
Y["bodyp"] = (Y.qo - Y.qc).abs() / (Y.qh - Y.ql)
# check low/open recovery on 1H rows against h1_cache (sample)
chk = []
for _, r in Y[Y.set == "b"].sample(200, random_state=1).iterrows():
    h = pd.read_csv(HERE / "h1_cache" / f"{r.ticker}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    t0 = pd.Timestamp(r.date) + pd.Timedelta(hours=int(r.alarm), minutes=15)
    if t0 in h.index: chk.append((abs(h.at[t0, "Low"] - r.ql) / r.qc * 100, abs(h.at[t0, "Open"] - r.qo) / r.qc * 100))
c = np.array(chk); print(f"recovery check on {len(c)} 1H rows: max |low err| {c[:, 0].max():.4f}%, max |open err| {c[:, 1].max():.4f}%")


def st(g):
    o = g.out
    return f"| {len(g)} | {(o == 'target').mean()*100:.0f} | {(o == 'stop').mean()*100:.0f} | {g.ret.mean()*1000 - 85:+.0f} | {g.ret.sum()*1000 - 85*len(g):+,.0f} |"


for s, nm, per, al in (("b", "1H 2024-Sep 2026 (judge)", 4, [10, 11]), ("a", "30m Jun-Sep 2026 (check)", 7, [2, 3, 4])):
    z = Y[Y.set == s].copy(); z["p"] = z.date.str[:per]
    print(f"\n## {nm}  (dojis: {int((z.bodyp < 0.05).sum())} at 5%, {int((z.bodyp < 0.10).sum())} at 10% of {len(z)})")
    print("| rule | n | target % | stop % | Rs net | total | by period |\n|---|---|---|---|---|---|---|")
    rules = (("today: EMA8 < EMA34", z.gap < 0), ("no EMA8 rule, no doji (body >= 5%)", z.bodyp >= 0.05), ("no EMA8 rule, no doji (body >= 10%)", z.bodyp >= 0.10))
    for lab, keep in rules:
        g = z[keep]; pp = (g.groupby("p").ret.mean() * 1000 - 85).round(0).astype(int).to_dict()
        print(f"| all setups, {lab} " + st(g) + " " + " / ".join(f"{v:+d}" for v in pp.values()) + " |")
    for lab, keep in rules:
        pk = z[keep & z.alarm.isin(al)].sort_values(["date", "alarm", "dist"]).groupby("date").head(1)
        pp = (pk.groupby("p").ret.mean() * 1000 - 85).round(0).astype(int).to_dict()
        print(f"| one-a-day, {lab} " + st(pk) + " " + " / ".join(f"{v:+d}" for v in pp.values()) + " |")
    added = z[(z.gap >= 0) & (z.bodyp >= 0.05)]; pp = (added.groupby("p").ret.mean() * 1000 - 85).round(0).astype(int).to_dict()
    print(f"| setups ADDED vs today (EMA8 above, not doji) " + st(added) + " " + " / ".join(f"{v:+d}" for v in pp.values()) + " |")
    dropped = z[(z.gap < 0) & (z.bodyp < 0.05)]; pp = (dropped.groupby("p").ret.mean() * 1000 - 85).round(0).astype(int).to_dict()
    print(f"| setups DROPPED vs today (today's dojis) " + st(dropped) + " " + " / ".join(f"{v:+d}" for v in pp.values()) + " |")
