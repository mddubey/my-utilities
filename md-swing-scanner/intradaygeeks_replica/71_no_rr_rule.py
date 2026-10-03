"""Same populations as 68 (30m, full hour at 11:15 / 12:15) and 67 set b (1H, 3 years) but WITHOUT the 2:1 rule
(user, 2026-10-04: the 2:1 cap is their own addition; check the KNACK-like group and second signals without it).
Then the previous-hour context from 70. Output: no_rr_rule.csv"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
s67 = open(HERE / "67_stop_rate_filters.py").read()
head, _ = s67.split('exec(compile(src, "63mod", "exec"))', 1)
head += '''src = src.replace("qi = np.where(k30 == q)[0]", "qi = np.where((k30 == q) | ((k30 == q - 1) & (q % 2 == 1)))[0]", 1)
assert src.count(" and (qh - qc) / qc * 100 <= 0.5)") == 2
src = src.replace(" and (qh - qc) / qc * 100 <= 0.5)", ")")
'''
exec(compile(head + 'exec(compile(src, "63mod", "exec"))\n', "71", "exec"))
exec(compile(open(HERE / "70_prev_hour_context.py").read().split('if __name__ == "__main__":')[0], "70", "exec"))
if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_")); t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    with Pool(6) as p:
        A = pd.DataFrame(sum(p.map(gen_a, t5, chunksize=10), [])); B = pd.DataFrame(sum(p.map(gen_b, t1, chunksize=10), []))
    out = []
    for nm, x, src in (("a (30m, full hour, no 2:1)", A, "a"), ("b (1H, 3 years, no 2:1)", B, "b")):
        with Pool(6) as p:
            ctx = pd.concat(p.starmap(context, [(g, src) for _, g in x.groupby("ticker")]))
        y = x.join(ctx, how="inner"); y["grp"] = label(y); y["name"] = nm; out.append(y); print(nm, len(x), len(y))
    pd.concat(out).to_csv(HERE / "no_rr_rule.csv", index=False)
