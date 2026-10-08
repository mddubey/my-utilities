"""Double rejection / flat trend (user, 2026-10-08: "if the candle rejects the 1H EMA8 along with the EMA34 the drop is
sharper"; and the trend rule shouldn't reject blindly when EMA8 is only a hair above EMA34 -- AMAGI 0.09%, HINDCOPPER 0.28%).
Results only, no adoption call (user). Spec fixed before running:
  Population: current rules (as 76 P0: full hour at :15, ATR >= 2.56%, 2:1 + 0.5% cap, strong-green-hour skip, red) EXCEPT the
  1H trend rule is loosened to EMA8 < EMA34 * 1.003, so flat-trend setups are generated too. Both sets.
  Groups by where the 1H EMA8 sits (E8 / E34 as of the last completed hour, same as the scan):
    A  single  -- E8 below the candle close (EMA8 underneath; today's usual trade)
    B  double, trend ok -- close <= E8 < E34 (closed below both lines)
    C  flat trend, wick reached E8 -- E34 <= E8 <= E34*(1+X), high >= E8 (rejected both)   X = 0.1 / 0.2 / 0.3 %
    C' flat trend, wick below E8 -- E34 <= E8 <= E34*(1+X), high < E8 (rejected E34 under a slightly higher E8)
  Outcome: generator exit (1% target / candle-high stop / 5h or EOD), Rs per lakh, net = gross - 85.
  Report per group: n, target / stall / stop %, gross, net, by month (30m) / year (1H); one-a-day plan (closest to EMA34,
  30m 10:45/11:15/11:45, 1H 11:15/12:15) today's rules (A+B) vs + C; label shuffle B vs A and C vs A+B (5,000)."""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
CAP = sys.argv[sys.argv.index("--cap") + 1] if "--cap" in sys.argv else "1.003"   # 1e9 = no trend filter at all
OUTCSV = "double_rejection.csv" if CAP == "1.003" else f"double_rejection_cap{CAP}.csv"
s67 = open(HERE / "67_stop_rate_filters.py").read()
head, tail = s67.split('exec(compile(src, "63mod", "exec"))', 1)
head += '''CAP = "''' + CAP + '''"
src = src.replace("qi = np.where(k30 == q)[0]", "qi = np.where((k30 == q) | ((k30 == q - 1) & (q % 2 == 1)))[0]", 1)
assert src.count("if not (E8 < E and qc < qo") == 1 and src.count("if not (E8[i] < E and qc < O[i]") == 1
src = src.replace("if not (E8 < E and qc < qo", "if not (E8 < E * " + CAP + " and qc < qo", 1)
src = src.replace("if not (E8[i] < E and qc < O[i]", "if not (E8[i] < E * " + CAP + " and qc < O[i]", 1)
src = src.replace("alarm=q,", "alarm=q, qc=qc, qh=qh,", 1).replace("alarm=T[i].hour,", "alarm=T[i].hour, qc=qc, qh=qh,", 1)
'''
exec(compile(head + 'exec(compile(src, "63mod", "exec"))\n', "101", "exec"))
ctx70 = {"__file__": str(HERE / "70_prev_hour_context.py")}
exec(compile(open(HERE / "70_prev_hour_context.py").read().split('if __name__ == "__main__":')[0], "70", "exec"), ctx70)

