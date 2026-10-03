"""User's chart observation (2026-10-03): shorts fail when the 1H 8-EMA sits BELOW the entry (support in the target's
path); they work when price is below BOTH 1H EMAs. Spec fixed before running. Same generators as 60 (clean, no position
blocking), all six filters + daily-range filter (ATR >= 2.56%). Feature: d8 = (entry - 1H EMA8)/entry*100, EMA8 as of
the last completed hour (same value the trend check uses). Groups: EMA8 above entry (d8 <= 0) | below within 1%
(0 < d8 < 1) | below by >= 1%. Rule: adopt only if it holds in BOTH the 30m (Jun-Sep 2026) and 1H (2024-26) sets."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from backtest import load
src = open(HERE / "60_filter_ablation.py").read().split('if __name__ == "__main__":')[0]
src = src.replace('rows.append(dict(set="a", ticker=t, date=day,', 'rows.append(dict(set="a", ticker=t, date=day, alarm=(base + (q + 1) * pd.Timedelta("30min")).strftime("%H:%M"), d8=(qc - E8) / qc * 100, atrp=(d.atr14 / d.Close * 100).shift(1).get(day, np.nan),')
src = src.replace('rows.append(dict(set="b", ticker=t, date=dd,', 'rows.append(dict(set="b", ticker=t, date=dd, d8=(qc - E8[i]) / qc * 100, atrp=(d.atr14 / d.Close * 100).shift(1).get(dd, np.nan),')
exec(compile(src, "60mod", "exec"))
if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_")); t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    with Pool(6) as p:
        A = pd.DataFrame(sum(p.map(gen_a, t5, chunksize=10), [])); B = pd.DataFrame(sum(p.map(gen_b, t1, chunksize=10), []))
    F = ["F1", "F2", "F3", "F4", "F5", "F6"]
    A = A[A[F].all(axis=1) & (A.atrp >= 2.56)].copy(); B = B[B[F].all(axis=1) & (B.atrp >= 2.56)].copy()
    pd.concat([A, B]).to_csv(HERE / "ema8_position.csv", index=False)
    lab = lambda s: pd.cut(s, [-np.inf, 0, 1, np.inf], labels=["1H 8-EMA ABOVE entry (no support below)", "8-EMA below, within 1% (support in the path)", "8-EMA below by 1%+"])
    for nm, D, per, nd in (("30-min version, Jun-Sep 2026 (by month)", A, lambda x: x.date.dt.month, A.date.nunique()),
                           ("1H version, clean, 2024-26 (by year)", B, lambda x: x.date.dt.year, B.date.nunique())):
        D["g"] = lab(D.d8)
        print(f"\n### {nm} -- all: {len(D)} trades, Rs{D.ret.mean()*1000:+.0f}/trade\n| where the 1H 8-EMA is | trades | share | per trade (Rs1 lakh) | hit Rs1,000 | by period |\n|---|---|---|---|---|---|")
        for k, g in D.groupby("g", observed=True):
            print(f"| {k} | {len(g)} | {len(g)/len(D)*100:.0f}% | Rs{g.ret.mean()*1000:+.0f} | {(g.ret>=0.999).mean()*100:.0f}% | " + " / ".join(f"Rs{v*1000:+.0f}" for v in g.groupby(per(g)).ret.mean()) + " |")
        k = D[D.d8 <= 0]
        print(f"| KEEP only '8-EMA above entry' | {len(k)} | {len(k)/len(D)*100:.0f}% | Rs{k.ret.mean()*1000:+.0f} | {(k.ret>=0.999).mean()*100:.0f}% | {len(k)/nd:.1f} setups/day |")
