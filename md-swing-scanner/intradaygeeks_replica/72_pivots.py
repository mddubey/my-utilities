"""Pivot re-test on the CURRENT rule set (user, 2026-10-04). Pivots were last tested on script 15's biased set
(position blocking, before checklist / 2:1 / ATR / full hour / green-hour skip). Spec fixed before running:
Classic pivots: PP=(H+L+C)/3, R1=2PP-L, S1=2PP-H, R2=PP+(H-L), S2=PP-(H-L). Daily from yesterday's H/L/C, weekly from
last completed week (W-FRI), monthly from last calendar month (added on the user's
TradingView point: Auto pivots = weekly on the 1H chart, monthly on the daily chart). For a short with entry E, stop price SP = E*(1+stop%), target T = E*0.99:
  P1 / P4  support in the target path:    S1 or S2 in (T, E)                   expect: NO better
  P2 / P5  rejection at a pivot:          PP, R1 or R2 in [E, SP*1.003]          expect: YES better
  P3 / P6  side of PP:                    E above PP                            no prior direction
Population: prev_hour_context.csv (script 70), sets a_full (30m, full hour at :15) and b (1H, 3 yr), minus the
strong-green-hour skip (group B at 11:45 / 12:15) = the current rules, ALL setups. Pass = helps Rs/trade in BOTH sets,
not carried by one month/year; anything passing gets a label-shuffle check."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import DAILY_DIR
HERE = Path(__file__).resolve().parent


def piv(H, L, C):
    pp = (H + L + C) / 3
    return dict(PP=pp, R1=2 * pp - L, S1=2 * pp - H, R2=pp + (H - L), S2=pp - (H - L))


def current_rules():
    d = pd.read_csv(HERE / "prev_hour_context.csv")
    d = d[d.set.isin(["a_full", "b"])].copy()
    late = np.where(d.set == "b", d.alarm == 11, d.alarm.isin([4, 5]))
    return d[~(late & d.grp.str.startswith("B"))].reset_index(drop=True)


def add_pivots(x):
    out = []
    for t, g in x.groupby("ticker"):
        f = DAILY_DIR / f"{t}.csv"
        if not f.exists():
            continue
        dd = pd.read_csv(f, index_col=0, parse_dates=True)[["High", "Low", "Close"]].dropna()
        mo = dd.resample("ME").agg({"High": "max", "Low": "min", "Close": "last"}).dropna()
        wk = dd.resample("W-FRI").agg({"High": "max", "Low": "min", "Close": "last"}).dropna()
        for ix, r in g.iterrows():
            day = pd.Timestamp(r.date)
            prev = dd[dd.index < day]
            if not len(prev):
                continue
            y = prev.iloc[-1]
            if abs(r.entry / y.Close - 1) > 0.15:          # split/adjustment mismatch guard
                continue
            w = wk[wk.index < day - pd.Timedelta(days=day.weekday())]   # weeks ended before this week's Monday
            if not len(w):
                continue
            w = w.iloc[-1]
            m = mo[mo.index < day.replace(day=1)]          # months ended before this month
            if not len(m):
                continue
            m = m.iloc[-1]
            E = r.entry; SP = E * (1 + r.stop / 100); T = E * 0.99
            rec = {"ix": ix}
            for tag, p in (("d", piv(y.High, y.Low, y.Close)), ("w", piv(w.High, w.Low, w.Close)),
                           ("m", piv(m.High, m.Low, m.Close))):
                rec[f"{tag}_sup_path"] = any(T < p[k] < E for k in ("S1", "S2"))
                rec[f"{tag}_at_pivot"] = any(E <= p[k] <= SP * 1.003 for k in ("PP", "R1", "R2"))
                rec[f"{tag}_above_pp"] = E > p["PP"]
                for k, v in p.items():
                    rec[f"{tag}_{k}"] = v
            out.append(rec)
    return pd.DataFrame(out).set_index("ix")


def row(g, lab):
    w = g.why
    return dict(group=lab, n=len(g), target=round((w == "target").mean() * 100, 1),
                stop=round((w == "stop").mean() * 100, 1), timeout=round(w.isin(["time", "eod"]).mean() * 100, 1),
                rs=round(g.ret.mean() * 1000))


if __name__ == "__main__":
    from multiprocessing import Pool
    x = current_rules()
    parts = [g for _, g in x.groupby("ticker")]
    with Pool(6) as p:
        pv = pd.concat(p.map(add_pivots, parts))
    y = x.join(pv, how="inner")
    y.to_csv(HERE / "pivots.csv", index=False)
    print(f"population: a_full {sum(x.set == 'a_full')} -> {sum(y.set == 'a_full')}, "
          f"b {sum(x.set == 'b')} -> {sum(y.set == 'b')} (after pivot join)")
    tests = [("P1 daily S1/S2 in target path", "d_sup_path"), ("P2 daily PP/R1/R2 at the stop", "d_at_pivot"),
             ("P3 entry above daily PP", "d_above_pp"), ("P4 weekly S1/S2 in target path", "w_sup_path"),
             ("P5 weekly PP/R1/R2 at the stop", "w_at_pivot"), ("P6 entry above weekly PP", "w_above_pp"),
             ("P7 monthly S1/S2 in target path", "m_sup_path"), ("P8 monthly PP/R1/R2 at the stop", "m_at_pivot"),
             ("P9 entry above monthly PP", "m_above_pp")]
    for s, nm, per in (("a_full", "30m Jun-Sep 2026", 7), ("b", "1H 3 years", 4)):
        z = y[y.set == s].copy(); z["per"] = z.date.str[:per]
        print(f"\n===== {nm} =====")
        for title, col in tests:
            rows = [row(z, "baseline"), row(z[z[col]], "YES"), row(z[~z[col]], "NO")]
            print(f"\n{title}")
            print(pd.DataFrame(rows).to_string(index=False))
            by = z.groupby(["per", col]).ret.agg(["mean", "size"]).unstack(col)
            line = "   by period Rs YES/NO: " + "  ".join(
                f"{p}: {by.loc[p, ('mean', True)] * 1000:+.0f}({int(by.loc[p, ('size', True)]) if not np.isnan(by.loc[p, ('size', True)]) else 0})"
                f"/{by.loc[p, ('mean', False)] * 1000:+.0f}({int(by.loc[p, ('size', False)]) if not np.isnan(by.loc[p, ('size', False)]) else 0})"
                for p in by.index)
            print(line)
