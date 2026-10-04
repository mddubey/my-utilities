"""T2 (user, 2026-10-04, SUNDARMFIN 19 Aug): the 1H trend rule (EMA8 < EMA34) also blocks shorts where the stock has
just topped -- EMA8 still ABOVE EMA34 but rolling over. Spec fixed before running:
  T2 group = every current rule EXCEPT the trend rule is replaced by: 1H EMA8 >= EMA34 AND the 1H EMA8 (as of the last
  completed hour) has fallen in each of the last 3 completed hours. Same candle, checklist, 2:1, ATR, exits, alarms;
  the strong-green-hour skip (script 70) applied the same way. Judged as its own group vs the current trades
  (obstacle_x_market.csv): Rs/trade, stop/target rates, by month (30m) / year (1H); and what adding it does to the
  one-a-day plan. Built like 68 (exec 67 source with string replacements)."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
s67 = open(HERE / "67_stop_rate_filters.py").read()
head, tail = s67.split('exec(compile(src, "63mod", "exec"))', 1)
head += '''src = src.replace("qi = np.where(k30 == q)[0]", "qi = np.where((k30 == q) | ((k30 == q - 1) & (q % 2 == 1)))[0]", 1)
src = src.replace("e8 = hc.ewm(span=8, adjust=False).mean().shift(1)",
                  "e8 = hc.ewm(span=8, adjust=False).mean().shift(1); _d = e8.diff(); F3H = (_d < 0) & (_d.shift(1) < 0) & (_d.shift(2) < 0)", 1)
src = src.replace("if not (E8 < E and qc < qo", "if not ((E8 >= E and bool(F3H.get(hs, False))) and qc < qo", 1)
src = src.replace("E8 = h.Close.ewm(span=8, adjust=False).mean().shift(1).values",
                  "E8 = h.Close.ewm(span=8, adjust=False).mean().shift(1).values; _d = np.diff(E8, prepend=np.nan); F3B = (_d < 0) & (np.roll(_d, 1) < 0) & (np.roll(_d, 2) < 0)", 1)
src = src.replace("if not (E8[i] < E and qc < O[i]", "if not ((E8[i] >= E and F3B[i]) and qc < O[i]", 1)
assert src.count("F3H") == 2 and src.count("F3B") == 2
'''
exec(compile(head + 'exec(compile(src, "63mod", "exec"))\n', "75", "exec"))
ctx70 = {"__file__": str(HERE / "70_prev_hour_context.py")}
exec(compile(open(HERE / "70_prev_hour_context.py").read().split('if __name__ == "__main__":')[0], "70", "exec"), ctx70)

if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_")); t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    with Pool(6) as p:
        A = pd.DataFrame(sum(p.map(gen_a, t5, chunksize=10), [])); B = pd.DataFrame(sum(p.map(gen_b, t1, chunksize=10), []))
    A["set"] = "a_full"; B["set"] = "b"
    out = []
    for x, src_ in ((A, "a"), (B, "b")):
        x = x.reset_index(drop=True); x["date"] = pd.to_datetime(x.date).dt.strftime("%Y-%m-%d")
        ctx = pd.concat([ctx70["context"](g, src_) for _, g in x.groupby("ticker")])
        x = x.join(ctx, how="left"); x["grp"] = ctx70["label"](x.fillna({"prev_above": True, "prev_green": False, "above_mid": False}))
        late = x.alarm.eq(11) if src_ == "b" else x.alarm.isin([4, 5])
        x["skipped"] = late & x.grp.str.startswith("B")
        out.append(x)
    T2 = pd.concat(out); T2.to_csv(HERE / "rolling_over.csv", index=False)
    cur = pd.read_csv(HERE / "obstacle_x_market.csv")

    def st(g):
        w = g.why
        return f"n={len(g):4d}  target {(w == 'target').mean()*100:4.1f}%  stop {(w == 'stop').mean()*100:4.1f}%  Rs {g.ret.mean()*1000:+5.0f}  total Rs {g.ret.sum()*1000:+7.0f}"
    for s, nm, per, al in (("a_full", "30m Jun-Sep 2026", 7, [3, 4]), ("b", "1H 3 years", 4, [10, 11])):
        c = cur[cur.set == s].copy(); t = T2[(T2.set == s) & ~T2.skipped].copy()
        print(f"\n===== {nm} =====  (T2 rows before green-hour skip: {(T2.set == s).sum()})")
        print("  current trades      ", st(c)); print("  T2 rolling-over     ", st(t))
        for lab, z in (("current", c), ("T2", t)):
            z["p"] = z.date.str[:per]
            print(f"   {lab:8s} by period: " + "  ".join(f"{k}: {g.ret.mean()*1000:+.0f}({len(g)})" for k, g in z.groupby("p")))
        both = pd.concat([c.assign(src="cur"), t.assign(src="T2")])
        def plan(z): return z[z.alarm.isin(al)].sort_values(["date", "alarm", "dist"]).groupby("date").head(1)
        pc, pb = plan(c), plan(both)
        print(f"  PLAN one/day: current {len(pc)} trades Rs {pc.ret.mean()*1000:+.0f} total {pc.ret.sum()*1000:+.0f} | with T2 added "
              f"{len(pb)} trades Rs {pb.ret.mean()*1000:+.0f} total {pb.ret.sum()*1000:+.0f} (T2 picked {(pb.src == 'T2').sum()})")
