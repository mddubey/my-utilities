"""Bisect the 'opened ABOVE the 1H EMA34' group (user, 2026-10-10: 'that can't be just dead'). Spec fixed before running.
Trades: 10:15 candle, red, full stack (148's population), day's open ABOVE the 1H EMA34. Splits (declared): (1) the 09:15 candle CLOSED
below the 1H EMA34 (fell through in hour 1; 10:15 = retest from below) vs still above (10:15 = first break); (2) already moved from the
day's high < 0.5 vs >= 0.5 of the daily ATR; (3) ATR >= 3% vs 2-3%; (4) price >= 0.5% above the live daily 8-EMA vs less. Both exits.
Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "148_clean_shape_0915.py").read().split("\ndef row(")[0])
src = open(Path(__file__).resolve().parent / "148_clean_shape_0915.py").read()
exec("def row(" + src.split("\ndef row(")[1].split("\n\n\nH = ")[0])
c915, dhi = {}, {}
for t, g in B.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    e34 = h.Close.ewm(span=34, adjust=False).mean().shift(1)
    for ix, r in g.iterrows():
        k9 = pd.Timestamp(f"{r.date} 09:15")
        if k9 in h.index: c915[ix] = h.at[k9, "Close"] < e34.get(k9)
        d0 = h[(h.index.normalize() == pd.Timestamp(r.date)) & (h.index <= pd.Timestamp(f"{r.date} {r.hour}"))]; dhi[ix] = d0.High.max()
B["c915_below"] = pd.Series(c915); B["moved"] = (pd.Series(dhi) - B.entry) / B.entry * 100 / B.atrp
B["d8gap"] = (B.entry - (2 / 9 * B.entry + 7 / 9 * B.s8)) / B.entry * 100
for c in ("c915_below", "moved", "atrp", "d8gap"): R[c] = R.ix.map(B[c])
X0 = R[(R.hour == "10:15") & R.red & ~R.below_open]
SPL = (("09:15 closed BELOW the line (10:15 = retest from below)", lambda d: d.c915_below == True), ("09:15 still ABOVE (10:15 = first break)", lambda d: d.c915_below == False),
       ("already moved < 0.5 ATR", lambda d: d.moved < 0.5), ("already moved >= 0.5 ATR (DLF-like)", lambda d: d.moved >= 0.5),
       ("ATR >= 3%", lambda d: d.atrp >= 3), ("ATR 2-3%", lambda d: d.atrp < 3),
       ("price >= 0.5% above daily 8-EMA", lambda d: d.d8gap >= 0.5), ("price < 0.5% above daily 8-EMA", lambda d: d.d8gap < 0.5))
H = "| split | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
for en in EX:
    X = X0[X0.ex == en]
    print(f"\n## {en} -- opened ABOVE the 1H EMA34 (10:15, red, full stack)\n" + H); print(row("ALL opened above", X))
    for nm, f in SPL: print(row(nm, X[f(X)]))
