import sys, os, time, glob, warnings, datetime as dt
import pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")
# Rejection-retest watcher (1-min, Yahoo). Keeps a list of pivots (daily / weekly / monthly PP, R1, R2) that were poked
# 09:20-09:59 and REJECTED (a 1-min close >= 0.4% back under within 10 min), then alerts when price comes back within 0.3%
# of the level (APPROACH, before the touch: place the limit then) and when it touches it (RETEST) by 10:30, each with the
# second push's volume vs the poke minute: WEAK (<= 0.5x, the slice that held up in the
# 2026-11-01 test, ratio rounded to 2 dp as in the test) or STRONG. Alerts only for R1/R2 (PP retests did not work in the
# test); REJECTED / BROKE lines only with --verbose. Completed 1-min bars only.
# Usage: python3 watch_retest.py YYYYMMDD [FOCUS,TICKERS] [--verbose]   (live; universe = ORB prep liq >= Rs40L/5m + focus)
#        python3 watch_retest.py YYYYMMDD --replay DIR [--verbose]        (replay a saved day from DIR/<TICKER>.csv 1-min files)
R = "/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
day = sys.argv[1]; dday = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]}")
replay = "--replay" in sys.argv
verbose = "--verbose" in sys.argv
args = [a for a in sys.argv[2:] if not a.startswith("--")]
focus = set() if replay or not args else set(args[0].split(","))


def levels(t):
    dd = pd.read_csv(R + f"data/daily/{t}.csv", parse_dates=["Date"]).set_index("Date"); dd = dd[dd.index < dday]
    if len(dd) < 30: return {}
    y = dd.iloc[-1]
    wk = dd[dd.index < dday - pd.Timedelta(days=dday.weekday())]; wk = wk[wk.index >= wk.index[-1] - pd.Timedelta(days=wk.index[-1].weekday())]
    mo = dd[dd.index < dday.replace(day=1)]; mo = mo[mo.index >= mo.index[-1].replace(day=1)]
    out = {}
    for tf, (h, l, c) in (("D", (y.High, y.Low, y.Close)), ("W", (wk.High.max(), wk.Low.min(), wk.Close.iloc[-1])),
                          ("M", (mo.High.max(), mo.Low.min(), mo.Close.iloc[-1]))):
        p = (h + l + c) / 3
        for k, v in (("PP", p), ("R1", 2 * p - l), ("R2", p + (h - l))): out[f"{tf}-{k}"] = v
    return out


if replay:
    src = sys.argv[sys.argv.index("--replay") + 1]
    TICK = sorted(os.path.basename(f)[:-4] for f in glob.glob(os.path.join(src, "*.csv")))
else:
    p = pd.read_csv(R + f"intradaygeeks_replica/prep/orb_prep_{day}.csv"); p = p[p.data_ok == True]
    TICK = sorted(set(p[p.liq5_L >= 40].t) | focus)
LV = {}
for t in TICK:
    try: LV[t] = levels(t)
    except Exception: pass
st = {}   # (t, level) -> dict(state, ...)
k_ = lambda v: f"{v / 1e3:.1f}k" if v < 1e6 else f"{v / 1e6:.2f}M"


