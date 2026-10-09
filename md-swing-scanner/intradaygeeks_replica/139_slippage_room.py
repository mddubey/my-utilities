"""Is there still 1% of room after slippage? (user, 2026-10-09 late: 'if I slip 0.1%, can I still capture 1%?'). Spec fixed before
running. Trades: revised frame (137) full stack, 10:15 candle, ATR >= 2%. Entry slippage s = 0 / 0.05 / 0.1 / 0.2%: the short fills
s% BELOW the candle close (worse); target = fill - 1% (the user still wants a full 1%); stop = the same candle high (now s% further).
Version 2 adds the same s% slippage on the STOP fill too. Walked on h1_cache, 5 candles / day's last candle, stop first. By ATR band.
Rs at Rs1 lakh, net. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "137_rerun_under_1pct_frame.py").read().split('LAY = {')[0])
Z = B[(B.hour == "10:15") & (B.atrp >= 2.0) & B.red & (B.n200 == True) & (B.s8 > B.s34) & (B.gap > -0.25) & (B.gap <= 0.5)].copy()
rows = []
for t, g in Z.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    H, L, C, T = h.High.values, h.Low.values, h.Close.values, h.index; day = T.normalize()
    for ix, r in g.iterrows():
        i = h.index.get_loc(pd.Timestamp(f"{r.date} 10:15"))
        for s in (0, 0.05, 0.1, 0.2):
            fill = r.entry * (1 - s / 100); tgt = fill * 0.99; px, o = None, "stall"
            for j in range(i + 1, len(C)):
                if day[j] != day[i]: px = C[j - 1]; break
                if H[j] >= r.high: px, o = r.high, "stop"; break
                if L[j] <= tgt: px, o = tgt, "target"; break
                if j - i >= 5 or j + 1 >= len(C) or day[j + 1] != day[i]: px = C[j]; break
            if px is None: continue
            px2 = px * (1 + s / 100) if o == "stop" else px
            rows.append(dict(s=s, atrp=r.atrp, o=o, rs=(fill - px) / fill * 1e5 - 85, rs2=(fill - px2) / fill * 1e5 - 85,
                             risk=(r.high - fill) / fill * 100))
A = pd.DataFrame(rows)
A["band"] = pd.cut(A.atrp, [2, 2.5, 3, 3.5, 99], labels=["2-2.5", "2.5-3", "3-3.5", "> 3.5"], include_lowest=True)
print("| entry slippage | trades | target % | stall % | stop % | median stop distance % | Rs/trade @1L | + same slip on stop fill | by ATR 2-2.5 / 2.5-3 / 3-3.5 / >3.5 (entry slip only) |\n|---|---|---|---|---|---|---|---|---|")
for s, g in A.groupby("s"):
    b = " / ".join(f"{x.rs.mean():+.0f}" for _, x in g.groupby("band", observed=True))
    print(f"| {s:g}% | {len(g)} | {(g.o=='target').mean()*100:.0f} | {(g.o=='stall').mean()*100:.0f} | {(g.o=='stop').mean()*100:.0f} | {g.risk.median():.2f} | {g.rs.mean():+.0f} | {g.rs2.mean():+.0f} | {b} |")
