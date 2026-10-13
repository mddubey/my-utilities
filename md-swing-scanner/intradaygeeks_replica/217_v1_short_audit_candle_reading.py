"""AUDIT of v1's existing SHORT trades by the user's candle reading (2026-10-13, user: 'below the 200-day v1 never works -- maybe a
by-product of counting trades that are not of that side'; MOTILALOFS 10:15 = body cross, 11:15 = support). Uses script 164's trades
(v1 rules without the Nifty filter, 2024-01..2026-09, 10:15 candle, E1 + E2) -- no new trades, no new rules. Classes declared before
running, from the user's definition (the trigger candle vs the 1H EMA34 'line'; close position cp = (C - L) / (H - L)):
  CLEAN REJECTION   opened below the line or only marginally above (<= +0.2%) AND closed in the bottom 40% (cp <= 0.4) -- sellers won AT the line
  WEAK REJECTION    opened below / marginally above AND closed higher (cp > 0.4) -- touched the line but sellers did not win the candle
  BREAKDOWN         opened clearly above (> +0.2%) AND cp <= 0.4 -- a body cross down, no fight at the line
  BREAKDOWN + WICK  opened clearly above AND cp > 0.4 -- body cross with buyers pushing back from below (support underneath)
  Report per class, Nifty above / below its 200-day, both exits: trades, stop %, Rs/trade @1L; plus by year below 200d.
Prints 10 random below-200d LOSERS (stops) with their class for a chart check."""
import sys, os, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.argv = ["x"]
__file__ = os.path.join(HERE, "164_v1_without_nifty200.py")
src = open(__file__).read().split("\nH = ")[0]
with contextlib.redirect_stdout(io.StringIO()): exec(src)
import pandas as pd, numpy as np

for c in ("ticker", "entry", "high", "low"): V[c] = V.ix.map(B[c])
rng = (V.high - V.low).replace(0, np.nan); V["cp"] = (V.entry - V.low) / rng
V["open_vs_line"] = (V.open / V.ema34 - 1) * 100
V["cls"] = np.select([(V.open_vs_line <= 0.2) & (V.cp <= 0.4), (V.open_vs_line <= 0.2) & (V.cp > 0.4), (V.open_vs_line > 0.2) & (V.cp <= 0.4)],
                     ["CLEAN REJECTION", "WEAK REJECTION", "BREAKDOWN"], "BREAKDOWN + WICK")
assert V.cp.notna().all() and (V.high >= V.ema34).all() and (V.entry < V.ema34).all(), "trigger-candle sanity failed"
ORDER = ["CLEAN REJECTION", "WEAK REJECTION", "BREAKDOWN", "BREAKDOWN + WICK"]
for en in sorted(V.ex.unique()):
    X = V[V.ex == en]
    print(f"\n## {en}\n| class | Nifty ABOVE 200d: trades / stopped / Rs @1L | Nifty BELOW 200d: trades / stopped / Rs @1L | below 200d by year 2024 / 2025 / 2026 (n) |\n|---|---|---|---|")
    for c in ORDER + ["ALL"]:
        x = X if c == "ALL" else X[X.cls == c]; cells = []
        for nv in (True, False):
            y = x[x.n200 == nv]; cells.append(f"{len(y)} / {(y.o == 'stop').mean()*100:.0f}% / {y.rs1L.mean():+.0f}" if len(y) else "0")
        yb = x[x.n200 == False]; yrs = " / ".join(f"{yb[yb.yr.astype(str) == str(yr)].rs1L.mean():+.0f} ({(yb.yr.astype(str) == str(yr)).sum()})" if (yb.yr.astype(str) == str(yr)).any() else "- (0)" for yr in (2024, 2025, 2026))
        print(f"| {c} | {cells[0]} | {cells[1]} | {yrs} |")
L = V[(V.n200 == False) & (V.o == "stop")].drop_duplicates("ix")
print(f"\nCHART CHECK -- 10 random below-200d STOPPED trades (unique trades: {len(L)}):")
print(L.sample(min(10, len(L)), random_state=13)[["date", "ticker", "cls", "open", "high", "low", "entry", "ema34", "open_vs_line", "cp"]].round(2).sort_values("date").to_string(index=False))
