"""Realistic version (user, 2026-10-09: 'I won't take a 1.7% stop for a 1% target'). Spec fixed before running.
Population: 5-filter stack + Nifty > 200-day SMA + gap in -0.25..+0.5% (script 123), candles 09:15 / 10:15.
Trade unchanged (candle-high stop, 1% target, 5 candles / EOD) but only setups the user would take (the user's standing
preference: at least 1:2, likes 1:3): stop <= 0.5% (1:2) and stop <= 0.33% (1:3); 'no cap' shown for reference.
Sizing as traded: fixed risk Rs1,000 per trade -> position = 1,000 / stop%; charges Rs85 per Rs1 lakh of position.
Report: setups, days with a setup, target/stall/stop, avg R, Rs per trade at Rs1,000 risk after charges, by year. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "122_gap_sweep_open_vs_ema.py").read().split("\ndef row(")[0])
X = S[(S.n834 == True) & (S.e8 > S.e34) & (S.atrp >= 2.56) & (S.l1 == True) & (S.gap > -0.25) & (S.gap <= 0.5)].copy()
X["R"] = X.ret / X.stop
X["pos"] = 1000 / (X.stop / 100); X["rs"] = X.ret / 100 * X.pos - 85 * X.pos / 1e5
print("| candle | stop cap | setups | days | target / stall / stop % | avg R | Rs/trade @ Rs1k risk (net) | 2024 / 2025 / 2026 | median position |\n|---|---|---|---|---|---|---|---|---|")
for hr in ("09:15", "10:15", "both"):
    H = X if hr == "both" else X[X.hour == hr]
    for lab, cap in (("no cap", 100), ("<= 0.5% (1:2)", 0.5), ("<= 0.33% (1:3)", 0.333)):
        g = H[H.stop <= cap]
        if len(g) == 0: continue
        o = g.out; y = " / ".join(f"{g[g.yr == k].rs.mean():+.0f}" if (g.yr == k).sum() >= 20 else "-" for k in ("2024", "2025", "2026"))
        print(f"| {hr} | {lab} | {len(g):,} | {g.date.nunique()} | {(o=='target').mean()*100:.0f} / {(o=='stall').mean()*100:.0f} / {(o=='stop').mean()*100:.0f} | "
              f"{g.R.mean():+.2f} | {g.rs.mean():+.0f} | {y} | Rs{g.pos.median()/1e5:.1f} lakh |")
