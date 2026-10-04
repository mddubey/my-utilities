"""User's chart read (2026-10-04, RELIGARE 24 Aug / VERANDA 19 Sep 2025): price rose after entry to touch the LIVE
daily 8-EMA sitting just above our stop, took the stop, then fell hard. Spec fixed before running:
  D8_ABOVE_STOP = live daily 8-EMA at entry (2/9*entry + 7/9*yesterday's EMA8) is above the stop (candle high).
  Expect: D8_ABOVE_STOP -> more stops and worse Rs; and more "stopped, then fell 1% from entry anyway later that day".
Population: obstacle_x_market.csv (current rules, all setups, both sets)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import DAILY_DIR, INTRADAY_5M_DIR
HERE = Path(__file__).resolve().parent


def one(args):
    t, g = args
    D = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True)
    e8 = D.Close.ewm(span=8, adjust=False).mean()
    src = {}
    out = []
    for ix, r in g.iterrows():
        k = "b" if r.set == "b" else "a"
        if k not in src:
            if k == "b":
                h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0)
                h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
                src[k] = (h, pd.Timedelta("60min"))
            else:
                m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True)
                m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
                src[k] = (m, pd.Timedelta("5min"))
        bars, step = src[k]
        day = pd.Timestamp(r.date); at = pd.Timestamp(r["at"])
        yd = e8[e8.index < day]
        if not len(yd):
            continue
        live = 2 / 9 * r.entry + 7 / 9 * yd.iloc[-1]
        aft = bars[(bars.index >= at) & (bars.index.normalize() == day) & (bars.index + step <= day + pd.Timedelta("15h30min"))]
        out.append(dict(ix=ix, d8_live=live, day_low_after=aft.Low.min() if len(aft) else np.nan,
                        day_high_after=aft.High.max() if len(aft) else np.nan))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    y = pd.read_csv(HERE / "obstacle_x_market.csv")
    with Pool(6) as p:
        res = sum(p.map(one, list(y.groupby("ticker"))), [])
    y = y.join(pd.DataFrame(res).set_index("ix"), how="inner")
    y["sp"] = y.entry * (1 + y.stop / 100)
    y["d8_above_stop"] = y.d8_live > y.sp
    y["d8_gap"] = (y.d8_live / y.sp - 1) * 100                       # + = daily 8-EMA above our stop
    y["fell_anyway"] = (y.why == "stop") & (y.day_low_after <= y.entry * 0.99)
    y.to_csv(HERE / "daily8_above_stop.csv", index=False)

    def st(g):
        w = g.why
        return pd.Series(dict(n=len(g), target=round((w == "target").mean() * 100, 1), stop=round((w == "stop").mean() * 100, 1),
                              rs=round(g.ret.mean() * 1000), stopped_then_fell_1pct=round(g.fell_anyway.mean() * 100, 1)))
    for s, nm, per in (("a_full", "30m Jun-Sep 2026", 7), ("b", "1H 3 years", 4)):
        z = y[y.set == s].copy(); z["p"] = z.date.str[:per]
        print(f"\n===== {nm} =====")
        print(pd.DataFrame({"baseline": st(z), "daily 8-EMA ABOVE stop": st(z[z.d8_above_stop]),
                            "daily 8-EMA at/below stop": st(z[~z.d8_above_stop])}).T.to_string())
        z["gb"] = pd.cut(z.d8_gap, [-99, -0.3, -0.1, 0, 0.1, 0.3, 99],
                         labels=["< -0.3% (D8 well below stop)", "-0.3..-0.1", "-0.1..0", "0..0.1 (just above)", "0.1..0.3", "> 0.3%"])
        print(z.groupby("gb", observed=True).apply(st).to_string())
        by = z.groupby(["p", "d8_above_stop"]).ret.mean().unstack() * 1000
        print("   Rs by period (ABOVE / at-or-below): " + "  ".join(f"{p}: {r[True]:+.0f}/{r[False]:+.0f}" for p, r in by.iterrows()))
