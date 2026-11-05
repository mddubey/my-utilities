"""CURRENTLY POKING A LEVEL -- the morning fade finder (asked 2026-11-05: the 09:21 top-20 in-play names move too fast to trade;
the fades actually taken since 2026-10-28 came from "what else is poking a level"). INFO only, not backtested; the user reads the chart.
Universe: today's ORB prep, data_ok, liq >= Rs15L per 5-min bar, price >= Rs100, no ATR filter.
Levels (per stock): D / W / M PP R1 R2, yday high, yday close, daily 8 / 21 / 34, weekly 8 (no 1H EMAs -- 34s are their own setup),
  + the 09:15 high once the 09:15 bar is done.
Runs 09:21-10:00 by default (user, 2026-11-05: the fade window; after 10 the list is noise on a trend day) (1-min bars; the 09:15 high is a level only once its bar is done, and counts only if re-touched after 09:20).
Base (both lists): the last 10 min are at the day high, after a push up of >= 0.3 ATR off the low before it; the stock opened under
  the zone; the zone (levels chained within 0.3%, width <= 0.6%) has a level other than the 09:15 high.
POKING = a level touched in the last 10 min (0.3% under .. a 0.6% wick through), price now 0.4% under .. 0.1% over it, no 1-min close
  more than 0.1% over it. ABOUT TO POKE = the next level 0.3-0.6% above the price, not touched yet.
Info columns: tests (separate 1-min touch episodes of the zone today), ref stop (test high / zone top + 0.05%), room (the first level,
  09:15 close or low under the price), day % / vs Nifty, push and speed (last-10-min range) in ATR. Sorted by higher-TF levels in the
  zone, tests, then slower. The 09:21 ORB scan stays as it is -- this runs alongside it (JYOTICNC 2026-11-04 came from the ORB list).
Usage: python3 poke_list.py [--every 5] [--until 10:00] [--top 20] [--at YYYY-MM-DD --times 09:30,09:35]   (replay: Yahoo 1-min, ~7 days)"""
import sys, time, glob, warnings, datetime as dt
import pandas as pd, numpy as np, yfinance as yf
warnings.filterwarnings("ignore")
R = "/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/"
OUT = R + "intradaygeeks_replica/poke_scans/"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
AT = pd.Timestamp(arg("--at")) if arg("--at") else None
DAY = (AT or pd.Timestamp.now(tz=IST).tz_localize(None)).normalize()
NEAR, WICK, ACC, CHAIN, WIDTH, PUSH = 0.003, 0.006, 0.001, 0.003, 0.006, 0.3


def universe():
    p = pd.read_csv(R + f"intradaygeeks_replica/prep/orb_prep_{DAY:%Y%m%d}.csv")
    return p[(p.data_ok == True) & (p.liq5_L >= 15) & (p.pc >= 100)].set_index("t")


def levels(t):
    dd = pd.read_csv(R + f"data/daily/{t}.csv", parse_dates=["Date"]).set_index("Date"); dd = dd[dd.index < DAY]; y = dd.iloc[-1]
    wk = dd[dd.index < DAY - pd.Timedelta(days=DAY.weekday())]; wk = wk[wk.index >= wk.index[-1] - pd.Timedelta(days=wk.index[-1].weekday())]
    mo = dd[dd.index < DAY.replace(day=1)]; mo = mo[mo.index >= mo.index[-1].replace(day=1)]
    L = {"yday high": y.High, "yday close": y.Close}
    for tf, (h, l, c) in (("D", (y.High, y.Low, y.Close)), ("W", (wk.High.max(), wk.Low.min(), wk.Close.iloc[-1])),
                          ("M", (mo.High.max(), mo.Low.min(), mo.Close.iloc[-1]))):
        pp = (h + l + c) / 3; L.update({f"{tf}-PP": pp, f"{tf}-R1": 2 * pp - l, f"{tf}-R2": pp + (h - l), f"{tf}-S1": 2 * pp - h})
    for s in (8, 21, 34): L[f"daily {s}"] = dd.Close.ewm(span=s, adjust=False).mean().iloc[-1]
    L["weekly 8"] = dd.Close.resample("W-FRI").last().dropna().ewm(span=8, adjust=False).mean().iloc[-1]
    return L, y.Close


