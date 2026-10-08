"""Fair test of the 10:45 follow-through lead (user, 2026-10-09). Spec fixed before running:
  10:45 half-hour signals (30m set, Jun 10 - Sep 30 2026): plan B EMA34 setups (green_rejection.csv red, price >= Rs100) and,
  separately, opening-rejection + lower-high setups (script 112). At 10:51: DEAD (stop touched 10:45-10:50) -> skip; 2:1 gone at
  the 10:50 price (stop > 0.5% away) -> skip; NEW: price at 10:50 (close of the 10:45-10:50 bar) above the signal close -> skip.
  Entry at the 10:50 price; stop = candle high; target entry*0.99; exit 5h / 15:15 (stop first if both in one bar).
  Plan B as traded: 10:45 entered at 10:50 if valid, else 11:15 (full hour, candle-close entry), else 11:45; with vs without
  the new skip. Results only, by month."""
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
exec(compile(open(HERE / "60_filter_ablation.py").read().split("def gen_a")[0], "60head", "exec"))


def late(rows):
    out = []
    for t, g in rows.groupby("ticker"):
        m = read(M5 / f"{t}.csv")
        for ix, r in g.iterrows():
            day = pd.Timestamp(r.date); y5 = m[(m.index >= day + pd.Timedelta("10h45min")) & (m.index < day + pd.Timedelta("10h50min"))]
            if len(y5) == 0: continue
            if y5.High.max() >= r.qh: out.append(dict(ix=ix, status="dead")); continue
            px0 = y5.Close.iloc[-1]
            if (r.qh - px0) / px0 * 100 > 0.5: out.append(dict(ix=ix, status="2:1 gone")); continue
            st = "ENTER, price above signal close" if px0 > r.qc else "ENTER, price at/below signal close"
            tgt = px0 * 0.99; b = m[(m.index >= day + pd.Timedelta("10h50min")) & (m.index.normalize() == day)]
            px, why = b.Close.iloc[-1], "stall"
            for ts, x in b.iterrows():
                if ts >= day + pd.Timedelta("15h15min"): px, why = x.Open, "stall"; break
                if x.High >= r.qh: px, why = r.qh, "stop"; break
                if x.Low <= tgt: px, why = tgt, "target"; break
            out.append(dict(ix=ix, status=st, ret50=(px0 - px) / px0 * 100, out50=why))
    return pd.DataFrame(out).set_index("ix")


def st(g, rc="ret", oc="out"):
    o = g[oc]
    return (f"| {len(g)} | {(o == 'target').mean()*100:.0f} | {(o == 'stall').mean()*100:.0f} | {(o == 'stop').mean()*100:.0f} | {g[rc].mean()*1000 - 85:+.0f} | "
            f"{g[rc].sum()*1000 - 85*len(g):+,.0f} | " + " / ".join(f"{v:+.0f}" for v in (g.groupby(g.date.str[:7])[rc].mean()*1000 - 85).values) + " |")


if __name__ == "__main__":
    G = pd.read_csv(HERE / "green_rejection.csv"); G = G[(G.set == "a") & (~G.green) & (G.qc >= 100)].copy()
    G["out"] = G.why.replace({"time": "stall", "eod": "stall"})
    O = pd.read_csv(HERE / "opening_rejection_lower_high.csv"); O = O[(O.set == "a") & O.oprej & O.lh].copy()
    H = "| n | target % | stall % | stop % | Rs net | total | Jun / Jul / Aug / Sep |"
    for nm, D in (("plan B EMA34 setups", G), ("opening rejection + lower high", O)):
        x = D[D.alarm == 2].copy(); x = x.join(late(x), how="inner")
        print(f"\n## 10:45 signals, {nm} -- entry at the 10:50 price\n| status at 10:51 " + H + "\n|---|---|---|---|---|---|---|---|")
        for k, g in x[x.status.str.startswith("ENTER")].groupby("status"):
            print(f"| {k} " + st(g, "ret50", "out50"))
        print("counts by status:", x.status.value_counts().to_dict())
    x = G[G.alarm == 2].copy(); x = x.join(late(x), how="inner")
    rest = G[G.alarm.isin([3, 4])].copy(); rest["ret50"], rest["out50"] = rest.ret, rest.out
    print("\n## one trade a day, plan B as traded (10:45 at 10:50 if valid, else 11:15, else 11:45)\n| plan " + H + "\n|---|---|---|---|---|---|---|---|")
    for lab, ok in (("today's checks (dead / 2:1)", x.status.str.startswith("ENTER")), ("+ NEW: skip if price above signal close at 10:50", x.status == "ENTER, price at/below signal close")):
        e = x[ok][["date", "alarm", "dist", "ret50", "out50"]]
        pool = pd.concat([e, rest[["date", "alarm", "dist", "ret50", "out50"]]])
        pk = pool.sort_values(["date", "alarm", "dist"]).groupby("date").head(1)
        print(f"| {lab} " + st(pk, "ret50", "out50"))