if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_")); t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    with Pool(6) as p:
        A = pd.DataFrame(sum(p.map(gen_a, t5, chunksize=10), [])); B = pd.DataFrame(sum(p.map(gen_b, t1, chunksize=10), []))
    out = []
    for x, s in ((A, "a"), (B, "b")):
        x = x.reset_index(drop=True); x["date"] = pd.to_datetime(x.date).dt.strftime("%Y-%m-%d"); x["set"] = s
        ctx = pd.concat([ctx70["context"](g, s) for _, g in x.groupby("ticker")])
        x = x.join(ctx, how="left"); x["grp"] = ctx70["label"](x.fillna({"prev_above": True, "prev_green": False, "above_mid": False}))
        late = x.alarm.eq(11) if s == "b" else x.alarm.isin([4, 5])
        out.append(x[~(late & x.grp.str.startswith("B"))])
    Y = pd.concat(out)
    Y["E34"] = Y.qc / (1 - Y.dist / 100); Y["E8"] = Y.qc * (1 - Y.d8 / 100); Y["gap"] = (Y.E8 - Y.E34) / Y.E34 * 100
    Y["out"] = Y.why.replace({"time": "stall", "eod": "stall"})
    Y["g"] = np.select([Y.E8 < Y.qc, Y.E8 < Y.E34, Y.qh >= Y.E8], ["A single", "B double, trend ok", "C flat, wick hit E8"], "C' flat, wick under E8")
    Y.to_csv(HERE / OUTCSV, index=False)
    if CAP != "1.003": sys.exit()
    rng = np.random.default_rng(101)

    def st(g):
        o = g.out; r = g.ret.mean() * 1000
        return f"| {len(g)} | {(o == 'target').mean()*100:.0f} | {(o == 'stall').mean()*100:.0f} | {(o == 'stop').mean()*100:.0f} | {r:+.0f} | {r - 85:+.0f} |"

    def shuf(x, lab):
        r = x.ret.values; d = r[lab].mean() - r[~lab].mean()
        sh = np.array([r[p].mean() - r[~p].mean() for p in (rng.permutation(lab) for _ in range(5000))])
        return f"{d*1000:+.0f} Rs/trade, p {np.mean(np.abs(sh) >= abs(d)):.3f}"
    for s, nm, per, al in (("a", "30m Jun-Sep 2026", 7, [2, 3, 4]), ("b", "1H 2024-Sep 2026", 4, [10, 11])):
        z = Y[Y.set == s].copy(); z["p"] = z.date.str[:per]
        cur = z[z.gap < 0]
        print(f"\n## {nm}  (today's rules = A + B: n {len(cur)})\n| group | X | n | target % | stall % | stop % | Rs gross | Rs net |\n|---|---|---|---|---|---|---|---|")
        print("| A single (EMA8 below close) | | " + st(z[z.g == "A single"])[2:])
        print("| B double, trend ok | | " + st(z[z.g == "B double, trend ok"])[2:])
        for X in (0.1, 0.2, 0.3):
            f = z[(z.gap >= 0) & (z.gap <= X)]
            print(f"| C flat, wick hit E8 | {X}% | " + st(f[f.g == "C flat, wick hit E8"])[2:])
            print(f"| C' flat, wick under E8 | {X}% | " + st(f[f.g == "C' flat, wick under E8"])[2:])
        t = z[z.gap <= 0.3].groupby(["p", "g"]).ret.agg(lambda r: f"{r.mean()*1000 - 85:+.0f} ({len(r)})").unstack().fillna("-")
        print("\nnet by period (n), C groups at X = 0.3%:\n" + t.to_string())
        print("\nB vs A: " + shuf(cur, (cur.g == "B double, trend ok").values))
        c3 = z[z.gap <= 0.3]; print("C (wick hit E8, X 0.3) vs A+B: " + shuf(c3[c3.g != "C' flat, wick under E8"], (c3[c3.g != "C' flat, wick under E8"].g == "C flat, wick hit E8").values))
        for lab, keep in [("today (A+B)", z.gap < 0)] + [(f"+ C, X {X}%", (z.gap < 0) | ((z.gap <= X) & (z.g == "C flat, wick hit E8"))) for X in (0.1, 0.2, 0.3)]:
            pk = z[keep & z.alarm.isin(al)].sort_values(["date", "alarm", "dist"]).groupby("date").head(1)
            pp = (pk.groupby("p").ret.mean() * 1000 - 85).round(0).astype(int).to_dict()
            print(f"plan {lab:14s} " + st(pk) + f" total net {pk.ret.sum()*1000 - 85*len(pk):+,.0f} | " + " ".join(f"{k}:{v:+d}" for k, v in pp.items()))
