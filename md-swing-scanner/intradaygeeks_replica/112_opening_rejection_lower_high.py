"""112 OPENING REJECTION + LOWER HIGH (user, 2026-10-09; from looking inside 111: 95% of the passing EMA8 setups had the day high
reach the daily 8-EMA in the 09:15 hour). Spec fixed before running: (1) the 09:15 hour's high >= live daily 8-EMA and that hour
closes below it (opening spike rejected at daily resistance); (2) later signal candle (plan B times) red, high >= 1H EMA8, close <
EMA8 by <= 0.5%, stop = candle high <= 0.5%, candle high < opening-hour high; (3) EMA8 < EMA34 (variant: gap >= 0.5%); (4) other
checks as today (below yday daily 8-EMA, VWAP, ADX, ATR, liquid, price >= Rs100, green-hour skip). Results only.
Built on: Strong-trend EMA8 rejection (user, 2026-10-08, after the channel's SBIN short: hourly bounces stopped at the 1H EMA8 while the
EMA34 sat ~0.6% higher; in strong trends pullbacks are shallow and only reach the fast average -- the 1H EMA8 spans ~ the same
time as a 15-min EMA34). Results only. Spec fixed before running:
  Same generator / candles / alarm times / checks as today's rules (67 chain: full hour at :15, ATR >= 2.56%, ADX <= 25, liquid,
  green-hour skip, red, VWAP), EXCEPT: level = 1H EMA8 (as of the last completed hour): high >= EMA8, close < EMA8 by <= 0.5%,
  stop = candle high <= 0.5%; strong trend = EMA8 at least X% below EMA34, X = 0.5 (main), 0.3 / 0.75 (robustness).
  Variant: with and without "day high >= live daily 8-EMA". Generated once at the loosest settings (X 0.3, no pierce check),
  then filtered. Price >= Rs100. Report setups alone and one-a-day plans: plan B / EMA8 setups alone / plan B + EMA8 setups
  (first alarm, then closest to its own level). Both sets; 1H 3-year = judge."""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
s67 = open(HERE / "67_stop_rate_filters.py").read()
head, tail = s67.split('exec(compile(src, "63mod", "exec"))', 1)
head += '''src = src.replace("qi = np.where(k30 == q)[0]", "qi = np.where((k30 == q) | ((k30 == q - 1) & (q % 2 == 1)))[0]", 1)
A = "if not (qh >= E and qc < E and (E - qc) / E * 100 <= 0.5 and (qh - qc) / qc * 100 <= 0.5): continue"
assert src.count(A) == 2
i1 = src.index(A); src = src[:i1] + "if not (qh >= E8 and qc < E8 and 0 < (E8 - qc) / E8 * 100 <= 0.5 and (qh - qc) / qc * 100 <= 0.5 and E8 < E): continue" + src[i1 + len(A):]
i2 = src.index(A); src = src[:i2] + "if not (qh >= E8[i] and qc < E8[i] and 0 < (E8[i] - qc) / E8[i] * 100 <= 0.5 and (qh - qc) / qc * 100 <= 0.5 and E8[i] < E): continue" + src[i2 + len(A):]
B1 = "if not (E8 < E and qc < qo and qc < D8 and hi_day[b] >= A8 * qc + (1 - A8) * D8 and qc < vw[b]): continue"
B2 = "if not (E8[i] < E and qc < O[i] and qc < D8 and hi_day[i] >= A8 * qc + (1 - A8) * D8 and qc < vw[i]): continue"
assert src.count(B1) == 1 and src.count(B2) == 1
src = src.replace(B1, "op = np.where(T < base + pd.Timedelta('60min'))[0]; ohi, ocl = H[op].max(), C[op[-1]]; olive = A8 * ocl + (1 - A8) * D8; oprej = bool(ohi >= olive and ocl < olive); lh = bool(qh < ohi)\\n            pierce = bool(hi_day[b] >= A8 * qc + (1 - A8) * D8)\\n            if not (qc < qo and qc < D8 and qc < vw[b]): continue", 1)
src = src.replace(B2, "j0 = int(np.argmax(day == dd)); ohi, ocl = H[j0], C[j0]; olive = A8 * ocl + (1 - A8) * D8; oprej = bool(ohi >= olive and ocl < olive); lh = bool(qh < ohi)\\n        pierce = bool(hi_day[i] >= A8 * qc + (1 - A8) * D8)\\n        if not (qc < O[i] and qc < D8 and qc < vw[i]): continue", 1)
src = src.replace("alarm=q,", "alarm=q, qc=qc, qh=qh, pierce=pierce, oprej=oprej, lh=lh, gap8=(E - E8) / E * 100, dist8=(E8 - qc) / E8 * 100,", 1)
src = src.replace("alarm=T[i].hour,", "alarm=T[i].hour, qc=qc, qh=qh, pierce=pierce, oprej=oprej, lh=lh, gap8=(E - E8[i]) / E * 100, dist8=(E8[i] - qc) / E8[i] * 100,", 1)
assert src.count("pierce=pierce") == 2
'''
exec(compile(head + 'exec(compile(src, "63mod", "exec"))\n', "111", "exec"))
ctx70 = {"__file__": str(HERE / "70_prev_hour_context.py")}
exec(compile(open(HERE / "70_prev_hour_context.py").read().split('if __name__ == "__main__":')[0], "70", "exec"), ctx70)

