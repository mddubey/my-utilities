"""CURRENT STATS of the HOURLY 34 REJECTION (formerly v1; simplified rules adopted 2026-10-18 = 203's default): liquid, >= Rs100, ATR >= 3%, any trend,
10:15 candle red at the 1H EMA34, doji skip, daily 8 not in the 1% target path, stop = candle high or the earlier wick if it fits in 0.5% (stop <= 0.5%),
1% target, out after 5 hourly bars / the day's last bar. 3-year 1H set 2024-01..2026-09, both Nifty regimes. Net of Rs85 per Rs1 lakh.
Report: per setup and one trade a day (highest ATR); win-rate stack (R > 0 / >= 0.25 / >= 0.5 / >= 1), payoff ratio, mean R, max drawdown, worst losing streak."""
import sys, os, io, contextlib, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
import pandas as pd, numpy as np
sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()): G = runpy.run_path("244_stop_above_earlier_wick.py")
X = G["X"].copy()
fb = X.earlier & (X.user_risk > 0.5)                        # the scan: earlier wick only if it fits in 0.5%, else the candle stop
for k in ("ret", "o", "risk", "rs1L", "rs1k"): X.loc[fb, f"u_{k}"] = X.loc[fb, f"b_{k}"]
X["R"] = (X.u_ret - 0.085) / X.u_risk; X["rs1L"] = X.u_rs1L; X["rs1k"] = X.u_rs1k; X["o"] = X.u_o
d = pd.to_datetime(X.date.astype(str).str[:10]); months = (d.max() - d.min()).days / 30.4
def stack(x):
    w = x.R[x.R > 0]; l = x.R[x.R <= 0]
    return (f"{(x.R > 0).mean()*100:.0f} / {(x.R >= 0.25).mean()*100:.0f} / {(x.R >= 0.5).mean()*100:.0f} / {(x.R >= 1).mean()*100:.0f}%", f"{w.mean() / abs(l.mean()):.2f}" if len(l) else "-")
def line(lab, x):
    st, pr = stack(x); s = (x.rs1L < 0).astype(int).astype(str).str.cat(); eq = x.sort_values("date").rs1k.cumsum()
    return (f"| {lab} | {len(x)} | {(x.o=='target').mean()*100:.0f} / {(x.o=='stall').mean()*100:.0f} / {(x.o=='stop').mean()*100:.0f}% | {x.u_risk.median():.2f}% | "
            f"{x.rs1L.mean():+.0f} | {x.rs1k.mean():+.0f} | {x.R.mean():+.2f} | {st} | {pr} |")
print(f"HOURLY 34 REJECTION -- {len(X)} setups, {d.min():%Y-%m-%d} .. {d.max():%Y-%m-%d} ({months:.0f} months, {len(X)/months:.1f} a month)")
H = "| group | setups | target / stall / stop | median stop | net Rs @1L | net Rs @1k risk | mean R | win stack R>0 / >=0.25 / >=0.5 / >=1 | payoff ratio |\n|---|---|---|---|---|---|---|---|---|"
print(f"\n### All setups\n{H}"); print(line("ALL", X))
t10 = X.groupby("date").rs1L.sum().nlargest(10).index; print(line("top-10 days removed", X[~X.date.isin(t10)]))
for y in ("2024", "2025", "2026"): print(line(f"year {y}", X[X.yr == y]))
print(line("Nifty above 200d", X[X.n200 == True])); print(line("Nifty below 200d", X[X.n200 == False]))
print(line("stock uptrend (info)", X[X.up])); print(line("stock downtrend (info)", X[~X.up]))
print(line("stop = earlier wick", X[X.earlier & ~fb])); print(line("stop = candle high", X[~(X.earlier & ~fb)]))
O = X.sort_values(["date", "atrp"], ascending=[True, False]).drop_duplicates("date").sort_values("date")
eq1L = O.rs1L.cumsum(); eq1k = O.rs1k.cumsum(); s = (O.rs1L < 0).astype(int).astype(str).str.cat()
print(f"\n### One trade a day (pick = highest ATR) -- {len(O)} trades on {len(O)} days ({len(O)/months:.1f} a month)\n{H}"); print(line("ONE A DAY", O))
for y in ("2024", "2025", "2026"): print(line(f"year {y}", O[O.yr == y]))
print(f"\nOne a day, equity: at a fixed Rs1 lakh per trade total {eq1L.iloc[-1]:+,.0f}, max drawdown {(eq1L-eq1L.cummax()).min():,.0f}; "
      f"at a fixed Rs1,000 risk per trade total {eq1k.iloc[-1]:+,.0f}, max drawdown {(eq1k-eq1k.cummax()).min():,.0f}; worst losing streak {max(len(k) for k in s.split('0'))} trades")
mo = O.groupby(O.date.astype(str).str[:7]).rs1k.sum(); print(f"months positive {(mo > 0).sum()} of {len(mo)}; worst month {mo.min():+,.0f}, best {mo.max():+,.0f} (Rs @1k risk)")
