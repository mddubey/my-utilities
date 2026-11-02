import sys, time, datetime as dt, warnings; warnings.filterwarnings("ignore")
import yfinance as yf
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
E, SL = 831.5, 834.1; R = SL - E
fired = set(sys.argv[1].split(",")) if len(sys.argv) > 1 else set()
last_status = 0
def bars(s):
    x = yf.download(s, period="1d", interval="1m", progress=False); x.columns = [c[0] for c in x.columns]
    x.index = x.index.tz_convert("Asia/Kolkata"); return x.dropna()
def alert(k, msg):
    if k in fired: return
    fired.add(k); print(f"ALERT {dt.datetime.now(IST):%H:%M} {msg} [seen:{','.join(sorted(fired))}]", flush=True)
while dt.datetime.now(IST).time() < dt.time(15, 30):
    try:
        n, c = bars("^NSEI"), bars("SHRIRAMFIN.NS")
        nl, cl = n.Close.iloc[-1], c.Close.iloc[-1]
        c = c.loc["2026-10-29 09:42":]; n2 = n.loc["2026-10-29 09:42":]   # only bars since the entry
        if c.High.max() >= SL: alert("s_stop", f"SHRIRAMFIN STOP {SL} hit (high {c.High.max():.2f})")
        elif c.High.max() >= 833.5: alert("s_833", f"SHRIRAMFIN back at yday high zone (high {c.High.max():.2f}), stop {SL}")
        for lvl, tag in ((825.5, "PP"), (821.0, "day low"), (817.1, "S1")):
            if c.Low.min() <= lvl: alert(f"s_{lvl}", f"SHRIRAMFIN {tag} {lvl} reached (low {c.Low.min():.2f}) = {(E-lvl)/R:+.1f}R / {(E-lvl)/E*100:+.2f}%")
        if n2.High.max() >= 22776: alert("n_778", f"NIFTY at yday high 22778 (high since entry {n2.High.max():.1f})")
        if n2.High.max() >= 22812: alert("n_815", f"NIFTY at R1+1D21 22815-22824 (high {n2.High.max():.1f})")
        if n2.Low.min() <= 22700: alert("n_700", f"NIFTY back to 1H EMAs ~22700 (low {n2.Low.min():.1f})")
        if n2.Low.min() <= 22660: alert("n_658", f"NIFTY at PP 22658 (low {n2.Low.min():.1f})")
        if time.time() - last_status >= 300:
            last_status = time.time()
            print(f"STATUS {dt.datetime.now(IST):%H:%M} NIFTY {nl:.1f} (high {n.High.max():.1f}) | SHRIRAMFIN {cl:.2f} (low since entry {c.Low.min():.2f}, high since entry {c.High.max():.2f}) = {(E-cl)/E*100:+.2f}% / {(E-cl)/R:+.2f}R", flush=True)
    except Exception as e:
        print(f"ERR {dt.datetime.now(IST):%H:%M} {e}", flush=True)
    time.sleep(45)
