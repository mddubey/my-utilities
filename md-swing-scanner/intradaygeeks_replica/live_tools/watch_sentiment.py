import re, sys, html, time, subprocess, warnings, datetime as dt, urllib.request, urllib.parse, xml.etree.ElementTree as ET
import pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")
# Live sentiment watcher, 09:15-15:30, ALERTS ONLY (no status lines; the user asked 2026-11-03). Every 5 min:
#  1) macro drift from the 09:15 reference -- Brent / S&P fut / USDINR (TradingView), India VIX (Yahoo): each step fires once,
#     plus a fast-move alert (15 min). Born from 2026-11-02: Brent slid -2.4% through the session, no 5/15-min spike, so
#     watch_gift.py never fired while it was undercutting the Nifty-short read;
#  2) sector indices and the top Nifty weights vs today's open (Yahoo 5-min): a big one-sided push moves the index;
#  3) India policy / market headlines (Google News RSS, titles only, untrusted text): instant alert on a policy keyword.
#     Born from the 2026-11-02 12:08 SEBI LTCG headline. RSS lags the wires (~5-20 min, not measured).
# Thresholds are trading-logic picks, not backtested. Drift is measured from 09:15 AND from Nifty's last close (15:30 prior session).
# Usage: python3 watch_sentiment.py [--replay YYYY-MM-DD]  (replay = macro/sector only)
IST = dt.timezone(dt.timedelta(hours=5, minutes=30)); TV = __file__.rsplit("/", 1)[0] + "/tv_bars.py"
replay = sys.argv[sys.argv.index("--replay") + 1] if "--replay" in sys.argv else None
# name: (symbol, drift steps % from 09:15, fast % in 15 min, label when DOWN, label when UP)
TVS = {"BRENT": ("NYMEX:BZF2027", (1.5, 2.5, 4.0), 1.0, "tailwind for Nifty (don't lean short)", "headwind for Nifty"),
       "SP_FUT": ("CME_MINI:ES1!", (0.6, 1.0, 1.5), 0.4, "risk-off (IT / Nifty headwind)", "risk-on"),
       "USDINR": ("FX_IDC:USDINR", (0.3, 0.5), 0.2, "rupee stronger (FPI-positive)", "rupee weaker (FPI-negative)")}
YH = {"INDIA_VIX": ("^INDIAVIX", (6, 10, 15), 4, "fear easing", "fear rising")}
SECT = {"IT": "^CNXIT", "BANK": "^NSEBANK", "METAL": "^CNXMETAL", "ENERGY": "^CNXENERGY", "AUTO": "^CNXAUTO", "FMCG": "^CNXFMCG", "PHARMA": "^CNXPHARMA"}
HEAVY = ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "BHARTIARTL", "TCS", "LT", "ITC", "SBIN", "AXISBANK"]
SECT_STEPS, HEAVY_STEPS = (1.5, 2.5), (2.5, 4.0)
NEWS_Q = ('India ("SBI results" OR "HDFC AMC" OR "AMC stocks" OR "capital market stocks" OR SEBI OR RBI OR LTCG OR "capital gains" OR STT OR FPI OR "Finance Ministry" OR "repo rate" OR Sensex OR Nifty '
          'OR "F&O" OR tariff OR Hormuz OR Iran OR OPEC) when:1h')
POLICY = re.compile(r"\b(ltcg|capital gains tax|stt|securities transaction|repo rate (cut|hike)|rbi (cuts|hikes|policy)|"
                    r"rate (cut|hike)|ban(s|ned)? .*(f&o|derivative|trading)|f&o curbs?|hormuz|ceasefire|strikes? on|attack(s|ed)? on|"
                    r"opec|tariffs? on india|sbi .*(profit|q2|results|net)|nifty .*(crash|plunge|tank|soar|surge)|"
                    r"sensex .*(crash|plunge|tank|soar|surge)|fpi .*(tax|outflow|selling)|emergency|resign|hdfc amc|amc (stocks|shares))", re.I)
