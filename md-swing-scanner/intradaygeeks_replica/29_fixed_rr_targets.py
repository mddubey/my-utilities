"""User: 'it stops often, but RR is 1:3, otherwise we don't trade'. Spec fixed 2026-10-01 before running.
Same triggers, same stop (wick), same time exits; ONLY the target changes: target = entry +/- k x risk, k = 2, 3, 4.
  5m : 18's 'held' triggers (Jun-Sep 2026), walked on 5m bars, out at 5h after entry or day's last bar.
  1h : 15's 1H-close triggers (trend, not daily-8 wrong side, no 09:15, 2024-26), walked on 1H bars, out at the 5th bar
       or day's last bar; stop first if one bar hits both (conservative).
Breakeven target-hit rate for a pure target/stop outcome = 1/(1+k); time exits make it fuzzier, so we report the
target-first share among stop/target-resolved trades vs 1/(1+k) as well."""
import warnings; warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
KS = (2, 3, 4)


def read(p):
    x = pd.read_csv(p, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[(x.Volume > 0) | (x.High != x.Low)]


def walk(H, L, C, T, k0, s, entry, stop, tgt, end_time=None, max_bars=None):
    last_day = T[k0].normalize()
    for j in range(k0 + 1, len(C)):
        if T[j].normalize() != last_day: return C[j - 1], "eod"
        if (L[j] <= stop) if s == 1 else (H[j] >= stop): return stop, "stop"
        if (H[j] >= tgt) if s == 1 else (L[j] <= tgt): return tgt, "target"
        if end_time is not None and T[j] >= end_time: return C[j], "time"
        if max_bars is not None and j - k0 >= max_bars: return C[j], "time"
    return C[-1], "eod"


def run5(args):
    t, rows = args
    x = read(HERE.parent / "intraday_cache" / f"{t}.csv"); H, L, C, T = x.High.values, x.Low.values, x.Close.values, x.index
    out = []
    for r in rows.itertuples():
        et = pd.Timestamp(f"{r.date:%Y-%m-%d} {r.entry_time}")
        if et not in x.index: continue
        k0 = x.index.get_loc(et); s = 1 if r.side == "long" else -1; risk = r.stop_rs; stop = r.entry - s * risk
        for k in KS:
            px, why = walk(H, L, C, T, k0, s, r.entry, stop, r.entry + s * k * risk, end_time=et + pd.Timedelta("5h"))
            out.append(dict(k=k, side=r.side, date=r.date, exit=why, R=(px - r.entry) * s / risk, ret=(px - r.entry) * s / r.entry * 100))
    return out


def run1(args):
    t, rows = args
    x = read(HERE / "h1_cache" / f"{t}.csv"); H, L, C, T = x.High.values, x.Low.values, x.Close.values, x.index
    out = []
    for r in rows.itertuples():
        if r.bt not in x.index: continue
        k0 = x.index.get_loc(r.bt); s = 1 if r.side == "long" else -1; risk = r.stop_rs; stop = r.price - s * risk
        for k in KS:
            px, why = walk(H, L, C, T, k0, s, r.price, stop, r.price + s * k * risk, max_bars=5)
            out.append(dict(k=k, side=r.side, date=r.date, exit=why, R=(px - r.price) * s / risk, ret=(px - r.price) * s / r.price * 100))
    return out


def report(D, title, per):
    print(f"\n### {title}\n| target | n | target hit % | stop % | time/eod % | target-first among resolved | breakeven 1/(1+k) | meanR | mean% | by period mean R |\n|---|---|---|---|---|---|---|---|---|---|")
    for k in KS:
        x = D[D.k == k]; e = x.exit.value_counts(normalize=True); res = x[x.exit.isin(["stop", "target"])]
        y = x.groupby(per(x)).R.mean()
        print(f"| 1:{k} | {len(x)} | {e.get('target',0)*100:.1f} | {e.get('stop',0)*100:.1f} | {(e.get('time',0)+e.get('eod',0))*100:.1f} | "
              f"{(res.exit=='target').mean()*100:.1f}% | {100/(1+k):.1f}% | {x.R.mean():+.3f} | {x.ret.mean():+.3f} | " + " / ".join(f"{a}:{b:+.2f}" for a, b in y.items()) + " |")
    for side in ("short", "long"):
        x = D[(D.k == 3) & (D.side == side)]; print(f"  1:3 {side}: n={len(x)} meanR {x.R.mean():+.3f} target hit {(x.exit=='target').mean()*100:.1f}%")


if __name__ == "__main__":
    from multiprocessing import Pool
    P = pd.read_csv(HERE / "pin_rejection_held_results.csv", parse_dates=["date"]); P = P[P.variant == "held"]
    A = pd.read_csv(HERE / "intraday_1h34_daily8_results.csv", parse_dates=["date"])
    A["bt"] = pd.to_datetime(A.ts, utc=True).dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    A = A[A.trend & (A.dstate != "wrong") & (A.bt.dt.strftime("%H:%M") != "09:15") & (A.date >= "2024-01-01")]
    with Pool(6) as p:
        D5 = pd.DataFrame(sum(p.map(run5, list(P.groupby("ticker"))), []))
        D1 = pd.DataFrame(sum(p.map(run1, list(A.groupby("ticker"))), []))
    D5.to_csv(HERE / "fixed_rr_5m.csv", index=False); D1.to_csv(HERE / "fixed_rr_1h.csv", index=False)
    report(D5, "5m held rejection, Jun-Sep 2026 (by month)", lambda x: x.date.dt.month)
    report(D1, "1H close, 2024-26 (by year)", lambda x: x.date.dt.year)
