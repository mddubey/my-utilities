"""Re-check the 10:15 alarm under TODAY's rules (user, 2026-10-04: free 10:15-10:20, busy ~10:20-10:50). The old
verdict (scripts 39 / 43, before the ATR filter and full-hour rule): 10:15 was the weakest alarm (30m: -0.003%/trade;
1H: +0.073 vs 11:15 +0.132) and adding it to the one-a-day plan made the plan worse. Spec fixed before running.
30m set, current checklist + 2:1 + ATR >= 2.56%:  V30 = 30-min candle 09:45-10:15;  V60 = full opening hour 09:15-10:15
(the hour-close rule used at 11:15 / 12:15). Entry at 10:15 on time (the user is free then). Plans, one trade a day:
  B  = 10:45 looked at 10:50 (scan rule) else 11:15 else 11:45   (script 83)
  C  = 10:15 first, else B.   Rs net of ~Rs85, target / stall / stop, by month."""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
MODE = sys.argv[1] if len(sys.argv) > 1 else "V30"
s67 = open(HERE / "67_stop_rate_filters.py").read()
head, tail = s67.split('exec(compile(src, "63mod", "exec"))', 1)
head += f'''src = src.replace("for q in (2, 3, 4, 5):", "for q in (1,):", 1)
if {MODE!r} == "V60":
    src = src.replace("qi = np.where(k30 == q)[0]", "qi = np.where((k30 == q) | (k30 == q - 1))[0]", 1)
'''
exec(compile(head + 'exec(compile(src, "63mod", "exec"))\n', "87", "exec"))
COST = 0.085

if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p:
        A = pd.DataFrame(sum(p.map(gen_a, t5, chunksize=10), []))
    A["date"] = pd.to_datetime(A.date).dt.strftime("%Y-%m-%d"); A["st"] = A.why.replace({"time": "stall", "eod": "stall"})
    sp = lambda g: f"n={len(g):3d} | tgt {(g.st == 'target').mean()*100:4.1f} stall {(g.st == 'stall').mean()*100:4.1f} stop {(g.st == 'stop').mean()*100:4.1f} | stop dist {g.stop.median():.2f}% | Rs gross {g.ret.mean()*1000:+4.0f} net {(g.ret.mean()-COST)*1000:+4.0f}"
    print(f"{MODE} 10:15 alarm, all setups: " + sp(A) + f" | {len(A)/71:.1f}/day | by month " + " ".join(f"{k}: {g.ret.mean()*1000:+.0f}" for k, g in A.groupby(A.date.str[:7])))
    late = pd.read_csv(HERE / "late_1045_and_retest.csv"); a = late[late.set == "a"].copy()
    a["st"] = a.why.replace({"time": "stall", "eod": "stall"}); a["r"] = a.ret
    pick = lambda d: d.sort_values(["date", "dist"]).groupby("date").head(1)
    v = a[(a.alarm == 2) & a["S10:50"].isin(["target", "stall", "stop"])].copy(); v["r"] = v["L10:50"]; v["st"] = v["S10:50"]
    parts = [pick(v)]
    for al in (3, 4):
        x = pick(a[a.alarm == al]); parts.append(x[~x.date.isin(pd.concat(parts).date)])
    B = pd.concat(parts)
    f15 = pick(A).assign(r=lambda d: d.ret)
    C = pd.concat([f15, B[~B.date.isin(f15.date)]])
    for nm, p in (("B  10:45@10:50 > 11:15 > 11:45", B), ("C  10:15 first, then B", C)):
        print(f"  PLAN {nm}: {len(p)} trades | tgt {(p.st == 'target').mean()*100:.0f} stall {(p.st == 'stall').mean()*100:.0f} stop {(p.st == 'stop').mean()*100:.0f} | net {(p.r.mean()-COST)*1000:+.0f}/trade | total net {(p.r-COST).sum()*1000:+,.0f} | "
              + " ".join(f"{k}: {g.r.mean()*1000:+.0f}" for k, g in p.groupby(p.date.str[:7])))
