"""Pre-screen before the alarms (user idea, 2026-10-03): how many real setups would a prior-close screen keep, and how
many stocks would still need live bars? Spec fixed before running. Universe/day: liquid (tv20 >= Rs 10cr) and daily
ADX(yday) <= 25. Screen from data known at the PREVIOUS close: (T) 1H EMA8 < EMA34 at yesterday's last hour;
(Dk) yesterday's close within k% of the 1H EMA34 (either side), k = 2 / 3 / 5. Setups = 43's 30m shorts (2:1 rule),
Jun 10 - Sep 30 2026."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from market_regime import _compute_adx
HERE = Path(__file__).resolve().parent


def screen(t):
    try: d = load(t)
    except Exception: return None
    d = d[d.index < "2026-10-01"]
    p = HERE / "h1_cache" / f"{t}.csv"
    if not p.exists() or len(d) < 60: return None
    h = pd.read_csv(p, index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    h = h[h.index < "2026-10-01"]
    e8, e34 = h.Close.ewm(span=8, adjust=False).mean(), h.Close.ewm(span=34, adjust=False).mean()
    last = pd.DataFrame({"c": h.Close, "e8": e8, "e34": e34}).groupby(h.index.normalize()).last()   # state at each day's close
    st = last.shift(1)                                                 # as known BEFORE each day
    adx = _compute_adx(d)[0].shift(1); tv = d.traded_value_sma20.shift(1)
    days = st.index[(st.index >= "2026-06-10")]
    rows = []
    for dd in days:
        if tv.get(dd, 0) < 1e8 or not (adx.get(dd, 99) <= 25) or np.isnan(st.loc[dd, "e34"]): continue
        s = st.loc[dd]; dist = abs(s.c / s.e34 - 1) * 100
        rows.append((t, dd, bool(s.e8 < s.e34), dist))
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    uni = pd.read_csv(HERE.parent / "nse_equity_universe.csv").ticker.tolist()
    with Pool(6) as p: S = pd.DataFrame(sum([r for r in p.map(screen, uni, chunksize=20) if r], []), columns=["ticker", "date", "trend", "dist"])
    A = pd.read_csv(HERE / "alarm_times_30m.csv", parse_dates=["date"]); A = A[A.alarm.isin(["10:45", "11:15", "11:45", "12:15"])]
    J = A.merge(S, on=["ticker", "date"], how="left")
    nd = S.date.nunique()
    print(f"days {nd} | stocks per day before screen (liquid & ADX <= 25): {len(S)/nd:.0f} | real setups {len(A)}\n")
    print("| prior-close screen | stocks to fetch per day | real setups kept | their mean % | setups dropped: mean % |\n|---|---|---|---|---|")
    for lab, mS, mJ in (("none", np.ones(len(S), bool), np.ones(len(J), bool)),
                        ("1H trend down", S.trend, J.trend == True),
                        ("trend + within 2% of 1H EMA34", S.trend & (S.dist <= 2), (J.trend == True) & (J.dist <= 2)),
                        ("trend + within 3%", S.trend & (S.dist <= 3), (J.trend == True) & (J.dist <= 3)),
                        ("trend + within 5%", S.trend & (S.dist <= 5), (J.trend == True) & (J.dist <= 5))):
        k, dr = J[mJ], J[~mJ]
        print(f"| {lab} | {mS.sum()/nd:.0f} | {len(k)/len(J)*100:.0f}% | {k.ret.mean():+.3f} | {dr.ret.mean():+.3f} (n {len(dr)}) |")
