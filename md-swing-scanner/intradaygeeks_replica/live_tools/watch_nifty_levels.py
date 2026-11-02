import sys, time, warnings, datetime as dt
warnings.filterwarnings("ignore")
import yfinance as yf
# Event-only Nifty level watcher (Yahoo ^NSEI 1-min). Prints: each 5-min bar close (one line), first touch of a level,
# a rejection (touched, then a 1-min close >= REJ pts back on the other side), and box-edge breaks.
# Edit LEVELS each day. Usage: python3 watch_nifty_levels.py
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
UP = {23042.2: "11:2x high", 23047: "R1", 23056: "1W8 live", 23157: "R2"}
DN = {23005: "11:00 low", 22988: "1D34", 22962: "yday high", 22905: "day low", 22852: "PP"}
BOX = (22905.1, 23042.2)  # opening box: day low / high at 09:18
TOUCH, REJ = 3, 10
touched, rejected, broke, last5 = {}, set(), set(), None
quiet = True  # first pass records past touches silently (re-arm without repeats)
import builtins
def emit(*a, **k):
    if not quiet or str(a[0]).startswith("watching"): builtins.print(*a, **k)
emit(f"watching Nifty from {dt.datetime.now(IST):%H:%M:%S}", flush=True)
while dt.datetime.now(IST).time() < dt.time(15, 31):
    try:
        d = yf.download("^NSEI", period="1d", interval="1m", progress=False)
        d.columns = [c[0] for c in d.columns]
        d.index = d.index.tz_convert(IST)
    except Exception as e:
        print(f"fetch error {e}", flush=True); time.sleep(30); continue
    if d.empty: time.sleep(30); continue
    done = d.iloc[:-1]  # last row may be a forming bar
    hi, lo, now, t = d.High.max(), d.Low.min(), d.Close.iloc[-1], d.index[-1]
    for lv, nm in UP.items():
        if lv not in touched and done.High.max() >= lv - TOUCH:
            touched[lv] = done.index[done.High >= lv - TOUCH][0]
            emit(f"{t:%H:%M} TOUCH {nm} {lv} (high {hi:.1f}) now {now:.1f}", flush=True)
        if lv in touched and lv not in rejected:
            after = done[done.index >= touched[lv]]
            if (after.Close <= lv - REJ).any() and after.Close.iloc[-1] <= lv - REJ:
                rejected.add(lv); emit(f"{t:%H:%M} REJECTED under {nm} {lv}: 1-min close {after.Close.iloc[-1]:.1f}, high {after.High.max():.1f}", flush=True)
    for lv, nm in DN.items():
        if lv not in touched and done.Low.min() <= lv + TOUCH:
            touched[lv] = done.index[done.Low <= lv + TOUCH][0]
            emit(f"{t:%H:%M} TOUCH {nm} {lv} (low {lo:.1f}) now {now:.1f}", flush=True)
        if lv in touched and lv not in rejected:
            after = done[done.index >= touched[lv]]
            if after.Close.iloc[-1] >= lv + REJ:
                rejected.add(lv); emit(f"{t:%H:%M} HELD above {nm} {lv}: 1-min close {after.Close.iloc[-1]:.1f}, low {after.Low.min():.1f}", flush=True)
    if "hi" not in broke and hi > BOX[1]: broke.add("hi"); emit(f"{t:%H:%M} BOX TOP {BOX[1]} broken, high {hi:.1f}", flush=True)
    if "lo" not in broke and lo < BOX[0]: broke.add("lo"); emit(f"{t:%H:%M} BOX LOW {BOX[0]} broken, low {lo:.1f}", flush=True)
    b5 = done.resample("5min").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
    full = b5[b5.index + dt.timedelta(minutes=5) <= done.index[-1] + dt.timedelta(minutes=1)]
    if len(full) and full.index[-1] != last5:
        last5 = full.index[-1]; r = full.iloc[-1]
        col = "red" if r.Close < r.Open else "green"
        emit(f"5m {last5:%H:%M} {col} O{r.Open:.1f} H{r.High:.1f} L{r.Low:.1f} C{r.Close:.1f} | day {lo:.1f}-{hi:.1f}", flush=True)
    if quiet: builtins.print(f"armed {t:%H:%M}: day {lo:.1f}-{hi:.1f}, now {now:.1f}, already touched {sorted(touched)}", flush=True)
    quiet = False
    time.sleep(20)
print("market closed", flush=True)
