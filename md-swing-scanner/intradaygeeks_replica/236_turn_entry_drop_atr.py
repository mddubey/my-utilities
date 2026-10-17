"""DROP THE ATR FILTERS from the turn-entry version (user, 2026-10-17: 'get rid of a lot of filters ... the mechanical ones; start with ATR').
Spec fixed before running. 233's events (turn 0.1% below the touch high, fixed 0.5% stop, 1% target / 15:15 -- F's trail is ~equal, 235),
v1's other day filters kept (liquid, >= Rs100, gap -0.25..+0.5, uptrend), daily 8 not in the path.
  WITH ATR (233 fair):  ATR >= 2%, branch A (opened 0-0.5% below the line) or B (opened above AND ATR >= 3%).
  WITHOUT ATR:          no ATR floor, branch A or B = opened above at any ATR.
  ATR buckets (daily ATR14 %, yesterday): < 1.5 / 1.5-2 / 2-2.5 / 2.5-3 / 3-4 / >= 4. Branch A vs B shown per bucket.
  Report net Rs per Rs1 lakh and per Rs1k risk, target / stall / stop, by month, top-10 days removed; one-a-day plan (first come)."""
import pandas as pd, numpy as np
from pathlib import Path
HERE = Path(__file__).resolve().parent; COST = 0.085
A = pd.read_csv(HERE / "v1_turn_entry.csv"); A = A[A.X == 0.001]
F = A[(A.liq >= 15) & (A.pc >= 100) & (A.gap > -0.25) & (A.gap <= 0.5) & A.up & ~A.in_path & A.ov.notna()].copy()
F["branch"] = np.where((F.ov >= -0.5) & (F.ov < 0), "A", np.where(F.ov >= 0, "B", "-"))
F = F[F.branch != "-"]
WITH = F[(F.atr >= 2) & ((F.branch == "A") | (F.atr >= 3))]; WITHOUT = F
def cell(x):
    if not len(x): return "0 | | | | | |"
    w = x.fixed_why; r = x.fixed_ret; t10 = x.groupby("date").fixed_ret.sum().nlargest(10).index
    mo = " / ".join(f"{(g.fixed_ret.mean()-COST)*1000:+.0f}" for _, g in x.groupby(x.date.str[:7]))
    return (f"{len(x)} | {(w=='target').mean()*100:.0f} / {(w=='stall').mean()*100:.0f} / {(w=='stop').mean()*100:.0f}% | {(r.mean()-COST)*1000:+.0f} | "
            f"{((r-COST)/0.5).mean()*1000:+.0f} | {(x[~x.date.isin(t10)].fixed_ret.mean()-COST)*1000:+.0f} | {mo}")
H = "| group | n | target / stall / stop | net Rs @1L | Rs @1k | top-10 days removed | months 06 / 07 / 08 / 09 / 10 |\n|---|---|---|---|---|---|---|"
print(f"### With vs without the ATR filters\n{H}")
print(f"| WITH ATR (233 fair group) | {cell(WITH)} |"); print(f"| WITHOUT ATR | {cell(WITHOUT)} |")
print(f"| added by dropping ATR | {cell(WITHOUT[~WITHOUT.index.isin(WITH.index)])} |")
B = pd.cut(F.atr, [0, 1.5, 2, 2.5, 3, 4, 99], right=False, labels=["< 1.5%", "1.5-2%", "2-2.5%", "2.5-3%", "3-4%", ">= 4%"])
print(f"\n### By ATR bucket (no ATR filter)\n{H}")
for b in B.cat.categories:
    x = F[B == b]; print(f"| ATR {b} | {cell(x)} |")
    for br in ("A", "B"): print(f"| ATR {b}, branch {br} | {cell(x[x.branch == br])} |")
def plan(x):
    o = x.sort_values(["date", "t_entry"]).drop_duplicates("date"); n = (o.fixed_ret - COST) * 1000; eq = n.cumsum()
    s = (n < 0).astype(int).astype(str).str.cat(); return f"{len(o)} trades / {x.date.nunique()} days, {n.mean():+.0f}/trade, total {eq.iloc[-1]:+,.0f}, max DD {(eq-eq.cummax()).min():,.0f}, worst streak {max(len(k) for k in s.split('0'))}"
print("\nOne a day, first come:"); print("  WITH ATR:   ", plan(WITH)); print("  WITHOUT ATR:", plan(WITHOUT))
print("  WITHOUT ATR but ATR >= 3% only:", plan(F[F.atr >= 3]))
