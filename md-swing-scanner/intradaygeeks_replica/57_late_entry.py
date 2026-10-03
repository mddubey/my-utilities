"""What does running the alarm scan late cost? Spec fixed 2026-10-03 before running.
Trades: 43's 30m-trigger shorts, 2:1 rule, alarms 10:45-12:15, Jun 10 - Sep 30 2026. Entry delayed by D = 0/5/10/15/20
min: fill = close of the 5m bar ending at alarm + D (D=0 = the backtest). Stop = the 30m candle high (unchanged),
target = fill - 1%, out at 5h after the alarm or the day's last 5m close, stop first. If price touched the stop
during the delay, the setup is dead (no trade). Late-entry rules: A take at market; B skip if fill is > 0.3% below the
candle close (don't chase); C skip unless (stop - fill)/fill <= 0.5% (2:1 still holds at the fill)."""
import warnings; warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; M5 = HERE.parent / "intraday_cache"


def run(args):
    t, g = args
    x = pd.read_csv(M5 / f"{t}.csv", index_col=0); x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    x = x[(x.Volume > 0) | (x.High != x.Low)]
    out = []
    for r in g.itertuples():
        d = x[x.index.normalize() == r.date]; H, L, C, T = d.High.values, d.Low.values, d.Close.values, d.index
        b0 = np.where(T == r.t_in - pd.Timedelta("5min"))[0]
        if len(b0) == 0: continue
        b0 = b0[0]; c0 = C[b0]; stop = c0 * (1 + r.stop_pct / 100); end = T[b0] + pd.Timedelta("5h")
        for D in (0, 5, 10, 15, 20):
            b = b0 + D // 5
            if b >= len(C): continue
            if D and H[b0 + 1:b + 1].max() >= stop: out.append(dict(key=r.Index, D=D, dead=True)); continue
            fill = C[b]; tgt = fill * 0.99; px = C[-1]
            for k in range(b + 1, len(C)):
                if H[k] >= stop: px = stop; break
                if L[k] <= tgt: px = tgt; break
                if T[k] >= end: px = C[k]; break
            out.append(dict(key=r.Index, D=D, dead=False, chase=(c0 - fill) / c0 * 100, risk=(stop - fill) / fill * 100,
                            ret=(fill - px) / fill * 100))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    A = pd.read_csv(HERE / "alarm_times_30m.csv", parse_dates=["date", "t_in"]); A = A[A.alarm.isin(["10:45", "11:15", "11:45", "12:15"])]
    with Pool(6) as p: R = pd.DataFrame(sum(p.map(run, list(A.groupby("ticker"))), []))
    R = R.join(A[["date"]], on="key")
    print(f"setups {A.shape[0]}\n| delay | already stopped out (dead) | A: take at market | B: skip if moved > 0.3% in favour | C: skip unless 2:1 still holds |\n|---|---|---|---|---|")
    for D, g in R.groupby("D"):
        live = g[~g.dead]; b = live[live.chase <= 0.3]; c = live[live.risk <= 0.5]
        print(f"| {D} min | {g.dead.mean()*100:.0f}% | {live.ret.mean():+.3f} (n {len(live)}) | {b.ret.mean():+.3f} (n {len(b)}) | {c.ret.mean():+.3f} (n {len(c)}) |")
    print("\nmedian price move during the delay (positive = moved in the short's favour, i.e. you'd chase):")
    print({D: round(g[~g.dead].chase.median(), 3) for D, g in R.groupby("D") if D})
