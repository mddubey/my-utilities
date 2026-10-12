"""Is the level the CAUSE? (user, 2026-10-12: 'are they reversing from there, or is it just one factor?'). DESCRIPTIVE. 191's in-play
shorts (paper rules, 5-min mid rule). Level L = yesterday's close when it sits 0-1% below the entry (the gap-fill group), and yesterday's
low the same way. For every such trade: did the price REACH the level (a 5-min low within 0.1% of L or below) before the stop / close?
If it reached it: stopped afterwards (= turned at the level) or went through and finished at the close? If stopped WITHOUT reaching it
the level cannot be the reason. PLACEBO: clear-path trades (no level within 2%) given a fake level at the same distances (0.5% and 1%
below the entry), same counts. CONFOUND: gap-ups only, near vs far from yesterday's close. Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
src = open(HERE / "191_orb_levels_in_path.py").read().split("\ndef row(")[0]
exec(src)
from orb_common import read5_official  # 2026-10-12: official 09:15 open
from data.paths import INTRADAY_5M_DIR
cache = {}


def path(r, L):
    t = r.ticker
    if t not in cache:
        m = read5_official(t)
        m["hm"] = m.index.strftime("%H:%M"); cache[t] = m
    m = cache[t]; d = m[m.index.normalize() == pd.Timestamp(r.date)]; e = r.e; stp = e * (1 + 0.1 * r.atr / 100)
    w = d[(d.hm >= r.et) & (d.hm < "15:15")]; reached, stop_at = None, None
    for ts, b in w.iterrows():
        if reached is None and b.Low <= L * 1.001: reached = ts
        if b.High >= stp and not (ts == w.index[0] and r.o10mid != "stop"): stop_at = ts; break
    return reached, stop_at


def tab(lab, g, Lcol=None, dist=None):
    out = []
    for _, r in g.iterrows():
        L = r.pdc_px if Lcol == "pdc" else (r.pdl_px if Lcol == "pdl" else r.e * (1 - dist / 100))
        rc, sa = path(r, L)
        if r.o10mid == "stop":
            out.append("stop, never reached the level" if (rc is None or (sa is not None and rc > sa)) else "reached the level, THEN stopped")
        else:
            out.append("reached the level, went on to the close" if rc is not None else "never reached, held to the close")
    s = pd.Series(out).value_counts()
    k = ["stop, never reached the level", "reached the level, THEN stopped", "reached the level, went on to the close", "never reached, held to the close"]
    reached = s.get(k[1], 0) + s.get(k[2], 0)
    print(f"| {lab} | {len(g)} | " + " | ".join(f"{s.get(x, 0)/len(g)*100:.0f}%" for x in k) + f" | {s.get(k[1], 0)/reached*100 if reached else float('nan'):.0f}% |")


Sh = X[X.side < 0].copy()
d_all = {t: load(t) for t in Sh.ticker.unique()}
Sh["pdc_px"] = [d_all[t].Close[d_all[t].index < pd.Timestamp(dt)].iloc[-1] for t, dt in zip(Sh.ticker, Sh.date)]
Sh["pdl_px"] = [d_all[t].Low[d_all[t].index < pd.Timestamp(dt)].iloc[-1] for t, dt in zip(Sh.ticker, Sh.date)]
Sh["gapup"] = [r.e > r.pdc_px for _, r in Sh.iterrows()]
print("| group | trades | stopped WITHOUT reaching the level | reached it, THEN stopped | reached it, went through to the close | never reached, held to the close | of those that reached it: share that then stopped |\n|---|---|---|---|---|---|---|")
tab("REAL: yesterday's close 0-1% below", Sh[Sh.pdc <= 1], "pdc")
tab("REAL: yesterday's low 0-1% below", Sh[Sh.pdl <= 1], "pdl")
clear = Sh[(Sh.near > 2) | Sh.near.isna()]
tab("PLACEBO: clear path, fake level 0.5% below", clear, dist=0.5)
tab("PLACEBO: clear path, fake level 1.0% below", clear, dist=1.0)
print("\nCONFOUND -- gap-up shorts only (entry above yesterday's close), Rs @1k net:")
for lab, g in (("gap-up, yesterday's close within 1% below", Sh[Sh.gapup & (Sh.pdc <= 1)]), ("gap-up, yesterday's close 1-2% below", Sh[Sh.gapup & (Sh.pdc > 1) & (Sh.pdc <= 2)]),
               ("gap-up, yesterday's close > 2% below", Sh[Sh.gapup & (Sh.pdc > 2)]), ("gap-DOWN shorts (yesterday's close above)", Sh[~Sh.gapup])):
    print(f"  {lab}: {len(g)} trades, stopped {(g.o10mid == 'stop').mean()*100:.0f}%, Rs {g.r1k10mid.mean():+.0f}")
