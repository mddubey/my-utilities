"""After our short, how often does price come back UP to touch the 1H EMA34? (user, 2026-10-10: 'volatile stocks chop back to the
line'). Spec fixed before running. Trades: 137 frame (10:15, red, full stack, E1 1% / stop <= 0.5%). After entry, until our exit
(target / stop / time), count hourly bars whose HIGH reached that bar's 1H EMA34 (as of the previous completed hour). Report: share of
trades that touched the line again, and how many times, by ATR (>= 3% vs 2-3%) and by outcome. Hourly bars: a touch and the stop in
the same hour count as a touch. Descriptive only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "137_rerun_under_1pct_frame.py").read().split('LAY = {')[0])
Z = B[(B.hour == "10:15") & (B.atrp >= 2.0) & B.red & (B.n200 == True) & (B.s8 > B.s34) & (B.gap > -0.25) & (B.gap <= 0.5)].copy()
tc = {}
for t, g in Z.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    e34 = h.Close.ewm(span=34, adjust=False).mean().shift(1).values; H, L = h.High.values, h.Low.values; day = h.index.normalize()
    for ix, r in g.iterrows():
        i = h.index.get_loc(pd.Timestamp(f"{r.date} 10:15")); n = 0; tgt = r.entry * 0.99
        for j in range(i + 1, len(H)):
            if day[j] != day[i]: break
            if H[j] >= e34[j]: n += 1
            if H[j] >= r.high or L[j] <= tgt or j - i >= 5: break
        tc[ix] = n
Z["touches"] = pd.Series(tc)
print("| group | trades | touched the EMA34 again | touched 2+ times | median touches |\n|---|---|---|---|---|")
for nm, X in (("ALL", Z), ("ATR >= 3%", Z[Z.atrp >= 3]), ("ATR 2-3%", Z[Z.atrp < 3])):
    print(f"| {nm} | {len(X)} | {(X.touches >= 1).mean()*100:.0f}% | {(X.touches >= 2).mean()*100:.0f}% | {X.touches.median():.0f} |")
print("\n| group / outcome | TARGET: touched again | STALL: touched again | STOP: touched again |\n|---|---|---|---|")
for nm, X in (("ATR >= 3%", Z[Z.atrp >= 3]), ("ATR 2-3%", Z[Z.atrp < 3])):
    print(f"| {nm} | " + " | ".join(f"{(X[X.o == o].touches >= 1).mean()*100:.0f}% (n {(X.o == o).sum()})" for o in ("target", "stall", "stop")) + " |")
print("\n| group | Rs/trade @1L if it did NOT touch again | if it touched again |\n|---|---|---|")
for nm, X in (("ATR >= 3%", Z[Z.atrp >= 3]), ("ATR 2-3%", Z[Z.atrp < 3])):
    print(f"| {nm} | {X[X.touches == 0].rs1L.mean():+.0f} (n {(X.touches == 0).sum()}) | {X[X.touches >= 1].rs1L.mean():+.0f} (n {(X.touches >= 1).sum()}) |")
