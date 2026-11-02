import subprocess, sys, time, datetime as dt
IST = dt.timezone(dt.timedelta(hours=5, minutes=30)); TV = sys.argv[1]
SYMS = {"GIFT": ("NSEIX:NIFTY1!", 0.30, 0.45), "BRENT": ("NYMEX:BZF2027", 0.8, 1.5), "SPFUT": ("CME_MINI:ES1!", 0.30, 0.50)}
last_status, last_alert = 0, {}
def bars(sym):
    out = subprocess.run([sys.executable, TV, sym, "1", "40"], capture_output=True, text=True, timeout=40).stdout.split("\n")
    r = []
    for l in out:
        p = l.split()
        if len(p) == 6: r.append((p[1], float(p[3]), float(p[4]), float(p[5])))
    return r
while True:
    now = dt.datetime.now(IST)
    day = len(sys.argv) > 2 and sys.argv[2] == "day"  # day mode: watch during market hours, stop 15:30
    if (now.time() >= dt.time(15, 30)) if day else (dt.time(2, 50) <= now.time() < dt.time(16, 0)): break
    snap = {}
    for k, (sym, a5, a15) in SYMS.items():
        try:
            b = bars(sym)
            if len(b) < 16: continue
            c = b[-1][3]; c5 = b[-6][3]; c15 = b[-16][3]
            m5, m15 = (c / c5 - 1) * 100, (c / c15 - 1) * 100
            snap[k] = (c, m15, b[-1][0])
            if k == "BRENT" and max(x[2] for x in b) > 114.07 and "dec_hi" not in last_alert:
                last_alert["dec_hi"] = time.time(); print(f"ALERT {now:%H:%M} BRENT (Jan) above today 07:15 spike high 114.07 ({c:.2f}) -- new 5-month high", flush=True)
            hit = abs(m5) >= a5 or abs(m15) >= a15
            if hit and time.time() - last_alert.get(k, 0) > 900:
                last_alert[k] = time.time()
                print(f"ALERT {now:%H:%M} {k} {c:.2f} | 5m {m5:+.2f}% | 15m {m15:+.2f}% (last bar {b[-1][0]})", flush=True)
        except Exception as e:
            print(f"ERR {now:%H:%M} {k} {e}", flush=True)
    if time.time() - last_status >= 3600 and snap:
        last_status = time.time()
        print("STATUS " + f"{now:%H:%M} " + " | ".join(f"{k} {v[0]:.2f} (15m {v[1]:+.2f}%, bar {v[2]})" for k, v in snap.items()), flush=True)
    time.sleep(60)
print("END session over", flush=True)
