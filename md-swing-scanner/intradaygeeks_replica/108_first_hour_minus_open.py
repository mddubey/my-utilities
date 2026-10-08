"""Option A, quick look (user, 2026-10-08): an artificial first candle that skips the 09:15-09:30 opening chaos (bars 3-6x
midday size). NON-STANDARD candle (nobody else draws a 45-min 09:30-10:15 bar) -- user wants a quick look before the
legit 15-min trigger (option C). Spec fixed before running:
  Candle 09:30-10:15 (5-min bars 09:30..10:10): red (close < 09:30 open), high >= 1H EMA34 (as of yesterday's last hour, the
  scan's convention for the 09:15 hour), close < EMA34 within 0.5%, stop = candle high <= 0.5% (2:1), 1H EMA8 < EMA34,
  close < yesterday's daily 8-EMA, day high (incl. 09:15-09:30) >= live daily 8-EMA, close < session VWAP to 10:15,
  daily ADX <= 25, ATR >= 2.56%, tv20 >= Rs10cr, price >= Rs100 (yesterday's close), no corporate-action day.
  Entry 10:15 close; exit 1% target / stop / 5h / 15:15 (stop first if both in one bar). Opening spike split: 09:15-09:30
  high above vs below the candle high. 30m set only (Jun 10 - Sep 30 2026, 5-min data, EMAs seeded from h1_cache).
  Plan: A at 10:15 else today's plan (10:45 / 11:15 / 11:45 from green_rejection.csv red setups, candle-close entry)."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
exec(compile(open(HERE / "60_filter_ablation.py").read().split("def gen_a")[0], "60head", "exec"))


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
        hs = day + pd.Timedelta("9h15min"); E, E8 = e34.get(hs, np.nan), e8.get(hs, np.nan)
        if np.isnan(E) or not E8 < E: continue
        a = g[(g.index >= day + pd.Timedelta("9h30min")) & (g.index < day + pd.Timedelta("10h15min"))]
        op = g[(g.index >= hs) & (g.index < day + pd.Timedelta("9h30min"))]
        if len(a) < 8 or len(op) < 2: continue
        o, hi, cl = a.Open.iloc[0], a.High.max(), a.Close.iloc[-1]
        upto = g[g.index < day + pd.Timedelta("10h15min")]
        vw = ((upto.High + upto.Low + upto.Close) / 3 * upto.Volume).sum() / max(upto.Volume.sum(), 1)
        live = A8 * cl + (1 - A8) * D8; dist = (E - cl) / E * 100; sp = (hi - cl) / cl * 100
        if not (cl < o and hi >= E and 0 < dist <= 0.5 and sp <= 0.5 and cl < D8 and upto.High.max() >= live and cl < vw): continue
        tgt = cl * 0.99; b = g[g.index >= day + pd.Timedelta("10h15min")]; end = day + pd.Timedelta("15h15min")
        px, why = None, None
        for ts, r in b.iterrows():
            if ts >= end or ts >= day + pd.Timedelta("15h15min"): px, why = r.Open, "stall"; break
            if r.High >= hi: px, why = hi, "stop"; break
            if r.Low <= tgt: px, why = tgt, "target"; break
        if px is None: px, why = b.Close.iloc[-1], "stall"
        out.append(dict(ticker=t, date=f"{day:%Y-%m-%d}", entry=cl, stop=hi, stop_pct=sp, dist=dist, ret=(cl - px) / cl * 100, out=why,
                        open_spike_above=bool(op.High.max() > hi)))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p:
        X = pd.DataFrame(sum(p.map(gen, t5, chunksize=10), []))
    X.to_csv(HERE / "first_hour_minus_open.csv", index=False); X["p"] = X.date.str[:7]

    def st(g):
        o = g.out
        return f"| {len(g)} | {(o == 'target').mean()*100:.0f} | {(o == 'stall').mean()*100:.0f} | {(o == 'stop').mean()*100:.0f} | {g.ret.mean()*1000 - 85:+.0f} | {g.ret.sum()*1000 - 85*len(g):+,.0f} | " + " / ".join(f"{v:+.0f}" for v in (g.groupby('p').ret.mean()*1000 - 85).values) + " |"
    print("| group | n | target % | stall % | stop % | Rs net | total | Jun / Jul / Aug / Sep |\n|---|---|---|---|---|---|---|---|")
    print("| A setups (09:30-10:15 candle), all " + st(X))
    print("| ... opening spike went ABOVE the A high " + st(X[X.open_spike_above]))
    print("| ... opening spike stayed below the A high " + st(X[~X.open_spike_above]))
    Y = pd.read_csv(HERE / "green_rejection.csv"); Y = Y[(Y.set == "a") & (~Y.green) & (Y.qc >= 100) & Y.alarm.isin([2, 3, 4])].copy()
    Y["out"] = Y.why.replace({"time": "stall", "eod": "stall"}); Y["p"] = Y.date.str[:7]
    B = Y.sort_values(["date", "alarm", "dist"]).groupby("date").head(1)
    Apk = X.sort_values(["date", "dist"]).groupby("date").head(1)
    comb = pd.concat([Apk, B[~B.date.isin(Apk.date)]])
    print("| plan B today (10:45 / 11:15 / 11:45) " + st(B))
    print("| A pick on its own (one a day) " + st(Apk))
    print("| A at 10:15, else plan B " + st(comb))
