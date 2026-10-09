"""Report for 115 (plain 1H EMA34 touch, liquid names). Results only: baseline, then one flag at a time (kept = flag true,
removed = flag false), distance / stop / hour buckets, by year. Net = Rs per Rs1 lakh after Rs85 charges."""
from pathlib import Path
import pandas as pd
HERE = Path(__file__).resolve().parent
P = pd.read_csv(HERE / "plain_touch_1h.csv"); P["yr"] = P.date.str[:4]
FL = ["red", "trend", "below_d8", "pierce_d8", "adx_ok", "below_vwap", "atr_ok", "rr_ok", "price_ok"]


def row(lab, g):
    if len(g) == 0: return f"| {lab} | 0 | | | | |"
    o = g.out; y = " / ".join(f"{g[g.yr == k].ret.mean()*1000 - 85:+.0f}" if (g.yr == k).any() else "-" for k in ("2024", "2025", "2026"))
    return (f"| {lab} | {len(g)} | {(o == 'target').mean()*100:.0f} / {(o == 'stall').mean()*100:.0f} / {(o == 'stop').mean()*100:.0f} | "
            f"{g.ret.mean()*1000 - 85:+.0f} | {(g.ret / g.stop.clip(lower=0.05)).median():+.2f} | {y} |")


H = "| n | target / stall / stop % | Rs net | median R | 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|"
L = P[P.liq >= 15]; T = P[P.liq < 15]
print(f"all touches {len(P)} | liquid (>= Rs15 lakh/5m) {len(L)} | thin {len(T)} | 09:15 candles in liquid: {(L.hour == '09:15').sum()}"
      " (Yahoo's 09:15 hourly bar often has volume 0 -> mostly counted thin)")
print("\n## baseline\n| group " + H)
print(row("LIQUID, plain touch (nothing applied)", L)); print(row("thin, for contrast", T))
cur = L[L.red & L.trend & L.below_d8 & L.pierce_d8 & L.adx_ok & L.below_vwap & L.atr_ok & L.rr_ok & L.price_ok & (L.dist <= 0.5)
        & L.hour.isin(["10:15", "11:15"])]
print(row("liquid, ALL current rules (incl. dist <= 0.5, 10:15/11:15 candles)", cur))
print("\n## one flag at a time on the liquid plain touch (kept = flag true, removed = false)\n| flag " + H)
for f in FL:
    print(row(f"{f} KEPT", L[L[f]])); print(row(f"{f} removed", L[~L[f]]))
for nm, col, bins in (("distance below EMA34 at close, %", "dist", [0, 0.25, 0.5, 1, 2, 100]),
                      ("stop (candle high above close), %", "stop", [0, 0.25, 0.5, 0.75, 1, 1.5, 100]),
                      ("liquidity, Rs lakh per 5-min bar", "liq", [15, 25, 50, 100, 250, 1e9])):
    print(f"\n## liquid, by {nm}\n| bucket " + H)
    for k, g in L.groupby(pd.cut(L[col], bins), observed=True): print(row(str(k), g))
print("\n## liquid, by candle hour\n| hour " + H)
for k, g in L.groupby("hour"): print(row(k, g))
