"""User (2026-10-03): find the SIMPLE textbook way to say "the 1H 8-EMA under my short is a problem". Textbook bearish
EMA stack: price < fast EMA < slow EMA, fast EMA sloping down ("don't trade inside the lines"). Spec fixed before running,
same population as 62/63. Groups: STACK (price below 8-EMA; 8 < 34 already required) vs INSIDE (price between 8 and 34),
each split by 8-EMA slope over the last completed hour (falling / rising). No thresholds to tune."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
src = open(HERE / "63_ema8_support_and_recent_fall.py").read().split('if __name__ == "__main__":')[0]
src = src.replace('E8 = e34.get(hs, np.nan), e8.get(hs, np.nan)', 'E8 = e34.get(hs, np.nan), e8.get(hs, np.nan); E8p = e8.shift(1).get(hs, np.nan)')
src = src.replace('d8=(qc - E8) / qc * 100,', 'd8=(qc - E8) / qc * 100, s8=(E8 - E8p) / qc * 100,')
src = src.replace('d8=(qc - E8[i]) / qc * 100,', 'd8=(qc - E8[i]) / qc * 100, s8=(E8[i] - E8[i - 1]) / qc * 100,')
exec(compile(src, "63mod", "exec"))
if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_")); t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    with Pool(6) as p:
        A = pd.DataFrame(sum(p.map(gen_a, t5, chunksize=10), [])); B = pd.DataFrame(sum(p.map(gen_b, t1, chunksize=10), []))
    Z = pd.concat([A, B]); Z.to_csv(HERE / "ema_stack.csv", index=False)
    for s, nm, per in (("a", "30m Jun-Sep 2026", lambda x: x.date.dt.month), ("b", "1H 2024-26", lambda x: x.date.dt.year)):
        D = Z[Z.set == s]
        print(f"\n{nm}: all {len(D)} Rs{D.ret.mean()*1000:+.0f}")
        for st in (True, False):
            for fall in (True, False):
                g = D[((D.d8 <= 0) == st) & ((D.s8 < 0) == fall)]
                print(f"| {'STACK price<8<34' if st else 'INSIDE 8<price<34'} | 8-EMA {'falling' if fall else 'rising '} | {len(g)} | Rs{g.ret.mean()*1000:+.0f} | stop {(g.why=='stop').mean()*100:.0f}% | "
                      + " / ".join(f"{v*1000:+.0f}" for v in g.groupby(per(g)).ret.mean()))
