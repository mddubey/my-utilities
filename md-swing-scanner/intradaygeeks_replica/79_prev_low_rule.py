"""Rule test (user, 2026-10-04): SKIP the short when the previous day's low sits between entry and the 1% target
(script 78: it makes the trade stall). Spec fixed before running. Population: current rules, all setups (how_low_P0.csv,
outcome = the live system's own exit: 1% target / candle-high stop / 5h or EOD, column ret).
  Headline: prev-day low in (entry*0.99, entry).  Neighbours: window 0.75% and 1.25% below entry.
  Report both sets: baseline / kept / removed (target / stall / stop, Rs), by month (30m) / year (1H);
  one-a-day plan (11:15 else 11:45 on 30m, 11:15 else 12:15 on 1H, closest to EMA; a skipped pick passes to the next);
  label-shuffle test on all setups (5,000) and within-day shuffle (2,000).
Pass = kept beats baseline in BOTH sets on all setups AND on the plan, not carried by one period, shuffle p < 0.05."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import DAILY_DIR
HERE = Path(__file__).resolve().parent


def prev_low(args):
    t, g = args
    D = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).Low.dropna()
    return [(ix, D[D.index < pd.Timestamp(r.date)].iloc[-1] if (D.index < pd.Timestamp(r.date)).any() else np.nan) for ix, r in g.iterrows()]


if __name__ == "__main__":
    from multiprocessing import Pool
    y = pd.read_csv(HERE / "how_low_P0.csv")
    with Pool(6) as p:
        pl = dict(sum(p.map(prev_low, list(y.groupby("ticker"))), []))
    y["prev_low"] = pd.Series(pl); y["pl_dist"] = (y.qc - y.prev_low) / y.qc * 100
    y["out"] = y.why.replace({"time": "stall", "eod": "stall"})
    y.to_csv(HERE / "prev_low_rule.csv", index=False)
    rng = np.random.default_rng(79)

    def st(g):
        o = g.out
        return f"{len(g):5d} | tgt {(o == 'target').mean()*100:4.1f} stall {(o == 'stall').mean()*100:4.1f} stop {(o == 'stop').mean()*100:4.1f} | Rs {g.ret.mean()*1000:+4.0f}"
    for s, nm, per, al in (("a", "30m Jun-Sep 2026", 7, [3, 4]), ("b", "1H 3 years", 4, [10, 11])):
        z = y[y.set == s].copy(); z["p"] = z.date.str[:per]
        plan = lambda x: x[x.alarm.isin(al)].sort_values(["date", "alarm", "dist"]).groupby("date").head(1)
        pb = plan(z)
        print(f"\n################ {nm}")
        print(f"  baseline          {st(z)}   | plan {len(pb)} trades Rs {pb.ret.mean()*1000:+.0f} total {pb.ret.sum()*1000:+.0f}")
        for w in (0.75, 1.0, 1.25):
            skip = (z.pl_dist > 0) & (z.pl_dist < w)
            k, r = z[~skip], z[skip]; pk = plan(k)
            tag = "HEADLINE" if w == 1.0 else "neighbour"
            print(f"\n  [{tag}] skip if prev-day low within {w}% below entry")
            print(f"    kept            {st(k)}   | plan {len(pk)} trades Rs {pk.ret.mean()*1000:+.0f} total {pk.ret.sum()*1000:+.0f}")
            print(f"    removed         {st(r)}")
            by = z.assign(sk=skip).groupby(["p", "sk"]).ret.agg(["mean", "size"]).unstack("sk")
            print("    by period base / kept / removed(n): " + "  ".join(
                f"{p}: {z[z.p == p].ret.mean()*1000:+.0f} / {by.loc[p, ('mean', False)]*1000:+.0f} / {by.loc[p, ('mean', True)]*1000:+.0f}({int(by.loc[p, ('size', True)])})" for p in by.index))
            pp = pb.assign(p=pb.date.str[:per]); pkk = pk.assign(p=pk.date.str[:per])
            print("    plan by period base / with rule: " + "  ".join(f"{p}: {pp[pp.p == p].ret.mean()*1000:+.0f} / {pkk[pkk.p == p].ret.mean()*1000:+.0f}" for p in sorted(pp.p.unique())))
            if w == 1.0:
                lab, ret = skip.values, z.ret.values; obs = ret[~lab].mean() - ret[lab].mean()
                sims = np.array([(lambda q: ret[~q].mean() - ret[q].mean())(rng.permutation(lab)) for _ in range(5000)])
                gi = z.groupby("date").indices; sims2 = []
                for _ in range(2000):
                    q = lab.copy()
                    for ii in gi.values(): q[ii] = rng.permutation(lab[ii])
                    sims2.append(ret[~q].mean() - ret[q].mean())
                print(f"    shuffle: kept-minus-removed {obs*1000:+.0f} Rs, p = {np.mean(sims >= obs):.4f}; within-day p = {np.mean(np.array(sims2) >= obs):.4f}")
