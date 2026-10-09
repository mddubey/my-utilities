"""Fixed-target sweep at 1:2 (user, 2026-10-09: 'sweep 1% / 0.5, 1.5 / 0.75, 2 / 1'). Spec fixed before running. Population:
plain liquid touch (115 v3), 09:15 + 10:15 candles, ATR >= 2%, current layers (red, Nifty > 200d, stock daily 8>34, gap
-0.25..+0.5). Exit pairs (target %, max candle-high stop %): 1 / 0.5 | 1.5 / 0.75 | 2 / 1. Stop = candle high; trade only if stop <=
cap. Exit 5 candles / day's last candle, stop first; walked on h1_cache. Every row: setups, days, target / stall / stop % with avg
Rs (@1L), Rs/trade @1L and @1k risk, by year. Both candles and by candle. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
src = open(Path(__file__).resolve().parent / "130_rebaseline_frozen_frame.py").read().split('B["tp"] = 0.5 * B.atrp')[0]
exec(src)
B = B[(B.atrp >= 2.0) & B.red & (B.n200 == True) & (B.s8 > B.s34) & (B.gap > -0.25) & (B.gap <= 0.5)].copy()
PAIRS = ((1.0, 0.5), (1.5, 0.75), (2.0, 1.0))
res = []
for t, g in B.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    H, L, C, T = h.High.values, h.Low.values, h.Close.values, h.index; day = T.normalize()
    for ix, r in g.iterrows():
        k = pd.Timestamp(f"{r.date} {r.hour}")
        if k not in h.index: continue
        i = h.index.get_loc(k)
        for tp, cap in PAIRS:
            if r.stop > cap: continue
            tgt = r.entry * (1 - tp / 100); px, o = None, "stall"
            for j in range(i + 1, len(C)):
                if day[j] != day[i]: px = C[j - 1]; break
                if H[j] >= r.high: px, o = r.high, "stop"; break
                if L[j] <= tgt: px, o = tgt, "target"; break
                if j - i >= 5 or j + 1 >= len(C) or day[j + 1] != day[i]: px = C[j]; break
            if px is None: continue
            ret = (r.entry - px) / r.entry * 100; pos = 1000 / (r.stop / 100)
            res.append(dict(pair=f"{tp:g}% / {cap:g}%", hour=r.hour, date=r.date, yr=r.yr, o=out_ if (out_ := o) else o,
                            rs1L=ret * 1000 - 85, rs1k=ret / 100 * pos - 85 * pos / 1e5))
R = pd.DataFrame(res)


def rw(lab, g):
    parts = []
    for o in ("target", "stall", "stop"):
        x = g[g.o == o]; parts.append(f"{len(x)/len(g)*100:.0f}% ({x.rs1L.mean():+,.0f})" if len(x) else "0%")
    y = " / ".join(f"{g[g.yr == k].rs1L.mean():+.0f}" if (g.yr == k).sum() >= 20 else "-" for k in ("2024", "2025", "2026"))
    return f"| {lab} | {len(g):,} | {g.date.nunique()} | " + " | ".join(parts) + f" | {g.rs1L.mean():+.0f} | {g.rs1k.mean():+.0f} | {g.rs1L.sum():+,.0f} | {y} |"


for HR in ("both", "09:15", "10:15"):
    X = R if HR == "both" else R[R.hour == HR]
    print(f"\n## candle {HR}\n| target / max stop | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | total @1L | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|---|")
    for pr in (f"{a:g}% / {b:g}%" for a, b in PAIRS): print(rw(pr, X[X.pair == pr]))
