"""Robustness of the 'middle-ATR band is worse' observation (user, 2026-10-04). The 3-4% band was picked AFTER looking,
so this is the pre-declared check (declared before running):
 1. Neighbour bands 2.9-3.9 / 3.1-4.1 / 3.25-4.25 (and the original 3-4): middle vs rest, both sets, by period, shuffle p.
 2. Mechanism version without hand-picked bands: stop distance / typical candle range (nz5 = median candle range of the
    previous 5 days, 30m candles on set a, 1H on set b), in terciles.
 3. One-a-day plan variants (same alarms, first alarm with a setup):
    A current: closest to the EMA
    B user's priority: volatile (ATR >= 4%) first, then calm (< 3%), then 3-4%; closest to the EMA within a band
    C skip the 3-4% band (pick passes to the next setup / next alarm)
 Rs gross and net of ~Rs85 charges; days traded; by month (30m) / year (1H)."""
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; COST = 0.085
y = pd.read_csv(HERE / "how_low_P0.csv"); rng = np.random.default_rng(81)
for s, nm, per, al in (("a", "30m Jun-Sep 2026", 7, [3, 4]), ("b", "1H 3 years", 4, [10, 11])):
    z = y[y.set == s].copy(); z["p"] = z.date.str[:per]; r = z.ret.values
    print(f"\n################ {nm}  (all setups {len(z)}, Rs {z.ret.mean()*1000:+.0f})")
    for lo, hi in ((3.0, 4.0), (2.9, 3.9), (3.1, 4.1), (3.25, 4.25)):
        m = ((z.atrp >= lo) & (z.atrp < hi)).values; obs = r[~m].mean() - r[m].mean()
        sims = np.array([(lambda q: r[~q].mean() - r[q].mean())(rng.permutation(m)) for _ in range(5000)])
        by = z.assign(m=m).groupby(["p", "m"]).ret.mean().unstack() * 1000
        print(f"  band {lo}-{hi}%: {m.mean()*100:3.0f}% of trades | Rs {r[m].mean()*1000:+4.0f} vs rest {r[~m].mean()*1000:+4.0f} | stop {(z[m].why == 'stop').mean()*100:.0f} vs {(z[~m].why == 'stop').mean()*100:.0f}% | p={np.mean(sims >= obs):.3f} | "
              + " ".join(f"{k}: {v[True]:+.0f}/{v[False]:+.0f}" for k, v in by.iterrows()))
    z["ratio"] = z.stop_pct / z.nz5
    z["tq"] = pd.qcut(z.ratio, 3, labels=["stop small vs candle", "middle", "stop large vs candle"])
    print("  stop / typical candle range, terciles:")
    for k, g in z.groupby("tq", observed=True):
        print(f"    {k:22s} ratio {g.ratio.min():.2f}-{g.ratio.max():.2f} n={len(g)} | Rs {g.ret.mean()*1000:+4.0f} | stop {(g.why == 'stop').mean()*100:.0f}% tgt {(g.why == 'target').mean()*100:.0f}% | median ATR {g.atrp.median():.2f}%")
    c = z[z.alarm.isin(al)].copy()
    c["band"] = np.where(c.atrp >= 4, 0, np.where(c.atrp < 3, 1, 2))
    plans = {"A closest to EMA (current)": c.sort_values(["date", "alarm", "dist"]),
             "B volatile > calm > 3-4%": c.sort_values(["date", "alarm", "band", "dist"]),
             "C skip the 3-4% band": c[c.band != 2].sort_values(["date", "alarm", "dist"])}
    for k, x in plans.items():
        p = x.groupby("date").head(1)
        print(f"  PLAN {k:28s} days {len(p):3d} | Rs gross {p.ret.mean()*1000:+4.0f} net {(p.ret.mean()-COST)*1000:+4.0f} | total net {(p.ret - COST).sum()*1000:+7.0f} | "
              + " ".join(f"{q}: {g.ret.mean()*1000:+.0f}" for q, g in p.groupby("p")))
