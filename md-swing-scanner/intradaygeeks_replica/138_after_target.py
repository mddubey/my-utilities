"""What happens AFTER the 1% target? (user, 2026-10-09 late: 'does the stock keep going after 1%? stop stays the same'). Spec fixed
before running. Trades: revised frame (137) full stack, 10:15 candle, ATR >= 2%, that HIT the 1% target. Continue the same trade
past the target with the SAME stop (candle high) until the stop or the time exit (5 candles / day's last candle). Measure: best
move reached (% below entry), share reaching 1.25 / 1.5 / 2 / 2.5 / 3%, how many came back to the stop, the held result vs booking
at 1%. By ATR band (2-2.5 | 2.5-3 | 3-3.5 | > 3.5). Rs at Rs1 lakh, net. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
exec(open(Path(__file__).resolve().parent / "137_rerun_under_1pct_frame.py").read().split('LAY = {')[0])
Z = B[(B.hour == "10:15") & (B.atrp >= 2.0) & B.red & (B.n200 == True) & (B.s8 > B.s34) & (B.gap > -0.25) & (B.gap <= 0.5) & (B.o == "target")].copy()
rows = []
for t, g in Z.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    H, L, C, T = h.High.values, h.Low.values, h.Close.values, h.index; day = T.normalize()
    for ix, r in g.iterrows():
        i = h.index.get_loc(pd.Timestamp(f"{r.date} 10:15")); e = r.entry; best = e; px = None; o = "time"
        for j in range(i + 1, len(C)):
            if day[j] != day[i]: px = C[j - 1]; break
            if H[j] >= r.high: px, o = r.high, "back to stop"; break
            best = min(best, L[j])
            if j - i >= 5 or j + 1 >= len(C) or day[j + 1] != day[i]: px = C[j]; break
        if px is None: continue
        rows.append(dict(atrp=r.atrp, best=(e - best) / e * 100, held=(e - px) / e * 1e5 - 85, o=o))
A = pd.DataFrame(rows)
A["band"] = pd.cut(A.atrp, [2, 2.5, 3, 3.5, 99], labels=["ATR 2-2.5%", "ATR 2.5-3%", "ATR 3-3.5%", "ATR > 3.5%"], include_lowest=True)
print(f"target-hit trades: {len(A)}\n\n| ATR band | trades | median best move % | reached 1.25% | 1.5% | 2% | 2.5% | 3% | came back to stop | held avg Rs | booked at 1% Rs |\n|---|---|---|---|---|---|---|---|---|---|---|")
for b, g in list(A.groupby("band", observed=True)) + [("ALL", A)]:
    print(f"| {b} | {len(g)} | {g.best.median():.2f} | " + " | ".join(f"{(g.best >= x).mean()*100:.0f}%" for x in (1.25, 1.5, 2, 2.5, 3))
          + f" | {(g.o == 'back to stop').mean()*100:.0f}% | {g.held.mean():+,.0f} | +915 |")
