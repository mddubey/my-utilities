"""10:45 signal, looked at late (user, 2026-10-04): short now if the price is still at/above the signal close, otherwise
rest a LIMIT sell at the signal close until 11:15; if unfilled, fall back to the 11:15 then 11:45 alarms. Spec fixed
before running. 30m set (how_low_P0.csv set a), look time 10:50 and 11:00.
  DEAD (stop touched before the look) -> no 10:45 trade.
  USER : price >= signal close -> short at market now; else limit at the signal close until 11:15.
  SCAN : ENTER (stop <= 0.5% from price) -> short now; SKIP -> no 10:45 trade (today's scan rule, = plan B in 83).
  MIX  : ENTER -> short now; SKIP -> limit at the signal close until 11:15.
  Fill: a 5-min bar with High >= limit (filled at the limit); if that bar also reaches the stop -> filled and stopped.
  Trade: target = fill - 1%, stop = candle high, out 5h after fill or EOD. Plan net of ~Rs85."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import INTRADAY_5M_DIR
HERE = Path(__file__).resolve().parent; COST = 0.085


def walk(b, k0, px, SP):
    if b.High.values[k0] >= SP: return -(SP - px) / px * 100, "stop"
    tg = px * 0.99; t0 = b.index[k0]
    for ts, br in b.iloc[k0 + 1:].iterrows():
        if br.High >= SP: return -(SP - px) / px * 100, "stop"
        if br.Low <= tg: return 1.0, "target"
        if ts >= t0 + pd.Timedelta("5h") or ts >= ts.normalize() + pd.Timedelta("15h10min"): return (px - br.Close) / px * 100, "stall"
    return (px - b.Close.values[-1]) / px * 100, "stall"


def one(args):
    t, g = args
    m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0); m.index = pd.to_datetime(m.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    out = []
    for ix, r in g.iterrows():
        day = pd.Timestamp(r.date); at = day + pd.Timedelta("10h45min"); E, SP = r.qc, r.qh
        d = m[(m.index >= at) & (m.index.normalize() == day)]
        rec = {"ix": ix}
        for lk in ("10:50", "11:00"):
            T = day + pd.Timedelta(hours=int(lk[:2]), minutes=int(lk[3:]))
            pre = d[d.index + pd.Timedelta("5min") <= T]
            post = d[d.index >= T].reset_index(drop=False).set_index("index") if False else d[d.index >= T]
            if len(pre) and pre.High.max() >= SP:
                for v in ("USER", "SCAN", "MIX"): rec[f"{v}{lk}"] = (np.nan, "dead")
                continue
            px = pre.Close.iloc[-1] if len(pre) else E
            enter_ok = (SP - px) / px * 100 <= 0.5
            now = walk(post, 0, px, SP) if len(post) else (np.nan, "none")
            # limit at the signal close until 11:15
            lim = (np.nan, "unfilled")
            win = post[post.index < day + pd.Timedelta("11h15min")]
            for k in range(len(win)):
                if win.High.values[k] >= E:
                    lim = walk(post, k, E, SP); break
            rec[f"USER{lk}"] = now if px >= E else lim
            rec[f"SCAN{lk}"] = now if enter_ok else (np.nan, "skip")
            rec[f"MIX{lk}"] = now if enter_ok else lim
        out.append(rec)
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    y = pd.read_csv(HERE / "how_low_P0.csv"); a = y[y.set == "a"]
    s45 = a[a.alarm == 2]
    with Pool(6) as p:
        R = pd.DataFrame(sum(p.map(one, list(s45.groupby("ticker"))), [])).set_index("ix")
    s45 = s45.join(R)
    pick = lambda al: a[a.alarm == al].sort_values(["date", "dist"]).groupby("date").head(1).assign(r=lambda d: d.ret, st=lambda d: d.why.replace({"time": "stall", "eod": "stall"}))
    p11, p1145 = pick(3), pick(4)
    A = pd.concat([p11, p1145[~p1145.date.isin(p11.date)]])
    print(f"PLAN A today (11:15 else 11:45): {len(A)} trades | net {(A.r.mean()-COST)*1000:+.0f}/trade | total net {(A.r-COST).sum()*1000:+,.0f}")
    for lk in ("10:50", "11:00"):
        print(f"\n--- look at {lk} ---")
        for v in ("SCAN", "USER", "MIX"):
            col = s45[f"{v}{lk}"]; r = col.map(lambda x: x[0]); st = col.map(lambda x: x[1])
            ok = s45[r.notna()].assign(r=r[r.notna()], st=st[r.notna()])
            first = ok.sort_values(["date", "dist"]).groupby("date").head(1)
            B = pd.concat([first, p11[~p11.date.isin(first.date)], p1145[~p1145.date.isin(first.date) & ~p1145.date.isin(p11.date)]])
            print(f"  {v:4s}: 10:45 trades taken {len(ok):3d} of {len(s45)} (dead {np.mean(st == 'dead')*100:.0f}%, limit unfilled {np.mean(st == 'unfilled')*100:.0f}%) "
                  f"| those: tgt {np.mean(ok.st == 'target')*100:.0f} stall {np.mean(ok.st == 'stall')*100:.0f} stop {np.mean(ok.st == 'stop')*100:.0f} Rs {ok.r.mean()*1000:+.0f}"
                  f" || PLAN {len(B)} trades net {(B.r.mean()-COST)*1000:+.0f}/trade total {(B.r-COST).sum()*1000:+,.0f} | "
                  + " ".join(f"{k}: {g.r.mean()*1000:+.0f}" for k, g in B.groupby(B.date.str[:7])))
        lim_only = s45[s45[f"MIX{lk}"].map(lambda x: x[1]) != "dead"]
        sk = lim_only[(lim_only.qh - 0) > 0]
