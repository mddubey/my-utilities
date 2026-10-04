"""RQ-CD1: what does a Prime BC breach do on Day+1, split by end-of-Day-0 confirmation?

Stock-only, descriptive. Population: canonical BC v2 primed touches (build_population,
bc_v2_recipe, gate_clock="T-1"), reused from pre_breach/bc_v2_chunk_*.csv.
Day 0 = touch day (High >= high10_prior * 1.005). Label at the Day 0 close:
Confirmed = Close0 > high10_prior (raw pivot, the 2026-09-24 Phase 1 definition), else Rejected.
Entry = Day 0 Close (proxy for a just-before-close entry; CAS caveat accepted).
Exits: Day+1 Open, Day+1 Close; context closes at D+3/D+5/D+10. All in % (no stop, no R).
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import backtest  # noqa: E402
import primed_engine as pe  # noqa: E402

OUT = Path(__file__).resolve().parent
HORIZONS = [3, 5, 10]


def build_events():
    pop = pd.concat([pd.read_csv(f, parse_dates=["entry_date"])
                     for f in sorted(glob.glob(str(ROOT / "pre_breach" / "bc_v2_chunk_*.csv")))])
    assert not pop.duplicated(["ticker", "entry_date"]).any()
    rows = []
    for t, g in pop.groupby("ticker"):
        d = backtest.load(t)
        dates = d.index
        pivot_chk = d.High.shift(1).rolling(10).max()
        for e in g.entry_date:
            i = dates.get_loc(e)
            r0 = d.iloc[i]
            assert abs(pivot_chk.iloc[i] - r0.high10_prior) < 1e-6
            assert r0.High >= r0.high10_prior * pe.TRIGGER_CLEARANCE
            rec = dict(ticker=t, d0=e, piv=r0.high10_prior, trigger=r0.high10_prior * pe.TRIGGER_CLEARANCE,
                       O0=r0.Open, H0=r0.High, L0=r0.Low, C0=r0.Close, confirmed=r0.Close > r0.high10_prior)
            if i + 1 < len(d) and not d.iloc[i + 1].corp_action_day:
                r1 = d.iloc[i + 1]
                rec.update(d1=dates[i + 1], O1=r1.Open, H1=r1.High, L1=r1.Low, C1=r1.Close)
            for h in HORIZONS:
                if i + h < len(d) and not d.iloc[i + 1:i + h + 1].corp_action_day.any():
                    rec[f"C{h}"] = d.iloc[i + h].Close
            rows.append(rec)
    ev = pd.DataFrame(rows)
    ev["year"] = ev.d0.dt.year
    p = lambda a, b: (a / b - 1) * 100
    ev["overnight"] = p(ev.O1, ev.C0)
    ev["intraday"] = p(ev.C1, ev.O1)
    ev["combined"] = p(ev.C1, ev.C0)
    ev["mfe_open"] = p(ev.H1, ev.O1)
    ev["mae_open"] = p(ev.L1, ev.O1)
    ev["mfe_entry"] = p(ev.H1, ev.C0)
    ev["mae_entry"] = p(ev.L1, ev.C0)
    for h in HORIZONS:
        ev[f"ret_d{h}"] = p(ev[f"C{h}"], ev.C0)
    ev.to_csv(OUT / "events.csv", index=False)
    return ev


def summary(x):
    c = x.combined
    return {
        "n": len(x), "win% (C1>C0)": (c > 0).mean() * 100, "mean comb": c.mean(), "med comb": c.median(),
        "mean ovn": x.overnight.mean(), "med ovn": x.overnight.median(), "gap-up% (O1>C0)": (x.overnight > 0).mean() * 100,
        "mean intra": x.intraday.mean(), "med intra": x.intraday.median(), "green% (C1>O1)": (x.intraday > 0).mean() * 100,
        "med MFE open": x.mfe_open.median(), "med MAE open": x.mae_open.median(),
        "med MFE entry": x.mfe_entry.median(), "med MAE entry": x.mae_entry.median(),
        "hit+1%": (x.mfe_entry >= 1).mean() * 100, "hit+2%": (x.mfe_entry >= 2).mean() * 100,
        "hit+3%": (x.mfe_entry >= 3).mean() * 100,
    }


def table(df, cols, fmt="{:+.2f}"):
    head = "| " + " | ".join(df.index.name and [df.index.name] or [""]) + " | " + " | ".join(cols) + " |"
    lines = [head, "|" + "---|" * (len(cols) + 1)]
    for k, r in df[cols].iterrows():
        lines.append(f"| {k} | " + " | ".join(
            (str(int(v)) if c == "n" else (f"{v:.1f}" if "%" in c else fmt.format(v))) if pd.notna(v) else "-"
            for c, v in r.items()) + " |")
    return "\n".join(lines)


def main():
    ev = build_events()
    d1 = ev.dropna(subset=["C1"])
    lab = lambda x: np.where(x.confirmed, "Confirmed", "Rejected")
    print(f"population n={len(ev)} ({ev.d0.min().date()}..{ev.d0.max().date()}); with clean Day+1 bar n={len(d1)}; "
          f"dropped {len(ev) - len(d1)} (no next bar / Day+1 corp action)")
    print(f"Confirmed share: {ev.confirmed.mean() * 100:.1f}%; Close0 between pivot and trigger: "
          f"{((ev.C0 > ev.piv) & (ev.C0 < ev.trigger)).mean() * 100:.1f}%")

    groups = {"ALL": d1, "Confirmed": d1[d1.confirmed], "Rejected": d1[~d1.confirmed]}
    s = pd.DataFrame({k: summary(v) for k, v in groups.items()}).T
    s.index.name = "group"
    print("\n=== Day+1, entry = Day 0 close (%) ===")
    print(table(s, ["n", "win% (C1>C0)", "mean comb", "med comb", "hit+1%", "hit+2%", "hit+3%"]))
    print("\n=== Overnight (C0->O1) vs Day+1 intraday (O1->C1) ===")
    print(table(s, ["n", "mean ovn", "med ovn", "gap-up% (O1>C0)", "mean intra", "med intra", "green% (C1>O1)"]))
    print("\n=== Day+1 excursions: from Day+1 open, and from Day 0 close (entry) ===")
    print(table(s, ["n", "med MFE open", "med MAE open", "med MFE entry", "med MAE entry"]))

    print("\n=== Distribution (percentiles, %) ===")
    qs = [5, 10, 25, 50, 75, 90, 95]
    for col in ["overnight", "intraday", "combined", "mfe_entry", "mae_entry"]:
        dd = pd.DataFrame({k: np.percentile(v[col], qs) for k, v in groups.items() if k != "ALL"},
                          index=[f"p{q}" for q in qs]).T
        dd.index.name = col
        print(table(dd, list(dd.columns)))

    print("\n=== Context horizons: close-to-close from Day 0 close (%) — context only ===")
    rows = {}
    for k, v in groups.items():
        r = {"n(d10)": v.ret_d10.notna().sum(), "mean d1": v.combined.mean()}
        for h in HORIZONS:
            r[f"mean d{h}"] = v[f"ret_d{h}"].mean()
        for h in HORIZONS:
            r[f"med d{h}"] = v[f"ret_d{h}"].median()
        r["d1 share of d10 mean %"] = v.combined.mean() / v.ret_d10.mean() * 100
        rows[k] = r
    c = pd.DataFrame(rows).T
    c.index.name = "group"
    print(table(c.rename(columns={"n(d10)": "n"}), ["n", "mean d1", "mean d3", "mean d5", "mean d10",
                                                      "med d3", "med d5", "med d10"]))
    print("d1 mean as share of d10 mean: " + ", ".join(f"{k} {v:.0f}%" for k, v in c["d1 share of d10 mean %"].items()))

    print("\n=== By year (Day+1 combined, overnight, intraday means; win%) ===")
    yr = []
    for (y, conf), g in d1.groupby(["year", "confirmed"]):
        yr.append(dict(year=y, group="Confirmed" if conf else "Rejected", n=len(g), win=(g.combined > 0).mean() * 100,
                       comb=g.combined.mean(), med=g.combined.median(), ovn=g.overnight.mean(), intra=g.intraday.mean(),
                       hit2=(g.mfe_entry >= 2).mean() * 100))
    yr = pd.DataFrame(yr).set_index(["year", "group"])
    print("| year | group | n | win% | mean comb | med comb | mean ovn | mean intra | hit+2% |\n|---|---|---|---|---|---|---|---|---|")
    for (y, gname), r in yr.iterrows():
        print(f"| {y} | {gname} | {int(r.n)} | {r.win:.1f} | {r.comb:+.2f} | {r.med:+.2f} | {r.ovn:+.2f} | {r.intra:+.2f} | {r.hit2:.1f} |")

    print("\n=== 5 random events for hand-check (seed 7) ===")
    smp = d1.sample(5, random_state=7)
    print(smp[["ticker", "d0", "piv", "trigger", "H0", "C0", "confirmed", "d1", "O1", "H1", "L1", "C1",
               "overnight", "intraday", "combined"]].to_string(index=False))


if __name__ == "__main__":
    main()
