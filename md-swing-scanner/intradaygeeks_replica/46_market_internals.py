"""Market internals at the moment of entry vs our 30m shorts (user, 2026-10-02). Spec fixed before running.
Built from 5m bars of all liquid NSE stocks (prior-day tv20 >= Rs 10cr), Jun 10 - Sep 30 2026, at each 5m bar END time:
  adv     = share of stocks above yesterday's close           bearish < 0.35 | bullish > 0.65
  upvol   = cum volume of stocks up on day / cum volume (up + down)   bearish < 0.40 | bullish > 0.60
  tick30  = share of stocks whose close is above their close 30 min earlier   bearish < 0.40 | bullish > 0.60
  nifty   = real Nifty 5m (Jul 10+) red / green vs yesterday's close
Trades: 43's 30m-trigger shorts at 10:45/11:15/11:45/12:15 with the 2:1 rule (n=785), graded at t_in."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
HERE = Path(__file__).resolve().parent; M5 = HERE.parent / "intraday_cache"


def one(t):
    try: d = load(t)
    except Exception: return None
    d = d[d.index < pd.Timestamp("2026-10-01")]
    pc, tv = d.Close.shift(1), d.traded_value_sma20.shift(1)
    x = pd.read_csv(M5 / f"{t}.csv", index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    x = x[(x.Volume > 0) | (x.High != x.Low)]
    if x.empty: return None
    day = x.index.normalize()
    ok = pd.Series(day, index=x.index).map(lambda d_: tv.get(d_, 0) >= 1e8).values
    x = x[ok]; day = x.index.normalize()
    if x.empty: return None
    prev = pd.Series(day, index=x.index).map(pc).values
    c30 = x.Close.groupby(day).shift(6)
    end = x.index + pd.Timedelta("5min")
    up = x.Close.values > prev
    return pd.DataFrame({"end": end, "up": up, "dn": x.Close.values < prev, "cv": x.Volume.groupby(day).cumsum().values,
                         "t30": np.where(c30.isna(), np.nan, (x.Close > c30).astype(float))})


if __name__ == "__main__":
    from multiprocessing import Pool
    tick = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p: parts = [r for r in p.map(one, tick, chunksize=20) if r is not None]
    P = pd.concat(parts)
    P["upv"] = P.cv * P.up; P["dnv"] = P.cv * P.dn
    I = P.groupby("end").agg(n=("up", "size"), adv=("up", "mean"), upv=("upv", "sum"), dnv=("dnv", "sum"), tick30=("t30", "mean"))
    I["upvol"] = I.upv / (I.upv + I.dnv); I = I[I.n >= 300]
    I.to_csv(HERE / "market_internals_5m.csv")
    n5 = pd.read_csv(HERE / "index_1h" / "_NIFTY_5m_60d.csv", index_col=0)
    n5.index = pd.to_datetime(n5.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None) + pd.Timedelta("5min")
    ND = pd.read_csv(HERE.parent / "data_cache" / "_NIFTY.csv", parse_dates=["Date"]).set_index("Date").Close.shift(1)
    T = pd.read_csv(HERE / "alarm_times_30m.csv", parse_dates=["date", "t_in", "t_out"])
    T = T[T.alarm.isin(["10:45", "11:15", "11:45", "12:15"])].copy()
    T = T.join(I[["adv", "upvol", "tick30"]], on="t_in")
    T["nifty_green"] = [(n5.Close.get(r.t_in, np.nan) > ND.get(r.date, np.nan)) if r.t_in in n5.index else np.nan for r in T.itertuples()]
    def cut(s, lo, hi): return pd.Series(np.select([s < lo, s > hi], ["bearish", "bullish"], "mixed"), index=s.index).where(s.notna())
    def line(x, lab):
        if len(x) < 30: print(f"| {lab} | {len(x)} | too few | | |"); return
        m = x.groupby(x.date.dt.month).ret.mean()
        print(f"| {lab} | {len(x)} | {(x.ret>0).mean()*100:.0f} | {x.ret.mean():+.3f} | " + " / ".join(f"{v:+.2f}" for v in m) + " |")
    print(f"internals built from ~{I.n.median():.0f} liquid stocks per bar\n| market at entry (shorts) | trades | win% | mean % | Jun / Jul / Aug / Sep |\n|---|---|---|---|---|")
    line(T, "BASELINE")
    for col, lo, hi, nm in (("adv", .35, .65, "advancers share"), ("upvol", .40, .60, "up-volume ratio"), ("tick30", .40, .60, "30-min TICK")):
        c = cut(T[col], lo, hi)
        for b in ("bearish", "mixed", "bullish"): line(T[c == b], f"{nm}: {b}")
    for v, nm in ((True, "Nifty GREEN on the day at entry"), (False, "Nifty RED on the day at entry")):
        line(T[T.nifty_green == v], nm)
    print("\nshare of trades by advancers bucket:", cut(T.adv, .35, .65).value_counts(normalize=True).round(2).to_dict())
