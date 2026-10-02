"""Attach the user's other filters to the 15 (1H close, no 09:15) and 16 (forming pin) trades, as splits.
Pre-declared (2026-10-01), no tuning: 1H ADX14 as of the last completed 1H bar > 25; daily ADX14 as of yesterday > 25;
classic pivots (PP=(H+L+C)/3, R1=2PP-L, S1=2PP-H) from the last completed DAY and WEEK. Room for a long = R1/entry-1:
'room>=1%' (target before R1), 'R1 within 1%' (target beyond R1), 'above R1' (already through). Shorts mirror with S1.
"""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from market_regime import _compute_adx
HERE = Path(__file__).resolve().parent


def piv(df, freq):
    g = df if freq is None else df.resample(freq).agg({"High": "max", "Low": "min", "Close": "last"}).dropna()
    pp = (g.High + g.Low + g.Close) / 3
    r1, s1 = (2 * pp - g.Low).shift(1), (2 * pp - g.High).shift(1)
    if freq is None: return r1, s1
    return r1.reindex(df.index, method="ffill"), s1.reindex(df.index, method="ffill")


def feats(args):
    t, rows = args
    try: d = load(t)
    except FileNotFoundError: return []
    dadx = _compute_adx(d)[0].shift(1)
    dr1, ds1 = piv(d, None); wr1, ws1 = piv(d, "W-FRI")
    h1 = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0)
    h1.index = pd.to_datetime(h1.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    hadx = _compute_adx(h1)[0].shift(1)
    out = []
    for r in rows.itertuples():
        s = 1 if r.side == "long" else -1
        def room(r1, s1):
            lv = r1 if s == 1 else s1
            if np.isnan(lv): return "na"
            x = (lv / r.entry - 1) * 100 * s
            return "through" if x <= 0 else ("within1" if x < 1 else "room1+")
        out.append(dict(key=r.key, hadx=hadx.get(r.hts, np.nan), dadx=dadx.get(r.date, np.nan),
                        d_piv=room(dr1.get(r.date, np.nan), ds1.get(r.date, np.nan)),
                        w_piv=room(wr1.get(r.date, np.nan), ws1.get(r.date, np.nan))))
    return out


def attach(R):
    from multiprocessing import Pool
    R = R.reset_index(drop=True); R["key"] = R.index
    with Pool(6) as p:
        f = sum(p.map(feats, list(R.groupby("ticker"))), [])
    return R.merge(pd.DataFrame(f), on="key", how="left")


if __name__ == "__main__":
    A = pd.read_csv(HERE / "intraday_1h34_daily8_results.csv", parse_dates=["date"])
    A["hts"] = pd.to_datetime(A.ts, utc=True).dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    A = A[A.trend & (A.dstate != "wrong") & (A.hts.dt.strftime("%H:%M") != "09:15") & (A.date >= "2024-01-01")]
    A["entry"] = A.price
    P = pd.read_csv(HERE / "pinbar_forming_5m_results.csv", parse_dates=["date"])
    P = P[(P.dstate != "wrong") & (P.hour != "15:15")]
    P["hts"] = pd.to_datetime(P.date.dt.strftime("%Y-%m-%d") + " " + P.hour)
    for nm, R in (("1h_close", A), ("forming_pin", P)):
        n0 = len(R); R = attach(R); assert len(R) == n0
        R.to_csv(HERE / f"splits_{nm}.csv", index=False); print(nm, n0, R[["hadx", "dadx"]].notna().mean().round(3).to_dict())
