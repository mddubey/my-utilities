"""Prior-bar trailing stop vs fixed 1% target, same entries (user, 2026-10-02). Spec fixed before running.
Entries: 43's 30-min rejection shorts at alarms 10:45/11:15/11:45/12:15 with the 2:1 rule (Jun 10 - Sep 30 2026).
Entry = 30m close, initial stop = 30m candle high. All exits flat by 15:15 (MIS). Exits:
  FIXED : 1% target, initial stop, 5h time limit
  T5/T15/T30 : no target; after each 5/15/30-min candle (09:15 grid) completed AFTER entry, stop = min(stop, that
               candle's high + Rs 0.05). Stop checked on every 5m bar (stop first). Never loosened."""
import warnings; warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; M5 = HERE.parent / "intraday_cache"


def read(p):
    x = pd.read_csv(p, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[(x.Volume > 0) | (x.High != x.Low)]


def sim(args):
    t, rows = args
    x = read(M5 / f"{t}.csv"); out = []
    for r in rows.itertuples():
        g = x[x.index.normalize() == r.date]
        g = g[g.index < r.date + pd.Timedelta("15h15min")]
        H, L, C, T = g.High.values, g.Low.values, g.Close.values, g.index
        bi = np.where(T == r.t_in - pd.Timedelta("5min"))[0]
        if len(bi) == 0: continue
        b = bi[0]; e = C[b]; s0 = e * (1 + r.stop_pct / 100); base = r.date + pd.Timedelta("9h15min")
        res = {}
        # FIXED
        px, why, kk = C[-1], "eod", len(C) - 1; tgt = e * 0.99; end = T[b] + pd.Timedelta("5h")
        for k in range(b + 1, len(C)):
            if H[k] >= s0: px, why, kk = s0, "stop", k; break
            if L[k] <= tgt: px, why, kk = tgt, "target", k; break
            if T[k] >= end: px, why, kk = C[k], "time", k; break
        res["FIXED"] = (px, why, kk)
        for n, lab in ((1, "T5"), (3, "T15"), (6, "T30")):
            stop = s0; px, why, kk = C[-1], "eod", len(C) - 1
            grp = ((T - base) // pd.Timedelta(f"{5*n}min")).values
            for k in range(b + 1, len(C)):
                if H[k] >= stop: px, why, kk = stop, "trail_stop" if stop < s0 else "stop", k; break
                last_of_block = (k == len(C) - 1) or grp[k + 1] != grp[k]
                if last_of_block:                                   # a candle just completed at bar k
                    blk = np.where(grp == grp[k])[0]; blk = blk[blk > b]
                    if len(blk) == n or (n > 1 and len(blk) > 0 and blk[0] > b and grp[b] != grp[k] and len(blk) == len(np.where(grp == grp[k])[0])):
                        stop = min(stop, H[np.where(grp == grp[k])[0]].max() + 0.05)
            res[lab] = (px, why, kk)
        out.append(dict(key=r.Index, **{f"{v}_ret": (e - p) / e * 100 for v, (p, w, k) in res.items()},
                        **{f"{v}_exit": w for v, (p, w, k) in res.items()}, **{f"{v}_min": (T[k] - T[b]).seconds // 60 for v, (p, w, k) in res.items()}))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    R = pd.read_csv(HERE / "alarm_times_30m.csv", parse_dates=["date", "t_in", "t_out"])
    R = R[R.alarm.isin(["10:45", "11:15", "11:45", "12:15"])].copy()
    with Pool(6) as p: F = sum(p.map(sim, list(R.groupby("ticker"))), [])
    R = R.join(pd.DataFrame(F).set_index("key"), how="inner"); R.to_csv(HERE / "prior_bar_trail.csv", index=False)
    one = R.sort_values(["date", "t_in", "below_ema"]).groupby("date").head(1)
    lab = {"FIXED": "fixed 1% target (current)", "T5": "trail prior 5-min candle", "T15": "trail prior 15-min candle", "T30": "trail prior 30-min candle"}
    for nm, D in (("ALL SETUPS", R), ("ONE TRADE PER DAY", one)):
        print(f"\n### {nm} (n={len(D)})\n| exit | win% | mean % | median % | avg win | avg loss | best trade | top-10 share of profit | median minutes held | net @0.06% | net @0.10% | Jun / Jul / Aug / Sep |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
        for v in ("FIXED", "T5", "T15", "T30"):
            r = D[f"{v}_ret"]; pos = r[r > 0].sum(); m = r.groupby(D.date.dt.month).mean()
            print(f"| {lab[v]} | {(r>0).mean()*100:.0f} | {r.mean():+.3f} | {r.median():+.3f} | {r[r>0].mean():+.2f} | {r[r<=0].mean():+.2f} | {r.max():+.2f} | "
                  f"{r.sort_values().tail(10).sum()/pos*100 if pos>0 else float('nan'):.0f}% | {D[f'{v}_min'].median():.0f} | {r.mean()-0.06:+.3f} | {r.mean()-0.10:+.3f} | "
                  + " / ".join(f"{a:+.2f}" for a in m) + " |")
