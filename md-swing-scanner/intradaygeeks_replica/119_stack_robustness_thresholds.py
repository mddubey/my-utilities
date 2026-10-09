"""Robustness check 1 of the short-stack LEAD (user, 2026-10-09). Spec fixed before running. Population: plain liquid 1H EMA34
short touch (115 v3), candles 09:15/10:15, red. Vary the three chosen parameters over pre-declared nearby values:
  ATR(14)% yday >= 2.0 / 2.56 / 3.0;  stock daily trend UP = daily 8-EMA > 21 / 34 / 50-EMA (yday);
  Nifty UP = daily 8-EMA > 34-EMA (yday)  or  close > 50-day SMA (yday).
Pass = positive across most cells and years, not only the one picked. Net = Rs per Rs1 lakh after Rs85. Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from data.paths import DAILY_DIR
P = pd.read_csv(HERE / "plain_touch_1h.csv")
S = P[(P.liq_prev >= 15) & P.hour.isin(["09:15", "10:15"]) & P.red].copy(); S["d"] = pd.to_datetime(S.date); S["yr"] = S.date.str[:4]
feat = []
for t, g in S.groupby("ticker"):
    d = load(t); c = d.Close
    f = pd.DataFrame({"e8": c.ewm(span=8, adjust=False).mean(), "e21": c.ewm(span=21, adjust=False).mean(),
                      "e34": c.ewm(span=34, adjust=False).mean(), "e50": c.ewm(span=50, adjust=False).mean(),
                      "atrp": d.atr14 / c * 100}).shift(1)
    x = g[["d"]].join(f, on="d"); x.index = g.index; feat.append(x.drop(columns="d"))
S = S.join(pd.concat(feat))
n = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index(); nc = n["Close"]
nf = pd.DataFrame({"n834": nc.ewm(span=8, adjust=False).mean() > nc.ewm(span=34, adjust=False).mean(), "nsma": nc > nc.rolling(50).mean()}).shift(1)
S = S.join(nf, on="d")


def cell(g):
    if len(g) < 50: return f"n {len(g)}"
    y = "/".join(f"{g[g.yr == k].ret.mean()*1000 - 85:+.0f}" for k in ("2024", "2025", "2026"))
    return f"{g.ret.mean()*1000 - 85:+.0f} ({y}) n{len(g)}"


for nname, ncol in (("Nifty 8>34", "n834"), ("Nifty > 50-day SMA", "nsma")):
    print(f"\n## {nname} -- cells: net (2024/2025/2026) n\n| stock trend \\ ATR | >= 2.0 | >= 2.56 | >= 3.0 |\n|---|---|---|---|")
    for tr in ("e21", "e34", "e50"):
        base = S[(S[ncol] == True) & (S.e8 > S[tr])]
        print(f"| daily 8 > {tr[1:]} | " + " | ".join(cell(base[base.atrp >= a]) for a in (2.0, 2.56, 3.0)) + " |")
