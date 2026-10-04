"""(1) Trade the 10:45 signal late, when the user's standup ends (user, 2026-10-04). Spec fixed before running.
    30m set only (the 1H set has no 10:45 alarm). For each 10:45 signal: enter at the last 5-min close before
    T = 10:45 (on time) / 10:50 / 11:00 / 11:05, ONLY IF the stop (candle high) was not touched since 10:45 and the
    stop is still <= 0.5% from that price (2:1). Target = fill - 1%, stop = candle high, out 5h after entry or EOD.
    Plans (one trade a day, closest to EMA within an alarm): A = 11:15 else 11:45 (today); B(T) = 10:45-at-T else
    11:15 else 11:45. Rs gross / net (~Rs85), target / stall / stop, by month.
(2) After a close entry, how often does price come back UP to the entry price / the 1H EMA34 before the trade ends,
    by final outcome; both sets."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import INTRADAY_5M_DIR
HERE = Path(__file__).resolve().parent; COST = 0.085
LATE = ["10:45", "10:50", "11:00", "11:05"]


def run(args):
    t, g = args
    cache = {}; out = []
    for ix, r in g.iterrows():
        s = r.set
        if s not in cache:
            p = INTRADAY_5M_DIR / f"{t}.csv" if s == "a" else HERE / "h1_cache" / f"{t}.csv"
            m = pd.read_csv(p, index_col=0); m.index = pd.to_datetime(m.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
            cache[s] = m
        m = cache[s]; day = pd.Timestamp(r.date)
        if s == "a":
            at = day + pd.Timedelta("9h15min") + (int(r.alarm) + 1) * pd.Timedelta("30min"); step = pd.Timedelta("5min")
        else:
            at = day + pd.Timedelta(hours=int(r.alarm) + 1, minutes=15); step = pd.Timedelta("60min")
        b = m[(m.index >= at) & (m.index.normalize() == day) & (m.index + step <= day + pd.Timedelta("15h15min"))]
        if b.empty: continue
        E, SP = r.qc, r.qh; ema = r.qc / (1 - r.dist / 100)
        H, L = b.High.values, b.Low.values
        # (2) retest after a close entry, before the trade's own exit (target / stop / 15:15)
        end = len(H)
        for k in range(len(H)):
            if H[k] >= SP or L[k] <= E * 0.99: end = k + 1; break
        hh = H[:end].max(); first = b.index[:end]
        rec = dict(ix=ix, back_to_entry=hh >= E * 1.0005, back_to_ema=hh >= ema, back_in_30=(H[:min(end, 6 if s == "a" else 1)].max() >= E * 1.0005))
        # (1) late entries for 10:45 signals
        if s == "a" and int(r.alarm) == 2:
            for lt in LATE:
                T = day + pd.Timedelta(hours=int(lt[:2]), minutes=int(lt[3:]))
                pre = m[(m.index >= at) & (m.index + step <= T)]
                if len(pre) and pre.High.max() >= SP: rec[f"L{lt}"] = np.nan; rec[f"S{lt}"] = "dead"; continue
                c = m[m.index + step <= T].Close
                px = c.iloc[-1] if T > at else E
                if (SP - px) / px * 100 > 0.5: rec[f"L{lt}"] = np.nan; rec[f"S{lt}"] = "skip_2to1"; continue
                aft = m[(m.index + step > T) & (m.index >= T) & (m.index.normalize() == day)]
                tg = px * 0.99; res, st = None, "stall"
                for ts, br in aft.iterrows():
                    if br.High >= SP: res, st = -(SP - px) / px * 100, "stop"; break
                    if br.Low <= tg: res, st = 1.0, "target"; break
                    if ts >= T + pd.Timedelta("5h") or ts + step > day + pd.Timedelta("15h15min"): res = (px - br.Close) / px * 100; break
                if res is None: res = (px - aft.Close.iloc[-1]) / px * 100 if len(aft) else 0.0
                rec[f"L{lt}"] = res; rec[f"S{lt}"] = st
        out.append(rec)
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    y = pd.read_csv(HERE / "how_low_P0.csv")
    with Pool(6) as p:
        R = pd.DataFrame(sum(p.map(run, list(y.groupby("ticker"))), [])).set_index("ix")
    y = y.join(R, how="inner"); y.to_csv(HERE / "late_1045_and_retest.csv", index=False)
    y["o"] = y.why.replace({"time": "stall", "eod": "stall"})
    print("=== (2) after a close entry: did price come back up to the entry / the 1H EMA34 before the trade ended? ===")
    for s, nm in (("a", "30m"), ("b", "1H")):
        z = y[y.set == s]
        for o, g in z.groupby("o"):
            print(f"  {nm} {o:7s} n={len(g):4d} | back to entry {g.back_to_entry.mean()*100:4.0f}% (within first {'30 min' if s == 'a' else 'hour'}: {g.back_in_30.mean()*100:3.0f}%) | back up to EMA34 {g.back_to_ema.mean()*100:4.0f}%")
    print("\n=== (1) 10:45 signal entered late (30m set) ===")
    a = y[y.set == "a"].copy(); a["p"] = a.date.str[:7]; s45 = a[a.alarm == 2]
    for lt in LATE:
        st = s45[f"S{lt}"]; ok = s45[st.isin(["target", "stall", "stop"])]
        print(f"  enter at {lt}: still valid {len(ok)}/{len(s45)} (dead {np.mean(st == 'dead')*100:.0f}%, 2:1 gone {np.mean(st == 'skip_2to1')*100:.0f}%) | "
              f"tgt {np.mean(ok[f'S{lt}'] == 'target')*100:.0f} stall {np.mean(ok[f'S{lt}'] == 'stall')*100:.0f} stop {np.mean(ok[f'S{lt}'] == 'stop')*100:.0f} | Rs gross {ok[f'L{lt}'].mean()*1000:+.0f} net {(ok[f'L{lt}'].mean()-COST)*1000:+.0f}")
    def pick(df, al): return df[df.alarm == al].sort_values(["date", "dist"]).groupby("date").head(1)
    p11, p1145 = pick(a, 3).assign(r=lambda d: d.ret), pick(a, 4).assign(r=lambda d: d.ret)
    A = pd.concat([p11, p1145[~p1145.date.isin(p11.date)]])
    print(f"\n  PLAN A (today: 11:15 else 11:45): {len(A)} trades | Rs gross {A.r.mean()*1000:+.0f} net {(A.r.mean()-COST)*1000:+.0f} | total net {(A.r-COST).sum()*1000:+.0f} | "
          + " ".join(f"{k}: {g.r.mean()*1000:+.0f}" for k, g in A.groupby("p")))
    for lt in LATE:
        v = s45[s45[f"S{lt}"].isin(["target", "stall", "stop"])].sort_values(["date", "dist"]).groupby("date").head(1).assign(r=lambda d: d[f"L{lt}"])
        B = pd.concat([v, p11[~p11.date.isin(v.date)], p1145[~p1145.date.isin(v.date) & ~p1145.date.isin(p11.date)]])
        print(f"  PLAN B 10:45@{lt} else 11:15 else 11:45: {len(B)} trades ({len(v)} from 10:45) | Rs gross {B.r.mean()*1000:+.0f} net {(B.r.mean()-COST)*1000:+.0f} | total net {(B.r-COST).sum()*1000:+.0f} | "
              + " ".join(f"{k}: {g.r.mean()*1000:+.0f}" for k, g in B.groupby("p")))
