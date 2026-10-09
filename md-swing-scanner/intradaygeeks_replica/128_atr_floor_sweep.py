"""ATR floor sweep (user, 2026-10-09: '2.56 is arbitrary'). Spec fixed before running: 10:15 candle, script 127's population
(no ATR filter), floors ATR >= 2.0 / 2.25 / 2.5 / 2.75 / 3.0 / 3.5 (cumulative) and 0.25-wide bands 1.75..3.5. Configs:
0.5 x ATR target with 'target >= 2x stop'; fixed 1% with 'target >= 2x stop'; 0.5 x ATR with no R:R condition.
Rs per trade at Rs1k risk (net), setups, days, by year. Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
sys.argv += ["--hour", "10:15"]
exec(open(Path(__file__).resolve().parent / "127_atr_filter_needed.py").read().split("BANDS = ")[0])
CF = (("0.5xATR, >= 1:2", "0.5 x ATR", lambda d: d.tp >= 2 * d.stop), ("fixed 1%, >= 1:2", "fixed 1%", lambda d: d.tp >= 2 * d.stop),
      ("0.5xATR, no R:R", "0.5 x ATR", lambda d: d.tp > 0))


def cell(g):
    if len(g) < 30: return f"- ({len(g)})"
    y = "/".join(f"{g[g.yr == k].rs.mean():+.0f}" if (g.yr == k).sum() >= 20 else "-" for k in ("2024", "2025", "2026"))
    return f"{g.rs.mean():+.0f} n{len(g)} d{g.date.nunique()} ({y})"


for title, rng in (("CUMULATIVE floors (ATR >= x)", [(f">= {a}", a, 99) for a in (2.0, 2.25, 2.5, 2.75, 3.0, 3.5)]),
                   ("BANDS (0.25 wide)", [(f"{a:.2f}-{a+0.25:.2f}", a, a + 0.25) for a in (1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25)] + [(">= 3.5", 3.5, 99)])):
    print(f"\n## {title} -- Rs/trade nSetups dDays (2024/2025/2026)\n| ATR | " + " | ".join(c[0] for c in CF) + " |\n|---|---|---|---|")
    for lab, lo, hi in rng:
        cells = []
        for _, tg, cond in CF:
            g = R[R.tgt == tg]; g = g[cond(g) & (g.atrp >= lo) & (g.atrp < hi)]; cells.append(cell(g))
        print(f"| {lab} | " + " | ".join(cells) + " |")
