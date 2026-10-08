"""Green rejection candles (user, 2026-10-08, TECHM 10:15-11:15: green hour that wicked into the 1H EMA34 and closed
back under it -- "even better rejection imo"). The red-candle rule was inherited from the channel's Chartink query
(open > close), never tested on its own. Script 60 (older rules) had green worse in both sets; this re-runs it on the
CURRENT rules. Spec fixed before running:
  Population: current rules exactly as 76 P0 (full hour at :15, ATR >= 2.56%, 2:1 + 0.5% cap, strong-green-hour skip)
  EXCEPT the red check is dropped; green = close >= open (a doji fails the current strict red rule, so it counts here).
  Groups: RED (current, reconciles with 76 P0: 511 / 1629), GREEN (all), GREEN-SS = green with close in the bottom half
  of the candle's range (pos <= 0.5: green shooting star -- a long upper wick; TECHM was 0.68 and would not qualify).
  Outcome: the generator's own exit (1% target / candle-high stop / 5h or EOD), Rs per Rs 1 lakh, net = gross - 85.
  Report both sets: per group n / target / stall / stop / Rs gross / net, by month (30m) / year (1H);
  one-a-day plan (30m: 10:45 else 11:15 else 11:45; 1H: 11:15 else 12:15; closest to EMA34 first) with red only vs
  red + green vs red + green-SS; label shuffle green vs red (5,000).
Pass (adopt green or green-SS) = adding it raises the all-setups mean AND the plan in BOTH sets, not one period, shuffle
p < 0.05 for the gap. Else the red rule stays."""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
s67 = open(HERE / "67_stop_rate_filters.py").read()
head, tail = s67.split('exec(compile(src, "63mod", "exec"))', 1)
head += '''src = src.replace("qi = np.where(k30 == q)[0]", "qi = np.where((k30 == q) | ((k30 == q - 1) & (q % 2 == 1)))[0]", 1)
assert src.count("and qc < qo and") == 1 and src.count("and qc < O[i] and") == 1
src = src.replace("and qc < qo and", "and", 1).replace("and qc < O[i] and", "and", 1)
src = src.replace("alarm=q,", "alarm=q, qc=qc, qh=qh, green=bool(qc >= qo),", 1).replace("alarm=T[i].hour,", "alarm=T[i].hour, qc=qc, qh=qh, green=bool(qc >= O[i]),", 1)
assert src.count("green=bool") == 2
'''
exec(compile(head + 'exec(compile(src, "63mod", "exec"))\n', "96", "exec"))
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
    Y = pd.concat(out); Y.to_csv(HERE / "green_rejection.csv", index=False)
    Y["out"] = Y.why.replace({"time": "stall", "eod": "stall"}); Y["g"] = np.where(~Y.green, "RED", np.where(Y.pos <= 0.5, "GREEN-SS", "GREEN-other"))
    rng = np.random.default_rng(96)

    def st(g):
        o = g.out; r = g.ret.mean() * 1000
        return f"| {len(g)} | {(o == 'target').mean()*100:.0f} | {(o == 'stall').mean()*100:.0f} | {(o == 'stop').mean()*100:.0f} | {r:+.0f} | {r - 85:+.0f} |"
    print("alarms seen:", {s: sorted(Y[Y.set == s].alarm.unique().tolist()) for s in "ab"})
    for s, nm, per, al in (("a", "30m Jun-Sep 2026", 7, [2, 3, 4]), ("b", "1H 2024-Sep 2026", 4, [10, 11])):
        z = Y[Y.set == s].copy(); z["p"] = z.date.str[:per]
        print(f"\n## {nm}   (RED reconciliation: {int((z.g == 'RED').sum())})\n| group | n | target % | stall % | stop % | Rs gross | Rs net |\n|---|---|---|---|---|---|---|")
        for lab, m in (("RED (current)", z.g == "RED"), ("GREEN all", z.green), ("  GREEN-SS (close bottom half)", z.g == "GREEN-SS"),
                       ("  GREEN-other", z.g == "GREEN-other"), ("RED + GREEN", np.ones(len(z), bool)), ("RED + GREEN-SS", z.g != "GREEN-other")):
            print(f"| {lab} " + st(z[m]))
        t = z.groupby(["p", "g"]).ret.agg(lambda r: f"{r.mean()*1000:+.0f} ({len(r)})").unstack().fillna("-")
        print("\nby period, Rs gross (n):\n" + t.to_string())
        for lab, keep in (("red only", z.g == "RED"), ("red + green", np.ones(len(z), bool)), ("red + green-SS", z.g != "GREEN-other")):
            pk = z[keep & z.alarm.isin(al)].sort_values(["date", "alarm", "dist"]).groupby("date").head(1)
            pp = pk.groupby("p").ret.mean() * 1000 - 85
            print(f"plan {lab:15s} " + st(pk) + "  net by period: " + " ".join(f"{k}:{v:+.0f}" for k, v in pp.items()) + f" | total net Rs {pk.ret.sum()*1000 - 85*len(pk):+.0f}")
        for lab, m in (("GREEN all", z.green), ("GREEN-SS", z.g == "GREEN-SS")):
            w = z[m | (z.g == "RED")]; lb = (w.g != "RED").values; r = w.ret.values
            d = r[lb].mean() - r[~lb].mean()
            sh = np.array([r[p].mean() - r[~p].mean() for p in (rng.permutation(lb) for _ in range(5000))])
            print(f"{lab} minus RED: {d*1000:+.0f} Rs/trade, shuffle p (two-sided) {np.mean(np.abs(sh) >= abs(d)):.3f}")
