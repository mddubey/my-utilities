"""RQ-CD2: after an EOD-confirmed BC breakout (Close > high10_prior, vol z >= 1.5, base_filters_pass
on Day 0's own row -- legitimate, the decision is at the close), does the stock actually keep
breaking out on Day+1?

Day+1 outcome classes (pre-declared, exhaustive):
  CONTINUED  C1 > H0                      (closes above the breakout day's high)
  EXT_ONLY   H1 > H0 and C1 <= H0, C1 > C0 (new high intraday, closes back under H0 but above C0)
  HELD       H1 <= H0 and C1 > C0          (no new high, still closes above C0)
  FADED      C1 <= C0 and C1 > pivot       (closes at/below C0, still above the 10d pivot)
  FAILED     C1 <= pivot                   (back below the 10d pivot)
Context: closed above H0 at any close within D+3 / D+5.
Comparison groups, same tickers/dates: CLOSE_NORMVOL (Close > pivot, vol z < 1.5, same filters),
ORDINARY (every day). Regime gate (Nifty ADX>=20 & Close>SMA200) reported as a split, not a filter.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import backtest  # noqa: E402
from market_regime import market_trending  # noqa: E402
from signals import base_filters_pass, VOL_ZSCORE_MIN  # noqa: E402

OUT = Path(__file__).resolve().parent
START, END = "2021-09-29", "2026-09-17"
CLASSES = ["CONTINUED", "EXT_ONLY", "HELD", "FADED", "FAILED"]


def events():
    tickers = sorted(pd.read_csv(ROOT / "nifty500_universe.csv", header=None)[0])
    out = []
    for n, t in enumerate(tickers):
        if n % 100 == 0:
            print(f"{n}/{len(tickers)}", flush=True)
        try:
            d = backtest.load(t)
        except FileNotFoundError:
            continue
        f = pd.DataFrame({"ticker": t, "d0": d.index, "piv": d.high10_prior.values, "H0": d.High.values,
                          "C0": d.Close.values, "volz": d.vol_zscore.values})
        for k in (1, 2, 3, 4, 5):
            f[f"H{k}"] = d.High.shift(-k).values
            f[f"C{k}"] = d.Close.shift(-k).values
        ca = d.corp_action_day.astype(int)
        f["ca5"] = sum(ca.shift(-k).fillna(1) for k in range(0, 6)).values
        f = f[(f.d0 >= START) & (f.d0 <= END) & (f.ca5 == 0) & f.C5.notna() & f.piv.notna()].copy()
        above = f.C0 > f.piv
        f["filt"] = False
        idx = f.index[above.values]
        f.loc[idx, "filt"] = d.loc[f.loc[idx, "d0"]].apply(base_filters_pass, axis=1).values
        f["group"] = "ORDINARY"
        f.loc[above & f.filt & (f.volz >= VOL_ZSCORE_MIN), "group"] = "BREAKOUT"
        f.loc[above & f.filt & ~(f.volz >= VOL_ZSCORE_MIN), "group"] = "CLOSE_NORMVOL"
        out.append(f)
    ev = pd.concat(out, ignore_index=True)
    c = np.select([ev.C1 > ev.H0, (ev.H1 > ev.H0) & (ev.C1 > ev.C0), ev.C1 > ev.C0, ev.C1 > ev.piv],
                  CLASSES[:4], CLASSES[4])
    ev["cls"] = c
    ev["cont_d3"] = (ev[["C1", "C2", "C3"]].max(axis=1) > ev.H0)
    ev["cont_d5"] = (ev[["C1", "C2", "C3", "C4", "C5"]].max(axis=1) > ev.H0)
    ev["year"] = ev.d0.dt.year
    dates = ev.loc[ev.group != "ORDINARY", "d0"].unique()
    reg = {dt: market_trending(dt, require_above_sma200=True) for dt in dates}
    ev["regime_open"] = ev.d0.map(reg)
    ev.to_csv(OUT / "events_cd2.csv", index=False)
    return ev


def row(name, x):
    p = x.cls.value_counts(normalize=True).reindex(CLASSES).fillna(0) * 100
    return (f"| {name} | {len(x):,} | " + " | ".join(f"{v:.1f}" for v in p)
            + f" | {x.cont_d3.mean()*100:.1f} | {x.cont_d5.mean()*100:.1f} |")


def main():
    ev = events()
    hdr = ("| group | n | CONTINUED (C1>H0) | EXT_ONLY | HELD | FADED | FAILED (C1<=pivot) | closed>H0 by D+3 | by D+5 |\n"
           "|---|---|---|---|---|---|---|---|---|")
    G = {"BREAKOUT (close>pivot, vol z>=1.5, filters)": ev[ev.group == "BREAKOUT"],
         "CLOSE_NORMVOL (close>pivot, vol z<1.5, filters)": ev[ev.group == "CLOSE_NORMVOL"],
         "ORDINARY day": ev[ev.group == "ORDINARY"]}
    print("\n=== Day+1 outcome, % of events ===\n" + hdr)
    for k, v in G.items():
        print(row(k, v))
    b = ev[ev.group == "BREAKOUT"]
    print("\n=== BREAKOUT by regime gate ===\n" + hdr)
    for k, v in b.groupby("regime_open"):
        print(row(f"regime {'OPEN' if k else 'CLOSED'}", v))
    print("\n=== BREAKOUT by year ===\n" + hdr)
    for y, v in b.groupby("year"):
        print(row(str(y), v))
    print("\n=== CLOSE_NORMVOL by year (comparison) ===\n" + hdr)
    for y, v in ev[ev.group == "CLOSE_NORMVOL"].groupby("year"):
        print(row(str(y), v))
    smp = b.sample(5, random_state=11)
    print("\n=== 5 random BREAKOUT events for hand-check ===")
    print(smp[["ticker", "d0", "piv", "H0", "C0", "volz", "H1", "C1", "cls", "cont_d5"]].to_string(index=False))


if __name__ == "__main__":
    main()
