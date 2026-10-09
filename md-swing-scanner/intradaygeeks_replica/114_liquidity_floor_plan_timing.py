"""Does plan B's timing still hold on the user's liquidity rule? (user, 2026-10-09, after the Rs15 lakh / 5-min bar rule went
live). Spec fixed before running:
  Population: plan B EMA34 setups, red, price >= Rs100 (green_rejection.csv, same as 113). 30m set (Jun 10 - Sep 30 2026) for the
  10:45 timing; 3-year 1H set (11:15 else 12:15) as the long-run check.
  Liquidity (= the scan's liq_L): median Rs turnover of the 5-min bars in the hour before the alarm candle closes, in lakh.
    30m set: from the 5-min cache. 1H set: no 5-min history -> the signal hour's turnover / 12 (a MEAN, which runs higher than
    the median), rescaled by the median/mean ratio measured on the 30m set's 11:15 / 12:15 setups (one number, reported).
  Universe groups (declared): all | liq >= 15 (live rule) | liq >= 20 | removed (< 15).
  Timing variants, one trade a day, first come (same alarm -> closest to the EMA):
    10:48 = the 10:45 candle at its close (candle-close entry), else 11:15, else 11:45;
    10:51 = the 10:45 candle at the 10:50 price if not dead and stop <= 0.5% from it, else 11:15, else 11:45 (plan B as run);
    11:00 = same at the 11:00 price (DEAD if the stop was touched 10:45-11:00);
    A = 11:15 else 11:45.
  Exit: target entry - 1%, stop = candle high, out 5h / 15:15 (stop first if both in one bar). Net = minus Rs85 per Rs1 lakh.
  Slippage version (declared guess): setups under Rs15 lakh pay an extra 0.3% of price on a stop (between IPCALAB 0.07% and
  PNGJL 0.7%); applied to the 'all' and 'removed' groups. Results only, by month / year."""
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
exec(compile(open(HERE / "60_filter_ablation.py").read().split("def gen_a")[0], "60head", "exec"))
CEND = {2: "10h45min", 3: "11h15min", 4: "11h45min", 5: "12h15min"}
SLIP = 0.3


def walk(b, day, px0, qh):
    tgt = px0 * 0.99; px, why = b.Close.iloc[-1], "stall"
    for ts, x in b.iterrows():
        if ts >= day + pd.Timedelta("15h15min"): px, why = x.Open, "stall"; break
        if x.High >= qh: px, why = qh, "stop"; break
        if x.Low <= tgt: px, why = tgt, "target"; break
    return (px0 - px) / px0 * 100, why


def enrich_a(G):
    out = []
    for t, g in G.groupby("ticker"):
        m = read(M5 / f"{t}.csv")
        for ix, r in g.iterrows():
            day = pd.Timestamp(r.date); ce = day + pd.Timedelta(CEND[r.alarm])
            lh = m[(m.index >= ce - pd.Timedelta("60min")) & (m.index < ce)]
            rec = dict(ix=ix, liq=float((lh.Volume * lh.Close).median()) / 1e5 if len(lh) else np.nan,
                       liq_mean=float((lh.Volume * lh.Close).mean()) / 1e5 if len(lh) else np.nan)
            if r.alarm == 2:
                for lab, look in (("51", "10h50min"), ("00", "11h00min")):
                    lk = day + pd.Timedelta(look); y = m[(m.index >= ce) & (m.index < lk)]
                    if len(y) == 0: continue
                    if y.High.max() >= r.qh: rec[f"st{lab}"] = "dead"; continue
                    px0 = y.Close.iloc[-1]
                    if (r.qh - px0) / px0 * 100 > 0.5: rec[f"st{lab}"] = "2:1 gone"; continue
                    b = m[(m.index >= lk) & (m.index.normalize() == day)]
                    if len(b) == 0: continue
                    rec[f"st{lab}"] = "ENTER"; rec[f"ret{lab}"], rec[f"out{lab}"] = walk(b, day, px0, r.qh)
            out.append(rec)
    return G.join(pd.DataFrame(out).set_index("ix"), how="left")


