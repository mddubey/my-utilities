"""Stacked 'avoid bad trades' filters, evaluated ONLY on the unseen test period (Jul 2025 - Sep 2026). Spec fixed
2026-10-02 before looking at test results. Data: 31's feature file (1H-close set). Thresholds from TRAIN only.
Stack A (mechanical): 8 features with largest |train top-vs-bottom quintile spread|; for each, skip the worst train
  quintile side (cutoff from train). Stack B (trader checklist): skip if
  B1 stretched: d8_ext_vs_d8_pct in the top train tercile (price far from daily 8-EMA)
  B2 opening gap in trade direction > 0.5%
  B3 setup bar after 12:15 (entry after 13:15)
  B4 sector moving against the trade (sector_so_s < 0; unmapped names dropped)
  B5 daily ADX > 25
  B6 price on the wrong side of VWAP"""
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
SPLIT = pd.Timestamp("2025-07-01")
X = pd.read_csv(HERE / "winners_losers_features_1h.csv", parse_dates=["date", "bar_ts"])
X["win"] = (X.R >= 0.25)
tr, te = X[X.date < SPLIT], X[X.date >= SPLIT].copy()
days = te.date.nunique()
def line(x, lab):
    if len(x) < 50: print(f"| {lab} | {len(x)} | too few |"); return
    q = x.groupby(x.date.dt.to_period("Q")).ret.mean()
    print(f"| {lab} | {len(x)} | {len(x)/days:.1f} | {x.win.mean()*100:.1f} | {x.ret.mean():+.3f} | {x.ret.median():+.3f} | {x.R.mean():+.3f} | "
          + " ".join(f"{v:+.2f}" for v in q) + f" | {(x.ret - 0.1).mean():+.3f} |")
HDR = "| group | n | trades/day | win% | mean% | med% | meanR | by quarter mean% | net @0.1% cost |\n|---|---|---|---|---|---|---|---|---|"
FEATS = ["is_short", "hour", "adx", "hadx", "dadx", "close_past_ema", "stop_pct", "stop_norm", "bar_range_pct", "avg_1h_range_pct",
         "wick_past_ema_pct", "d8_ext_vs_d8_pct", "stock_so_s", "nifty_so_s", "sector_so_s", "rvol", "atrp", "gap_s", "rsi_s",
         "ret5_s", "ret20_s", "room20", "logprice"]
sp = {}
for f in FEATS:
    a = tr[[f, "ret"]].dropna()
    if a[f].nunique() <= 2: sp[f] = (a[a[f] == 1].ret.mean() - a[a[f] == 0].ret.mean(), None); continue
    q = a[f].quantile([.2, .8]).values
    sp[f] = (a[a[f] >= q[1]].ret.mean() - a[a[f] <= q[0]].ret.mean(), q)
top8 = sorted(sp, key=lambda f: -abs(sp[f][0]))[:8]
print(f"test period: {len(te)} trades over {days} days | Stack A features (train-chosen): {top8}\n")
print("STACK A (mechanical, sequential)\n" + HDR); line(te, "BASELINE (test)")
k = te
for f in top8:
    s, q = sp[f]
    if q is None: k = k[k[f] == (1 if s > 0 else 0)]
    else: k = k[k[f] > q[0]] if s > 0 else k[k[f] < q[1]]
    line(k, f"  + skip worst fifth of {f}")
cut = tr.d8_ext_vs_d8_pct.quantile(2 / 3)
rules = [("B1 skip stretched from daily 8-EMA", lambda d: d.d8_ext_vs_d8_pct <= cut),
         ("B2 skip with-direction gap > 0.5%", lambda d: d.gap_s <= 0.5),
         ("B3 skip setups after 12:15", lambda d: d.bar_ts.dt.strftime("%H:%M") <= "12:15"),
         ("B4 skip sector against (mapped names only)", lambda d: d.sector_so_s > 0),
         ("B5 skip daily ADX > 25", lambda d: d.dadx <= 25),
         ("B6 skip wrong side of VWAP", lambda d: d.vwap_with == True)]
print("\nSTACK B (trader checklist, sequential)\n" + HDR); line(te, "BASELINE (test)")
k = te
for lab, r in rules:
    k = k[r(k)]; line(k, f"  + {lab}")
print("\nSTACK B final, by side:")
for s_ in ("short", "long"): line(k[k.side == s_], f"  {s_}")
print("\nSTACK B rules one at a time (KEPT vs REMOVED on test):\n| rule | kept n | kept mean% | removed n | removed mean% |\n|---|---|---|---|---|")
for lab, r in rules:
    m = r(te); print(f"| {lab} | {m.sum()} | {te[m].ret.mean():+.3f} | {(~m).sum()} | {te[~m].ret.mean():+.3f} |")
