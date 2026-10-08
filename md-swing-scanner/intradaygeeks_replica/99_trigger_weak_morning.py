"""Pre-placed trigger (98) on already-weak mornings (user, 2026-10-08: on drawdown days the fall after a rejection is fast,
so by 10:45 the move is gone -- catch it at the touch). Spec fixed before running:
  Population: script 98's fills armed at 10:15 (preplaced_trigger.csv, all fills, every variant).
  Day conditions known at 10:15:
    nifty = Nifty at 10:15 (close of the 09:15 hour bar) vs yesterday's close: < -0.3% weak / -0.3..+0.3 flat / > +0.3 strong
    breadth = share of the 150 most liquid stocks (fixed list: highest mean daily Rs traded over the window -- universe
    choice only, not a signal) above yesterday's close at 10:15: < 35% bearish / 35-65 mixed / > 65 bullish
  Report per group: fills, target / stall / stop %, Rs net per trade, total, by month (main variant) and all 4 variants.
  Real = weak (or bearish) group positive net in >= 3 of 4 months for the main variant (EMA-0.2 / +0.3) with the other
  variants agreeing in sign, and label-shuffle p < 0.05 for weak-vs-rest (5,000)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import INDEX_INTRADAY_DIR, INTRADAY_5M_DIR as M5, DAILY_DIR
HERE = Path(__file__).resolve().parent

X = pd.read_csv(HERE / "preplaced_trigger.csv"); X = X[X.arm == "10:15"].copy()
days = sorted(X.date.unique())
n = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_1h.csv", index_col=0, parse_dates=True)
n.index = n.index.tz_convert("Asia/Kolkata").tz_localize(None)
dc = n.Close.groupby(n.index.normalize()).last()
nifty = {}
for d in days:
    D = pd.Timestamp(d); b = n[n.index == D + pd.Timedelta("9h15min")]; prev = dc[dc.index < D]
    if len(b) and len(prev): nifty[d] = (b.Close.iloc[0] / prev.iloc[-1] - 1) * 100

# breadth: 150 most liquid (mean Rs traded over the window), share above yesterday's close at 10:15
tv = {}
for p in M5.glob("*.csv"):
    if p.stem.startswith("_"): continue
    try:
        dd = pd.read_csv(DAILY_DIR / f"{p.stem}.csv", index_col=0, parse_dates=True)
        w = dd[(dd.index >= "2026-06-10") & (dd.index < "2026-10-01")]
        tv[p.stem] = float((w.Close * w.Volume).mean())
    except Exception: pass
top = sorted(tv, key=tv.get, reverse=True)[:150]
up = {d: [0, 0] for d in days}
for t in top:
    m = pd.read_csv(M5 / f"{t}.csv", index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
    dd = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).Close
    for d in days:
        D = pd.Timestamp(d); b = m[(m.index >= D + pd.Timedelta("9h15min")) & (m.index < D + pd.Timedelta("10h15min"))]
        pc = dd[dd.index < D]
        if len(b) and len(pc): up[d][0] += int(b.Close.iloc[-1] > pc.iloc[-1]); up[d][1] += 1
breadth = {d: v[0] / v[1] * 100 for d, v in up.items() if v[1] > 50}
X["nifty"] = X.date.map(nifty); X["breadth"] = X.date.map(breadth)
X["ng"] = pd.cut(X.nifty, [-99, -0.3, 0.3, 99], labels=["weak < -0.3%", "flat", "strong > +0.3%"])
X["bg"] = pd.cut(X.breadth, [-1, 35, 65, 101], labels=["bearish < 35%", "mixed", "bullish > 65%"])
X.to_csv(HERE / "trigger_weak_morning.csv", index=False)
print(f"days: {len(days)} | nifty known {len(nifty)} | breadth known {len(breadth)} | days by nifty group: "
      f"{pd.Series({d: pd.cut([v], [-99, -0.3, 0.3, 99], labels=['weak', 'flat', 'strong'])[0] for d, v in nifty.items()}).value_counts().to_dict()}")


def st(g):
    o = g.why; r = g.ret.mean() * 1000
    return f"| {len(g)} | {g.date.nunique()} | {(o == 'target').mean()*100:.0f} | {(o == 'stall').mean()*100:.0f} | {(o == 'stop').mean()*100:.0f} | {r - 85:+.0f} | {g.ret.sum()*1000 - 85*len(g):+,.0f} |"


rng = np.random.default_rng(99)
for col, nm in (("ng", "Nifty at 10:15 vs yesterday"), ("bg", "breadth at 10:15")):
    for a, b in [(0.2, 0.3), (0.1, 0.3), (0.2, 0.2), (0.1, 0.2)]:
        z = X[(X.a == a) & (X.b == b)].dropna(subset=[col])
        print(f"\n## {nm} -- trigger EMA-{a}% / stop EMA+{b}%\n| group | fills | days | target % | stall % | stop % | Rs net/trade | total net |\n|---|---|---|---|---|---|---|---|")
        for k, g in z.groupby(col): print(f"| {k} " + st(g))
        if (a, b) == (0.2, 0.3):
            first = z[col].cat.categories[0]
            print("net by month: " + " | ".join(f"{k}: " + " ".join(f"{m[5:]}:{v:+.0f}(n{c})" for m, v, c in zip(
                g.groupby(g.date.str[:7]).ret.mean().index, g.groupby(g.date.str[:7]).ret.mean().values * 1000 - 85, g.groupby(g.date.str[:7]).size().values))
                for k, g in z.groupby(col)))
            # the condition is a DAY label and fills cluster by day -> shuffle the labels across days, not across fills
            dl = z.groupby("date")[col].first(); dd = z.date.values; r = z.ret.values
            def gap(lab):
                lb = pd.Series(dd).map(lab).values == first
                return r[lb].mean() - r[~lb].mean()
            dlt = gap(dl)
            sh = np.array([gap(pd.Series(rng.permutation(dl.values), index=dl.index)) for _ in range(5000)])
            print(f"{first} minus rest: {dlt*1000:+.0f} Rs/trade, day-level shuffle p {np.mean(np.abs(sh) >= abs(dlt)):.3f}")
