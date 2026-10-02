"""Pre-declared cue splits (definitions from the 2026-10-01 literature review, adopted before looking), on two trade sets:
  5m : 18's 'held' rejection trades (Jun-Sep 2026), entry known at the close of a 5m bar.
  1h : 15's 1H-close trades (trend, not daily-8 wrong side, no 09:15 setup, 2024-26), entry at a 1H close.
All features use only data known at the entry bar's close (or the prior close). Sign s = +1 long / -1 short.
  nifty_with   : Nifty since-open return (last COMPLETED Nifty 1H bar close / day's 09:15 open - 1) * s > 0
  tod          : entry-time bucket 10:15-11:30 / 11:30-13:30 / 13:30-14:30 / 14:30+
  rvol         : stock cumulative volume 09:15->entry / mean of the same window over the prior 14 sessions; <1, 1-2, >=2
  atr_terc     : prior-day ATR14 % of price, terciles within each trade set
  vwap_with    : (entry - session VWAP) * s > 0   (1h set: VWAP from 1H typical price -- an approximation)
  rs_with      : (stock since-open - Nifty since-open) * s > 0
  sector_with  : mean since-open return of same-sector peers (Nifty-500 sector map, excl. the stock) * s > 0
  gap          : (open / prev close - 1) * s : < -0.5% / -0.5..+0.5% / > +0.5%
  rsi_with     : 1H RSI14 of last completed 1H bar >= 50 (long) / <= 50 (short)
"""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from signals import rsi
HERE = Path(__file__).resolve().parent
H1, M5 = HERE / "h1_cache", HERE.parent / "intraday_cache"
SECT = pd.read_csv(HERE.parent / "data_cache" / "_sectors.csv").dropna().set_index("ticker").sector


def read(p):
    x = pd.read_csv(p, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[(x.Volume > 0) | (x.High != x.Low)][["Open", "High", "Low", "Close", "Volume"]]


def bar_feats(x, step):
    """per bar: since-open return at bar close, cum volume, VWAP, rvol vs prior 14 sessions same time-of-day."""
    day = x.index.normalize(); tod = x.index.strftime("%H:%M")
    o = x.groupby(day).Open.transform("first")
    f = pd.DataFrame(index=x.index)
    f["since_open"] = x.Close / o - 1
    cv = x.Volume.groupby(day).cumsum()
    tp = (x.High + x.Low + x.Close) / 3
    f["vwap"] = (tp * x.Volume).groupby(day).cumsum() / cv.replace(0, np.nan)
    piv = pd.DataFrame({"d": day, "t": tod, "cv": cv.values}).pivot_table(index="d", columns="t", values="cv").ffill(axis=1)
    base = piv.rolling(14, min_periods=10).mean().shift(1)
    f["rvol"] = [cv.iloc[i] / base.at[day[i], tod[i]] if tod[i] in base.columns and day[i] in base.index else np.nan
                 for i in range(len(x))]
    return f


def peer_since_open(t, kind):
    p = (M5 if kind == "5m" else H1) / f"{t}.csv"
    if not p.exists(): return None
    x = read(p)
    if kind == "5m": x = x[x.index >= "2026-06-01"]
    else: x = x[x.index >= "2023-12-01"]
    day = x.index.normalize()
    return (x.Close / x.groupby(day).Open.transform("first") - 1).rename(t)


def sector_table(kind):
    from multiprocessing import Pool
    ts = [t for t in SECT.index]
    with Pool(6) as p: ser = [s for s in p.starmap(peer_since_open, [(t, kind) for t in ts]) if s is not None]
    M = pd.concat(ser, axis=1)
    return M


def nifty():
    n = read(HERE / "index_1h" / "_NIFTY_1h.csv")
    day = n.index.normalize()
    n["since_open"] = n.Close / n.groupby(day).Open.transform("first") - 1
    n["end"] = n.index + pd.Timedelta("60min")
    return n


def feats(args):
    t, rows, kind = args
    p = (M5 if kind == "5m" else H1) / f"{t}.csv"
    x = read(p)
    if kind == "5m": x = x[x.index >= "2026-05-01"]
    else: x = x[x.index >= "2023-11-01"]
    f = bar_feats(x, kind)
    h1 = read(H1 / f"{t}.csv"); r1 = rsi(h1.Close, 14)
    d = load(t); atrp = (d.atr14 / d.Close).shift(1) * 100; gap = d.Open / d.Close.shift(1) - 1
    out = []
    for r in rows.itertuples():
        s = 1 if r.side == "long" else -1
        bt = r.bar_ts                                        # entry bar start
        if bt not in f.index: out.append(dict(key=r.key)); continue
        fb = f.loc[bt]
        hr = r1[r1.index + pd.Timedelta("60min") <= r.decide_ts]
        out.append(dict(key=r.key, stock_so=fb.since_open, rvol=fb.rvol, vwap_with=bool((r.entry - fb.vwap) * s > 0),
                        atrp=atrp.get(r.date, np.nan), gap_s=gap.get(r.date, np.nan) * 100 * s,
                        rsi1h=hr.iloc[-1] if len(hr) else np.nan))
    return out


def build(R, kind):
    from multiprocessing import Pool
    R = R.reset_index(drop=True); R["key"] = R.index
    with Pool(6) as p:
        F = sum(p.map(feats, [(t, g, kind) for t, g in R.groupby("ticker")]), [])
    R = R.merge(pd.DataFrame(F), on="key", how="left")
    N = nifty()
    def nso(ts):
        z = N[N.end <= ts]
        return z.since_open.iloc[-1] if len(z) and z.index[-1].normalize() == ts.normalize() else np.nan
    R["nifty_so"] = [nso(ts) for ts in R.decide_ts]
    S = sector_table(kind)
    sec = R.ticker.map(SECT)
    vals = []
    for r, sc in zip(R.itertuples(), sec):
        if pd.isna(sc) or r.bar_ts not in S.index: vals.append(np.nan); continue
        peers = [c for c in SECT[SECT == sc].index if c in S.columns and c != r.ticker]
        vals.append(S.loc[r.bar_ts, peers].mean() if peers else np.nan)
    R["sector_so"] = vals
    return R


if __name__ == "__main__":
    P = pd.read_csv(HERE / "pin_rejection_held_results.csv", parse_dates=["date"]); P = P[P.variant == "held"]
    P["bar_ts"] = pd.to_datetime(P.date.dt.strftime("%Y-%m-%d") + " " + P.entry_time)
    P["decide_ts"] = P.bar_ts + pd.Timedelta("5min")
    A = pd.read_csv(HERE / "intraday_1h34_daily8_results.csv", parse_dates=["date"])
    A["bar_ts"] = pd.to_datetime(A.ts, utc=True).dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    A = A[A.trend & (A.dstate != "wrong") & (A.bar_ts.dt.strftime("%H:%M") != "09:15") & (A.date >= "2024-01-01")]
    A["entry"] = A.price; A["decide_ts"] = A.bar_ts + pd.Timedelta("60min")
    for nm, R, kind in (("5m_held", P, "5m"), ("1h_close", A, "1h")):
        n0 = len(R); R = build(R, kind); assert len(R) == n0
        R.to_csv(HERE / f"cues_{nm}.csv", index=False)
        print(nm, n0, R[["rvol", "nifty_so", "sector_so", "rsi1h", "atrp", "gap_s"]].notna().mean().round(2).to_dict(), flush=True)
