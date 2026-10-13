"""REVERSE-ENGINEER the channel's intraday calls (user, 2026-10-14: 'he is looking at charts, I am not -- that is his edge; categorise his
calls into the nine scanners; he trades overbought / oversold, hourly 34, 30 min; his longs on clear Nifty-up days are good, his shorts
weaker'). DESCRIPTIVE ONLY, nothing traded. Spec fixed before running:
  Calls: telegram_calls_scored.csv (240 intraday stock calls, 2024-12 .. 2026-09, scored by 05: fill at the call price, first of SL / T1 on
  hourly bars, else day close; r60 = R, gross). Plus % return = R x stop% (removes tiny-stop inflation).
  At the call time, for each call, which of the channel's own Chartink scanners (CHARTINK_QUERIES.md) it matches -- side-matched:
    S1  SWING 1H        long: live price > 1H EMA34 and < 1H EMA8 (live = EMA updated with the call price) | short mirror
    S2  SWING 30 MIN    same on the PREVIOUS completed 30-min candle (5-min data -> only calls from 2026-06-10)
    S3  15-min 150/200  long: price between 15-min EMA200 (below) and EMA150 (above) | short mirror (5-min data only)
    S4  1H 150/200      same band on 1H EMAs
    S5  DAILY 150/200   same band on daily EMAs (live)
    S6  PINBAR 1H       long: last completed 1H candle = bullish hammer (formula) | short: 1H bearish pinbar formula
    S7  PINBAR 1D       long: yesterday's daily candle = bullish hammer | short: yesterday = bearish pinbar 1D (below daily EMA8)
    S8  REVERSAL        long: yesterday RSI14 < 20, price > yesterday's high, yesterday's close <= day-before's high | short mirror (80)
    S9  OB / OS 1D      long: yesterday RSI14 < 30 (oversold) | short: > 70 (overbought)
  LEVELS: is the STOP just beyond (0-0.25%) / the ENTRY within +-0.25% of: 1H EMA34 (live), yesterday's daily EMA8 / EMA21 (touch prices),
    yesterday's close / high / low, today's open, today's high / low so far.
  NIFTY: above its own day open at the call (last completed Nifty 1H close; 5-min close where available) -> aligned = long & up / short & down.
  SPEED (calls from 2026-06-10, 5-min data): share of the way to T1 already done 5 / 10 / 15 min after the call; still fillable at the
    called price after 5 / 10 min.
  FIX 2026-10-14: day high / low so far from bars finished before the call only (5-min where available, else completed hours + the open).
  Report: frequency of each tag by side, win % / mean R / mean % per tag, 'no scanner matched', Nifty-aligned vs not."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from data.paths import DAILY_DIR, INTRADAY_5M_DIR
C = pd.read_csv(HERE / "telegram_calls_scored.csv"); C["ts"] = pd.to_datetime(C.ts)
C = C[C.r60.notna()].copy()
ix = HERE.parent / "data" / "index_intraday"
def idx(f):
    x = pd.read_csv(ix / f, index_col=0); x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None); return x[~x.index.duplicated()]
N1 = idx("_NIFTY_1h.csv"); N5 = idx("_NIFTY_5m_60d.csv"); ND = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index()


def rsi(c, n=14):
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def hammer(o, h, l, c): return c <= h and (h - c) < (c - o) and c > o and (o - l) >= (c - o)
def bear1h(o, h, l, c): return o > c and (h - o) > (o - c) * 2 and (c - l) < (o - c)
def bear1d(o, h, l, c, e8): rg = h - l; return rg > 0 and (o - l) <= rg * 0.4 and (c - l) <= rg * 0.4 and c > l and c < e8
def live_ema(prev, p, n): return prev + 2 / (n + 1) * (p - prev)


rows = []; cache = {}
for _, k in C.iterrows():
    t = k.ticker; ts = k.ts; day = ts.normalize(); s = 1 if k.direction == "long" else -1; P = k.entry
    try:
        if t not in cache:
            D = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).sort_index()
            H = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); H.index = pd.to_datetime(H.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
            H = H[~H.index.duplicated()]
            M = None
            if (INTRADAY_5M_DIR / f"{t}.csv").exists():
                M = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True); M.index = M.index.tz_convert("Asia/Kolkata").tz_localize(None); M = M[~M.index.duplicated()]
            cache[t] = (D, H, M)
        D, H, M = cache[t]
    except Exception: continue
    y = D[D.index < day]
    if len(y) < 210 or day not in D.index: continue
    yd = y.iloc[-1]; y2 = y.iloc[-2]
    e8d, e21d = y.Close.ewm(span=8, adjust=False).mean().iloc[-1], y.Close.ewm(span=21, adjust=False).mean().iloc[-1]
    e150d, e200d = y.Close.ewm(span=150, adjust=False).mean().iloc[-1], y.Close.ewm(span=200, adjust=False).mean().iloc[-1]
    r_ = rsi(y.Close); rsi_y = r_.iloc[-1]
    hb = H[H.index + pd.Timedelta("60min") <= ts]                      # completed hourly bars before the call
    if len(hb) < 210: continue
    he = {n: hb.Close.ewm(span=n, adjust=False).mean().iloc[-1] for n in (8, 34, 150, 200)}
    hl = {n: live_ema(he[n], P, n) for n in he}
    lb = hb.iloc[-1]; dopen = D.Open[day]
    # 2026-10-14 FIX: day high / low SO FAR must use only bars finished before the call (first run used the whole call hour = look-ahead)
    m_pre = None
    if M is not None:
        m_pre = M[(M.index.normalize() == day) & (M.index + pd.Timedelta("5min") <= ts)]
    if m_pre is not None and len(m_pre): dhi, dlo = max(m_pre.High.max(), dopen), min(m_pre.Low.min(), dopen)
    else:
        th = H[(H.index.normalize() == day) & (H.index + pd.Timedelta("60min") <= ts)]
        dhi = max(th.High.max(), dopen) if len(th) else dopen; dlo = min(th.Low.min(), dopen) if len(th) else dopen
    tags = {}
    tags["S1 SWING 1H"] = (P > hl[34] and P < hl[8]) if s > 0 else (P < hl[34] and P > hl[8])
    tags["S4 1H 150/200"] = (hl[200] < P < hl[150]) if s > 0 else (hl[150] < P < hl[200])
    d150, d200 = live_ema(e150d, P, 150), live_ema(e200d, P, 200)
    tags["S5 DAILY 150/200"] = (d200 < P < d150) if s > 0 else (d150 < P < d200)
    tags["S6 PINBAR 1H"] = hammer(lb.Open, lb.High, lb.Low, lb.Close) if s > 0 else bear1h(lb.Open, lb.High, lb.Low, lb.Close)
    tags["S7 PINBAR 1D"] = hammer(yd.Open, yd.High, yd.Low, yd.Close) if s > 0 else bear1d(yd.Open, yd.High, yd.Low, yd.Close, e8d)
    tags["S8 REVERSAL"] = (rsi_y < 20 and P > yd.High and yd.Close <= y2.High) if s > 0 else (rsi_y > 80 and P < yd.Low and yd.Close >= y2.Low)
    tags["S9 OB/OS 1D"] = (rsi_y < 30) if s > 0 else (rsi_y > 70)
    m = None
    if M is not None:
        m = M[(M.index.normalize() <= day)]
        m = m[m.index > day - pd.Timedelta(days=12)]
    if m is not None and (m.index.normalize() == day).any() and len(m[m.index < ts]) > 200:
        mb = m[m.index + pd.Timedelta("5min") <= ts]
        m30 = mb.Close.resample("30min", offset="15min").last().dropna(); m30 = m30[m30.index + pd.Timedelta("30min") <= ts]
        e8_30, e34_30 = m30.ewm(span=8, adjust=False).mean().iloc[-1], m30.ewm(span=34, adjust=False).mean().iloc[-1]; c30 = m30.iloc[-1]
        tags["S2 SWING 30M"] = (e34_30 < c30 < e8_30) if s > 0 else (e8_30 < c30 < e34_30)
        m15 = mb.Close.resample("15min", offset="15min").last().dropna()
        a, b = m15.ewm(span=150, adjust=False).mean().iloc[-1], m15.ewm(span=200, adjust=False).mean().iloc[-1]
        tags["S3 15M 150/200"] = (b < P < a) if s > 0 else (a < P < b)
    else:
        tags["S2 SWING 30M"] = np.nan; tags["S3 15M 150/200"] = np.nan
    levels = {"1H EMA34": hl[34], "yday EMA8": e8d, "yday EMA21": e21d, "yday close": yd.Close, "yday high": yd.High, "yday low": yd.Low,
              "today open": dopen, "today high so far": dhi, "today low so far": dlo}
    stop_beyond = {f"stop@{n}": bool(lv == lv and 0 <= -s * (k.sl / lv - 1) * 100 <= 0.25) for n, lv in levels.items()}
    entry_at = {f"entry@{n}": bool(lv == lv and abs(P / lv - 1) * 100 <= 0.25) for n, lv in levels.items()}
    nb = N1[(N1.index + pd.Timedelta("60min") <= ts) & (N1.index.normalize() == day)]
    n5 = N5[(N5.index + pd.Timedelta("5min") <= ts) & (N5.index.normalize() == day)]
    nlast = n5.Close.iloc[-1] if len(n5) else (nb.Close.iloc[-1] if len(nb) else np.nan)
    nup = (nlast > ND.Open.get(day, np.nan)) if nlast == nlast else np.nan
    risk_pct = abs(P - k.sl) / P * 100
    rec = dict(t=t, ts=ts, side=k.direction, r=k.r60, out=k.out60, pct=k.r60 * risk_pct, risk_pct=risk_pct, rsi_y=rsi_y,
               nifty_up=nup, aligned=(nup == (s > 0)) if nup == nup else np.nan, **tags, **stop_beyond, **entry_at)
    # speed (5-min only)
    if m is not None and (m.index.normalize() == day).any():
        af = M[(M.index >= ts.ceil("5min")) & (M.index.normalize() == day)]
        tgt = k.target1; way = abs(tgt - P)
        for mm in (5, 10, 15):
            w = af[af.index < ts.ceil("5min") + pd.Timedelta(minutes=mm)]
            if len(w) and way > 0:
                best = (w.High.max() - P) if s > 0 else (P - w.Low.min()); rec[f"done{mm}"] = best / way
                rec[f"fill{mm}"] = bool((w.iloc[-1].Close <= P) if s > 0 else (w.iloc[-1].Close >= P))
    rows.append(rec)
X = pd.DataFrame(rows); X.to_csv(HERE / "channel_calls_tagged.csv", index=False)
SC = ["S1 SWING 1H", "S2 SWING 30M", "S3 15M 150/200", "S4 1H 150/200", "S5 DAILY 150/200", "S6 PINBAR 1H", "S7 PINBAR 1D", "S8 REVERSAL", "S9 OB/OS 1D"]
X["any_daily_1h"] = X[["S1 SWING 1H", "S4 1H 150/200", "S5 DAILY 150/200", "S6 PINBAR 1H", "S7 PINBAR 1D", "S8 REVERSAL", "S9 OB/OS 1D"]].any(axis=1)


def st(x):
    if not len(x): return "0"
    return f"{len(x)} | {(x.r > 0).mean()*100:.0f}% | {x.r.mean():+.2f} | {x.pct.mean():+.3f}%"


print(f"calls tagged: {len(X)} (longs {(X.side == 'long').sum()}, shorts {(X.side == 'short').sum()}); 5-min-era calls: {X['S2 SWING 30M'].notna().sum()}")
print("\n| scanner match (side-matched) | LONGS: n / win % / mean R / mean % | SHORTS: n / win % / mean R / mean % |\n|---|---|---|")
print(f"| ALL calls | {st(X[X.side == 'long'])} | {st(X[X.side == 'short'])} |")
for c in SC:
    xx = X[X[c] == True]; print(f"| {c} | {st(xx[xx.side == 'long'])} | {st(xx[xx.side == 'short'])} |")
xx = X[~X.any_daily_1h]; print(f"| none of the 1H / daily scanners | {st(xx[xx.side == 'long'])} | {st(xx[xx.side == 'short'])} |")
print("\nshare of calls matching each scanner (longs / shorts): " + " | ".join(f"{c.split()[0]} {X[(X.side=='long')][c].mean()*100:.0f}% / {X[(X.side=='short')][c].mean()*100:.0f}%" for c in SC))
print("\nLEVELS -- share of calls whose STOP sits 0-0.25% beyond / ENTRY within 0.25% of each level (longs / shorts):")
for n in ["1H EMA34", "yday EMA8", "yday EMA21", "yday close", "yday high", "yday low", "today open", "today high so far", "today low so far"]:
    print(f"  {n:18s} stop {X[X.side=='long'][f'stop@{n}'].mean()*100:4.0f}% / {X[X.side=='short'][f'stop@{n}'].mean()*100:4.0f}%   entry {X[X.side=='long'][f'entry@{n}'].mean()*100:4.0f}% / {X[X.side=='short'][f'entry@{n}'].mean()*100:4.0f}%")
X["any_stop_level"] = X[[c for c in X.columns if c.startswith("stop@")]].any(axis=1)
print(f"  stop beyond ANY of these levels: longs {X[X.side=='long'].any_stop_level.mean()*100:.0f}% / shorts {X[X.side=='short'].any_stop_level.mean()*100:.0f}%")
print(f"  results: stop at a level {st(X[X.any_stop_level])} | not {st(X[~X.any_stop_level])}")
print("\nNIFTY at the call (n / win % / mean R / mean %):")
for sd in ("long", "short"):
    for a, lab in ((True, "aligned (Nifty with the trade)"), (False, "against Nifty")):
        print(f"  {sd:5s} {lab:32s} {st(X[(X.side == sd) & (X.aligned == a)])}")
if "done5" in X:
    Y = X[X.done5.notna()]
    print(f"\nSPEED (5-min era, {len(Y)} calls): share of the way to T1 done after 5 / 10 / 15 min: median {Y.done5.median()*100:.0f}% / {Y.done10.median()*100:.0f}% / {Y.done15.median()*100:.0f}%; "
          f"WINNERS (out = target1): {Y[Y.out=='target1'].done5.median()*100:.0f}% / {Y[Y.out=='target1'].done10.median()*100:.0f}% / {Y[Y.out=='target1'].done15.median()*100:.0f}% "
          f"(n {(Y.out=='target1').sum()}); still fillable at the called price after 5 / 10 min: winners {Y[Y.out=='target1'].fill5.mean()*100:.0f}% / {Y[Y.out=='target1'].fill10.mean()*100:.0f}%, losers {Y[Y.out!='target1'].fill5.mean()*100:.0f}% / {Y[Y.out!='target1'].fill10.mean()*100:.0f}%")