# instant alerts = market-moving EVENTS only (tightened 2026-11-03 09:15: SEBI / RBI explainers and recaps were noise)
import json, os, email.utils
STATE = f"/tmp/watch_sentiment_{dt.date.today():%Y%m%d}.json"   # survives a restart: no re-fired headlines
try: _st = json.load(open(STATE)); seen = set(_st["seen"]); told = [(pd.Timestamp(a), set(b)) for a, b in _st["told"]]
except Exception: seen, told = set(), []
try: fired = {tuple(x) for x in json.load(open(STATE)).get("fired", [])}   # macro steps already alerted (a restart re-fired them)
except Exception: fired = set()
def save():
    try: json.dump({"seen": sorted(seen), "told": [(str(a), sorted(b)) for a, b in told],
                   "fired": [list(f) for f in fired if all(isinstance(z, (str, int, float, bool)) for z in f)]}, open(STATE, "w"))
    except Exception: pass
_unused, _unused2, _unused3 = set(), set(), []   # told = (time, significant words) of headlines already alerted
STOP = {"india", "indian", "stock", "stocks", "market", "markets", "after", "amid", "says", "report", "reports", "news", "today", "their", "about"}


def alert(now, msg):
    print(f"ALERT {now:%H:%M} {msg}", flush=True)


_cache = {}


def tv(sym, n=900):   # ~3 days of 5-min bars: reaches the prior 15:30 even after a weekend
    if replay and sym in _cache: return _cache[sym]
    out = subprocess.run([sys.executable, TV, sym, "5", str(n)], capture_output=True, text=True, timeout=60).stdout.split("\n")
    r = [(pd.Timestamp(f"{p[0]} {p[1]}"), float(p[5])) for p in (l.split() for l in out) if len(p) == 6]
    # an empty fetch (TV hiccup, 2026-11-11 10:05) must still carry a DatetimeIndex, else `s.index <= now` throws
    _cache[sym] = pd.Series([v for _, v in r], index=pd.DatetimeIndex([t for t, _ in r]), dtype=float)
    _cache[sym] = _cache[sym][~_cache[sym].index.duplicated(keep="last")].sort_index(); return _cache[sym]


