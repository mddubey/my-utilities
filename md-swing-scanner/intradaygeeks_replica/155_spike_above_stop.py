"""Check 3, counting first (user, 2026-10-10: 'a 09:15 spike above our stop must be very common'). Spec fixed before running.
v1 trades (10:15, red, full stack, Rs100 floor, cut dojis removed), branches A and B, exits E1 / E2. Spike = the day's high so far
(09:15 + 10:15 candles) minus OUR stop (the 10:15 candle high), as a share of the daily ATR. Buckets: 0 (our candle made the day's
high) | 0-0.1 | 0.1-0.25 | > 0.25 x ATR. Report how common each is and how it did. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "154_doji_check.py").read().split("\nH = ")[0])
h915 = {}
for t, g in B.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    for ix, r in g.iterrows():
        k = pd.Timestamp(f"{r.date} 09:15")
        if k in h.index: h915[ix] = h.at[k, "High"]
B["spk"] = ((pd.concat([pd.Series(h915), B.high], axis=1).max(axis=1) - B.high) / B.entry * 100 / B.atrp)
R["spk"] = R.ix.map(B.spk)
X0 = X0.copy(); X0["spk"] = X0.ix.map(B.spk)
X0 = X0[~((X0.bodyp < 0.25) & (X0.open >= X0.ema34))]
H = "| spike above our stop | setups | share | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 |\n|---|---|---|---|---|---|---|---|---|"
for en in EX:
    for bn, bm in (("A", lambda d: (d.ov >= -0.5) & (d.ov < 0)), ("B", lambda d: (d.ov >= 0) & (d.atrp >= 3))):
        X = X0[X0.ex == en]; X = X[bm(X)]
        print(f"\n## {en} -- branch {bn} ({len(X)} trades)\n" + H)
        for lab, lo, hi in (("none (our candle made the day's high)", -1, 1e-9), ("0-0.1 x ATR", 1e-9, 0.1), ("0.1-0.25 x ATR", 0.1, 0.25), ("> 0.25 x ATR (big morning spike)", 0.25, 99)):
            g = X[(X.spk > lo) & (X.spk <= hi)]
            if len(g) < 15: print(f"| {lab} | {len(g)} | {len(g)/len(X)*100:.0f}% | | | | | | |"); continue
            parts = [f"{(g.o == o).mean()*100:.0f}% ({g[g.o == o].rs1L.mean():+,.0f})" for o in ("target", "stall", "stop")]
            y = " / ".join(f"{g[g.yr == k].rs1L.mean():+.0f}" if (g.yr == k).sum() >= 15 else "-" for k in ("2024", "2025"))
            print(f"| {lab} | {len(g)} | {len(g)/len(X)*100:.0f}% | " + " | ".join(parts) + f" | {g.rs1L.mean():+.0f} | {g.rs1k.mean():+.0f} | {y} |")
