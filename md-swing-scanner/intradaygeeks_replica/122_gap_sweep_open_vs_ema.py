"""Gap sweep + where the day OPENS vs the 1H EMA34 (user, 2026-10-09). Spec fixed before running.
  1. Gap (open / prev close - 1) in 0.25% steps: <= -0.5 | -0.5..-0.25 | -0.25..0 | 0..+0.25 | +0.25..+0.5 | +0.5..+0.75 |
     +0.75..+1 | > +1.
  2. User's chart theory: day's OPEN vs the 1H EMA34 of the signal candle: open below it | 0-0.25% above | 0.25-0.5 |
     0.5-1 | > 1% above. Far above -> price falls to the EMA34 and holds it as support (bad short); just above -> touches,
     slips under, keeps falling (good short).
Populations: (b) the 5-filter short stack; (c) + Nifty > 200-day SMA. By year. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "120_long_term_market_filter.py").read().split("def row")[0])
gp = []
for t, g in S.groupby("ticker"):
    d = load(t); f = pd.DataFrame({"gap": (d.Open / d.Close.shift(1) - 1) * 100, "dopen": d.Open})
    x = g[["d"]].join(f, on="d"); x.index = g.index; gp.append(x[["gap", "dopen"]])
S = S.join(pd.concat(gp))
S["ovsE"] = (S.dopen / S.ema34 - 1) * 100


def row(lab, g):
    if len(g) == 0: return f"| {lab} | 0 | | | |"
    o = g.out; y = " / ".join(f"{g[g.yr == k].ret.mean()*1000 - 85:+.0f}" if (g.yr == k).sum() >= 30 else "-" for k in ("2024", "2025", "2026"))
    return f"| {lab} | {len(g):,} | {(o == 'target').mean()*100:.0f} / {(o == 'stall').mean()*100:.0f} / {(o == 'stop').mean()*100:.0f} | {g.ret.mean()*1000 - 85:+.0f} | {y} |"


H = "| bucket | setups | target / stall / stop % | Rs net | 2024 / 2025 / 2026 |\n|---|---|---|---|---|"
STK = S[(S.n834 == True) & (S.e8 > S.e34) & (S.atrp >= 2.56)]
for nm, X in (("(b) 5-filter stack", STK), ("(c) stack + Nifty > 200-day", STK[STK.l1 == True])):
    print(f"\n## {nm}: GAP sweep\n" + H)
    for lab, g in X.groupby(pd.cut(X.gap, [-100, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1, 100]), observed=True): print(row(str(lab), g))
    print(f"\n## {nm}: day OPEN vs 1H EMA34\n" + H)
    for lab, g in X.groupby(pd.cut(X.ovsE, [-100, 0, 0.25, 0.5, 1, 100], labels=["opens BELOW EMA34", "0-0.25% above", "0.25-0.5% above", "0.5-1% above", "> 1% above"]), observed=True): print(row(str(lab), g))
