"""Half-hour rejection that CLOSES ABOVE the 1H EMA34 (user, 2026-10-12, from live INOXINDIA / TIMEX: the 10:15-10:45
candle wicked into resistance, closed green and ABOVE the line, then dropped ~1% by 11:10 -- neither plan B (red, close
below) nor v1 (full hour, stop too wide by 11:15) caught it).
Spec fixed before running:
  Universe: liquid (prior-day median 5-min turnover >= Rs15 lakh; 1H set: prior-day median hourly turnover /12 x 0.72),
  price >= Rs100, daily ATR14 >= 2%, 20-day traded value >= Rs10 cr (all yesterday's values). Daily trend (EMA8 > EMA34,
  the v1 universe both trades came from) is recorded and split, not required.
  Trigger: the 10:15-10:45 30-min candle (30m set) / the 10:15-11:15 hourly candle (1H set) with HIGH >= the 1H EMA34
  as of the 09:15 hour's close AND LOW <= it (the candle crosses the line). v1 of this script lacked the LOW condition and
  counted candles sitting wholly above the line (14k in 4 months) -- not a touch; fixed before reading any result.
  Groups (by the candle's close C, open O, range position pos = (C-L)/(H-L)):
    RED_BELOW   C < EMA34 and C < O  (the current red rule's core)
    GREEN_BELOW C < EMA34 and C >= O (script 96's green)
    ABOVE_WICK  C >= EMA34 and pos <= 0.75 (upper wick >= 1/4 of the range -- the user's shape; INOXINDIA 0.65, TIMEX 0.54)
      of which pos <= 0.5 shown separately
    ABOVE_NOWICK C >= EMA34 and pos > 0.75 (closed near the high: no rejection; contrast)
  Trade: short at the candle close, stop = candle high, exits (a) 1% target, else out at 15:15; (b) hold to 15:15,
  stop only. Stop first if stop and target share a bar. Net = ret% x 1000 - 85 (Rs per Rs1 lakh); R = move / stop.
  Report per group: n, target / stop %, net, R, w/o the top-10 trades, by month (30m) / year (1H), 2:1 split (stop <= 0.5%),
  daily up/down, Nifty above/below 200d; label shuffle ABOVE_WICK vs RED_BELOW (5,000).
  Pass = ABOVE_WICK net > 0 in BOTH sets and both exits, not carried by the top 10, and not worse than RED_BELOW.
Usage: python3 208_half_candle_close_above.py"""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
from multiprocessing import Pool
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from data.paths import DAILY_DIR, INTRADAY_5M_DIR


def daily_ctx(t):
    d = load(t)
    c = d.Close
    x = pd.DataFrame({"pc": c, "atrp": d.atr14 / c * 100, "tv": d.traded_value_sma20,
                      "up": c.ewm(span=8, adjust=False).mean() > c.ewm(span=34, adjust=False).mean()}).shift(1)
    return x


def h1(t):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0)
    h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return h[~h.index.duplicated()]


def group(o, hi, lo, c, e):
    pos = (c - lo) / (hi - lo) if hi > lo else 1.0
    if c < e: return ("RED_BELOW" if c < o else "GREEN_BELOW"), pos
    return ("ABOVE_WICK" if pos <= 0.75 else "ABOVE_NOWICK"), pos


def walk(bars, c, hi):
    """bars: later bars (High, Low, Close) up to the exit bar inclusive. Returns exit price for target and hold."""
    tgt = c * 0.99; xt = xh = None
    for b in bars.itertuples():
        if xt is None:
            if b.High >= hi: xt = hi
            elif b.Low <= tgt: xt = tgt
        if xh is None and b.High >= hi: xh = hi
        if xt is not None and xh is not None: break
    last = bars.Close.iloc[-1]
    return (last if xt is None else xt), (last if xh is None else xh), xt == tgt


