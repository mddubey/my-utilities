"""Body position vs the lines instead of the EMA8 < EMA34 rule (user, 2026-10-08: the EMA8 rule removes more than one thing --
compressed-line indecision (bad) AND clean double rejections (should keep); "75% of the body below is fine, indecision is the
line right through the middle"). Theory: Brooks (bars straddling the MA have no bias; actionable bars sit on one side),
auction theory (body on the level = acceptance, wick through + body away = rejection), Guppy (MA compression = balance).
Results only. Spec fixed before running:
  Population: double_rejection_cap1e9.csv (current rules, NO trend filter, 30m warm-up fixed), price >= Rs100, both sets
  (1H 3-year = judge, 30m = check). Open recovered from the logged wick: qo = qh - wick * qc / 100 (wick = (qh - qo) / qc * 100).
  Lowest line pierced L = EMA34, or EMA8 when the wick reached it and it sits between the close and EMA34.
  below_share = part of the red body (close..open) below L, 0..1. Buckets 1.0 / 0.75-0.99 / 0.5-0.75 / < 0.5.
  Kinds: today (EMA8 < EMA34) | removed-both (EMA8 >= EMA34, wick reached EMA8) | removed-34only (EMA8 >= EMA34, wick below EMA8).
  Candidate rule: below_share >= 0.75, NO EMA8 rule. Compare with today's EMA8 rule: n, target / stop %, Rs net, by year /
  month, one-a-day plan (30m 10:45/11:15/11:45, 1H 11:15/12:15, closest to EMA34)."""
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
Y = pd.read_csv(HERE / "double_rejection_cap1e9.csv"); Y = Y[Y.qc >= 100].copy()
Y["qo"] = Y.qh - Y.wick * Y.qc / 100
Y["kind"] = np.where(Y.gap < 0, "today (EMA8 below)", np.where(Y.qh >= Y.E8, "removed: rejected by both", "removed: EMA34 only"))
L = np.where((Y.E8 > Y.qc) & (Y.E8 < Y.E34) & (Y.qh >= Y.E8), Y.E8, Y.E34)
body = (Y.qo - Y.qc).clip(lower=1e-9)
Y["below"] = ((np.minimum(Y.qo, L) - Y.qc) / body).clip(0, 1)
Y.loc[Y.qo <= Y.qc, "below"] = np.nan                          # not red (should not happen: red is required)
Y["bb"] = pd.cut(Y.below, [-0.01, 0.5, 0.75, 0.999, 1.01], labels=["< 50% (line through middle or higher)", "50-75%", "75-99%", "100% (fully below)"])
Y.to_csv(HERE / "body_below_lines.csv", index=False)


def st(g):
    o = g.out
    return f"| {len(g)} | {(o == 'target').mean()*100:.0f} | {(o == 'stop').mean()*100:.0f} | {g.ret.mean()*1000 - 85:+.0f} | {g.ret.sum()*1000 - 85*len(g):+,.0f} |"


for s, nm, per, al in (("b", "1H 2024-Sep 2026 (judge)", 4, [10, 11]), ("a", "30m Jun-Sep 2026 (check, warm-up fixed)", 7, [2, 3, 4])):
    z = Y[Y.set == s].dropna(subset=["below"]).copy(); z["p"] = z.date.str[:per]
    print(f"\n## {nm}\n| kind | body below the line | n | target % | stop % | Rs net | total | by period |\n|---|---|---|---|---|---|---|---|")
    for (k, b), g in z.groupby(["kind", "bb"], observed=True):
        pp = (g.groupby("p").ret.mean() * 1000 - 85).round(0).astype(int).to_dict()
        print(f"| {k} | {b} " + st(g) + " " + " / ".join(f"{v:+d}" for v in pp.values()) + " |")
    print(f"\n| rule | n | target % | stop % | Rs net | total | by period |\n|---|---|---|---|---|---|---|")
    for lab, keep in (("today: EMA8 < EMA34", z.gap < 0), ("candidate: body >= 75% below, no EMA8 rule", z.below >= 0.75),
                      ("both: EMA8 < EMA34 AND body >= 75% below", (z.gap < 0) & (z.below >= 0.75))):
        g = z[keep]; pp = (g.groupby("p").ret.mean() * 1000 - 85).round(0).astype(int).to_dict()
        print(f"| all setups, {lab} " + st(g) + " " + " / ".join(f"{v:+d}" for v in pp.values()) + " |")
        pk = z[keep & z.alarm.isin(al)].sort_values(["date", "alarm", "dist"]).groupby("date").head(1)
        pp = (pk.groupby("p").ret.mean() * 1000 - 85).round(0).astype(int).to_dict()
        print(f"| one-a-day, {lab} " + st(pk) + " " + " / ".join(f"{v:+d}" for v in pp.values()) + " |")