if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_")); t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    print("generating...", flush=True)
    with Pool(6) as p:
        A_ = pd.DataFrame(sum(p.map(gen_a, t5, chunksize=10), [])); B_ = pd.DataFrame(sum(p.map(gen_b, t1, chunksize=10), []))
    out = []
    for x, s in ((A_, "a"), (B_, "b")):
        x = x.reset_index(drop=True); x["date"] = pd.to_datetime(x.date).dt.strftime("%Y-%m-%d"); x["set"] = s
        ctx = pd.concat([ctx70["context"](g, s) for _, g in x.groupby("ticker")])
        x = x.join(ctx, how="left"); x["grp"] = ctx70["label"](x.fillna({"prev_above": True, "prev_green": False, "above_mid": False}))
        late = x.alarm.eq(11) if s == "b" else x.alarm.isin([4, 5])
        out.append(x[~(late & x.grp.str.startswith("B"))])
    Y = pd.concat(out); Y = Y[Y.qc >= 100]; Y["out"] = Y.why.replace({"time": "stall", "eod": "stall"})
    Y.to_csv(HERE / "opening_rejection_lower_high.csv", index=False)
    G = pd.read_csv(HERE / "green_rejection.csv"); G = G[(~G.green) & (G.qc >= 100)].copy(); G["out"] = G.why.replace({"time": "stall", "eod": "stall"})

    def st(g):
        o = g.out
        return f"| {len(g)} | {(o == 'target').mean()*100:.0f} | {(o == 'stall').mean()*100:.0f} | {(o == 'stop').mean()*100:.0f} | {g.ret.mean()*1000 - 85:+.0f} | {g.ret.sum()*1000 - 85*len(g):+,.0f} | " + " / ".join(f"{v:+.0f}" for v in (g.groupby('p').ret.mean()*1000 - 85).values) + " |"
    for s_, nm, per, al in (("b", "1H 2024-Sep 2026 (judge)", 4, [10, 11]), ("a", "30m Jun-Sep 2026 (check)", 7, [2, 3, 4])):
        y = Y[Y.set == s_].copy(); y["p"] = y.date.str[:per]; g0 = G[G.set == s_].copy(); g0["p"] = g0.date.str[:per]
        print(f"\n## {nm}\n| setups | n | target % | stall % | stop % | Rs net | total | by period |\n|---|---|---|---|---|---|---|---|")
        for lab, m in (("EMA8 rejection, all (EMA8 < EMA34)", np.ones(len(y), bool)),
                       ("OPENING REJECTION + LOWER HIGH (main)", y.oprej & y.lh),
                       ("  ... and EMA8 >= 0.5% below EMA34", y.oprej & y.lh & (y.gap8 >= 0.5)),
                       ("EMA8 rejection WITHOUT the opening structure", ~(y.oprej & y.lh))):
            print(f"| {lab} " + st(y[m]))
        print("| (reference) today's EMA34 setups " + st(g0))
        B = g0[g0.alarm.isin(al)].sort_values(["date", "alarm", "dist"]).groupby("date").head(1)
        print(f"\none trade a day\n| plan | n | target % | stall % | stop % | Rs net | total | by period |\n|---|---|---|---|---|---|---|---|")
        print("| plan B today " + st(B))
        for lab, m in (("opening rejection + lower high", y.oprej & y.lh), ("... with gap >= 0.5%", y.oprej & y.lh & (y.gap8 >= 0.5))):
            e = y[m & y.alarm.isin(al)].copy(); e["key"] = e.dist8
            pk = e.sort_values(["date", "alarm", "key"]).groupby("date").head(1)
            print(f"| {lab}, alone " + st(pk))
            b2 = g0[g0.alarm.isin(al)].copy(); b2["key"] = b2.dist
            comb = pd.concat([b2[["date", "alarm", "key", "ret", "out", "p"]], e[["date", "alarm", "key", "ret", "out", "p"]]])
            print(f"| plan B + {lab} " + st(comb.sort_values(["date", "alarm", "key"]).groupby("date").head(1)))
