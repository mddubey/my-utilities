"""STACKED SUPPORT + PIN at the 1H EMA34 (user, 2026-10-15, from MOTILALOFS 2026-10-13 11:15: 'a perfect support -- the daily 8 just
below the 34 and a pin with a lower wick on the 34; both together make it a better combo'). Spec declared in chat before running:
  Universe (v1 / 218): liquid (prev-day median 5-min turnover >= Rs15 lakh; 1H set: median hourly turnover / 12 x 0.72), close >= Rs100,
    daily ATR14 >= 2%.
  LONG: (1) daily EMA8 > EMA34 (yesterday) and 1H EMA8 > EMA34 (as of the last completed hour)
        (2) came from above: the day's official open > the 1H EMA34 at the open
        (3) stacked: yesterday's daily EMA8 (= today's touch price) 0..0.5% UNDER the 1H EMA34 (0.3 / 0.75% shown too)
        (4) pin candle (half-hour 10:15..13:15 on the 30m set, hourly 10:15..13:15 on the 1H set): low <= the 34 and >= daily 8 - 0.1%,
            lower wick >= 1/3 of the range, close in the top half. First such candle per stock-day.
        entry = candle close; stop = min(candle low, daily 8) - 0.1%; exits: 1% target / 2R / hold, all out at 15:15, stop first on a tie.
  SHORT = mirror (downtrends, opened below, daily 8 0..0.5% ABOVE the 34, upper-wick pin under the daily 8 + 0.1%, close bottom half).
  Report: Rs per Rs1 lakh net of Rs85, stopped / target %, per set; 1H set by year, Nifty vs 200d, bear phase 2026-03..09; Nifty above /
  below its own day open at entry; trades per day. Hand check: MOTILALOFS 2026-10-13 (30m) must be caught; 3 random setups printed."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from backtest import load
from orb_common import read5_official
from data.paths import DAILY_DIR, INTRADAY_5M_DIR, INDEX_INTRADAY_DIR
COST = 0.085; STACKS = (0.3, 0.5, 0.75); TOL = 0.001


def h1(t):
    p = HERE / "h1_cache" / f"{t}.csv"
    if not p.exists(): return None
    h = pd.read_csv(p, index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return h[~h.index.duplicated()].sort_index()


def exits(after, e, stop, side, step_end):
    """after: bars after entry (same day, ending by 15:15). Returns dict of exit -> (ret %, why)."""
    out = {}
    for nm, tg in (("t1", e * (1 + 0.01 * side)), ("r2", e + 2 * (e - stop)), ("hold", None)):
        res = None
        for _, b in after.iterrows():
            if (b.Low <= stop) if side == 1 else (b.High >= stop): res = ((stop - e) / e * 100 * side, "stop"); break
            if tg is not None and ((b.High >= tg) if side == 1 else (b.Low <= tg)): res = ((tg - e) / e * 100 * side, "target"); break
        if res is None: res = (((after.Close.iloc[-1] - e) / e * 100 * side) if len(after) else 0.0, "time")
        out[nm] = res
    return out


def run(t):
    try:
        d = load(t); h = h1(t)
    except Exception: return []
    if h is None or len(h) < 100: return []
    try: m5 = read5_official(t)
    except Exception: m5 = None
    dO = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).Open
    d8 = d.Close.ewm(span=8, adjust=False).mean(); d34 = d.Close.ewm(span=34, adjust=False).mean()
    e34 = h.Close.ewm(span=34, adjust=False).mean().shift(1); e8 = h.Close.ewm(span=8, adjust=False).mean().shift(1)
    hv = (h.Volume * h.Close); hday = h.index.normalize()
    out = []
    for setname in ("a", "b"):
        if setname == "a":
            if m5 is None: continue
            bars = m5; days = sorted(set(m5.index.normalize())); step = pd.Timedelta("5min"); clen = pd.Timedelta("30min")
            starts = ["10:15", "10:45", "11:15", "11:45", "12:15", "12:45", "13:15"]
        else:
            bars = h[h.index >= "2024-01-01"]; days = sorted(set(bars.index.normalize())); step = pd.Timedelta("60min"); clen = step
            starts = ["10:15", "11:15", "12:15", "13:15"]
        bday = bars.index.normalize()
        for i in range(1, len(days)):
            D, P = days[i], days[i - 1]
            dd = d[d.index < D]
            if len(dd) < 60: continue
            pc = dd.Close.iloc[-1]; atrp = dd.atr14.iloc[-1] / pc * 100
            if pc < 100 or atrp < 2: continue
            if setname == "a":
                pv = m5[(bday == P) & (m5.Volume > 0)]; liq = (pv.Volume * pv.Close).median() if len(pv) else 0
            else:
                pv = hv[(hday == P) & (h.Volume > 0)]; liq = pv.median() / 12 * 0.72 if len(pv) else 0
            if liq < 15e5: continue
            D8y, D34y = d8[dd.index[-1]], d34[dd.index[-1]]
            g = bars[bday == D]
            if len(g) < (60 if setname == "a" else 6): continue
            k0 = D + pd.Timedelta("9h15min")
            if k0 not in e34.index or np.isnan(e34[k0]): continue
            oo = dO.get(D, np.nan)
            if not oo == oo: continue
            done = set()
            for s in starts:
                ss = D + pd.Timedelta(hours=int(s[:2]), minutes=int(s[3:])); hk = ss if s.endswith("15") else ss - pd.Timedelta("30min")
                if hk not in e34.index: continue
                line, l8 = e34[hk], e8[hk]
                c = g[(g.index >= ss) & (g.index < ss + clen)]
                if len(c) < (6 if setname == "a" else 1): continue
                o, hi, lo, cl = c.Open.iloc[0], c.High.max(), c.Low.min(), c.Close.iloc[-1]
                rg = hi - lo
                if rg <= 0: continue
                cp = (cl - lo) / rg
                for side in (1, -1):
                    if side in done: continue
                    if side == 1:
                        ok = D8y > D34y and l8 > line and oo > e34[k0]
                        stack = (line - D8y) / line * 100
                        pin = lo <= line and lo >= D8y * (1 - TOL) and (min(o, cl) - lo) >= rg / 3 and cp >= 0.5
                        stop = min(lo, D8y) * (1 - TOL)
                    else:
                        ok = D8y < D34y and l8 < line and oo < e34[k0]
                        stack = (D8y - line) / line * 100
                        pin = hi >= line and hi <= D8y * (1 + TOL) and (hi - max(o, cl)) >= rg / 3 and cp <= 0.5
                        stop = max(hi, D8y) * (1 + TOL)
                    if not (ok and pin and 0 <= stack <= max(STACKS)): continue
                    done.add(side)
                    after = g[(g.index >= ss + clen) & (g.index + step <= D + pd.Timedelta("15h15min"))]
                    ex = exits(after, cl, stop, side, None)
                    out.append(dict(set=setname, ticker=t, date=D.strftime("%Y-%m-%d"), start=s, side="LONG" if side == 1 else "SHORT",
                                    entry=round(cl, 2), stop=round(stop, 2), risk=abs(cl - stop) / cl * 100, stack=stack, line=round(line, 2),
                                    d8=round(D8y, 2), low=lo, high=hi, t_entry=ss + clen,
                                    **{f"{k}_ret": v[0] for k, v in ex.items()}, **{f"{k}_why": v[1] for k, v in ex.items()}))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    uni = [f.stem for f in (HERE / "h1_cache").glob("*.csv") if not f.stem.startswith("_")]
    with Pool(6) as p: X = pd.DataFrame([r for rr in p.map(run, uni, chunksize=10) for r in rr])
    N1 = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_1h.csv", index_col=0); N1.index = pd.to_datetime(N1.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    N1 = N1[~N1.index.duplicated()].sort_index()
    nopen = N1.Open.groupby(N1.index.normalize()).first()
    def nup(T):
        s = N1.Close[(N1.index + pd.Timedelta("60min") <= T) & (N1.index.normalize() == T.normalize())]
        o = nopen.get(T.normalize(), np.nan)
        return np.nan if not len(s) or not o == o else s.iloc[-1] > o
    X["nifty_up"] = [nup(T) for T in X.t_entry]
    nd = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).Close.sort_index()
    ab = (nd > nd.rolling(200).mean()).shift(1); X["n200"] = X.date.map(lambda s: ab.get(pd.Timestamp(s), np.nan))
    X.drop(columns=["t_entry"]).to_csv(HERE / "stacked_support_pin.csv", index=False)

    def row(lab, x):
        if not len(x): return f"| {lab} | 0 |" + " |" * 7
        cells = [f"{len(x)}", f"{(x.t1_why == 'stop').mean()*100:.0f}%", f"{(x.t1_why == 'target').mean()*100:.0f}%"]
        for k in ("t1", "r2", "hold"): cells.append(f"{(x[f'{k}_ret'].mean() - COST)*1000:+.0f}")
        cells.append(f"{x.risk.median():.2f}%"); cells.append(f"{x.groupby('date').size().mean():.1f}")
        return f"| {lab} | " + " | ".join(cells) + " |"
    HDR = "| group | trades | stopped (1%) | 1% target | net 1% | net 2R | net hold | median risk | per day |\n|---|---|---|---|---|---|---|---|---|"
    for s, nm in (("a", "30m set (half-hour pins, 5-min exits), 2026-06..10"), ("b", "3-yr 1H set (hourly pins, hourly exits), 2024-01..2026-10")):
        for side in ("LONG", "SHORT"):
            x0 = X[(X.set == s) & (X.side == side)]
            print(f"\n### {nm} -- {side}  (net Rs per Rs1 lakh)\n{HDR}")
            for st in STACKS:
                x = x0[x0["stack"] <= st]; print(row(f"stack 0-{st}%" + (" (MAIN)" if st == 0.5 else ""), x))
            x = x0[x0["stack"] <= 0.5]
            print(row("MAIN, Nifty above its open at entry", x[x.nifty_up == True])); print(row("MAIN, Nifty below its open", x[x.nifty_up == False]))
            print(row("MAIN, Nifty above 200d", x[x.n200 == True])); print(row("MAIN, Nifty below 200d", x[x.n200 == False]))
            if s == "b":
                for yr, g in x.groupby(x.date.str[:4]): print(row(f"MAIN {yr}", g))
                print(row("MAIN bear phase 2026-03..09", x[(x.date >= "2026-03") & (x.date < "2026-10")]))
    print("\nHAND CHECK MOTILALOFS 2026-10-13:")
    hc = X[(X.ticker == "MOTILALOFS") & (X.date == "2026-10-13")]
    print(hc.drop(columns=["t_entry"]).round(3).to_string(index=False) if len(hc) else "  NOT CAUGHT")
    print("\n3 random MAIN setups (30m):")
    print(X[(X.set == "a") & (X["stack"] <= 0.5)].sample(3, random_state=11).drop(columns=["t_entry"]).round(3).to_string(index=False))
