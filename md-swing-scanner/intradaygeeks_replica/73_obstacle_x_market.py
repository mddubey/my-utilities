"""User's rule (2026-10-04): trade by default; SKIP only when a pivot sits in the way of the target AND the market isn't
helping. Spec fixed before running:
  OBSTACLE: any pivot level (PP/R1/R2/S1/S2) strictly between the 1% target and the entry. Headline = WEEKLY (what the
            1H chart shows with TradingView Auto pivots); daily and monthly = checks.
  MARKET UP at the alarm: M1 = Nifty above its day open (headline; 1H set only, Nifty 5m starts 2026-07-10)
                          M2 = > 50% of liquid stocks (20d traded value >= Rs10 cr) above yesterday's close
                               (1H set: breadth_1h.csv from 48; 30m set: built here from the 5m cache, stocks with
                               5m data from Jun 10 so the universe doesn't change mid-sample).
  SKIP = obstacle AND market up. One-a-day plan: a skipped pick passes to the next setup (next closest at that alarm,
  then 11:45 / 12:15). Population: pivots.csv (script 72) = current rules, all setups."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import INTRADAY_5M_DIR, INDEX_INTRADAY_DIR
from backtest import load
HERE = Path(__file__).resolve().parent


def alarm_time(r):
    d = pd.Timestamp(r.date)
    if r.set == "b":
        return d + pd.Timedelta(hours=int(r.alarm) + 1, minutes=15)      # 1H bar 10:15 -> closes 11:15
    return d + pd.Timedelta("9h15min") + (int(r.alarm) + 1) * pd.Timedelta("30min")


def breadth_5m_one(t):
    m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True)
    m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
    if m.index.min() > pd.Timestamp("2026-06-12"):
        return None
    try:
        d = load(t)
    except Exception:
        return None
    pc, tv = d.Close.shift(1), d.traded_value_sma20.shift(1)
    out = []
    for day, g in m.groupby(m.index.normalize()):
        if day not in pc.index or not (tv.get(day, 0) >= 1e8):
            continue
        for k in (2, 3, 4, 5):
            at = day + pd.Timedelta("9h15min") + (k + 1) * pd.Timedelta("30min")
            c = g.Close[g.index < at]
            if len(c):
                out.append((at, c.iloc[-1] > pc[day]))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    y = pd.read_csv(HERE / "pivots.csv")
    y["at"] = y.apply(alarm_time, axis=1)
    T = y.entry * 0.99
    for tag in "dwm":
        y[f"obs_{tag}"] = np.column_stack([(y[f"{tag}_{k}"] > T) & (y[f"{tag}_{k}"] < y.entry)
                                           for k in ("PP", "R1", "R2", "S1", "S2")]).any(axis=1)
    # M1: Nifty above day open at the alarm
    n5 = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_5m_60d.csv", index_col=0, parse_dates=True)
    n1 = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_1h.csv", index_col=0, parse_dates=True)
    for n in (n5, n1):
        n.index = pd.to_datetime(n.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)

    def m1(r):
        src = n1 if r.set == "b" else n5
        g = src[src.index.normalize() == pd.Timestamp(r.date)]
        if g.empty:
            return np.nan
        step = pd.Timedelta("60min") if r.set == "b" else pd.Timedelta("5min")
        c = g.Close[g.index + step <= r["at"]]
        return float(c.iloc[-1] > g.Open.iloc[0]) if len(c) else np.nan
    y["m1"] = y.apply(m1, axis=1)
    # M2: breadth
    BR = pd.read_csv(HERE / "breadth_1h.csv", parse_dates=["bt"]).set_index("bt").adv
    b_adv = (y["at"] - pd.Timedelta("60min")).map(BR)
    ticks = sorted(p.stem for p in INTRADAY_5M_DIR.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p:
        parts = [r for r in p.map(breadth_5m_one, ticks, chunksize=20) if r]
    b5 = pd.DataFrame(sum(parts, []), columns=["at", "up"]).groupby("at").up.agg(["mean", "size"])
    b5 = b5[b5["size"] >= 200]["mean"]
    print(f"5m breadth: {len(b5)} alarm times with >= 200 liquid stocks")
    y["adv"] = np.where(y.set == "b", b_adv, y["at"].map(b5))
    y["m2"] = np.where(y.adv.isna(), np.nan, (y.adv > 0.5).astype(float))
    y.to_csv(HERE / "obstacle_x_market.csv", index=False)

    def stats(g):
        w = g.why
        return pd.Series(dict(n=len(g), target=round((w == "target").mean() * 100, 1),
                              stop=round((w == "stop").mean() * 100, 1), rs=round(g.ret.mean() * 1000) if len(g) else np.nan,
                              total=round(g.ret.sum() * 1000)))

    def plan(z, skip):
        al = [10, 11] if z.set.iloc[0] == "b" else [3, 4]
        z = z[z.alarm.isin(al) & ~skip.loc[z.index]]
        return z.sort_values(["date", "alarm", "dist"]).groupby("date").head(1)

    for s, nm, per in (("a_full", "30m Jun-Sep 2026", 7), ("b", "1H 3 years", 4)):
        z = y[y.set == s].copy(); z["per"] = z.date.str[:per]
        for mk in ("m1", "m2"):
            for tag, tn in (("w", "WEEKLY"), ("d", "daily"), ("m", "monthly")):
                zz = z[z[mk].notna()]
                if zz.empty:
                    continue
                obs, up = zz[f"obs_{tag}"], zz[mk] == 1
                print(f"\n===== {nm} | {tn} pivot obstacle x {mk.upper()} ({'Nifty above open' if mk == 'm1' else 'breadth > 50%'})"
                      f" | n={len(zz)} =====")
                cells = pd.DataFrame({f"{'obstacle' if o else 'clear'} / {'mkt UP' if u else 'mkt down'}":
                                      stats(zz[(obs == o) & (up == u)]) for o in (True, False) for u in (True, False)}).T
                print(cells.to_string())
                skip = obs & up
                rows = {"baseline": stats(zz), "kept": stats(zz[~skip]), "removed": stats(zz[skip])}
                print(pd.DataFrame(rows).T.to_string())
                by = zz.groupby("per").apply(lambda g: f"{g.ret.mean()*1000:+.0f}/{g[~skip.loc[g.index]].ret.mean()*1000:+.0f}/"
                                             f"{g[skip.loc[g.index]].ret.mean()*1000:+.0f}({skip.loc[g.index].sum()})")
                print("   by period base/kept/removed(n): " + "  ".join(f"{k}: {v}" for k, v in by.items()))
                pb, pk = plan(zz, pd.Series(False, index=zz.index)), plan(zz, skip)
                print(f"   PLAN one/day: baseline {len(pb)} trades Rs{pb.ret.mean()*1000:+.0f} total {pb.ret.sum()*1000:+.0f}"
                      f" | with skip {len(pk)} trades Rs{pk.ret.mean()*1000:+.0f} total {pk.ret.sum()*1000:+.0f}")
