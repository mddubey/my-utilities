"""Lower the stop rate (user, 2026-10-03). Spec fixed before running. Same population as 62-66 (60's generators: all six
filters + 2:1 rule + daily ATR >= 2.56%, no position blocking). Two filters, each judged on BOTH sets with baseline /
kept / removed, stop rate, target rate, per-trade, setups/day, by month (30m) / year (1H):
 (a) NOISE: ratio = stop distance % / typical candle range %, typical = median of the stock's daily-median candle range
     (H-L)/C over the previous N trading days (N = 5 headline; 3 and 10 pre-declared robustness), candle = the trigger
     timeframe (30m in set a, 1H in set b). KEEP if ratio >= 1.0 (stop wider than one typical candle).
 (b) REJECTION STRENGTH: pos = (close - low) / (high - low) of the trigger candle (0 = closed at its low).
     KEEP if pos <= 0.5 (bottom half); stricter variant pos <= 1/3."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
src = open(HERE / "63_ema8_support_and_recent_fall.py").read().split('if __name__ == "__main__":')[0]
# set a: 30m candle ranges per day -> rolling noise
src = src.replace('atrp = (d.atr14 / d.Close * 100).shift(1); rows = []\n    for day, g in m.groupby',
 'atrp = (d.atr14 / d.Close * 100).shift(1); rows = []\n'
 '    dn = m.index.normalize(); k30all = dn + pd.Timedelta("9h15min") + ((m.index - dn - pd.Timedelta("9h15min")) // pd.Timedelta("30min")) * pd.Timedelta("30min")\n'
 '    c30 = m.groupby(k30all).agg(H=("High", "max"), L=("Low", "min"), C=("Close", "last"))\n'
 '    NZ = noise_by_day((c30.H - c30.L) / c30.C * 100, c30.index.normalize())\n'
 '    for day, g in m.groupby', 1)
src = src.replace('d8=(qc - E8) / qc * 100,',
 'd8=(qc - E8) / qc * 100, alarm=q, dist=(E - qc) / E * 100, wick=(qh - qo) / qc * 100, stop=(qh - qc) / qc * 100, pos=(qc - L[qi].min()) / max(qh - L[qi].min(), 1e-9), '
 '**{f"nz{n}": NZ[n].get(day, np.nan) for n in (3, 5, 10)},', 1)
# set b: 1H bar ranges
src = src.replace('hi_day = h.High.groupby(day).cummax().values; atrp',
 'hi_day = h.High.groupby(day).cummax().values; NZ = noise_by_day((h.High - h.Low) / h.Close * 100, day); atrp', 1)
src = src.replace('d8=(qc - E8[i]) / qc * 100,',
 'd8=(qc - E8[i]) / qc * 100, alarm=T[i].hour, dist=(E - qc) / E * 100, wick=(qh - O[i]) / qc * 100, stop=(qh - qc) / qc * 100, pos=(qc - L[i]) / max(qh - L[i], 1e-9), '
 '**{f"nz{n}": NZ[n].get(dd, np.nan) for n in (3, 5, 10)},', 1)
src = src.replace("def walk(", '''def noise_by_day(rng, days):
    """typical candle range known BEFORE each day: median over the previous n days of each day's median range"""
    dm = pd.Series(np.asarray(rng), index=np.asarray(days)).groupby(level=0).median()
    return {n: dm.rolling(n, min_periods=n).median().shift(1) for n in (3, 5, 10)}


def walk(''', 1)
assert src.count("nz{n}") == 2 and "NZ = noise_by_day" in src
exec(compile(src, "63mod", "exec"))
if __name__ == "__main__" and "--gen" in sys.argv:
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_")); t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    with Pool(6) as p:
        A = pd.DataFrame(sum(p.map(gen_a, t5, chunksize=10), [])); B = pd.DataFrame(sum(p.map(gen_b, t1, chunksize=10), []))
    pd.concat([A, B]).to_csv(HERE / "stop_rate_filters.csv", index=False)
    print(len(A), len(B))


def report(df):
    """baseline / kept / removed per filter and set; Rs per trade on Rs 1 lakh"""
    df = df.copy(); df["date"] = pd.to_datetime(df.date); df["per"] = np.where(df.set == "a", df.date.dt.strftime("%b"), df.date.dt.year.astype(str))
    for n in (3, 5, 10): df[f"ratio{n}"] = df.stop / df[f"nz{n}"]
    F = {"noise5 >= 1": lambda x: x.ratio5 >= 1, "noise3 >= 1": lambda x: x.ratio3 >= 1, "noise10 >= 1": lambda x: x.ratio10 >= 1,
         "pos <= 0.5": lambda x: x.pos <= 0.5, "pos <= 1/3": lambda x: x.pos <= 1 / 3}
    def line(g, days):
        return f"{len(g):5d} {len(g) / days:5.2f} {(g.why == 'stop').mean() * 100:5.1f} {(g.why == 'target').mean() * 100:5.1f} {g.ret.mean() * 1000:+6.0f}"
    for s, nm in (("a", "30m Jun-Sep 2026"), ("b", "1H 2024-26")):
        x = df[df.set == s]; days = x.date.nunique(); pers = list(dict.fromkeys(x.sort_values("date").per))
        print(f"\n=== set {s}: {nm}  ({len(x)} trades, {days} days; noise NaN: n3 {x.nz3.isna().sum()} n5 {x.nz5.isna().sum()} n10 {x.nz10.isna().sum()})")
        print(f"{'filter':14s} {'group':8s} {'n':>5s} {'/day':>5s} {'stop%':>5s} {'tgt%':>5s} {'Rs/tr':>6s} | Rs/trade by " + ("month" if s == "a" else "year") + ": " + " ".join(f"{p:>6s}" for p in pers))
        for fn, f in [("baseline", None)] + list(F.items()):
            groups = [("all", x)] if f is None else [("kept", x[f(x)]), ("removed", x[~f(x) & ~x[fn.split()[0].replace('noise', 'ratio') if 'noise' in fn else 'pos'].isna()])]
            for gn, g in groups:
                bp = " ".join(f"{g[g.per == p].ret.mean() * 1000:+6.0f}" if (g.per == p).sum() else "     -" for p in pers)
                print(f"{fn:14s} {gn:8s} {line(g, days)} | {bp}   n/{'mo' if s == 'a' else 'yr'}: " + " ".join(str((g.per == p).sum()) for p in pers))
        print("gradient, noise ratio (5d):")
        for lo, hi in ((0, .5), (.5, .75), (.75, 1), (1, 1.5), (1.5, 99)):
            g = x[(x.ratio5 >= lo) & (x.ratio5 < hi)]; print(f"  {lo:4.2f}-{hi:<5.2f} {line(g, days)}")
        print("gradient, close position in candle:")
        for lo, hi in ((0, 1 / 3), (1 / 3, .5), (.5, 2 / 3), (2 / 3, 1.01)):
            g = x[(x.pos >= lo) & (x.pos < hi)]; print(f"  {lo:4.2f}-{hi:<5.2f} {line(g, days)}")
        print(f"  median stop {x.stop.median():.2f}%, median typical range (5d) {x.nz5.median():.2f}%, median ratio {x.ratio5.median():.2f}")


if __name__ == "__main__":
    report(pd.read_csv(HERE / "stop_rate_filters.csv"))
