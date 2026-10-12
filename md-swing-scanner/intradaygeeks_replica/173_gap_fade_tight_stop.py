"""Gap fade with a TIGHT stop and a further target (user, 2026-10-11, after 172: heat before the move median 0.32%, move median 0.88%).
Spec fixed before running. Same entries as 171 (gap >= 0.5%, first 5-min close below the 15- or 30-min opening-range low before
11:15, entry above yday close; 5-min data, 84 bear days; liquid, >= Rs100, ATR >= 2%). Stop = entry + 0.4% | + 0.5% (fixed). Target =
1% | 2 x stop. Exit target / stop / 15:15, stop first if both in one bar. Rs @1L and @1k risk, t / s / s, days with a setup, by month,
weak/strong gap, without the top-10 days. Results only."""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from orb_common import read5_official
from data.paths import DAILY_DIR, INTRADAY_5M_DIR


def gen(t):
    p = INTRADAY_5M_DIR / f"{t}.csv"
    if not p.exists(): return []
    try: d = load(t)
    except Exception: return []
    c = d.Close
    D = pd.DataFrame({"pc": c.shift(1), "tv": d.traded_value_sma20.shift(1), "atrp": (d.atr14 / c * 100).shift(1), "ca": d.corp_action_day if "corp_action_day" in d else False})
    m = read5_official(t)  # 2026-10-12: official 09:15 open
    m = m[m.index >= "2026-05-01"]
    if len(m) < 500: return []
    m["day"] = m.index.normalize(); m["hm"] = m.index.strftime("%H:%M"); m["to"] = m.Volume * m.Close
    medto = m[m.Volume > 0].groupby("day").to.median().shift(1)
    v15 = m[m.hm.isin(["09:20", "09:25"])].groupby("day").Volume.sum(); v15n = v15.rolling(20, min_periods=10).mean().shift(1)
    out = []
    for dd, g in m.groupby("day"):
        if dd < pd.Timestamp("2026-06-10") or dd not in D.index: continue
        x = D.loc[dd]
        if not (x.pc >= 100) or not (x.tv >= 1e8) or bool(x.ca) or not (x.atrp >= 2) or medto.get(dd, 0) < 15e5: continue
        g = g.sort_index()
        if g.hm.iloc[0] != "09:15": continue
        gap = (g.Open.iloc[0] / x.pc - 1) * 100
        if gap < 0.5: continue
        vr = v15.get(dd, np.nan) / v15n.get(dd, np.nan) if v15n.get(dd, 0) > 0 else np.nan
        for orn, orend in (("OR15", "09:30"), ("OR30", "09:45")):
            rg = g[g.hm < orend]; after = g[g.hm >= orend]
            if len(rg) < 2 or len(after) == 0: continue
            orl = rg.Low.min(); brk = after[(after.Close < orl) & (after.hm < "11:15")]
            if len(brk) == 0: continue
            k = brk.index[0]; e = brk.Close.iloc[0]
            if e <= x.pc: continue
            rest = g[g.index > k]
            for sp in (0.4, 0.5):
                stp = e * (1 + sp / 100)
                for tn, tp in (("1%", 1.0), ("2x stop", 2 * sp)):
                    tgt = e * (1 - tp / 100); px, o, ts = None, "stall", k
                    for ts, b in rest.iterrows():
                        if b.hm >= "15:15": px = b.Open; break
                        if b.High >= stp: px, o = stp, "stop"; break
                        if b.Low <= tgt: px, o = tgt, "target"; break
                    if px is None: px = rest.Close.iloc[-1] if len(rest) else e
                    ret = (e - px) / e * 100; pos = 1000 / (sp / 100)
                    out.append(dict(date=dd.strftime("%Y-%m-%d"), mon=dd.strftime("%Y-%m"), orn=orn, sp=sp, tn=tn, vr=vr, o=o, mins=(ts - k).total_seconds() / 60 + 5,
                                    rs1L=ret * 1000 - 85, rs1k=ret / 100 * pos - 85 * pos / 1e5))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    tk = sorted(p.stem for p in INTRADAY_5M_DIR.glob("*.csv") if not p.stem.startswith("_")); t0 = time.time()
    with Pool(6) as pl: R = pd.DataFrame(sum(pl.map(gen, tk, chunksize=8), []))
    n = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index(); ND = len(n.loc["2026-06-10":].index)
    print(f"rows {len(R):,} in {time.time()-t0:.0f}s | trading days {ND}")
    print("| range | stop | target | gaps | trades | days w/ setup | target / stall / stop % | Rs/trade @1L | @1k risk | w/o top-10 days | by month Jun / Jul / Aug / Sep / Oct |\n|---|---|---|---|---|---|---|---|---|---|---|")
    for orn in ("OR15", "OR30"):
        for sp in (0.4, 0.5):
            for tn in ("1%", "2x stop"):
                for gl, gm in (("all", lambda d: d.vr.notna() | d.vr.isna()), ("weak", lambda d: d.vr < 2), ("vol ratio missing", lambda d: d.vr.isna())):
                    g = R[(R.orn == orn) & (R.sp == sp) & (R.tn == tn)]; g = g[gm(g)]; o = g.o
                    byd = g.groupby("date").rs1L.sum().sort_values(ascending=False); wo = g[~g.date.isin(byd.head(10).index)].rs1L.mean()
                    mon = " / ".join(f"{g[g.mon == k].rs1L.mean():+.0f}" for k in sorted(g.mon.unique()))
                    if "--speed" in sys.argv: continue
                    print(f"| {orn} | {sp}% | {tn} | {gl} | {len(g):,} | {g.date.nunique()/ND*100:.0f}% | {(o=='target').mean()*100:.0f} / {(o=='stall').mean()*100:.0f} / {(o=='stop').mean()*100:.0f} | {g.rs1L.mean():+.0f} | {g.rs1k.mean():+.0f} | {wo:+.0f} | {mon} |")
    if "--speed" in sys.argv:   # 2026-10-11: how fast is the stop hit? minutes from the entry bar's close to the exit bar's close
        B = [5, 10, 15, 30, 60, 120, 400]
        print("\n| range | stop | target | outcome | n | <=5m | <=10m | <=15m | <=30m | <=60m | <=2h | later | median min |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for orn in ("OR15", "OR30"):
            for sp, tn in ((0.4, "1%"), (0.5, "1%")):
                g = R[(R.orn == orn) & (R.sp == sp) & (R.tn == tn)]
                for oc in ("stop", "target"):
                    x = g[g.o == oc].mins; cum = [(x <= b).mean() * 100 for b in B[:-1]]
                    print(f"| {orn} | {sp}% | {tn} | {oc} | {len(x)} | " + " | ".join(f"{c:.0f}%" for c in cum) + f" | {100 - cum[-1]:.0f}% | {x.median():.0f} |")
