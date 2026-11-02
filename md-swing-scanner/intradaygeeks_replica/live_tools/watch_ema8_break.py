import time, warnings, datetime as dt
warnings.filterwarnings("ignore")
import yfinance as yf
# Nifty 5-min EMA8 break watcher (Yahoo). Events: a completed 5m close under the 5m EMA8 (BREAK), then a 1m retest
# of the EMA8 from below that closes back under it (RETEST FAILED = PE cue); a 5m close over FLAG_HIGH (flag broke up);
# HDFCBANK 1m close under its daily 8 (HDFC_LEVEL). Usage: python3 watch_ema8_break.py
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
FLAG_HIGH, HDFC_LEVEL = 23118.0, 691.92
RANGE_LOW = 23077.5
TRAIL = 23050
HEAVY = ["HDFCBANK", "ICICIBANK", "RELIANCE", "INFY", "BHARTIARTL", "LT", "AXISBANK", "SBIN"]
state = {"break": None, "retest_done": False, "flag": False, "hdfc": False, "last5": None}
def get(sym, per, iv):
    d = yf.download(sym, period=per, interval=iv, progress=False); d.columns = [c[0] for c in d.columns]
    d.index = d.index.tz_convert(IST); return d
print(f"watching Nifty 5m EMA8 from {dt.datetime.now(IST):%H:%M:%S}", flush=True)
while dt.datetime.now(IST).time() < dt.time(15, 25):
    try:
        b5 = get("^NSEI", "5d", "5m"); m1 = get("^NSEI", "1d", "1m"); h = get("HDFCBANK.NS", "1d", "1m")
        if b5.empty or m1.empty or h.empty: raise ValueError("empty download")
    except Exception as e:
        print(f"fetch error {e}", flush=True); time.sleep(30); continue
    now = dt.datetime.now(IST)
    done = b5[b5.index + dt.timedelta(minutes=5) <= now]
    ema = done.Close.ewm(span=8, adjust=False).mean()
    t5, c5, e5 = done.index[-1], done.Close.iloc[-1], ema.iloc[-1]
    if t5 != state["last5"]:
        state["last5"] = t5
        o5, h5, l5 = done.Open.iloc[-1], done.High.iloc[-1], done.Low.iloc[-1]
        hd = h.Close.iloc[-2] if len(h) > 1 else float("nan")
        # seller strength, 0-5: under EMA8 / lower high than prior bar / close in the bar's lower third /
        # HDFCBANK under its daily 8 / >= 5 of 8 heavyweights down over the last 5-min bar
        try:
            hw = yf.download([k + ".NS" for k in HEAVY], period="1d", interval="5m", group_by="ticker", progress=False)
            dn = sum(1 for k in HEAVY if len(hw[k + ".NS"].dropna()) > 2 and hw[k + ".NS"].dropna().Close.iloc[-2] < hw[k + ".NS"].dropna().Close.iloc[-3])
        except Exception: dn = -1
        rng = max(h5 - l5, 0.1)
        pts = [c5 < e5, h5 < done.High.iloc[-2], (c5 - l5) / rng <= 0.33, hd < HDFC_LEVEL - 1.5, dn >= 5]
        sc = sum(pts); verdict = "HOLD" if sc >= 3 and c5 < e5 else ("CAUTION" if sc == 2 else "SELLERS WEAK")
        print(f"5m {t5:%H:%M} {'red' if c5 < o5 else 'green'} H{h5:.1f} L{l5:.1f} C{c5:.1f} | EMA8 {e5:.1f} ({c5 - e5:+.1f}) | HDFCBANK {hd:.2f} | heavy down {dn}/8 | sellers {sc}/5 -> {verdict}", flush=True)
        if c5 > TRAIL: print(f"{t5:%H:%M} EXIT: 5m close {c5:.1f} over trail stop {TRAIL}", flush=True)
        if c5 < e5 - 10 and state["break"] is None:  # a real break: 10+ points under
            state["break"] = t5; print(f"{t5:%H:%M} BREAK: 5m close {c5:.1f} under 5m EMA8 {e5:.1f} -- wait for the retest to fail", flush=True)
        if c5 > FLAG_HIGH and not state["flag"]:
            state["flag"] = True; print(f"{t5:%H:%M} FLAG BROKE UP: 5m close {c5:.1f} over {FLAG_HIGH} -- no PE", flush=True)
        if state["break"] is not None and c5 > e5 + 3 and t5 > state["break"]:
            print(f"{t5:%H:%M} BREAK UNDONE: 5m close {c5:.1f} back over EMA8 {e5:.1f}", flush=True); state["break"] = None; state["retest_done"] = False
    if c5 < RANGE_LOW and not state.get("range"):
        state["range"] = True; print(f"{t5:%H:%M} RANGE BREAK: 5m close {c5:.1f} under {RANGE_LOW} -- PE trigger, stop over 23105", flush=True)
    if state["break"] is not None and not state["retest_done"]:
        after = m1[m1.index >= state["break"] + dt.timedelta(minutes=5)].iloc[:-1]
        tagged = after[after.High >= e5 - 2]
        if len(tagged) and after.Close.iloc[-1] < e5 - 3 and after.index[-1] > tagged.index[0]:
            state["retest_done"] = True
            print(f"{after.index[-1]:%H:%M} RETEST FAILED: tagged EMA8 {e5:.1f} (high {tagged.High.max():.1f}), 1m close {after.Close.iloc[-1]:.1f} -- PE cue, stop over {max(tagged.High.max(), e5) + 8:.0f}", flush=True)
    hc = h.Close.iloc[-2] if len(h) > 1 else None
    if hc is not None and hc < HDFC_LEVEL and not state["hdfc"]:
        state["hdfc"] = True; print(f"{h.index[-2]:%H:%M} HDFCBANK 1m close {hc:.2f} under its daily 8 {HDFC_LEVEL}", flush=True)
    if hc is not None and hc > HDFC_LEVEL + 1 and state["hdfc"]: state["hdfc"] = False
    time.sleep(20)
print("watch ended", flush=True)
