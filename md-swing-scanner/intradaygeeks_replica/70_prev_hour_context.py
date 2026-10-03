"""Previous-hour context of each trade (user, 2026-10-04, KNACK 30 Sep): is the trigger a rejection from BELOW, or a
pullback onto the 1H 34-EMA after price had closed above it? Two pre-declared, chart-logic measures of the last
finished hourly bar before the trigger hour:
  SIDE:     previous hourly close above the 1H EMA34 (EMA incl. that bar) -> the EMA was support, not resistance.
  STRENGTH: previous hour green AND trigger close still above that green bar's midpoint -> shallow pullback after a
            strong hour (buyers still in control); below the midpoint = sellers took over ("dark cloud" convention).
Reads stop_rate_filters.csv (sets a, b: script 67) and full_hour_trigger.csv (set a full-hour: script 68)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import INTRADAY_5M_DIR
HERE = Path(__file__).resolve().parent


def hour_key(idx):
    d = idx.normalize(); return d + pd.Timedelta("9h15min") + ((idx - d - pd.Timedelta("9h15min")) // pd.Timedelta("60min")) * pd.Timedelta("60min")


def hourly(t, src):
    """hourly O/C (09:15 grid) + for set a the 5-min closes (to read the close at any alarm time)"""
    if src == "a":
        m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
        return m.groupby(hour_key(m.index)).agg(O=("Open", "first"), C=("Close", "last")), m.Close
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0, parse_dates=True)
    h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return h.rename(columns={"Open": "O", "Close": "C"})[["O", "C"]], None


def context(rows, src):
    """per trade: prev hourly close above EMA34 (side), prev hour green, trigger close above prev bar midpoint"""
    res = {}
    for t, g in rows.groupby("ticker"):
        H, c5 = hourly(t, src); e34 = H.C.ewm(span=34, adjust=False).mean(); pos = {k: i for i, k in enumerate(H.index)}
        for ix, r in g.iterrows():
            d = pd.Timestamp(r.date)
            if src == "a":
                hs = d + pd.Timedelta("9h15min") + ((r.alarm * 30) // 60) * pd.Timedelta("60min")
                at = d + pd.Timedelta("9h15min") + (r.alarm + 1) * pd.Timedelta("30min")
                cc = c5[c5.index < at]; entry = cc.iloc[-1] if len(cc) else np.nan
            else:
                hs = d + pd.Timedelta(hours=int(r.alarm), minutes=15); entry = np.nan
            i = pos.get(hs)
            if i is None or i < 1: continue
            if src == "b": entry = H.C.iloc[i]
            pO, pC, pE = H.O.iloc[i - 1], H.C.iloc[i - 1], e34.iloc[i - 1]
            res[ix] = dict(prev_above=bool(pC > pE), prev_green=bool(pC > pO), above_mid=bool(entry > (pO + pC) / 2), entry=entry)
    return pd.DataFrame.from_dict(res, orient="index")


def label(x):
    return np.where(~x.prev_above, "A: prev hour closed BELOW EMA",
           np.where(x.prev_green & x.above_mid, "B: above EMA, strong green, shallow pullback", "C: above EMA, other"))


if __name__ == "__main__":
    from multiprocessing import Pool
    old = pd.read_csv(HERE / "stop_rate_filters.csv"); new = pd.read_csv(HERE / "full_hour_trigger.csv"); new["set"] = "a_full"
    sets = {"a (30m, old)": old[old.set == "a"], "a (30m, full hour at :15)": new, "b (1H, 3 years)": old[old.set == "b"]}
    out = []
    for nm, x in sets.items():
        src = "b" if nm.startswith("b") else "a"
        parts = [g for _, g in x.groupby("ticker")]
        with Pool(6) as p:
            ctx = pd.concat(p.starmap(context, [(g, src) for g in parts]))
        y = x.join(ctx, how="inner"); y["grp"] = label(y); y["name"] = nm; out.append(y)
    pd.concat(out).to_csv(HERE / "prev_hour_context.csv", index=False)