def step(t, b, now):
    """b = completed 1-min bars of today (IST naive index) up to 'now'."""
    s = b[b.index.strftime("%H:%M") >= "09:20"]
    if not len(s): return
    p0 = s.Open.iloc[0]; last = s.index[-1]; hm = last.strftime("%H:%M")
    poked_min = {v["poke"] for (tt, _), v in st.items() if tt == t and "poke" in v}
    for nm, L in sorted(LV.get(t, {}).items(), key=lambda z: z[1]):
        key = (t, nm); v = st.get(key); alert = nm.endswith(("R1", "R2"))
        if v is None:
            if L <= p0: st[key] = {"state": "below_open"}; continue
            w = s[(s.index.strftime("%H:%M") <= "09:59") & (s.High > L)]
            if not len(w):
                if hm > "09:59": st[key] = {"state": "never"}
                continue
            ct = w.index[0]
            if ct in poked_min: st[key] = {"state": "dup"}; continue   # same poke minute as a lower pivot
            v = st[key] = {"state": "poked", "poke": ct, "pv": s.Volume.loc[ct], "L": L}; poked_min.add(ct)
        if v["state"] == "poked":
            win = s[(s.index >= v["poke"]) & (s.index <= v["poke"] + pd.Timedelta("10min"))]
            rj = win[win.Close <= L * 0.996]
            if len(rj):
                ph = s[(s.index >= v["poke"]) & (s.index <= rj.index[0])].High.max()
                v.update(state="rejected", ph=ph, rj=rj.index[0])
                if verbose: print(f"{rj.index[0]:%H:%M} REJECTED {t} {nm} {L:.2f} | poke {v['poke']:%H:%M} vol {k_(v['pv'])}, push high {ph:.2f}, "
                      f"close {rj.Close.iloc[0]:.2f} ({(rj.Close.iloc[0] / L - 1) * 100:+.2f}%) -> on the retest list till 10:30", flush=True)
            elif last > v["poke"] + pd.Timedelta("10min"): v["state"] = "no_rejection"
        if v["state"] == "rejected":
            aft = s[s.index > v["rj"]]
            br = aft[aft.High >= v["ph"] * 1.005]
            # APPROACH: back within 0.3% of the level but not yet at the limit -> place the limit now; volume of the push so
            # far = max 1-min volume of the last 3 completed bars (all before the touch; this is the read tested live-usable)
            ap = aft[(aft.High >= L * 0.997) & (aft.index.strftime("%H:%M") <= "10:30")]
            if len(ap) and not v.get("appr") and ap.High.iloc[0] < L * 0.999 and (not len(br) or ap.index[0] < br.index[0]):
                v["appr"] = True; ai = s.index.get_loc(ap.index[0])
                vp = s.Volume.iloc[max(s.index.get_loc(v["rj"]) + 1, ai - 2):ai + 1].max(); rp = vp / v["pv"] if v["pv"] > 0 else float("nan")
                tagp = ">> WEAK  (<= 0.5x poke)" if round(rp, 2) <= 0.5 else "   STRONG (> 0.5x poke)"
                if alert or verbose: print(f"{ap.index[0]:%H:%M} APPROACH {t} {nm} {L:.2f} | high {ap.High.iloc[0]:.2f} ({(ap.High.iloc[0] / L - 1) * 100:+.2f}%), "
                      f"push vol so far {k_(vp)} = {rp:.2f}x poke -> {tagp} | limit {L * 0.999:.2f}, stop {v['ph'] * 1.005:.2f} "
                      f"({(v['ph'] * 1.005 / (L * 0.999) - 1) * 100:.2f}%), 1% tgt {L * 0.999 * 0.99:.2f}", flush=True)
            tst = aft[(aft.High >= L * 0.999) & (aft.index.strftime("%H:%M") <= "10:30")]
            if len(tst) and (not len(br) or tst.index[0] <= br.index[0]):
                ti = tst.index[0]; i = s.index.get_loc(ti)
                v2 = s.Volume.iloc[max(0, i - 2):i + 1].max(); r = v2 / v["pv"] if v["pv"] > 0 else float("nan")
                tag = ">> WEAK  (<= 0.5x poke)" if round(r, 2) <= 0.5 else "   STRONG (> 0.5x poke)"
                v["state"] = "retested"
                if alert or verbose: print(f"{ti:%H:%M} RETEST   {t} {nm} {L:.2f} | high {tst.High.iloc[0]:.2f}, 2nd push vol {k_(v2)} = {r:.2f}x poke -> {tag} | "
                      f"limit {L * 0.999:.2f}, stop {v['ph'] * 1.005:.2f} ({(v['ph'] * 1.005 / (L * 0.999) - 1) * 100:.2f}%), "
                      f"1% tgt {L * 0.999 * 0.99:.2f}", flush=True)
            elif len(br):
                v["state"] = "broke"
                if verbose: print(f"{br.index[0]:%H:%M} BROKE    {t} {nm} {L:.2f} | over push high + 0.5% ({v['ph'] * 1.005:.2f}) -- dropped", flush=True)
            elif hm > "10:30": v["state"] = "expired"


def summary():
    rj = [(t, nm) for (t, nm), v in st.items() if v.get("state") == "expired" and nm.endswith(("R1", "R2"))]
    print(f"10:30 retest window closed: {len(rj)} rejected R1/R2 levels never came back" + (f" ({', '.join(f'{t} {n}' for t, n in rj[:12])}{' ...' if len(rj) > 12 else ''})" if rj else ""), flush=True)


print(f"watching {len(LV)} stocks for pivot rejections + retests ({'replay ' + day if replay else 'live'})", flush=True)
if replay:
    data = {}
    for t in LV:
        x = pd.read_csv(os.path.join(src, f"{t}.csv"), index_col=0, parse_dates=True)
        data[t] = x[x.index.normalize() == dday]
    for mnt in pd.date_range(dday + pd.Timedelta("9h20min"), dday + pd.Timedelta("10h31min"), freq="1min"):
        for t, x in data.items():
            if len(x): step(t, x[x.index <= mnt], mnt)
    summary(); sys.exit()
done_summary = False
while dt.datetime.now(IST).time() < dt.time(10, 32):
    if dt.datetime.now(IST).time() < dt.time(9, 21): time.sleep(20); continue
    try:
        d = yf.download([t + ".NS" for t in LV], period="1d", interval="1m", group_by="ticker", progress=False, threads=True)
    except Exception as e:
        print(f"fetch error {e}", flush=True); time.sleep(30); continue
    for t in LV:
        try: x = d[t + ".NS"].dropna(how="all")
        except KeyError: continue
        if len(x) < 2: continue
        x.index = x.index.tz_convert(IST).tz_localize(None)
        step(t, x.iloc[:-1], None)   # drop the forming bar
    time.sleep(45)
summary()
print("watch ended 10:32", flush=True)
