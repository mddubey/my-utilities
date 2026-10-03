"""Quality ladder: cut setups with evidence-backed filters until ~1/day, not by ranking (user, 2026-10-03).
Spec fixed before running. Filters added cumulatively in this fixed order:
  S1 stock steadily below VWAP: >= 70% of closes since 09:15 below session VWAP (30m set: 5m closes; 1H set: the
     1-2 completed 1H closes before entry vs 1H-typical-price VWAP -- coarse, labelled)
  S2 wick only slightly above the 1H 34-EMA: (stop - EMA) <= 0.3% of entry
  S3 his SWING 1H state also true: last completed 1H close below 1H EMA34 and above 1H EMA8 (EMAs incl. that candle)
A step is KEPT only if it raises the all-setups mean in BOTH sets. Whatever remains: first come (earliest alarm; same
alarm -> closest to EMA). Sets: (a) 30m-trigger shorts, 2:1, alarms 10:45-12:15, Jun 10 - Sep 30 2026;
(b) 1H-close checklist shorts, 2:1, 0.5% cap, alarms 11:15/12:15, 2024-26."""
import warnings; warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; M5 = HERE.parent / "intraday_cache"


def read(p):
    x = pd.read_csv(p, index_col=0); x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[(x.Volume > 0) | (x.High != x.Low)]


def feats_a(args):
    t, g = args
    m = read(M5 / f"{t}.csv"); h = read(HERE / "h1_cache" / f"{t}.csv")
    e8, e34 = h.Close.ewm(span=8, adjust=False).mean(), h.Close.ewm(span=34, adjust=False).mean()
    out = []
    for r in g.itertuples():
        d = m[(m.index.normalize() == r.date) & (m.index + pd.Timedelta("5min") <= r.t_in)]
        if d.empty: out.append((r.Index, np.nan, np.nan)); continue
        vw = ((d.High + d.Low + d.Close) / 3 * d.Volume).cumsum() / d.Volume.cumsum().replace(0, np.nan)
        hc = h[h.index + pd.Timedelta("60min") <= r.t_in]
        sw = bool(hc.Close.iloc[-1] < e34.loc[hc.index[-1]] and hc.Close.iloc[-1] > e8.loc[hc.index[-1]]) if len(hc) else np.nan
        out.append((r.Index, (d.Close < vw).mean(), sw))
    return out


def feats_b(args):
    t, g = args
    h = read(HERE / "h1_cache" / f"{t}.csv")
    e8, e34 = h.Close.ewm(span=8, adjust=False).mean(), h.Close.ewm(span=34, adjust=False).mean()
    out = []
    for r in g.itertuples():
        d = h[(h.index.normalize() == r.date) & (h.index <= r.bar_ts)]
        vw = ((d.High + d.Low + d.Close) / 3 * d.Volume).cumsum() / d.Volume.cumsum().replace(0, np.nan)
        sw = bool(h.Close.loc[r.bar_ts] < e34.loc[r.bar_ts] and h.Close.loc[r.bar_ts] > e8.loc[r.bar_ts]) if r.bar_ts in h.index else np.nan
        out.append((r.Index, (d.Close < vw).mean() if len(d) else np.nan, sw))
    return out


def ladder(D, per, nd, title):
    steps = [("base", np.ones(len(D), bool)), ("S1 steadily below VWAP", D.below_share >= 0.7),
             ("S2 wick <= 0.3% above EMA", D.wick <= 0.3), ("S3 SWING 1H also true", D.swing == True)]
    print(f"\n### {title}\n| step (cumulative) | setups/day | mean % all setups | by period | first-come one/day: mean % | days with a trade |\n|---|---|---|---|---|---|")
    m = np.ones(len(D), bool); res = {}
    for nm, f in steps:
        m = m & np.asarray(f); x = D[m]
        one = x.sort_values(["date", "t_in", "dist"]).groupby("date").head(1)
        p = x.groupby(per(x)).ret.mean()
        res[nm] = x.ret.mean()
        print(f"| {nm} | {len(x)/nd:.2f} | {x.ret.mean():+.3f} (n {len(x)}) | " + " / ".join(f"{v:+.2f}" for v in p) +
              f" | {one.ret.mean():+.3f} (n {len(one)}) | {len(one)/nd*100:.0f}% |")
    return res


if __name__ == "__main__":
    from multiprocessing import Pool
    A = pd.read_csv(HERE / "alarm_times_30m.csv", parse_dates=["date", "t_in"])
    A = A[A.alarm.isin(["10:45", "11:15", "11:45", "12:15"])].copy().rename(columns={"below_ema": "dist"})
    A["wick"] = A.stop_pct - A.dist
    X = pd.read_csv(HERE / "gap_live_entry_1h.csv", parse_dates=["date", "bar_ts"])
    B = X[(X.side == "short") & X.bar_ts.dt.strftime("%H:%M").isin(["10:15", "11:15"]) & (X.dadx <= 25) & (X.vwap_with == True)
          & (X.st_live <= 0) & (X.close_past_ema > 0) & (X.close_past_ema <= 0.5) & (X.stop_pct <= 0.5)].copy()
    B["t_in"] = B.bar_ts + pd.Timedelta("60min"); B["dist"] = B.close_past_ema; B["wick"] = B.wick_past_ema_pct
    with Pool(6) as p:
        FA = sum(p.map(feats_a, list(A.groupby("ticker"))), []); FB = sum(p.map(feats_b, list(B.groupby("ticker"))), [])
    A = A.join(pd.DataFrame(FA, columns=["i", "below_share", "swing"]).set_index("i"))
    B = B.join(pd.DataFrame(FB, columns=["i", "below_share", "swing"]).set_index("i"))
    A.to_csv(HERE / "quality_ladder_a.csv", index=False); B.to_csv(HERE / "quality_ladder_b.csv", index=False)
    ra = ladder(A, lambda x: x.date.dt.month, 79, "(a) 30-min trigger, Jun 10 - Sep 30 2026 (by month)")
    rb = ladder(B, lambda x: x.date.dt.year, 675, "(b) 1H close, 2024-26 (by year; S1 coarse on 1H bars)")
    print("\nkeep rule (raises mean in BOTH sets vs previous step):")
    keys = list(ra); 
    for i in range(1, len(keys)):
        a, b = ra[keys[i]] - ra[keys[i-1]], rb[keys[i]] - rb[keys[i-1]]
        print(f"  {keys[i]}: 30m {a:+.3f}, 1H {b:+.3f} -> {'KEEP' if a > 0 and b > 0 else 'drop'}")
