"""Check 2 refined by the user (2026-10-10): the problem is the DOJI, worst when the 1H EMA34 cuts through its body. Spec fixed
before running. v1 trades (10:15, red, full stack, Rs100 price floor), branches A (opened 0-0.5% below the 1H EMA34) and B (opened
above, ATR >= 3%), exits E1 / E2. Signal-candle groups: normal (body >= 25% of range) | doji entirely below the line (body < 25%,
candle open < EMA34) | doji CUT by the line (body < 25%, candle open >= EMA34 > close). Also shown: body 25-50% (info). Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "150_open_below_sweep.py").read().split("\nEDG = ")[0])
B["bodyp"] = (B.open - B.entry) / (B.high - B["low"]).replace(0, float("nan"))
for c in ("bodyp", "price_ok", "atrp", "open", "ema34"): R[c] = R.ix.map(B[c])
X0 = R[(R.hour == "10:15") & R.red & (R.price_ok == True)]
H = "| group | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
for en in EX:
    for bn, bm in (("A: opened 0-0.5% below", lambda d: (d.ov >= -0.5) & (d.ov < 0)), ("B: opened above, ATR >= 3%", lambda d: (d.ov >= 0) & (d.atrp >= 3))):
        X = X0[(X0.ex == en)]; X = X[bm(X)]
        doji = X.bodyp < 0.25; cut = X.open >= X.ema34
        print(f"\n## {en} -- branch {bn} ({len(X)} trades; dojis {doji.mean()*100:.0f}%, of which cut by the line {(doji & cut).sum()})\n" + H)
        print(row("ALL", X)); print(row("normal candle (body >= 25%)", X[~doji])); print(row("  of which body 25-50% (info)", X[(X.bodyp >= 0.25) & (X.bodyp < 0.5)]))
        print(row("doji entirely BELOW the line", X[doji & ~cut])); print(row("doji CUT by the line (worst)", X[doji & cut]))
        print(row("ALL minus the cut dojis", X[~(doji & cut)]))