def enrich_b(G):
    out = []
    for t, g in G.groupby("ticker"):
        p = HERE / "h1_cache" / f"{t}.csv"
        if not p.exists(): continue
        h = pd.read_csv(p, index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
        for ix, r in g.iterrows():
            st = pd.Timestamp(r.date) + pd.Timedelta("10h15min" if r.alarm == 10 else "11h15min")
            if st in h.index: out.append(dict(ix=ix, liq_mean=float(h.at[st, "Volume"] * h.at[st, "Close"]) / 12 / 1e5))
    return G.join(pd.DataFrame(out).set_index("ix"), how="left")


def row(lab, g, per):
    o = g.out
    by = " / ".join(f"{v:+.0f}" for v in (g.groupby(g.date.str[:per])["ret"].mean() * 1000 - 85).values)
    eq = (g.sort_values("date").ret * 1000 - 85).cumsum(); dd = (eq - eq.cummax()).min()
    s = (g.sort_values("date").ret <= 0).astype(int); streak = int(s.groupby((s != s.shift()).cumsum()).sum().max()) if len(s) else 0
    return (f"| {lab} | {len(g)} | {(o == 'target').mean()*100:.0f} / {(o == 'stall').mean()*100:.0f} / {(o == 'stop').mean()*100:.0f} | "
            f"{g.ret.mean()*1000 - 85:+.0f} | {g.ret.sum()*1000 - 85*len(g):+,.0f} | {streak} | {dd:,.0f} | {by} |")


def pick(pool):
    return pool.sort_values(["date", "alarm", "dist"]).groupby("date").head(1)


def slip(df):
    df = df.copy(); hit = (df.out == "stop") & (df.liq < 15); df.loc[hit, "ret"] -= SLIP; return df


if __name__ == "__main__":
    G = pd.read_csv(HERE / "green_rejection.csv"); G = G[(~G.green) & (G.qc >= 100)].copy()
    G["out"] = G.why.replace({"time": "stall", "eod": "stall"})
    A = enrich_a(G[(G.set == "a") & G.alarm.isin([2, 3, 4])].copy())
    days_a = A.date.nunique()
    ratio = (A[A.alarm.isin([3, 4])].liq / A[A.alarm.isin([3, 4])].liq_mean).median()
    B = enrich_b(G[G.set == "b"].copy()); B["liq"] = B.liq_mean * ratio
    print(f"30m set: {len(A)} setups at 10:45/11:15/11:45 on {days_a} days, liquidity known for {A.liq.notna().sum()} | "
          f"median/mean ratio (30m, 11:15/11:45) = {ratio:.2f} -> 1H liquidity = hour turnover / 12 x {ratio:.2f}; "
          f"1H set {len(B)} setups, liquidity known {B.liq.notna().sum()}")
    GR = (("all", lambda d: d.liq.notna() | d.liq.isna()), (">= Rs15 lakh (live rule)", lambda d: d.liq >= 15),
          (">= Rs20 lakh", lambda d: d.liq >= 20), ("removed (< Rs15)", lambda d: d.liq < 15))
    H = "| n | target / stall / stop % | Rs net/trade | total | worst streak | max DD | {} |\n|---|---|---|---|---|---|---|---|"
    rest = A[A.alarm.isin([3, 4])][["date", "alarm", "dist", "ret", "out", "liq"]]
    a2 = A[A.alarm == 2]
    variants = {
        "10:48 (candle close)": a2[["date", "alarm", "dist", "ret", "out", "liq"]],
        "10:51 (plan B as run)": a2[a2.st51 == "ENTER"].assign(ret=lambda d: d.ret51, out=lambda d: d.out51)[["date", "alarm", "dist", "ret", "out", "liq"]],
        "11:00": a2[a2.st00 == "ENTER"].assign(ret=lambda d: d.ret00, out=lambda d: d.out00)[["date", "alarm", "dist", "ret", "out", "liq"]],
        "A: 11:15 else 11:45": a2.iloc[0:0][["date", "alarm", "dist", "ret", "out", "liq"]],
    }
    for sl in (False, True):
        print(f"\n## 30m set, one trade a day{' -- WITH 0.3% stop slippage on names < Rs15 lakh' if sl else ''} (days in set: {days_a})")
        for gname, f in GR:
            if sl and gname not in ("all", "removed (< Rs15)"): continue
            print(f"\n### universe: {gname}\n| variant " + H.format("Jun / Jul / Aug / Sep"))
            for vname, v10 in variants.items():
                pool = pd.concat([v10, rest]); pool = pool[f(pool)]
                if sl: pool = slip(pool)
                pk = pick(pool)
                print(row(f"{vname} (no-trade days {days_a - len(pk)})", pk, 7))
    # setup level, all alarms, 30m
    print("\n## 30m set, ALL setups (not one a day), candle-close entry\n| group " + H.format("Jun / Jul / Aug / Sep"))
    for gname, f in GR: print(row(gname, A[f(A)], 7))
    # 1H set
    days_b = B.date.nunique()
    print(f"\n## 3-year 1H set, one trade a day, 11:15 else 12:15 (days in set: {days_b})\n| universe " + H.format("2024 / 2025 / 2026"))
    for gname, f in GR:
        pk = pick(B[f(B)]); print(row(f"{gname} (no-trade days {days_b - len(pk)})", pk, 4))
    pk = pick(slip(B)); print(row("all, WITH 0.3% slippage < Rs15", pk, 4))
    print("\n## 3-year 1H set, ALL setups\n| group " + H.format("2024 / 2025 / 2026"))
    for gname, f in GR: print(row(gname, B[f(B)], 4))
