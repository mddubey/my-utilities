"""Wider stop on drawdown days, still 1:2 (user, 2026-10-08: "on a drawdown day the stock is likely to fall more -- is it OK
if the stop is 0.7% as long as it still gives 1:2?"). Spec fixed before running:
  Population: how_low_P1.csv = current rules WITHOUT the 2:1 cap (close within 0.5% of the 1H EMA34, any stop), both sets
  (a = 30m Jun-Sep 2026, b = 1H 2024 - Sep 2026). Stop = candle high (stop_pct).
  Stop buckets: <= 0.5 (today's rule) / 0.5-0.75 / 0.75-1.0 %.
  Day type at entry: Nifty's last COMPLETED hourly close at the entry time vs yesterday's close: drawdown < -0.3%
  (deep check < -0.75%), flat -0.3..+0.3, strong > +0.3%. (Hourly Nifty file; 30m alarms use the last full hour.)
  Outcome with a 1:2 target: +2 x stop if the price reaches entry - 2 x stop before the stop (mfe_stop >= 2 x stop_pct,
  walk to 15:15), else -stop if stopped, else the 15:15 close. Rs per Rs 1 lakh, net = gross - 85.
  Pass = 0.5-0.75% bucket on drawdown days positive net in BOTH sets, most months / years, day-level shuffle p < 0.05
  (drawdown vs rest, within that bucket)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import INDEX_INTRADAY_DIR
HERE = Path(__file__).resolve().parent

y = pd.read_csv(HERE / "how_low_P1.csv")
n = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_1h.csv", index_col=0, parse_dates=True)
n.index = n.index.tz_convert("Asia/Kolkata").tz_localize(None)
dc = n.Close.groupby(n.index.normalize()).last()
day = pd.to_datetime(y.date)
ent = np.where(y.set == "a", day + pd.Timedelta("9h15min") + (y.alarm + 1) * pd.Timedelta("30min"),
               day + pd.to_timedelta(y.alarm + 1, unit="h") + pd.Timedelta("15min"))
y["entry_t"] = pd.to_datetime(ent)
ends = n.index + pd.Timedelta("60min")
nv = []
for d, t in zip(day, y.entry_t):
    bars = n[(n.index.normalize() == d) & (ends <= t)]; prev = dc[dc.index < d]
    nv.append((bars.Close.iloc[-1] / prev.iloc[-1] - 1) * 100 if len(bars) and len(prev) else np.nan)
y["nifty"] = nv
y = y.dropna(subset=["nifty"])
y["sb"] = pd.cut(y.stop_pct, [0, 0.5, 0.75, 1.0], labels=["<=0.5", "0.5-0.75", "0.75-1.0"])
y = y.dropna(subset=["sb"])
y["dt"] = pd.cut(y.nifty, [-99, -0.3, 0.3, 99], labels=["drawdown < -0.3%", "flat", "strong > +0.3%"])
hit = y.mfe_stop >= 2 * y.stop_pct
y["out"] = np.where(hit, "2R target", np.where(y.stopped, "stop", "15:15"))
y["r2"] = np.where(hit, 2 * y.stop_pct, np.where(y.stopped, -y.stop_pct, y.close_ret))
y.to_csv(HERE / "wide_stop_drawdown.csv", index=False)
rng = np.random.default_rng(100)


def st(g):
    r = g.r2.mean() * 1000
    return f"| {len(g)} | {(g.out == '2R target').mean()*100:.0f} | {(g.out == 'stop').mean()*100:.0f} | {(g.out == '15:15').mean()*100:.0f} | {r:+.0f} | {r - 85:+.0f} | {g.r2.sum()*1000 - 85*len(g):+,.0f} |"


for s, nm, per in (("a", "30m set, Jun-Sep 2026", 7), ("b", "1H set, 2024 - Sep 2026", 4)):
    z = y[y.set == s].copy(); z["p"] = z.date.str[:per]
    print(f"\n## {nm}\n| stop bucket | day type | n | 2R hit % | stop % | out 15:15 % | Rs gross | Rs net | total net |\n|---|---|---|---|---|---|---|---|---|")
    for sb, g1 in z.groupby("sb"):
        for dt, g in g1.groupby("dt"):
            print(f"| {sb} | {dt} " + st(g))
        dd = g1[g1.nifty < -0.75]
        if len(dd): print(f"| {sb} | (deep < -0.75%) " + st(dd))
    w = z[z.sb == "0.5-0.75"]
    for dt, g in w.groupby("dt"):
        pp = g.groupby("p").r2.mean() * 1000 - 85
        print(f"0.5-0.75 / {dt} net by period: " + " ".join(f"{k}:{v:+.0f}(n{c})" for k, v, c in zip(pp.index, pp.values, g.groupby("p").size().values)))
    lab = w.groupby("date").dt.first(); dates = w.date.values; r = w.r2.values
    def gap(L):
        m = pd.Series(dates).map(L).values == "drawdown < -0.3%"
        return r[m].mean() - r[~m].mean() if m.any() and (~m).any() else np.nan
    g0 = gap(lab); sh = np.array([gap(pd.Series(rng.permutation(lab.values), index=lab.index)) for _ in range(5000)])
    print(f"0.5-0.75: drawdown minus rest {g0*1000:+.0f} Rs/trade, day-level shuffle p {np.nanmean(np.abs(sh) >= abs(g0)):.3f}")
