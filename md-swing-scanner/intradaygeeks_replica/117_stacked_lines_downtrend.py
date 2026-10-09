"""Stacked-lines downtrend shape (user, 2026-10-09, from the live trades: BPCL, J&KBANK, PNGJL, TECHM all had it). Spec fixed
before running. Population: plain liquid 1H EMA34 touch (script 115 v3: high >= 1H EMA34, close below; previous-day liquidity
>= Rs15 lakh / 5-min bar), all hours, 2024-01..2026-09; stop = candle high, target 1%, out 5 candles / EOD.
  T  daily trend DOWN: yesterday's daily 8-EMA < yesterday's daily 34-EMA.
  S  lines STACKED: live daily 8-EMA (2/9 x close + 7/9 x yesterday's EMA8) sits ABOVE the 1H EMA34 by 0 to 0.5%
     (0.5% = the widest gap in the live trades). With S the close is below both lines.
  T + S together = the shape. Also shown (sub-check, declared): T + S + the candle's high reached the live daily 8-EMA.
Baseline, each alone, together, removed; all hours and by candle hour; by year. Net = Rs per Rs1 lakh after Rs85."""
from pathlib import Path
import pandas as pd
HERE = Path(__file__).resolve().parent
P = pd.read_csv(HERE / "plain_touch_1h.csv"); P["yr"] = P.date.str[:4]
L = P[P.liq_prev >= 15].copy()
L["live8"] = 2 / 9 * L.entry + 7 / 9 * L.d8y
gap = (L.live8 - L.ema34) / L.ema34 * 100
L["T"] = L.d8y < L.d34y; L["S"] = (gap >= 0) & (gap <= 0.5); L["TS"] = L["T"] & L["S"]; L["TSH"] = L.TS & (L.high >= L.live8)


def row(lab, g):
    if len(g) == 0: return f"| {lab} | 0 | | | |"
    o = g.out; y = " / ".join(f"{g[g.yr == k].ret.mean()*1000 - 85:+.0f}" if (g.yr == k).any() else "-" for k in ("2024", "2025", "2026"))
    return f"| {lab} | {len(g)} | {(o == 'target').mean()*100:.0f} / {(o == 'stall').mean()*100:.0f} / {(o == 'stop').mean()*100:.0f} | {g.ret.mean()*1000 - 85:+.0f} | {y} |"


H = "| n | target / stall / stop % | Rs net | 2024 / 2025 / 2026 |\n|---|---|---|---|---|"
print(f"liquid plain touches {len(L)}; T known for {L.d34y.notna().sum()}")
print("\n## all hours\n| group " + H)
print(row("BASELINE plain touch", L))
print(row("T daily trend down", L[L["T"]])); print(row("  not T (daily up)", L[~L["T"]]))
print(row("S lines stacked 0-0.5%", L[L.S])); print(row("  not S", L[~L.S]))
print(row("T + S = THE SHAPE", L[L.TS])); print(row("  removed (not the shape)", L[~L.TS]))
print(row("T + S + candle high reached daily 8", L[L.TSH]))
print("\n## THE SHAPE (T + S) by candle hour, vs baseline same hour\n| hour / group " + H)
for hr, g in L.groupby("hour"):
    print(row(f"{hr} baseline", g)); print(row(f"{hr} SHAPE", g[g.TS]))
