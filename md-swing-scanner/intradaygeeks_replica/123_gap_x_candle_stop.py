"""Big-gap days: are the 09:15 candle's stops eating the targets, and is the 10:15 candle better on those days? (user, 2026-10-09).
Spec fixed before running. Population: 5-filter stack + Nifty > 200-day SMA (scripts 120/122). Gap groups: gap down (< -0.25%),
good zone (-0.25..+0.5), big gap up (> +0.5). For each gap group x candle (09:15 / 10:15): setups, median stop %, target/stall/stop,
avg win % / avg loss %, net, by year. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "122_gap_sweep_open_vs_ema.py").read().split("\ndef row(")[0])
X = S[(S.n834 == True) & (S.e8 > S.e34) & (S.atrp >= 2.56) & (S.l1 == True)].copy()
X["gg"] = pd.cut(X.gap, [-100, -0.25, 0.5, 100], labels=["gap down < -0.25%", "good zone -0.25..+0.5", "big gap up > +0.5%"])
print("| gap | candle | setups | median stop % | target / stall / stop % | avg win % | avg loss % | Rs net | 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|")
for (gg, hr), g in X.groupby(["gg", "hour"], observed=True):
    o = g.out; y = " / ".join(f"{g[g.yr == k].ret.mean()*1000 - 85:+.0f}" if (g.yr == k).sum() >= 30 else "-" for k in ("2024", "2025", "2026"))
    print(f"| {gg} | {hr} | {len(g):,} | {g.stop.median():.2f} | {(o=='target').mean()*100:.0f} / {(o=='stall').mean()*100:.0f} / {(o=='stop').mean()*100:.0f} | "
          f"{g.ret[g.ret > 0].mean():+.2f} | {g.ret[g.ret <= 0].mean():+.2f} | {g.ret.mean()*1000 - 85:+.0f} | {y} |")
