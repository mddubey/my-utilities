"""Re-baseline under the FROZEN frame (STRATEGY 8j, user 2026-10-09). Spec fixed before running.
Base = plain liquid 1H EMA34 touch (115 v3), 09:15 + 10:15 candles, 2024-01..2026-09, with the frozen exit's own eligibility:
ATR >= 2% (yday) and candle-high stop <= half of the 0.5 x ATR target. Exit: target 0.5 x ATR, stop candle high, 5 candles /
day's last candle, stop first (re-walked on h1_cache). Layers, each shown ALONE on the base and then CUMULATIVE in this order:
red | Nifty daily 8>34 | Nifty > 200-day SMA | stock daily 8>34 | gap -0.25..+0.5%. Every row: setups, days, target / stall / stop
% with each outcome's avg Rs (fixed Rs1 lakh), Rs/trade at Rs1 lakh and at Rs1k risk (net of Rs85 per lakh), by year. Results only."""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from data.paths import DAILY_DIR
P = pd.read_csv(HERE / "plain_touch_1h.csv")
B = P[(P.liq_prev >= 15) & P.hour.isin(["09:15", "10:15"])].copy(); B["d"] = pd.to_datetime(B.date); B["yr"] = B.date.str[:4]
feat = []
for t, g in B.groupby("ticker"):
    d = load(t); c = d.Close
    f = pd.DataFrame({"atrp": (d.atr14 / c * 100).shift(1), "s8": c.ewm(span=8, adjust=False).mean().shift(1),
                      "s34": c.ewm(span=34, adjust=False).mean().shift(1), "gap": (d.Open / c.shift(1) - 1) * 100})
    x = g[["d"]].join(f, on="d"); x.index = g.index; feat.append(x.drop(columns="d"))
B = B.join(pd.concat(feat))
n = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index(); nc = n["Close"]
B = B.join(pd.DataFrame({"n834": (nc.ewm(span=8, adjust=False).mean() > nc.ewm(span=34, adjust=False).mean()).shift(1),
                         "n200": (nc > nc.rolling(200).mean()).shift(1)}), on="d")
B["tp"] = 0.5 * B.atrp
B = B[(B.atrp >= 2.0) & (B.stop <= B.tp / 2)].copy()
print(f"base (frozen-frame eligible) setups: {len(B):,} on {B.date.nunique()} days; walking...", flush=True)
t0 = time.time(); out = {}
for t, g in B.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    H, L, C, T = h.High.values, h.Low.values, h.Close.values, h.index; day = T.normalize()
    for ix, r in g.iterrows():
        k = pd.Timestamp(f"{r.date} {r.hour}")
        if k not in h.index: continue
        i = h.index.get_loc(k); tgt = r.entry * (1 - r.tp / 100); px, o = None, "stall"
        for j in range(i + 1, len(C)):
            if day[j] != day[i]: px = C[j - 1]; break
            if H[j] >= r.high: px, o = r.high, "stop"; break
            if L[j] <= tgt: px, o = tgt, "target"; break
            if j - i >= 5 or j + 1 >= len(C) or day[j + 1] != day[i]: px = C[j]; break
        if px is not None: out[ix] = ((r.entry - px) / r.entry * 100, o)
B = B.loc[list(out)]; B["ret"] = [out[i][0] for i in B.index]; B["o"] = [out[i][1] for i in B.index]
B["rs1L"] = B.ret * 1000 - 85; pos = 1000 / (B.stop / 100); B["rs1k"] = B.ret / 100 * pos - 85 * pos / 1e5
print(f"walked {len(B):,} in {time.time()-t0:.0f}s\n")


def row(lab, g):
    if len(g) < 30: return f"| {lab} | {len(g)} | | | | | | |"
    parts = []
    for o in ("target", "stall", "stop"):
        x = g[g.o == o]; parts.append(f"{len(x)/len(g)*100:.0f}% ({x.rs1L.mean():+,.0f})" if len(x) else "0%")
    y = " / ".join(f"{g[g.yr == k].rs1L.mean():+.0f}" if (g.yr == k).sum() >= 20 else "-" for k in ("2024", "2025", "2026"))
    return f"| {lab} | {len(g):,} | {g.date.nunique()} | " + " | ".join(parts) + f" | {g.rs1L.mean():+.0f} | {g.rs1k.mean():+.0f} | {y} |"


H = "| group | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | Rs/trade @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
LAY = (("red", lambda d: d.red), ("Nifty 8>34", lambda d: d.n834 == True), ("Nifty > 200d", lambda d: d.n200 == True),
       ("stock daily 8>34", lambda d: d.s8 > d.s34), ("gap -0.25..+0.5", lambda d: (d.gap > -0.25) & (d.gap <= 0.5)))
for HR in ("both", "09:15", "10:15"):
    X = B if HR == "both" else B[B.hour == HR]
    print(f"\n## candle {HR} -- each layer ALONE on the base\n" + H); print(row("BASE (plain touch, frozen exit)", X))
    for nm, f in LAY: print(row(f"+ {nm} only", X[f(X)]))
    print(f"\n## candle {HR} -- CUMULATIVE\n" + H); Y = X; print(row("BASE", Y))
    for nm, f in LAY: Y = Y[f(Y)]; print(row(f"+ {nm}", Y))
