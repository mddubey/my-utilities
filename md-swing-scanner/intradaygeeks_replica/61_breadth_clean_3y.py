"""Re-check 'bullish breadth -> shorts weaker' (47) on CLEAN 3-year 1H data (60's generator, no position blocking),
current filters incl. the daily-range filter (ATR >= 2.56%). Spec fixed 2026-10-03 before running. Breadth = share of
liquid stocks above yesterday's close at the setup candle's close (breadth_1h.csv, from 48). Buckets as in 47
(< 35% / 35-65% / > 65%), plus 35-50 / 50-65 split. By year."""
import importlib.util, os, sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from backtest import load
src = open(HERE / "60_filter_ablation.py").read().split('if __name__ == "__main__":')[0]
src = src.replace('rows.append(dict(set="b", ticker=t, date=dd,', 'rows.append(dict(set="b", ticker=t, date=dd, bt=T[i], atrp=(d.atr14 / d.Close * 100).shift(1).get(dd, np.nan),')
exec(compile(src, "60mod", "exec"))
if __name__ == "__main__":
    from multiprocessing import Pool
    t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    with Pool(6) as p: B = pd.DataFrame(sum(p.map(gen_b, t1, chunksize=10), []))
    F = ["F1", "F2", "F3", "F4", "F5", "F6"]
    B = B[B[F].all(axis=1) & (B.atrp >= 2.56)].copy()
    BR = pd.read_csv(HERE / "breadth_1h.csv", parse_dates=["bt"]).set_index("bt")
    B["adv"] = B.bt.map(BR.adv)
    B["b"] = pd.cut(B.adv, [0, 0.35, 0.5, 0.65, 1], labels=["< 35% (bearish)", "35-50%", "50-65%", "> 65% (bullish)"])
    print(f"clean 1H shorts, all filters + range filter: {len(B)} trades, mean {B.ret.mean()*1000:+.0f} per ₹1 lakh")
    print("| breadth at entry | trades | per trade (₹1 lakh) | 2024 / 2025 / 2026 |\n|---|---|---|---|")
    for k, g in B.groupby("b", observed=True):
        print(f"| {k} | {len(g)} | ₹{g.ret.mean()*1000:+.0f} | " + " / ".join(f"₹{v*1000:+.0f}" for v in g.groupby(g.date.dt.year).ret.mean()) + " |")
