"""User (2026-10-03): replace distance cut-offs with how the chart is actually read. Spec fixed before running, no tuning:
In the last N completed 1H candles before entry (N = 2, 3, 4, all pre-declared, none chosen after), each candle compared
with the 1H 8-EMA level it was trading against (EMA as of the prior hour's close):
  HOLD   (8-EMA acting as support)    : low <= 8-EMA and close > 8-EMA
  REJECT (8-EMA acting as resistance) : high >= 8-EMA and close < 8-EMA
Trade groups: hold only | reject only | both | neither. Same population as 62-65. Passes only if it helps in BOTH sets."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
src = open(HERE / "63_ema8_support_and_recent_fall.py").read().split('if __name__ == "__main__":')[0]
src = src.replace('atrp = (d.atr14 / d.Close * 100).shift(1); rows = []\n    for day, g in m.groupby',
    'atrp = (d.atr14 / d.Close * 100).shift(1); rows = []\n'
    '    hk = hour_key(m.index); hh = m.High.groupby(hk).max(); hl = m.Low.groupby(hk).min()\n'
    '    HOLD = ((hl <= e8) & (hc > e8)).values; REJ = ((hh >= e8) & (hc < e8)).values; HI = hc.index\n'
    '    for day, g in m.groupby', 1)
src = src.replace('d8=(qc - E8) / qc * 100,',
    'd8=(qc - E8) / qc * 100, **hr(HOLD, REJ, HI.get_loc(base + ((q + 1) * 30 // 60 - 1) * pd.Timedelta("60min"))),', 1)
src = src.replace('d8=(qc - E8[i]) / qc * 100,',
    'd8=(qc - E8[i]) / qc * 100, **hr((L <= E8) & (C > E8), (H >= E8) & (C < E8), i),', 1)
src = src.replace("def walk(", '''def hr(HOLD, REJ, j):
    return {f"{k}{n}": bool(X[max(j - n + 1, 0):j + 1].any()) for n in (2, 3, 4) for k, X in (("hold", HOLD), ("rej", REJ))}


def walk(''', 1)
assert src.count("**hr(") == 2
exec(compile(src, "63mod", "exec"))
if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_")); t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    with Pool(6) as p:
        A = pd.DataFrame(sum(p.map(gen_a, t5, chunksize=10), [])); B = pd.DataFrame(sum(p.map(gen_b, t1, chunksize=10), []))
    pd.concat([A, B]).to_csv(HERE / "ema8_hold_reject.csv", index=False)
    print(len(A), len(B))