def bars(tickers):
    kw = dict(start=f"{DAY:%Y-%m-%d}", end=f"{DAY + pd.Timedelta(days=1):%Y-%m-%d}") if AT else dict(period="1d")
    out, todo = {}, list(tickers)
    for attempt in range(2):   # chunks of 100 + one retry for the misses (Yahoo rate-limits a 450-ticker 1-min pull)
        miss = []
        for i in range(0, len(todo), 100):
            ch = todo[i:i + 100]
            try: d = yf.download(ch, interval="1m", group_by="ticker", progress=False, threads=True, **kw)
            except Exception: miss += ch; continue
            for s_ in ch:
                try:
                    x = d[s_].dropna(how="all")
                    if not len(x): raise ValueError
                    x.index = x.index.tz_convert(IST).tz_localize(None); out[s_] = x
                except Exception: miss.append(s_)
        todo = miss
        if not todo: break
        time.sleep(3)
    return out, todo


def zone_of(lv, top):
    z = [(v, k) for v, k in lv if v == top]   # chain out from the top level: neighbours within 0.3%, total width <= 0.6%
    for v, k in reversed([q for q in lv if q[0] < top]):
        if z[0][0] / v - 1 <= CHAIN and top / v - 1 <= WIDTH: z.insert(0, (v, k))
        else: break
    for v, k in [q for q in lv if q[0] > top]:
        if v / z[-1][0] - 1 <= CHAIN and v / z[0][0] - 1 <= WIDTH: z.append((v, k))
        else: break
    return z


def scan(P, LV, B0, now):
    B = {k: v[v.index + pd.Timedelta("1min") <= now] for k, v in B0.items()}   # completed 1-min bars only
    n = B.get("^NSEI"); nifty = (n.Close.iloc[-1] / n.Open.iloc[0] - 1) * 100 if n is not None and len(n) else np.nan
    t920 = DAY + pd.Timedelta("9h20min"); rows = []
    for t, (L0, yc) in LV.items():
        x = B.get(t + ".NS")
        if x is None or len(x) < 3: continue
        L = {k: v for k, v in L0.items() if not k.endswith("S1")}
        f5 = x[x.index < t920]; aft = x[x.index >= t920]
        if len(aft): L["09:15 high"] = f5.High.max()
        last = x.Close.iloc[-1]; rec = x.iloc[-10:]; rhi = rec.High.max(); dhi = x.High.max()
        atr_px = P.loc[t, "atrp"] / 100 * yc
        push = (dhi - x[x.index <= x.High.idxmax()].Low.min()) / atr_px
        if rhi < dhi * 0.998 or push < PUSH: continue   # the last 10 min are AT the day high, after a push up of >= 0.3 ATR
        lv = sorted((v, k) for k, v in L.items())
        # POKING: touched (within 0.3% under, or a wick <= 0.6% through) and the price at / up to 0.4% under; no 1-min close > +0.1% over
        poke = [(v, k) for v, k in lv if v * (1 - NEAR) <= rhi <= v * (1 + WICK) and v * 0.996 <= last <= v * (1 + ACC)
                and not (rec.Close > v * (1 + ACC)).any() and not (k == "09:15 high" and aft.High.max() < v * (1 - NEAR))]
        near = [(v, k) for v, k in lv if v > rhi * (1 + NEAR) and v / last - 1 <= 0.006]
        if poke: state, top = "POKING", max(poke)[0]
        elif near: state, top = "ABOUT TO POKE", min(near)[0]
        else: continue
        z = zone_of(lv, top); bot, ztop = z[0][0], z[-1][0]
        if all(k == "09:15 high" for v, k in z): continue   # the 09:15 high alone broke 7 of 7 on 2026-11-04
        if x.Open.iloc[0] >= bot * (1 - NEAR): continue      # opened at / above the zone: not a push up into it
        hit = x.High >= bot * (1 - NEAR); tests = int((hit & ~hit.shift(fill_value=False)).sum())   # separate 1-min touch episodes
        thi = max(x[hit].High.max() if hit.any() else rhi, rhi)
        stop = np.ceil(max(thi, ztop) * 1.0005 * 10) / 10
        below = sorted([(v, k) for k, v in L0.items() if v < last * 0.999] + [(q, k) for q, k in ((f5.Close.iloc[-1], "09:15 close"), (f5.Low.min(), "09:15 low"))
                                                                              if len(aft) and q < last * 0.999])
        rv, rk = below[-1] if below else (np.nan, "-")
        rows.append(dict(state=state, ticker=t, now=round(last, 2), zone=" + ".join(f"{k} {v:.2f}" for v, k in z), n_levels=len(z),
                         tests=tests, test_high=round(thi, 2), stop=stop, stop_pct=round((stop / last - 1) * 100, 2),
                         room=f"{rk} {rv:.2f}" if below else "-", room_pct=round((1 - rv / last) * 100, 2) if below else np.nan,
                         day_pct=round((last / yc - 1) * 100, 2), vs_nifty_open=round((last / x.Open.iloc[0] - 1) * 100 - nifty, 2),   # both from today's open (2026-11-05 gap-day fix)
                         push_atr=round(push, 2), speed=round((rhi - rec.Low.min()) / atr_px, 2)))
    return pd.DataFrame(rows), nifty


