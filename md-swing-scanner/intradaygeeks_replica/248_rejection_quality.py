"""REAL REJECTION vs FEEBLE (user, 2026-10-18): classify the 10:15 hourly candle (classes fixed before running, first match wins):
  NO UPPER WICK  upper wick < 10% of the range
  INDECISIVE     both wicks >= 20% of the range and within 1.5x of each other (the line cuts through)
  CLEAN          upper wick >= lower wick
  BUYER-LED      lower wick > upper wick (the rest)
Population: the hourly 34 rejection (245's X, all setups; scan stop rules), one a day. Rules: R1 = skip NO UPPER WICK; R2 = R1 + pick priority CLEAN >
INDECISIVE > BUYER-LED (ties -> highest ATR) instead of highest ATR alone. Report per class and per rule, net Rs @1L / @1k risk, entry vs line, stop, years."""
import sys, os, io, contextlib, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
import pandas as pd, numpy as np
sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()): G = runpy.run_path("245_hourly34_stats.py")
X = G["X"].copy(); N = G["G"]["N"].reset_index(drop=True); BB = G["G"]["G"]["B"]
n = N.loc[X.index]; op = n.ix.map(BB["open"]).values; lo = n.ix.map(BB["low"]).values; hi = n.high.values; cl = n.entry.values; E = n.ema34.values
rg = hi - lo; uw = (hi - np.maximum(op, cl)) / rg; lw = (np.minimum(op, cl) - lo) / rg
ratio = np.maximum(uw, lw) / np.maximum(np.minimum(uw, lw), 1e-9)
X["cls"] = np.select([uw < 0.10, (uw >= 0.2) & (lw >= 0.2) & (ratio <= 1.5), uw >= lw], ["NO UPPER WICK", "INDECISIVE", "CLEAN"], "BUYER-LED")
X["below_line"] = (1 - cl / E) * 100
PR = {"CLEAN": 0, "INDECISIVE": 1, "BUYER-LED": 2, "NO UPPER WICK": 3}; X["pri"] = X.cls.map(PR)
def line(lab, x):
    return (f"| {lab} | {len(x)} | {(x.o=='target').mean()*100:.0f} / {(x.o=='stall').mean()*100:.0f} / {(x.o=='stop').mean()*100:.0f}% | {x.rs1L.mean():+.0f} | {x.rs1k.mean():+.0f} | "
            f"{x.below_line.median():.2f}% | {x.u_risk.median():.2f}% | " + " / ".join(f"{x[x.yr == y].rs1L.mean():+.0f}" for y in ("2024", "2025", "2026")) + " |")
H = "| group | n | target / stall / stop | net @1L | net @1k risk | entry below the line (median) | stop (median) | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|"
for lab, S in (("ALL SETUPS", X), ("ONE A DAY (highest ATR, as now)", X.sort_values(["date", "atrp"], ascending=[True, False]).drop_duplicates("date"))):
    print(f"\n### {lab}\n{H}")
    for c in ("CLEAN", "INDECISIVE", "BUYER-LED", "NO UPPER WICK"): print(line(c, S[S.cls == c]))
    print(line("ALL", S))
def plan(x, key):
    o = x.sort_values(["date"] + key, ascending=[True] + [k != "atrp" for k in key[:-1]] + [False]).drop_duplicates("date"); eq = o.rs1k.cumsum(); s = (o.rs1L < 0).astype(int).astype(str).str.cat()
    return f"{len(o)} | {(o.o=='target').mean()*100:.0f} / {(o.o=='stall').mean()*100:.0f} / {(o.o=='stop').mean()*100:.0f}% | {o.rs1L.mean():+.0f} | {o.rs1k.mean():+.0f} | {o.rs1L.drop(o.rs1L.nlargest(10).index).mean():+.0f} | " + " / ".join(f"{o[o.yr == y].rs1L.mean():+.0f}" for y in ("2024", "2025", "2026")) + f" | {eq.iloc[-1]:+,.0f} / {(eq-eq.cummax()).min():,.0f} | {max(len(k) for k in s.split('0'))} |"
print("\n### ONE A DAY plans\n| plan | trades | target / stall / stop | net @1L | net @1k | @1L w/o 10 best trades | @1L 2024 / 2025 / 2026 | @1k total / max DD | worst streak |\n|---|---|---|---|---|---|---|---|---|")
print("| now: highest ATR | " + plan(X, ["atrp"]))
print("| R1: skip NO UPPER WICK, highest ATR | " + plan(X[X.cls != "NO UPPER WICK"], ["atrp"]))
print("| R2: R1 + clean first, then indecisive, then buyer-led | " + plan(X[X.cls != "NO UPPER WICK"], ["pri", "atrp"]))
