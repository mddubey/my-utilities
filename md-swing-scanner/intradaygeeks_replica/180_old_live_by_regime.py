"""Old live version (plan B rules, 1H 3-year set, red, >= Rs100) split by Nifty above / below its 200-day (user, 2026-10-11: does the
pre-v1 live rejection work in the bear regime?). All setups and one-a-day (11:15 else 12:15); all vs liquid >= Rs15 lakh/5m. Results only."""
import os, sys; os.chdir("/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/intradaygeeks_replica")
__file__ = os.path.abspath("114_liquidity_floor_plan_timing.py")
exec(open("114_liquidity_floor_plan_timing.py").read().split('\nif __name__ == "__main__":')[0])
import pandas as pd
from data.paths import DAILY_DIR
G = pd.read_csv(HERE / "green_rejection.csv"); G = G[(~G.green) & (G.qc >= 100)].copy(); G["out"] = G.why.replace({"time": "stall", "eod": "stall"})
A = G[(G.set == "a") & G.alarm.isin([2, 3, 4])].copy()
ratio = 0.72
B = enrich_b(G[G.set == "b"].copy()); B["liq"] = B.liq_mean * ratio
N = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index(); n200 = (N.Close > N.Close.rolling(200).mean()).shift(1)
B["n200"] = [n200.get(pd.Timestamp(d)) for d in B.date]
def rw(lab, g):
    o = g.out; y = " / ".join(f"{(g[g.date.str[:4] == k].ret.mean()*1000-85):+.0f} ({(g.date.str[:4] == k).sum()})" for k in ("2024", "2025", "2026"))
    av = " / ".join(f"{g[o == k].ret.mean()*1000-85:+.0f}" for k in ("target", "stall", "stop"))
    return f"| {lab} | {len(g)} | {(o=='target').mean()*100:.0f} / {(o=='stall').mean()*100:.0f} / {(o=='stop').mean()*100:.0f} | {av} | {g.ret.mean()*1000-85:+.0f} | {y} |"
print(f"3-year 1H set, old live rules (red, >= Rs100): {len(B)} setups {B.date.min()}..{B.date.max()}")
print("| group | trades | target / stall / stop % | avg Rs t / s / s | Rs/trade @1L | 2024 / 2025 / 2026 (n) |\n|---|---|---|---|---|---|")
for ul, f in (("all", lambda d: d.liq == d.liq), ("liquid >= Rs15L", lambda d: d.liq >= 15)):
    for reg in (True, False):
        g = B[f(B) & (B.n200 == reg)]
        print(rw(f"{ul}, Nifty {'above' if reg else 'BELOW'} 200d, ALL setups", g))
        print(rw(f"{ul}, Nifty {'above' if reg else 'BELOW'} 200d, ONE a day (11:15 else 12:15)", pick(g)))
Z = B[(B.n200 == False) & (B.date >= "2026-03-01")]
print("\nbear phase 2026-03..09, by month (Rs/trade @1L, trades): all setups | liquid all setups | liquid one-a-day")
for m, g in Z.groupby(Z.date.str[:7]):
    l = g[g.liq >= 15]; p = pick(l)
    print(f"| {m} | {g.ret.mean()*1000-85:+.0f} ({len(g)}) | {l.ret.mean()*1000-85:+.0f} ({len(l)}) | {p.ret.mean()*1000-85:+.0f} ({len(p)}) |")
