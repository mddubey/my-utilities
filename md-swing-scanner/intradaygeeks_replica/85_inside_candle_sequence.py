"""Inside the trigger candle (user, 2026-10-04): a 30-min candle hides the ORDER of events. Spec fixed before running.
Population: today's 30m-set trades (how_low_P0.csv set a; 10:45 / 11:45 = 30-min candle, 11:15 / 12:15 = full hour).
Split the trigger candle into two halves (15+15 min, or 30+30 min for the full hour):
  SEQUENTIAL = the candle's high was made in the FIRST half AND the second half made a LOWER LOW than the first half
               (rejected at the EMA, then sellers pushed again).   OTHER = everything else.
Report target / stall / stop, Rs gross / net, by month, and the one-a-day plans A (11:15 else 11:45) and B (10:45 at
10:50 else 11:15 else 11:45, from script 83) with OTHER skipped (a skipped pick passes to the next setup)."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import INTRADAY_5M_DIR
HERE = Path(__file__).resolve().parent; COST = 0.085


def one(args):
    t, g = args
    m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0); m.index = pd.to_datetime(m.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    out = []
    for ix, r in g.iterrows():
        day = pd.Timestamp(r.date); at = day + pd.Timedelta("9h15min") + (int(r.alarm) + 1) * pd.Timedelta("30min")
        span = pd.Timedelta("60min") if int(r.alarm) in (3, 5) else pd.Timedelta("30min")
        c = m[(m.index >= at - span) & (m.index < at)]
        h1, h2 = c[c.index < at - span / 2], c[c.index >= at - span / 2]
        if h1.empty or h2.empty: continue
        out.append(dict(ix=ix, seq=bool(h1.High.max() >= h2.High.max() and h2.Low.min() < h1.Low.min()),
                        high_first=bool(h1.High.max() >= h2.High.max()), lower_low=bool(h2.Low.min() < h1.Low.min())))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    y = pd.read_csv(HERE / "how_low_P0.csv"); y = y[y.set == "a"]
    with Pool(6) as p:
        R = pd.DataFrame(sum(p.map(one, list(y.groupby("ticker"))), [])).set_index("ix")
    z = y.join(R, how="inner"); z["o"] = z.why.replace({"time": "stall", "eod": "stall"}); z["p"] = z.date.str[:7]
    sp = lambda g: f"n={len(g):3d} | tgt {(g.o == 'target').mean()*100:4.1f} stall {(g.o == 'stall').mean()*100:4.1f} stop {(g.o == 'stop').mean()*100:4.1f} | Rs gross {g.ret.mean()*1000:+4.0f} net {(g.ret.mean()-COST)*1000:+4.0f}"
    print("all              ", sp(z))
    print("SEQUENTIAL       ", sp(z[z.seq]))
    print("OTHER            ", sp(z[~z.seq]))
    print("  parts: high made in first half", sp(z[z.high_first]), "|| second half lower low", sp(z[z.lower_low]))
    print("  by month seq / other: " + "  ".join(f"{k}: {g[g.seq].ret.mean()*1000:+.0f}({g.seq.sum()}) / {g[~g.seq].ret.mean()*1000:+.0f}" for k, g in z.groupby("p")))
    for al, lab in ((2, "10:45"), (3, "11:15 (full hour)"), (4, "11:45"), (5, "12:15 (full hour)")):
        g = z[z.alarm == al]; print(f"  {lab:18s} seq {sp(g[g.seq])}  || other {sp(g[~g.seq])}")
    rng = np.random.default_rng(85); lab_ = z.seq.values; r = z.ret.values; obs = r[lab_].mean() - r[~lab_].mean()
    sims = np.array([(lambda q: r[q].mean() - r[~q].mean())(rng.permutation(lab_)) for _ in range(5000)])
    print(f"  shuffle p = {np.mean(sims >= obs):.3f}")
    late = pd.read_csv(HERE / "late_1045_and_retest.csv"); late = late[late.set == "a"][["ticker", "date", "alarm", "L10:50", "S10:50"]]
    z = z.merge(late, on=["ticker", "date", "alarm"], how="left")
    def plan(df, use_late):
        parts = []
        if use_late:
            v = df[(df.alarm == 2) & df["S10:50"].isin(["target", "stall", "stop"])].assign(r=lambda d: d["L10:50"])
            parts.append(v.sort_values(["date", "dist"]).groupby("date").head(1))
        for al in (3, 4):
            v = df[df.alarm == al].assign(r=lambda d: d.ret); v = v.sort_values(["date", "dist"]).groupby("date").head(1)
            done = pd.concat(parts).date if parts else pd.Series(dtype=str)
            parts.append(v[~v.date.isin(done)])
        return pd.concat(parts)
    for nm, ul in (("A 11:15 else 11:45", False), ("B 10:45@10:50 else 11:15 else 11:45", True)):
        for f, df in (("all setups", z), ("SEQUENTIAL only", z[z.seq])):
            p = plan(df, ul)
            print(f"  PLAN {nm:36s} {f:16s} {len(p):3d} trades | net {(p.r.mean()-COST)*1000:+4.0f}/trade | total net {(p.r - COST).sum()*1000:+7.0f} | "
                  + " ".join(f"{k}: {g.r.mean()*1000:+.0f}" for k, g in p.groupby(p.date.str[:7])))
