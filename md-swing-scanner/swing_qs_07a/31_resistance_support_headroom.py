"""RQ-QS-07A-BT1-S-H1 -- Is the move size (how far it rises, how far it dips)
just noise, or does it track known resistance/support structure? (2026-10-02,
user-directed follow-up.) User's exact question: is there a nearby
overhead/floor level that would cap the realistic reward or widen the real
risk, such that some candidates should be SKIPPED even if they otherwise
look like good S/BT1 setups?

PRE-DECLARED, 3 mechanically distinct resistance levels and 3 mechanically
distinct support levels (Rule #19), all PRIOR-day-known (shift(1) before any
rolling max/min, so today's own high/low never defines "the resistance" --
that would be circular with the move being measured):
  RESISTANCE (tests against max_return_d3 -- room to rise):
    res_10d   = prior 10-day high (`high10_prior`, already a production column)
    res_52w   = prior 52-week high (fresh, shift(1).rolling(252).max())
    res_pivot = classic floor-trader R1 (`pivots.py`'s daily_pivots, prior-day
                H/L/C based, already production-used for VCP/Coiled Spring's
                resistance-exit)
  SUPPORT (tests against adverse_d3 -- room to fall before any floor):
    sup_5d    = prior 5-day low (`range5_low`, already a production column)
    sup_52w   = prior 52-week low (fresh, shift(1).rolling(252).min())
    sup_pivot = classic floor-trader S1 (same source as res_pivot)

CONTROL VARIABLE: atr14_pct (volatility) included alongside every distance
metric -- a stock that already ran hard is typically both far from
resistance AND more volatile, so any apparent resistance-distance effect
must be checked against ATR, not just reported on its own (same discipline
as checking BT1 against prior momentum/W overlap).

POPULATION: the already-built S population (166,668 rows, `s_bt1_combo.csv`)
joined to `event_matrix.csv` for max_return_d3/adverse_d3 (already computed,
not re-derived).
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots
from signals import atr

OUT_DIR = "swing_qs_07a"

print("Loading S population + joining real max_return_d3/adverse_d3...", flush=True)
s = pd.read_csv(f"{OUT_DIR}/s_bt1_combo.csv", parse_dates=["date"])[["ticker", "date"]]
em = pd.read_csv(f"{OUT_DIR}/event_matrix.csv", parse_dates=["date"],
                  usecols=["ticker", "date", "max_return_d3", "adverse_d3"])
base = s.merge(em, on=["ticker", "date"], how="left").dropna(subset=["max_return_d3", "adverse_d3"])
print(f"n={len(base):,}")

print("\nComputing prior-day-known resistance/support distances + ATR%% (per-ticker, vectorized)...", flush=True)
grouped = dict(tuple(base.groupby("ticker")))
rows_out = []
for n, t in enumerate(grouped):
    if n % 300 == 0:
        print(f"  {n}/{len(grouped)} tickers", flush=True)
    idf = load(t, daily_pivots)
    close = idf.Close
    res_52w = idf.High.shift(1).rolling(252).max()
    sup_52w = idf.Low.shift(1).rolling(252).min()
    atr_pct = atr(idf, 14) / close * 100

    feat = pd.DataFrame({
        "dist_res_10d_pct": (idf.high10_prior / close - 1) * 100,
        "dist_res_52w_pct": (res_52w / close - 1) * 100,
        "dist_res_pivot_pct": (idf.r1 / close - 1) * 100,
        "dist_sup_5d_pct": (close / idf.range5_low - 1) * 100,
        "dist_sup_52w_pct": (close / sup_52w - 1) * 100,
        "dist_sup_pivot_pct": (close / idf.s1 - 1) * 100,
        "atr_pct": atr_pct,
    })
    sub = grouped[t]
    for r in sub.itertuples():
        if r.date not in feat.index:
            continue
        row = feat.loc[r.date]
        rows_out.append(dict(ticker=t, date=r.date, max_return_d3=r.max_return_d3, adverse_d3=r.adverse_d3, **row.to_dict()))

out = pd.DataFrame(rows_out)
out.to_csv(f"{OUT_DIR}/resistance_support_headroom.csv", index=False)
print(f"\n{len(out):,} rows, saved resistance_support_headroom.csv")

print(f"\n{'='*110}\nDoes distance-to-RESISTANCE correlate with how far it actually rises (max_return_d3)?\n{'='*110}")
for f in ["dist_res_10d_pct", "dist_res_52w_pct", "dist_res_pivot_pct", "atr_pct"]:
    d = out.dropna(subset=[f, "max_return_d3"])
    print(f"  {f:22s} Spearman corr with max_return_d3 = {d[f].corr(d.max_return_d3, method='spearman'):+.3f}  (n={len(d):,})")

print(f"\n{'='*110}\nDoes distance-to-SUPPORT correlate with how far it actually dips (adverse_d3)?\n{'='*110}")
for f in ["dist_sup_5d_pct", "dist_sup_52w_pct", "dist_sup_pivot_pct", "atr_pct"]:
    d = out.dropna(subset=[f, "adverse_d3"])
    print(f"  {f:22s} Spearman corr with adverse_d3 = {d[f].corr(d.adverse_d3, method='spearman'):+.3f}  (n={len(d):,})")

print(f"\n{'='*110}\nPartial check: does dist_res_10d_pct still matter once you control for ATR%% (quartile-match)?\n{'='*110}")
d = out.dropna(subset=["dist_res_10d_pct", "max_return_d3", "atr_pct"]).copy()
d["atr_q"] = pd.qcut(d.atr_pct.rank(method="first"), 4, labels=["ATR-Q1", "ATR-Q2", "ATR-Q3", "ATR-Q4"])
for q in ["ATR-Q1", "ATR-Q2", "ATR-Q3", "ATR-Q4"]:
    dq = d[d.atr_q == q]
    corr = dq.dist_res_10d_pct.corr(dq.max_return_d3, method="spearman")
    print(f"  within {q} (similar volatility): corr(dist_res_10d_pct, max_return_d3) = {corr:+.3f}  (n={len(dq):,})")

print("\nDONE")
