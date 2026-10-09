"""Fine sweep of how far BELOW the 1H EMA34 the day opened (user, 2026-10-10), both exits. Spec fixed before running. Trades: 10:15
candle, red, liquid, ATR >= 2, Nifty > 200d, stock daily 8>34, gap -0.25..+0.5 (148's population). Buckets of (day open / 1H EMA34
- 1): < -1 | -1..-0.75 | -0.75..-0.5 | -0.5..-0.4 | -0.4..-0.3 | -0.3..-0.2 | -0.2..-0.1 | -0.1..0 | 0..+0.5 | > +0.5. Exits E1 (1% /
stop <= 0.5%) and E2 (max(1%, 0.35 x ATR) / stop <= half the target). Cells are small -- results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "148_clean_shape_0915.py").read().split("\ndef row(")[0])
src = open(Path(__file__).resolve().parent / "148_clean_shape_0915.py").read()
exec("def row(" + src.split("\ndef row(")[1].split("\n\n\nH = ")[0])
ov = (B.dayopen / B.ema34 - 1) * 100
R["ov"] = R.ix.map(ov)
X0 = R[(R.hour == "10:15") & R.red]
EDG = [-99, -1, -0.75, -0.5, -0.4, -0.3, -0.2, -0.1, 0, 0.5, 99]
LAB = ["< -1%", "-1 to -0.75%", "-0.75 to -0.5%", "-0.5 to -0.4%", "-0.4 to -0.3%", "-0.3 to -0.2%", "-0.2 to -0.1%", "-0.1 to 0%", "0 to +0.5% (above)", "> +0.5% (above)"]
H = "| open vs 1H EMA34 | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
for en in EX:
    X = X0[X0.ex == en]; b = pd.cut(X.ov, EDG, labels=LAB)
    print(f"\n## {en} (10:15, red, full stack)\n" + H)
    for lab in LAB: print(row(lab, X[b == lab]))
    print(row("ALL below (-inf..0)", X[X.ov < 0])); print(row("just below (-0.5..0)", X[(X.ov >= -0.5) & (X.ov < 0)])); print(row("-1..-0.5", X[(X.ov >= -1) & (X.ov < -0.5)]))
