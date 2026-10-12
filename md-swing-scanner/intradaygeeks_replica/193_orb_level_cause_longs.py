"""Longs mirror of 192 (user, 2026-10-12): in-play LONGS (green 09:15 candle, buy-stop at its high, paper rules). Level 0-1% ABOVE the
entry: yesterday's HIGH, and yesterday's CLOSE (only above a long when the stock gapped DOWN = the long's gap-fill level). Did price
reach it (a 5-min high within 0.1% of L or above) and THEN get stopped, vs stopped before reaching it, vs went through? PLACEBO:
clear-path longs (no level within 2% above) with a fake level 0.5% / 1% above. CONFOUND: by gap direction and distance to yesterday's
high / close. Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
exec(open(HERE / "191_orb_levels_in_path.py").read().split("\ndef row(")[0])
from orb_common import read5_official  # 2026-10-12: official 09:15 open
from data.paths import INTRADAY_5M_DIR
cache = {}


def path(r, L):
    t = r.ticker
    if t not in cache:
        m = read5_official(t)
        m["hm"] = m.index.strftime("%H:%M"); cache[t] = m
    m = cache[t]; d = m[m.index.normalize() == pd.Timestamp(r.date)]; e = r.e; stp = e * (1 - 0.1 * r.atr / 100)
    w = d[(d.hm >= r.et) & (d.hm < "15:15")]; reached, stop_at = None, None
    for ts, b in w.iterrows():
        if reached is None and b.High >= L * 0.999: reached = ts
        if b.Low <= stp and not (ts == w.index[0] and r.o10mid != "stop"): stop_at = ts; break
    return reached, stop_at


def tab(lab, g, Lcol=None, dist=None):
    out = []
    for _, r in g.iterrows():
        L = r.pdh_px if Lcol == "pdh" else (r.pdc_px if Lcol == "pdc" else r.e * (1 + dist / 100))
        rc, sa = path(r, L)
        if r.o10mid == "stop": out.append("a" if (rc is None or (sa is not None and rc > sa)) else "b")
        else: out.append("c" if rc is not None else "d")
    s = pd.Series(out).value_counts(); reached = s.get("b", 0) + s.get("c", 0)
    print(f"| {lab} | {len(g)} | " + " | ".join(f"{s.get(x, 0)/len(g)*100:.0f}%" for x in "abcd") + f" | {s.get('b', 0)/reached*100 if reached else float('nan'):.0f}% |")


Lg = X[X.side > 0].copy()
dd = {t: load(t) for t in Lg.ticker.unique()}
Lg["pdc_px"] = [dd[t].Close[dd[t].index < pd.Timestamp(x)].iloc[-1] for t, x in zip(Lg.ticker, Lg.date)]
Lg["pdh_px"] = [dd[t].High[dd[t].index < pd.Timestamp(x)].iloc[-1] for t, x in zip(Lg.ticker, Lg.date)]
Lg["gapdown"] = Lg.e < Lg.pdc_px
print("| group (longs) | trades | stopped WITHOUT reaching the level | reached it, THEN stopped | reached it, went through to the close | never reached, held to the close | of those that reached it: share then stopped |\n|---|---|---|---|---|---|---|")
tab("REAL: yesterday's high 0-1% above", Lg[Lg.pdl <= 1], "pdh")
tab("REAL: yesterday's close 0-1% above (gap-down longs)", Lg[Lg.pdc <= 1], "pdc")
clear = Lg[(Lg.near > 2) | Lg.near.isna()]
tab("PLACEBO: clear path, fake level 0.5% above", clear, dist=0.5)
tab("PLACEBO: clear path, fake level 1.0% above", clear, dist=1.0)
print("\nCONFOUND -- Rs @1k net per trade:")
for lab, g in (("yesterday's high within 1% above", Lg[Lg.pdl <= 1]), ("yesterday's high 1-2% above", Lg[(Lg.pdl > 1) & (Lg.pdl <= 2)]),
               ("yesterday's high > 2% above", Lg[Lg.pdl > 2]), ("already ABOVE yesterday's high (no such level)", Lg[Lg.pdl.isna()]),
               ("gap-down longs, yesterday's close within 1% above", Lg[Lg.gapdown & (Lg.pdc <= 1)]), ("gap-down longs, close 1-2% above", Lg[Lg.gapdown & (Lg.pdc > 1) & (Lg.pdc <= 2)]),
               ("gap-down longs, close > 2% above", Lg[Lg.gapdown & (Lg.pdc > 2)]), ("gap-UP longs", Lg[~Lg.gapdown])):
    print(f"  {lab}: {len(g)} trades, stopped {(g.o10mid == 'stop').mean()*100:.0f}%, Rs {g.r1k10mid.mean():+.0f}")
