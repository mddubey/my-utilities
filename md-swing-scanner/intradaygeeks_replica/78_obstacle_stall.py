"""Does support between entry and the 1% target cause STALLS (time exit) rather than stops? (user, 2026-10-04)
Spec fixed before running. Population: current rules, all setups (how_low_P0.csv joined to obstacle_x_market.csv).
Outcome = 1% target, stop = candle high, out at 15:15 (t1.0 from script 76), split TARGET / STALL (15:15 exit) / STOP.
Obstacle types (each tested alone; level strictly between the 1% target and entry):
  daily PP/S1/S2 | weekly PP/S1/S2 | monthly PP/S1/S2 | previous day's low | day's low so far | 1H EMA8 (if below entry)
Per type: obstacle vs clear -> target / stall / stop %, Rs; and for obstacle trades: did price reach the first obstacle
before the stop, and how far past it did it go (before the stop, and by 15:15 ignoring the stop).
Information only (user will not take a target below 1%): adaptive target = just above the first obstacle
(level + 0.05% of entry) vs fixed 1%."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import DAILY_DIR, INTRADAY_5M_DIR
HERE = Path(__file__).resolve().parent


def extra(args):
    t, g = args
    D = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True)[["Low"]].dropna()
    bars = {}; out = []
    for ix, r in g.iterrows():
        s = r.set
        if s not in bars:
            p = INTRADAY_5M_DIR / f"{t}.csv" if s == "a" else HERE / "h1_cache" / f"{t}.csv"
            m = pd.read_csv(p, index_col=0); m.index = pd.to_datetime(m.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
            bars[s] = (m, pd.Timedelta("5min") if s == "a" else pd.Timedelta("60min"))
        m, step = bars[s]; day = pd.Timestamp(r.date)
        at = day + pd.Timedelta("9h15min") + (int(r.alarm) + 1) * pd.Timedelta("30min") if s == "a" else day + pd.Timedelta(hours=int(r.alarm) + 1, minutes=15)
        dm = m[m.index.normalize() == day]; before = dm[dm.index + step <= at]
        pl = D.Low[D.index < day]
        out.append(dict(ix=ix, prev_low=pl.iloc[-1] if len(pl) else np.nan, day_low_so_far=before.Low.min() if len(before) else np.nan))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    H = pd.read_csv(HERE / "how_low_P0.csv"); O = pd.read_csv(HERE / "obstacle_x_market.csv")
    O["set2"] = O.set.map({"a_full": "a", "b": "b"})
    y = H.merge(O[["set2", "ticker", "date", "alarm"] + [f"{p}_{k}" for p in "dwm" for k in ("PP", "S1", "S2")]],
                left_on=["set", "ticker", "date", "alarm"], right_on=["set2", "ticker", "date", "alarm"], how="inner")
    assert len(y) == len(H), (len(y), len(H))
    with Pool(6) as p:
        ex = pd.DataFrame(sum(p.map(extra, list(y.groupby("ticker"))), [])).set_index("ix")
    y = y.join(ex)
    y["h1_ema8"] = y.qc * (1 - y.d8 / 100)
    E, T = y.qc, y.qc * 0.99
    y["out"] = np.where(np.isclose(y["t1.0"], 1.0), "target", np.where(np.isclose(y["t1.0"], -y.stop_pct), "stop", "stall"))
    TYPES = {"daily PP/S1/S2": ["d_PP", "d_S1", "d_S2"], "weekly PP/S1/S2": ["w_PP", "w_S1", "w_S2"],
             "monthly PP/S1/S2": ["m_PP", "m_S1", "m_S2"], "previous day's low": ["prev_low"],
             "day's low so far": ["day_low_so_far"], "1H EMA8 below entry": ["h1_ema8"]}

    def first_obstacle(cols):
        L = np.column_stack([y[c].values for c in cols]).astype(float)
        L[(L <= T.values[:, None]) | (L >= E.values[:, None])] = np.nan
        return np.nanmax(L, axis=1)            # nearest below entry = highest level inside the path

    def row(g):
        o = g.out
        return f"{len(g):5d} | tgt {(o == 'target').mean()*100:4.1f}  stall {(o == 'stall').mean()*100:4.1f}  stop {(o == 'stop').mean()*100:4.1f} | Rs {g['t1.0'].mean()*1000:+4.0f}"
    for s, nm, per in (("a", "30m Jun-Sep 2026", 7), ("b", "1H 3 years", 4)):
        z0 = y[y.set == s]
        print(f"\n################ {nm}: all {row(z0)}")
        for name, cols in TYPES.items():
            lvl = first_obstacle(cols)[y.set.values == s]; has = ~np.isnan(lvl); z = z0.copy(); z["lvl"] = lvl
            ob, cl = z[has], z[~has]
            if has.sum() < 15: print(f"  {name}: too few ({has.sum()})"); continue
            d = (ob.qc - ob.lvl) / ob.qc * 100                          # obstacle distance below entry, %
            reach = ob.mfe_stop >= d - 0.05
            past_stop = (ob.mfe_stop - d)[reach]; past_eod = (ob.mfe_eod - d)[ob.mfe_eod >= d - 0.05]
            adapt = np.where(ob.mfe_stop >= d - 0.05, d - 0.05, ob["t1.0"])
            by = z.assign(h=has).groupby([z.date.str[:per], "h"])["t1.0"].mean().unstack() * 1000
            print(f"\n  {name}:  obstacle {row(ob)}   (median distance below entry {d.median():.2f}%)")
            print(f"  {'':{len(name)}}   clear    {row(cl)}")
            print(f"     reached the obstacle before the stop: {reach.mean()*100:.0f}% | of those, went past it by (before stop) median {past_stop.median():.2f}%, "
                  f"p75 {past_stop.quantile(.75):.2f}%; by 15:15 ignoring stop median {past_eod.median():.2f}% | went 1% past entry anyway {(ob.mfe_stop >= 1).mean()*100:.0f}%")
            print(f"     info only -- target just above the obstacle: Rs {adapt.mean()*1000:+.0f} vs fixed 1% Rs {ob['t1.0'].mean()*1000:+.0f} (avg target {(d - 0.05).mean():.2f}%)")
            print("     Rs by period obstacle/clear: " + "  ".join(f"{k}: {v.get(True, np.nan):+.0f}/{v.get(False, np.nan):+.0f}" for k, v in by.iterrows()))
