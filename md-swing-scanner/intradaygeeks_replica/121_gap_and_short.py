"""Does a good intraday short need a GAP UP? (user, 2026-10-09: 'uptrend gaps up overnight then fades in the day -> short the
fade'). Spec fixed before running. Gap = stock's open today / yesterday's close - 1 (daily data, known at 09:15). Buckets:
<= -1% | -1..-0.25 | -0.25..+0.25 (flat) | +0.25..+1 | >= +1%. Populations: (a) plain liquid touch, 09:15/10:15 candles, red
(script 119's S); split by stock daily trend (8>34 up / down); (b) the short stack (+ Nifty 8>34, stock up, ATR >= 2.56);
(c) the stack with Nifty > 200-day SMA. By year. Net = Rs per Rs1 lakh after Rs85. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "120_long_term_market_filter.py").read().split("def row")[0])
gp = []
for t, g in S.groupby("ticker"):
    d = load(t); gap = (d.Open / d.Close.shift(1) - 1) * 100
    x = g[["d"]].join(gap.rename("gap"), on="d"); gp.append(x.gap)
S["gap"] = pd.concat(gp)
B = [-100, -1, -0.25, 0.25, 1, 100]; LB = ["gap down >= 1%", "gap down 0.25-1%", "flat (+/-0.25%)", "gap up 0.25-1%", "gap up >= 1%"]
S["gb"] = pd.cut(S.gap, B, labels=LB)


def row(lab, g):
    if len(g) == 0: return f"| {lab} | 0 | | | |"
    o = g.out; y = " / ".join(f"{g[g.yr == k].ret.mean()*1000 - 85:+.0f}" if (g.yr == k).sum() >= 30 else "-" for k in ("2024", "2025", "2026"))
    return f"| {lab} | {len(g):,} | {(o == 'target').mean()*100:.0f} / {(o == 'stall').mean()*100:.0f} / {(o == 'stop').mean()*100:.0f} | {g.ret.mean()*1000 - 85:+.0f} | {y} |"


H = "| gap | setups | target / stall / stop % | Rs net | 2024 / 2025 / 2026 |\n|---|---|---|---|---|"
for nm, X in (("(a) early red liquid touch, stock in daily UPtrend", S[S.e8 > S.e34]),
              ("(a) early red liquid touch, stock in daily DOWNtrend", S[S.e8 <= S.e34]),
              ("(b) the short stack", S[(S.n834 == True) & (S.e8 > S.e34) & (S.atrp >= 2.56)]),
              ("(c) stack + Nifty > 200-day SMA", S[(S.n834 == True) & (S.e8 > S.e34) & (S.atrp >= 2.56) & (S.l1 == True)])):
    print(f"\n## {nm}\n" + H); print(row("ALL", X))
    for b in LB: print(row(b, X[X.gb == b]))