def main():
    P = universe(); LV = {}
    for t in P.index:
        try: LV[t] = levels(t)
        except Exception: pass
    import os; os.makedirs(OUT, exist_ok=True)
    every = float(arg("--every", 0)); until = dt.time(*map(int, arg("--until", "10:00").split(":"))); prev = set()
    for f in sorted(glob.glob(OUT + f"poke_{DAY:%Y%m%d}_*.csv"))[-1:]:
        try: prev = set(pd.read_csv(f).ticker)
        except Exception: pass
    times = [pd.Timestamp(f"{DAY:%Y-%m-%d} {h}") for h in arg("--times").split(",")] if arg("--times") else [AT]
    B0 = None
    while True:
        if AT and B0 is None: B0, miss = bars([t + ".NS" for t in LV] + ["^NSEI"])
        if AT and not times: break
        now = times.pop(0) if AT else pd.Timestamp.now(tz=IST).tz_localize(None).floor("min")
        if not AT: B0, miss = bars([t + ".NS" for t in LV] + ["^NSEI"])
        x, nifty = scan(P, LV, B0, now)
        if len(x):
            x["new"] = np.where(x.ticker.isin(prev), "", "NEW")
            x["htf"] = x.zone.str.count(r"[DWM]-|yday|daily|weekly")
            x = x.sort_values(["state", "htf", "tests", "speed"], ascending=[False, False, False, True])
            if not AT: x.to_csv(OUT + f"poke_{DAY:%Y%m%d}_{now:%H%M}.csv", index=False)
            prev = set(x.ticker)
        np_ = int((x.state == "POKING").sum()) if len(x) else 0
        print(f"POKE {now:%H:%M} | universe {len(LV)} | Nifty {nifty:+.2f}% from open | poking {np_}, about to poke {len(x) - np_}, "
              f"new {int((x.new == 'NEW').sum()) if len(x) else 0} | no data {len(miss)}", flush=True)
        if len(x):
            with pd.option_context("display.width", 400, "display.max_colwidth", 90, "display.max_rows", 200):
                for st, k in (("POKING", int(arg("--top", 15))), ("ABOUT TO POKE", 10)):
                    print(x[x.state == st].head(k).to_string(index=False), flush=True)
        if AT: continue
        if not every or dt.datetime.now(IST).time() >= until: break
        time.sleep(every * 60 - time.time() % (every * 60) + 15)   # on the 5-min marks + 15 s for Yahoo to publish


if __name__ == "__main__":
    main()
