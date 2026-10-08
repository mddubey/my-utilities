"""EMA34 slope vs the EMA8/EMA34 crossover (user, 2026-10-08: "the trend filter is not right even if the data shows it -- find
what it is really filtering"). Results only. Spec fixed before running:
  Population: double_rejection_cap1e9.csv (script 101 --cap 1e9 = current rules with NO trend filter; 30m set with the
  warm-up fix), both sets. Groups: kept today (EMA8 < EMA34) / removed today (EMA8 >= EMA34).
  slope_N = (EMA34 as of the last completed hour - EMA34 N hours earlier) / EMA34, %, from h1_cache closes (identical to the
  5-min-derived closes on the overlap), N = 3 / 5 / 8. Buckets: falling < -0.1 / flat -0.1..+0.1 / rising > +0.1 %.
  Per N: crossover group x slope bucket -> n, target / stop %, Rs net, by year (1H) / month (30m).
  Rules compared on the one-a-day plan (30m 10:45/11:15/11:45, 1H 11:15/12:15, closest to EMA34):
    today = crossover; on top = crossover AND slope_N < 0; instead = slope_N < 0 (no crossover)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
NS = (3, 5, 8)
Y = pd.read_csv(HERE / "double_rejection_cap1e9.csv")
Y["hs"] = np.where(Y.set == "a", pd.to_datetime(Y.date) + pd.Timedelta("9h15min") + pd.to_timedelta((Y.alarm * 30 // 60) * 60, unit="m"),
                   pd.to_datetime(Y.date) + pd.to_timedelta(Y.alarm, unit="h") + pd.Timedelta("15min"))
Y["hs"] = pd.to_datetime(Y.hs)
for N in NS: Y[f"s{N}"] = np.nan
for t, g in Y.groupby("ticker"):
    p = HERE / "h1_cache" / f"{t}.csv"
    if not p.exists(): continue
    h = pd.read_csv(p, index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    e = h.Close.ewm(span=34, adjust=False).mean().shift(1)          # as of the last completed hour, like the rule
    pos = {k: i for i, k in enumerate(e.index)}
    for ix, r in g.iterrows():
        i = pos.get(r.hs)
        if i is None or i < 200: continue
        for N in NS: Y.at[ix, f"s{N}"] = (e.iloc[i] - e.iloc[i - N]) / e.iloc[i - N] * 100
Y["grp"] = np.where(Y.gap < 0, "kept (EMA8<EMA34)", "removed (EMA8>=EMA34)")
Y.to_csv(HERE / "ema34_slope.csv", index=False)
print("rows", len(Y), "| slope known", int(Y.s5.notna().sum()))


def st(g):
    o = g.out; r = g.ret.mean() * 1000
    return f"| {len(g)} | {(o == 'target').mean()*100:.0f} | {(o == 'stop').mean()*100:.0f} | {r - 85:+.0f} |"


for s, nm, per, al in (("a", "30m Jun-Sep 2026 (warm-up fixed)", 7, [2, 3, 4]), ("b", "1H 2024-Sep 2026", 4, [10, 11])):
    z = Y[(Y.set == s) & Y.s5.notna()].copy(); z["p"] = z.date.str[:per]
    for N in NS:
        z["sb"] = pd.cut(z[f"s{N}"], [-99, -0.1, 0.1, 99], labels=["falling", "flat", "rising"])
        print(f"\n## {nm} -- slope over {N}h\n| group | EMA34 | n | target % | stop % | Rs net | by period |\n|---|---|---|---|---|---|---|")
        for (gname, sb), g in z.groupby(["grp", "sb"], observed=True):
            pp = (g.groupby("p").ret.mean() * 1000 - 85).round(0).astype(int).to_dict()
            print(f"| {gname} | {sb} " + st(g) + " " + " ".join(f"{k[2:] if per == 4 else k[5:]}:{v:+d}" for k, v in pp.items()) + " |")
        for lab, keep in (("today: crossover", z.gap < 0), (f"on top: crossover + slope{N}<0", (z.gap < 0) & (z[f"s{N}"] < 0)),
                          (f"instead: slope{N}<0 only", z[f"s{N}"] < 0)):
            pk = z[keep & z.alarm.isin(al)].sort_values(["date", "alarm", "dist"]).groupby("date").head(1)
            pp = (pk.groupby("p").ret.mean() * 1000 - 85).round(0).astype(int).to_dict()
            print(f"plan {lab:30s} n {len(pk):3d} | target {(pk.out == 'target').mean()*100:.0f}% stop {(pk.out == 'stop').mean()*100:.0f}% | "
                  f"net/trade {pk.ret.mean()*1000 - 85:+.0f} | total {pk.ret.sum()*1000 - 85*len(pk):+,.0f} | " + " ".join(f"{k[2:] if per == 4 else k[5:]}:{v:+d}" for k, v in pp.items()))