def yh(syms, day):
    if replay and "yh" in _cache: return _cache["yh"]
    d = yf.download(syms, start=day, end=(pd.Timestamp(day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"), interval="5m",
                    group_by="ticker", progress=False, threads=True)
    out = {}
    for s in syms:
        try:
            x = d[s].dropna(how="all"); x.index = x.index.tz_convert(IST).tz_localize(None); out[s] = x
        except Exception: pass
    _cache["yh"] = out; return out


def steps(now, key, chg, levels, dn, up, extra=""):
    chg = float(chg); pos = bool(chg > 0)   # plain types so the step keys survive the JSON state file
    new = [lv for lv in levels if abs(chg) >= lv and (key, lv, pos) not in fired]
    if new:   # one line for the highest step crossed
        fired.update((key, lv, pos) for lv in new)
        alert(now, f"{key} {chg:+.2f}%{'' if 'since' in key else ' from 09:15'}{extra} -> {up if chg > 0 else dn}")


def prev_session(day):
    n = pd.read_csv(__file__.rsplit("/", 2)[0] + "/../data/daily/_NIFTY.csv", parse_dates=["Date"])
    return n[n.Date < pd.Timestamp(day)].Date.iloc[-1].strftime("%Y-%m-%d")


def macro(now, day):
    t915 = pd.Timestamp(f"{day} 09:15"); tprev = pd.Timestamp(f"{prev_session(day)} 15:30")
    for k, (sym, lv, fast, dn, up) in TVS.items():
        try:
            s = tv(sym); s = s[s.index <= now]
            ref = s[s.index <= t915]
            if not len(ref) or s.index[-1] < t915: continue
            c, r0 = s.iloc[-1], ref.iloc[-1]
            steps(now, k, (c / r0 - 1) * 100, lv, dn, up, f" ({r0:g} -> {c:g})")
            # also vs Nifty's last close: what the index has NOT priced yet (11-02: Brent -2.7% by 09:15, -1.3% after it)
            pc = s[s.index <= tprev]
            if len(pc): steps(now, k + " since Nifty's last close", (c / pc.iloc[-1] - 1) * 100, lv, dn, up, f" ({pc.iloc[-1]:g} -> {c:g})")
            back = s[s.index <= s.index[-1] - pd.Timedelta("15min")]
            if len(back):
                f = (c / back.iloc[-1] - 1) * 100
                slot = str(s.index[-1].floor("30min"))   # Timestamp // Timedelta is unsupported (2026-11-12 11:50 BRENT error)
                if abs(f) >= fast and (k, "fast", slot) not in fired:
                    fired.add((k, "fast", slot))
                    alert(now, f"{k} fast move {f:+.2f}% in 15 min ({c:g}) -> {up if f > 0 else dn}")
        except Exception as e: print(f"ERR {now:%H:%M} {k} {e}", flush=True)
    syms = [v[0] for v in YH.values()] + list(SECT.values()) + [h + ".NS" for h in HEAVY]
    d = yh(syms, day)
    def chg(s):
        x = d.get(s)
        if x is None or not len(x): return None
        x = x[x.index <= now - pd.Timedelta("5min")]   # completed bars only
        return (x.Close.iloc[-1] / x.Open.iloc[0] - 1) * 100 if len(x) else None
    for k, (s, lv, fast, dn, up) in YH.items():
        c = chg(s)
        if c is not None: steps(now, k, c, lv, dn, up)
    for k, s in SECT.items():
        c = chg(s)
        if c is not None: steps(now, f"SECTOR {k}", c, SECT_STEPS, "dragging Nifty", "lifting Nifty")
    for h in HEAVY:
        c = chg(h + ".NS")
        if c is not None: steps(now, f"HEAVYWEIGHT {h}", c, HEAVY_STEPS, "dragging Nifty", "lifting Nifty")


def news(now, first):
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(NEWS_Q) + "&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        root = ET.fromstring(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())
    except Exception as e:
        print(f"ERR {now:%H:%M} news {e}", flush=True); return
    for it in root.iter("item"):
        t = html.unescape((it.findtext("title") or "").strip())
        k = re.sub(r"\W+", " ", t.lower())[:90]
        if not t or k in seen: continue
        seen.add(k)
        try: age = now - pd.Timestamp(email.utils.parsedate_to_datetime(it.findtext("pubDate"))).tz_convert(IST).tz_localize(None)
        except Exception: age = pd.Timedelta(0)
        if first or not POLICY.search(t) or age > pd.Timedelta("45min"): continue   # fresh headlines only (recaps get re-served)
        if re.search(r"ltcg|capital gains", t, re.I) and not re.search(r"\b(approv|announc|notif|reject|cabinet|scrapped|cleared|decid)", t, re.I):
            continue   # LTCG commentary was re-worded by every outlet (2026-11-03): alert only on an actual decision
        w = {x for x in re.findall(r"[a-z]{5,}", t.lower().split(" - ")[0]) if x not in STOP}
        if any(now - tt < pd.Timedelta("3h") and len(w & ww) >= 2 for tt, ww in told): continue   # same story re-worded
        told.append((now, w)); alert(now, f"NEWS {t[:200]} ({int(age.total_seconds() // 60)} min old)")
    save()


if replay:
    for m in pd.date_range(f"{replay} 09:20", f"{replay} 15:30", freq="5min"): macro(m, replay)
    sys.exit()
print("sentiment watch on: alerts only (macro drift, sectors / heavyweights, policy headlines), 09:15-15:30", flush=True)
first = True
while True:
    now = dt.datetime.now(IST).replace(tzinfo=None)
    if now.time() >= dt.time(15, 30): break
    if now.time() < dt.time(9, 15): news(now, first); first = False; time.sleep(120); continue
    news(now, first); first = False
    macro(now, now.strftime("%Y-%m-%d")); save()
    time.sleep(300 - time.time() % 300 + 20)
print("END sentiment watch", flush=True)
