import sys, time, datetime as dt, pandas as pd, yfinance as yf, warnings; warnings.filterwarnings("ignore")
# Event-only poke watcher over the liquid ORB-prep universe (Yahoo 5-min, ~2-min loop). Prints a line when a stock
# (a) reaches a level at its day high (POKING), (b) turns >= 0.3% off a high made at a level in the last 15 min (TURNING),
# (c) breaks >= 0.15% above a poked level (THROUGH). Always reports the FOCUS names on each state change.
# Usage: python3 watch_pokes.py YYYYMMDD [FOCUS,TICKERS]
R = "/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
day = sys.argv[1]; focus = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else set()
p = pd.read_csv(R + f"intradaygeeks_replica/prep/orb_prep_{day}.csv"); p = p[p.data_ok == True]
p = p[(p.liq5_L >= 40) | p.t.isin(focus)].set_index("t")
lv = {}
for t in p.index:
    try:
        y = pd.read_csv(R + f"data/daily/{t}.csv", index_col=0).iloc[-1]; P = (y.High + y.Low + y.Close) / 3
        L = {"yday high": y.High, "yday close": y.Close, "R1": 2*P - y.Low, "R2": P + y.High - y.Low, "daily 8": p.loc[t, "e8y"]}
        try:
            h = pd.read_csv(R + f"data/intraday_60m/{t}.csv", index_col=0); c = [x for x in h.columns if x.lower() == "close"][0]
            L["1H34"] = h[c].ewm(span=34, adjust=False).mean().iloc[-1]
        except Exception: pass
        lv[t] = L
    except Exception: pass
state = {}
print(f"watching {len(lv)} stocks (liq >= Rs40L/5m + focus {sorted(focus)}) from {dt.datetime.now(IST):%H:%M}", flush=True)
while dt.datetime.now(IST).time() < dt.time(15, 20):
    try: x = yf.download([t + ".NS" for t in lv], period="1d", interval="5m", group_by="ticker", progress=False, threads=True)
    except Exception as e: print(f"fetch error {e}", flush=True); time.sleep(60); continue
    now_t = dt.datetime.now(IST)
    for t, L in lv.items():
        try: b = x[t + ".NS"].dropna()
        except Exception: continue
        if b.empty: continue
        b.index = b.index.tz_convert(IST)
        L2 = dict(L); L2["09:15 high"] = b.High.iloc[0]
        hi, now = b.High.max(), b.Close.iloc[-1]; hh = b.High.idxmax()
        lvl = [(k, v) for k, v in L2.items() if hi >= v * 0.997 and hi <= v * 1.0015 and not (k == "09:15 high" and hh == b.index[0])]
        thru = [(k, v) for k, v in L2.items() if hi > v * 1.0015 and hi <= v * 1.006 and now > v * 1.0015]
        off = (hi - now) / hi * 100; chg = (now / L["yday close"] - 1) * 100
        tag = " | ".join(f"{k} {v:.2f}" for k, v in lvl)
        if lvl and off < 0.15: s = "POKING"
        elif lvl and off >= 0.3 and (now_t - hh).total_seconds() <= 20 * 60: s = "TURNING"
        elif thru and off < 0.15: s = "THROUGH"; tag = " | ".join(f"{k} {v:.2f}" for k, v in thru)
        else: s = None
        key = (s, round(hi, 2)) if s in ("TURNING",) else ((s, tag) if s else None)  # POKING/THROUGH: once per level, not per new tick high
        if s and state.get(t) != key and (s != "THROUGH" or t in focus) and (s != "TURNING" or state.get(t, (None,))[0] == "POKING" or t in focus):
            print(f"{now_t:%H:%M} {s:8} {t}{' *' if t in focus else ''} now {now:.2f} ({chg:+.2f}%) high {hi:.2f}@{hh:%H:%M} off {off:.2f}% | {tag} | liq {p.loc[t,'liq5_L']:.0f}L", flush=True)
        if s: state[t] = key
        elif t in focus and state.get(t) not in (None, "idle"):
            state[t] = "idle"; print(f"{now_t:%H:%M} idle     {t} * now {now:.2f} ({chg:+.2f}%) high {hi:.2f}@{hh:%H:%M} off {off:.2f}%", flush=True)
    time.sleep(110)
print("watch ended 15:20", flush=True)
