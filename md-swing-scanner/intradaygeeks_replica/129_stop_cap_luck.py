"""Stop cap sweet spot + LUCK test (user, 2026-10-09: 'nothing is fixed now; what if luck gives me only the wide-stop SLs?').
Spec fixed before running. Setups: 10:15 candle, script 127 population with ATR >= 2%, target 0.5 x ATR, only if target >= 2 x
stop. Fixed Rs1 lakh position (user's mental model), charges Rs85. Stop caps (candle-high stop must be <= cap): 0.5 / 0.6 /
0.75 / 0.9 / 1.0% / none. Per cap: setups, days, target/stall/stop %, avg win Rs, avg loss Rs, max single loss Rs, Rs/trade.
LUCK: 2,000 simulated paths, each takes ONE RANDOM setup per trading day that has one (seeded): total Rs (5th / median / 95th
pct), max drawdown Rs (median / 95th worst), longest losing streak (median / 95th worst). Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
sys.argv += ["--hour", "10:15"]
__file__ = str(Path(__file__).resolve())
exec(open(Path(__file__).resolve().parent / "127_atr_filter_needed.py").read().split("BANDS = ")[0])
G = R[(R.tgt == "0.5 x ATR") & (R.atrp >= 2.0)].copy(); G = G[G.tp >= 2 * G.stop]
G["rs1L"] = G.ret * 1000 - 85
rng = np.random.default_rng(7)


def luck(g, runs=2000):
    days = sorted(g.date.unique()); by = [g[g.date == d].rs1L.values for d in days]
    tot, dd, st = [], [], []
    for _ in range(runs):
        x = np.array([b[rng.integers(len(b))] for b in by]); eq = np.cumsum(x)
        tot.append(eq[-1]); dd.append((eq - np.maximum.accumulate(eq)).min())
        s = (x <= 0).astype(int); runs_ = np.diff(np.flatnonzero(np.r_[1, np.diff(s) != 0, 1])); st.append(max((r for r, v in zip(runs_, s[np.r_[0, np.cumsum(runs_)[:-1]]]) if v == 1), default=0))
    q = lambda a, p: np.percentile(a, p)
    return (f"{q(tot,5):+,.0f} / {q(tot,50):+,.0f} / {q(tot,95):+,.0f} | {q(dd,50):,.0f} / {q(dd,5):,.0f} | {q(st,50):.0f} / {q(st,95):.0f}")


print("| stop cap | setups | days | target / stall / stop % | avg win Rs | avg loss Rs | max single loss Rs | Rs/trade | LUCK total Rs 5th / median / 95th | max drawdown median / bad-luck | losing streak median / bad-luck |\n|---|---|---|---|---|---|---|---|---|---|---|")
for lab, cap in (("<= 0.5%", 0.5), ("<= 0.6%", 0.6), ("<= 0.75%", 0.75), ("<= 0.9%", 0.9), ("<= 1.0%", 1.0), ("no cap", 99)):
    g = G[G.stop <= cap]; o = g.out
    print(f"| {lab} | {len(g):,} | {g.date.nunique()} | {(o=='target').mean()*100:.0f} / {(o=='stall').mean()*100:.0f} / {(o=='stop').mean()*100:.0f} | "
          f"{g.rs1L[g.rs1L > 0].mean():+,.0f} | {g.rs1L[g.rs1L <= 0].mean():+,.0f} | {g.rs1L.min():+,.0f} | {g.rs1L.mean():+.0f} | {luck(g)} |")


# 2026-10-09 comparison rows (same luck test): fixed 1% with stop <= 0.5% (the old rule), 0.35 x ATR and 0.25 x ATR with >= 1:2
print("\n| config | setups | days | t/s/s % | avg win | avg loss | max loss | Rs/trade | LUCK 5th/med/95th | DD med/bad | streak med/bad |")
for lab, tg in (("fixed 1%, stop<=0.5%", "fixed 1%"), ("0.35xATR, >=1:2", "0.35 x ATR"), ("0.25xATR, >=1:2", "0.25 x ATR")):
    g = R[(R.tgt == tg) & (R.atrp >= 2.0)]; g = g[g.tp >= 2 * g.stop].copy(); g["rs1L"] = g.ret * 1000 - 85; o = g.out
    print(f"| {lab} | {len(g):,} | {g.date.nunique()} | {(o=='target').mean()*100:.0f}/{(o=='stall').mean()*100:.0f}/{(o=='stop').mean()*100:.0f} | {g.rs1L[g.rs1L>0].mean():+,.0f} | {g.rs1L[g.rs1L<=0].mean():+,.0f} | {g.rs1L.min():+,.0f} | {g.rs1L.mean():+.0f} | {luck(g)} |")
