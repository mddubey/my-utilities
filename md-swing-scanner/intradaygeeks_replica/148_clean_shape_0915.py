"""Clean shape: 'opened BELOW the 1H EMA34, rallied up into it, rejected' -- on the 09:15 candle (entry 10:15, no red requirement)
and on the 10:15 candle (user, 2026-10-10). Spec fixed before running. Common layers: liquid, ATR >= 2%, Nifty > 200-day SMA, stock
daily 8>34, gap -0.25..+0.5%. Shape: the day's open (= 09:15 candle open) BELOW the 1H EMA34, candle high >= EMA34, close < EMA34.
09:15 candle: no red requirement (132 showed red hurts there); 10:15 candle: red kept (as in the stack) and also shown without.
Exits: E1 1% target, stop = candle high <= 0.5%; E2 target max(1%, 0.35 x ATR), stop <= half the target. Walked on h1_cache.
Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "130_rebaseline_frozen_frame.py").read().split('B["tp"] = 0.5 * B.atrp')[0])
B = B[(B.atrp >= 2.0) & (B.n200 == True) & (B.s8 > B.s34) & (B.gap > -0.25) & (B.gap <= 0.5)].copy()
dop = {}
for t, g in B.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    for ix, r in g.iterrows():
        k = pd.Timestamp(f"{r.date} 09:15")
        if k in h.index: dop[ix] = h.at[k, "Open"]
B["dayopen"] = pd.Series(dop); B = B[B.dayopen.notna()]
B["below_open"] = B.dayopen < B.ema34
EX = {"E1 1% / stop <= 0.5%": (lambda r: 1.0, lambda r, tp: r.stop <= 0.5), "E2 max(1%, 0.35xATR) / >= 1:2": (lambda r: max(1.0, 0.35 * r.atrp), lambda r, tp: r.stop <= tp / 2)}
res = []
for t, g in B.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    H, L, C, T = h.High.values, h.Low.values, h.Close.values, h.index; day = T.normalize()
    for ix, r in g.iterrows():
        k = pd.Timestamp(f"{r.date} {r.hour}")
        if k not in h.index: continue
        i = h.index.get_loc(k)
        for en, (tf, ok) in EX.items():
            tp = tf(r)
            if not ok(r, tp): continue
            tgt = r.entry * (1 - tp / 100); px, o = None, "stall"
            for j in range(i + 1, len(C)):
                if day[j] != day[i]: px = C[j - 1]; break
                if H[j] >= r.high: px, o = r.high, "stop"; break
                if L[j] <= tgt: px, o = tgt, "target"; break
                if j - i >= 5 or j + 1 >= len(C) or day[j + 1] != day[i]: px = C[j]; break
            if px is None: continue
            ret = (r.entry - px) / r.entry * 100; pos = 1000 / (r.stop / 100)
            res.append(dict(ix=ix, ex=en, hour=r.hour, red=r.red, below_open=r.below_open, date=r.date, yr=r.yr, o=o,
                            rs1L=ret * 1000 - 85, rs1k=ret / 100 * pos - 85 * pos / 1e5))
R = pd.DataFrame(res)


def row(lab, g):
    if len(g) < 20: return f"| {lab} | {len(g)} | | | | | | | |"
    parts = []
    for o in ("target", "stall", "stop"):
        x = g[g.o == o]; parts.append(f"{len(x)/len(g)*100:.0f}% ({x.rs1L.mean():+,.0f})" if len(x) else "0%")
    y = " / ".join(f"{g[g.yr == k].rs1L.mean():+.0f}" if (g.yr == k).sum() >= 20 else "-" for k in ("2024", "2025", "2026"))
    return f"| {lab} | {len(g):,} | {g.date.nunique()} | " + " | ".join(parts) + f" | {g.rs1L.mean():+.0f} | {g.rs1k.mean():+.0f} | {y} |"


H = "| version | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
for en in EX:
    X = R[R.ex == en]
    print(f"\n## {en}\n" + H)
    print(row("09:15 candle, OPENED BELOW + rallied in + rejected, any colour (entry 10:15)", X[(X.hour == "09:15") & X.below_open]))
    print(row("09:15 candle, same shape, red only", X[(X.hour == "09:15") & X.below_open & X.red]))
    print(row("09:15 candle, opened ABOVE (contrast)", X[(X.hour == "09:15") & ~X.below_open]))
    print(row("10:15 candle, opened below, red (as in the stack)", X[(X.hour == "10:15") & X.below_open & X.red]))
    print(row("10:15 candle, opened below, any colour", X[(X.hour == "10:15") & X.below_open]))
    print(row("BOTH candles, opened below, (09:15 any colour, 10:15 red)", X[X.below_open & ((X.hour == "09:15") | X.red)]))