def gen(t):
    out = []
    try:
        dc = daily_ctx(t); H = h1(t)
    except Exception: return out
    if len(H) < 60: return out
    H["e34"] = H.Close.ewm(span=34, adjust=False).mean()
    H["day"] = H.index.normalize(); H["hm"] = H.index.strftime("%H:%M")
    H["nb"] = np.arange(len(H))
    e915 = H[(H.hm == "09:15") & (H.nb >= 60)].set_index("day").e34   # >= 60 hourly bars before (EMA warm-up)
    # 1H-set liquidity: prior day's median hourly turnover (non-zero bars) / 12 x 0.72
    hv = (H.Volume * H.Close)[H.Volume > 0].groupby(H.day[H.Volume > 0]).median() / 12 * 0.72 / 1e5
    hliq = hv.shift(1)
    # ---- 1H set: the 10:15 hourly candle, entry 11:15, exits through the 14:15 bar (= 15:15)
    for day, g in H[H.day >= "2024-01-01"].groupby("day"):
        if day not in dc.index or day not in e915.index: continue
        r = dc.loc[day]
        if not (r.pc >= 100 and r.atrp >= 2 and r.tv >= 1e8 and hliq.get(day, 0) >= 15): continue
        cb = g[g.hm == "10:15"]
        if not len(cb): continue
        cb = cb.iloc[0]; e = e915[day]
        if not (cb.High >= e and cb.Low <= e) or cb.High <= cb.Close: continue
        later = g[(g.hm > "10:15") & (g.hm <= "14:15")]
        if len(later) < 3: continue
        grp, pos = group(cb.Open, cb.High, cb.Low, cb.Close, e)
        xt, xh, hit = walk(later, cb.Close, cb.High)
        out.append(dict(set="1H", t=t, day=day, grp=grp, pos=pos, c=cb.Close, hi=cb.High, e=e, stop=(cb.High / cb.Close - 1) * 100,
                        xt=xt, xh=xh, hit=hit, up=bool(r.up), atrp=r.atrp))
    # ---- 30m set: the 10:15-10:45 candle from 5-min bars, entry 10:45, exits through the 15:10 bar
    p = INTRADAY_5M_DIR / f"{t}.csv"
    if not p.exists(): return out
    m = pd.read_csv(p, index_col=0, parse_dates=True)
    m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None); m = m[~m.index.duplicated()]
    m["day"] = m.index.normalize(); m["hm"] = m.index.strftime("%H:%M")
    lq = (m.Volume * m.Close)[m.Volume > 0].groupby(m.day[m.Volume > 0]).median() / 1e5
    days = sorted(m.day.unique())
    for i, day in enumerate(days[1:], 1):
        if day not in dc.index or day not in e915.index: continue
        r = dc.loc[day]
        if not (r.pc >= 100 and r.atrp >= 2 and r.tv >= 1e8 and lq.get(days[i - 1], 0) >= 15): continue
        g = m[m.day == day]
        cb = g[(g.hm >= "10:15") & (g.hm < "10:45")]
        if len(cb) < 6: continue
        o, hi, lo, c = cb.Open.iloc[0], cb.High.max(), cb.Low.min(), cb.Close.iloc[-1]; e = e915[day]
        if not (hi >= e and lo <= e) or hi <= c: continue
        later = g[(g.hm >= "10:45") & (g.hm <= "15:10")]
        if len(later) < 40: continue
        grp, pos = group(o, hi, lo, c, e)
        xt, xh, hit = walk(later, c, hi)
        out.append(dict(set="30m", t=t, day=day, grp=grp, pos=pos, c=c, hi=hi, e=e, stop=(hi / c - 1) * 100,
                        xt=xt, xh=xh, hit=hit, up=bool(r.up), atrp=r.atrp))
    return out


def stats(x, col):
    ret = (x.c - x[col]) / x.c * 100; net = ret * 1000 - 85; R = (x.c - x[col]) / (x.hi - x.c)
    top = net.sort_values(ascending=False)
    stp = (x[col] == x.hi).mean() * 100
    return dict(n=len(x), stop_pct=round(stp, 0), net=round(net.mean(), 0), R=round(R.mean(), 2),
                wo_top10=round(top.iloc[10:].mean(), 0) if len(x) > 20 else np.nan, med_stop=round(x.stop.median(), 2))


def table(S, by=None, col="xt"):
    rows = []
    groups = ["RED_BELOW", "GREEN_BELOW", "ABOVE_WICK", "ABOVE_WICK pos<=0.5", "ABOVE_NOWICK", "ALL"]
    for gname in groups:
        x = S[S.grp == gname] if gname in S.grp.unique() else (S[(S.grp == "ABOVE_WICK") & (S.pos <= 0.5)] if "pos" in gname else S)
        if by is None:
            rows.append(dict(group=gname, **stats(x, col)) | (dict(target_pct=round(x.hit.mean() * 100, 0)) if col == "xt" else {}))
        else:
            d = {"group": gname}
            for k, y in x.groupby(by): d[str(k)] = f"{stats(y, col)['net']:+.0f} ({len(y)})"
            rows.append(d)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    uni = [p.stem for p in (HERE / "h1_cache").glob("*.csv")]
    with Pool(6) as pool:
        res = []
        for k, r in enumerate(pool.imap_unordered(gen, uni, chunksize=10), 1):
            res.extend(r)
            if k % 200 == 0: print(f"  {k}/{len(uni)} tickers, {len(res)} setups", flush=True)
    A = pd.DataFrame(res); A.to_csv(HERE / "half_candle_above.csv", index=False)
    N = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index().Close
    n200 = (N > N.rolling(200).mean()).shift(1)
    A["nifty"] = A.day.map(lambda d: "N>200d" if n200.get(d, False) else "N<200d")
    A["month"] = pd.to_datetime(A.day).dt.strftime("%Y-%m"); A["year"] = pd.to_datetime(A.day).dt.year
    A["rr"] = np.where(A.stop <= 0.5, "stop<=0.5", "stop>0.5"); A["trend"] = np.where(A.up, "daily up", "daily down")
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print("\nHAND CHECK (2026-10-12):"); print(A[(A.day == "2026-10-12") & A.t.isin(["INOXINDIA", "TIMEX"])].to_string(index=False))
    for s in ("30m", "1H"):
        S = A[A.set == s].copy()
        print(f"\n===== {s} set: {S.day.min():%Y-%m-%d} .. {S.day.max():%Y-%m-%d} =====")
        for col, lab in (("xt", "1% TARGET"), ("xh", "HOLD to 15:15")):
            print(f"\n-- {lab}"); print(table(S, None, col).to_string(index=False))
        for by in (("month" if s == "30m" else "year"), "rr", "trend", "nifty"):
            print(f"\n-- 1% target, net Rs @1L (n) by {by}"); print(table(S, by, "xt").to_string(index=False))
        a = S[S.grp.isin(["ABOVE_WICK", "RED_BELOW"])]; net = ((a.c - a.xt) / a.c * 100 * 1000 - 85).values
        lab = (a.grp == "ABOVE_WICK").values; obs = net[lab].mean() - net[~lab].mean(); rng = np.random.default_rng(0)
        sh = [net[p].mean() - net[~p].mean() for p in (rng.permutation(lab) for _ in range(5000))]
        print(f"\nshuffle ABOVE_WICK - RED_BELOW (1% target): {obs:+.0f}, p(two-sided) = {np.mean(np.abs(sh) >= abs(obs)):.3f}")
