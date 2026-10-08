"""Option C (user, 2026-10-08): 1H EMA34 as the LEVEL, a standard 15-minute candle as the TRIGGER (Elder triple screen:
daily trend -> 1H setup -> 15m trigger; opening-range idea: nothing before 09:30). Results only. Spec fixed before running:
  Level: 1H EMA34 / EMA8 as of the last completed hour before the hour the 15-min candle sits in (scan convention),
  EMA8 < EMA34. Trigger: 15-min candle closing 09:45 .. 12:15 (09:30 onward): red, high >= EMA34, close < EMA34 by <= 0.5%,
  stop = candle high <= 0.5% (2:1). Checks at the candle close: below yesterday's daily 8-EMA, day high >= live daily 8-EMA,
  below session VWAP, daily ADX <= 25, ATR >= 2.56%, tv20 >= Rs10cr, price >= Rs100, no corporate-action day.
  Entry at the candle close; exit 1% target / stop / 5h / 15:15 (stop first if both in one bar). 30m set only (Jun 10 - Sep 30
  2026, 5-min bars, EMAs seeded from h1_cache). Report: all triggers by candle close time; one trade a day (first come by
  time, then closest to EMA34) at checkpoints 10:45/11:00/11:15/11:30/11:45, and at plan B's 10:45/11:15/11:45; plan B alongside."""
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
exec(compile(open(HERE / "60_filter_ablation.py").read().split("def gen_a")[0], "60head", "exec"))
CLOSES = [f"{h:02d}:{m:02d}" for h in (9, 10, 11, 12) for m in (0, 15, 30, 45) if "09:45" <= f"{h:02d}:{m:02d}" <= "12:15"]


def gen(t):
    p = M5 / f"{t}.csv"
    if not p.exists(): return []
    try: d, d8y, adx, tv = daily_inputs(t)
    except Exception: return []
    atrp = (d.atr14 / d.Close * 100).shift(1); pc = d.Close.shift(1)
    m = read(p)
    if len(m) < 1500: return []
    hc = seeded_hourly(t, m)
    e34 = hc.ewm(span=34, adjust=False).mean().shift(1); e8 = hc.ewm(span=8, adjust=False).mean().shift(1)
    out = []
    for day, g in m.groupby(m.index.normalize()):
        if day < pd.Timestamp("2026-06-10") or tv.get(day, 0) < 1e8 or bool(d.corp_action_day.get(day, False)): continue
        D8, AD, AT, PC = d8y.get(day, np.nan), adx.get(day, np.nan), atrp.get(day, np.nan), pc.get(day, np.nan)
        if np.isnan(D8) or np.isnan(AD) or AD > 25 or np.isnan(AT) or AT < 2.56 or np.isnan(PC) or PC < 100: continue
        for cs in CLOSES:
            cend = day + pd.Timedelta(hours=int(cs[:2]), minutes=int(cs[3:])); cst = cend - pd.Timedelta("15min")
            hs = day + pd.Timedelta("9h15min") + ((cst - day - pd.Timedelta("9h15min")) // pd.Timedelta("60min")) * pd.Timedelta("60min")
            E, E8 = e34.get(hs, np.nan), e8.get(hs, np.nan)
            if np.isnan(E) or not E8 < E: continue
            c = g[(g.index >= cst) & (g.index < cend)]
            if len(c) < 3: continue
            o, hi, cl = c.Open.iloc[0], c.High.max(), c.Close.iloc[-1]
            dist = (E - cl) / E * 100; sp = (hi - cl) / cl * 100
            if not (cl < o and hi >= E and 0 < dist <= 0.5 and sp <= 0.5 and cl < D8): continue
            upto = g[g.index < cend]
            vw = ((upto.High + upto.Low + upto.Close) / 3 * upto.Volume).sum() / max(upto.Volume.sum(), 1)
            if not (upto.High.max() >= A8 * cl + (1 - A8) * D8 and cl < vw): continue
            tgt = cl * 0.99; end = min(cend + pd.Timedelta("5h"), day + pd.Timedelta("15h15min")); b = g[g.index >= cend]
            px, why = None, None
            for ts, r in b.iterrows():
                if ts >= end: px, why = r.Open, "stall"; break
                if r.High >= hi: px, why = hi, "stop"; break
                if r.Low <= tgt: px, why = tgt, "target"; break
            if px is None: px, why = b.Close.iloc[-1], "stall"
            out.append(dict(ticker=t, date=f"{day:%Y-%m-%d}", close_t=cs, entry=cl, stop_pct=sp, dist=dist, ret=(cl - px) / cl * 100, out=why))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p:
        X = pd.DataFrame(sum(p.map(gen, t5, chunksize=10), []))
    X.to_csv(HERE / "option_c_15m.csv", index=False); X["p"] = X.date.str[:7]

    def st(g):
        o = g.out
        return (f"| {len(g)} | {g.stop_pct.median():.2f} | {(o == 'target').mean()*100:.0f} | {(o == 'stall').mean()*100:.0f} | {(o == 'stop').mean()*100:.0f} | "
                f"{g.ret.mean()*1000 - 85:+.0f} | {g.ret.sum()*1000 - 85*len(g):+,.0f} | " + " / ".join(f"{v:+.0f}" for v in (g.groupby('p').ret.mean()*1000 - 85).values) + " |")
    H = "| n | median stop % | target % | stall % | stop % | Rs net | total | Jun / Jul / Aug / Sep |"
    print("## all 15-min triggers by candle close time\n| close " + H + "\n|---|---|---|---|---|---|---|---|---|")
    for cs, g in X.groupby("close_t"): print(f"| {cs} " + st(g))
    print(f"| ALL " + st(X))
    Y = pd.read_csv(HERE / "green_rejection.csv"); Y = Y[(Y.set == "a") & (~Y.green) & (Y.qc >= 100) & Y.alarm.isin([2, 3, 4])].copy()
    Y["out"] = Y.why.replace({"time": "stall", "eod": "stall"}); Y["p"] = Y.date.str[:7]; Y["stop_pct"] = Y["stop"]
    B = Y.sort_values(["date", "alarm", "dist"]).groupby("date").head(1)
    print("\n## one trade a day\n| plan " + H + "\n|---|---|---|---|---|---|---|---|---|")
    print("| plan B today (30m / full-hour candles at 10:45 / 11:15 / 11:45) " + st(B))
    for lab, cps in (("C at 10:45 / 11:15 / 11:45 (same times as plan B)", ["10:45", "11:15", "11:45"]),
                     ("C at 10:45 / 11:00 / 11:15 / 11:30 / 11:45", ["10:45", "11:00", "11:15", "11:30", "11:45"]),
                     ("C at 10:15 (your free slot) / 10:45 / 11:00 / 11:15 / 11:30 / 11:45", ["10:15", "10:45", "11:00", "11:15", "11:30", "11:45"])):
        pk = X[X.close_t.isin(cps)].sort_values(["date", "close_t", "dist"]).groupby("date").head(1)
        print(f"| {lab} " + st(pk))
