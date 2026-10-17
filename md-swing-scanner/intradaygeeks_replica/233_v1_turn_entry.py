"""v1 WITH THE USER'S ENTRY: sell the 1H EMA34 rejection AS IT FORMS, not at the hour close (user, 2026-10-17: 'I am not waiting for the
whole candle to end ... if you would have entered even 10:45 the whole move was gone, and I wouldn't enter at 11:15 because that is so far
from the 34 MA'). Spec fixed before running (go-ahead 2026-10-17):
  Data: 30m set (5-min bars 2026-06..10, official open) -- ALL with Nifty below its 200-day, so this is v1 with the gate OFF, bear phase.
  Line: the 1H EMA34 as of the last completed hourly bar (09:15-aligned 60-min cache, 3-year warm-up), fixed for the hour.
  Day filters (v1's, known at the open): prev-day median 5-min turnover >= Rs15 lakh, prev close >= Rs100, daily ATR14 >= 2%,
    gap -0.25..+0.5%; shown with and without the stock daily 8 > 34 uptrend.  Plus the daily 8 TOUCH (yesterday's EMA8) NOT between
    the entry and the 1% target (232's filter); removed group shown.
  EVENT (first per stock-day, bars starting 09:30..13:10): previous 5-min close below the line, bar high >= line x (1 - 0.05%) = touch.
    Running high from the touch. TURN = price trades X below the running high -> SELL there (fill = trigger, or the bar open if it opened
    below the trigger on a later bar). X = 0.1% and 0.2%. Abandon the event if the running high goes > 0.3% above the line (breakout) or
    no turn within 6 bars (30 min); scanning then continues for a new touch.
  Stops: TIGHT = running high + 0.05%;  FIXED = entry + 0.5% (~ the user's live stops 0.53-0.55%).  1% target, else out at the 15:15
    close; stop first on a tie; no trailing.
  Hour of entry: 09:30-10:15 / 10:15-11:15 / 11:15-12:15 / 12:15-13:15.
  SAME-EVENT COMPARISON: v1's way = the hourly candle that holds the touch closes red, below the line, high >= line, stop = hour high
    <= 0.5% -> short at the hour close; how often it qualifies, how far its entry is below the line, and both results on matched events.
  Net Rs per Rs1 lakh (ret - 0.085%), Rs per Rs1k risk, target / stall / stop, by month, top-10 days removed.
  FIXES 2026-10-17 (user's ABREL 2026-07-13 chart check; earlier results SUPERSEDED): (1) a turn inside the touch bar counts only if
    that bar CLOSES at / below the sell price, else a sell-stop rests from the next bar (entry bar can stop us, counted against us);
    (2) 'from below' also needs the last COMPLETED hourly candle closed below the line (ABREL sat on the 34 from above all day).
  Hand checks: ABREL 2026-07-13 must give NO event; KALYANKJIL 2026-10-16 (user short 560 ~11:20, line 561.23), BAJFINANCE 2026-10-15 (user 963; gap -0.53 = outside the gap zone)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from orb_common import read5_official
from data.paths import DAILY_DIR, INTRADAY_5M_DIR, INTRADAY_60M_DIR
COST = 0.085; TOUCH = 0.0005; MAXUP = 0.003; WAIT = 6; XS = (0.001, 0.002)
HOURS = [("09:30-10:15", "09:30", "10:15"), ("10:15-11:15", "10:15", "11:15"), ("11:15-12:15", "11:15", "12:15"), ("12:15-13:15", "12:15", "13:15")]


def walk(H, L, C, i0, e, stop, last):
    tg = e * 0.99
    for k in range(i0, last + 1):
        if H[k] >= stop: return (e - stop) / e * 100, "stop"
        if L[k] <= tg: return 1.0, "target"
    return (e - C[last]) / e * 100, "stall"


def run(t):
    try:
        m = read5_official(t)
        d = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).sort_index(); d = d[~d.index.duplicated()].dropna(subset=["Close"])
        h = pd.read_csv(INTRADAY_60M_DIR / f"{t}.csv", index_col=0)
    except Exception: return []
    h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None); h = h[~h.index.duplicated()].sort_index().dropna(subset=["Close"])
    e34h = h.Close.ewm(span=34, adjust=False).mean(); hidx = h.index.values
    tr = pd.concat([d.High - d.Low, (d.High - d.Close.shift()).abs(), (d.Low - d.Close.shift()).abs()], axis=1).max(axis=1)
    dl = pd.DataFrame({"pc": d.Close, "atr": tr.rolling(14).mean() / d.Close * 100, "s8": d.Close.ewm(span=8, adjust=False).mean(),
                       "s34": d.Close.ewm(span=34, adjust=False).mean()}).shift(1)
    md = m.index.normalize(); days = sorted(set(md)); out = []
    for a in range(1, len(days)):
        D, P = days[a], days[a - 1]
        if D not in dl.index: continue
        lv = dl.loc[D]
        if not (lv.pc == lv.pc and lv.atr == lv.atr): continue
        pv = m[(md == P) & (m.Volume > 0)]
        liq = (pv.Volume * pv.Close).median() / 1e5 if len(pv) else 0
        g = m[md == D]; ts = g.index; hm = ts.strftime("%H:%M").values
        if len(g) < 60 and not ((t, D) in {("KALYANKJIL", pd.Timestamp("2026-10-16")), ("BAJFINANCE", pd.Timestamp("2026-10-15"))}): continue
        O, H, L, C = g.Open.values, g.High.values, g.Low.values, g.Close.values
        lasts = np.where(hm <= "15:10")[0]
        if not len(lasts): continue
        last = lasts[-1]
        # line per 5-min bar: EMA34 after the last hourly bar that ENDED by this bar's hour start
        hstart = ts.floor("60min") + pd.Timedelta("15min"); hstart = hstart.where(hstart <= ts, hstart - pd.Timedelta("60min"))
        pos = np.searchsorted(hidx, (hstart - pd.Timedelta("60min")).values, side="right") - 1
        line = np.where(pos >= 0, e34h.values[np.clip(pos, 0, None)], np.nan)
        hclose = np.where(pos >= 0, h.Close.values[np.clip(pos, 0, None)], np.nan)   # FIX 2: the last COMPLETED hourly close
        base = dict(ticker=t, date=D.strftime("%Y-%m-%d"), ov=(O[0] / line[0] - 1) * 100 if line[0] == line[0] else np.nan, liq=liq, pc=lv.pc, atr=lv.atr, gap=(O[0] / lv.pc - 1) * 100, up=bool(lv.s8 > lv.s34), s8=lv.s8)
        for X in XS:
            i = 1; ev = None
            while i < last:
                if hm[i] < "09:30" or hm[i] > "13:10" or not line[i] == line[i]: i += 1; continue
                if not (C[i - 1] < line[i] and hclose[i] < line[i] and H[i] >= line[i] * (1 - TOUCH)): i += 1; continue
                lvl = line[i]; hi = -1.0; done = None
                for j in range(i, min(i + WAIT, last)):
                    if j > i and hm[j] > "13:10": break
                    if j == i:
                        # FIX 1 (2026-10-17, ABREL chart check): inside the touch bar the order is unknown -- count a turn only if the bar
                        # CLOSES at / below the sell price (the drop came after the high); otherwise a sell-stop rests from the next bar
                        hi = H[j]
                        if hi > lvl * (1 + MAXUP): break
                        trig = hi * (1 - X)
                        if C[j] <= trig: e = trig; done = (j, e, hi); break
                        continue
                    trig = hi * (1 - X)                      # resting sell-stop from the high known BEFORE this bar
                    if L[j] <= trig:
                        e = min(O[j], trig); done = (j, e, hi); break      # tight stop = high known when the order rested
                    hi = max(hi, H[j])
                    if hi > lvl * (1 + MAXUP): break
                if done is None:
                    i += 1
                    while i < last and C[i - 1] >= line[i]: i += 1     # wait until price is back under the line
                    continue
                j, e, hi = done; ev = dict(base, X=X, t_touch=hm[i], t_entry=hm[j], line=lvl, entry=e, hi=hi, same_bar=(j == i),
                                           in_path=bool(e * 0.99 < lv.s8 < e))
                for nm, s in (("tight", hi * (1 + TICK)), ("fixed", e * 1.005)):
                    r, w = walk(H, L, C, j + 1, e, s, last) if j == i else ((e - s) / e * 100, "stop") if H[j] >= s else walk(H, L, C, j + 1, e, s, last); ev[f"{nm}_ret"], ev[f"{nm}_why"], ev[f"{nm}_risk"] = r, w, (s - e) / e * 100
                # v1's way on the same event: the hourly candle holding the touch
                hs = hstart[i]; hb = np.where((ts >= hs) & (ts < hs + pd.Timedelta("60min")))[0]
                ev["v1_ok"] = False
                if len(hb) and hb[-1] < last:
                    ho, hh, hc = O[hb[0]], H[hb].max(), C[hb[-1]]
                    if hc < ho and hc < lvl and hh >= lvl and (hh / hc - 1) <= 0.005:
                        r, w = walk(H, L, C, hb[-1] + 1, hc, hh, last)
                        ev.update(v1_ok=True, v1_entry=hc, v1_time=(ts[hb[-1]] + pd.Timedelta("5min")).strftime("%H:%M"), v1_below_line=(hc / lvl - 1) * 100,
                                  v1_ret=r, v1_why=w, v1_risk=(hh / hc - 1) * 100)
                break
            if ev: out.append(ev)
    return out


TICK = 0.0005
if __name__ == "__main__":
    from multiprocessing import Pool
    uni = [f.stem for f in INTRADAY_5M_DIR.glob("*.csv") if not f.stem.startswith("_")]
    with Pool(6) as p: A = pd.DataFrame([r for rr in p.map(run, uni, chunksize=20) for r in rr])
    A.to_csv(HERE / "v1_turn_entry.csv", index=False)
    F = A[(A.liq >= 15) & (A.pc >= 100) & (A.atr >= 2) & (A.gap > -0.25) & (A.gap <= 0.5)].copy()
    print(f"events (all stocks) {len(A)}; after v1 day filters {len(F)} ({F.date.min()} .. {F.date.max()}, {F.date.nunique()} days)")

    def cells(x, s):
        if not len(x): return "0 | | | |"
        w = x[f"{s}_why"]; r = x[f"{s}_ret"]
        return (f"{len(x)} | {(w=='target').mean()*100:.0f} / {(w=='stall').mean()*100:.0f} / {(w=='stop').mean()*100:.0f}% | {x[f'{s}_risk'].median():.2f}% | "
                f"{(r.mean()-COST)*1000:+.0f} | {((r - COST) / x[f'{s}_risk']).mean()*1000:+.0f}")
    HDR = "| group | n | target / stall / stop | med stop | net Rs @1L | Rs @1k risk |\n|---|---|---|---|---|---|"
    for X in XS:
        x0 = F[F.X == X]
        for s in ("tight", "fixed"):
            print(f"\n### Turn {X*100:.1f}% below the touch high, {s.upper()} stop\n{HDR}")
            for lab, x in (("all (gate off, both trends)", x0), ("KEPT daily 8 not in path", x0[~x0.in_path]), ("removed: daily 8 in path", x0[x0.in_path]),
                           ("KEPT + uptrend (v1 trend)", x0[~x0.in_path & x0.up]), ("KEPT + downtrend", x0[~x0.in_path & ~x0.up])):
                print(f"| {lab} | {cells(x, s)} |")
            k = x0[~x0.in_path]
            top10 = k.groupby("date")[f"{s}_ret"].sum().nlargest(10).index
            print(f"| KEPT, top-10 days removed | {cells(k[~k.date.isin(top10)], s)} |")
            for lab, a, b in HOURS: print(f"| KEPT, entry {lab} | {cells(k[(k.t_entry >= a) & (k.t_entry < b)], s)} |")
            for mo, g in k.groupby(k.date.str[:7]): print(f"| KEPT, month {mo} | {cells(g, s)} |")
            print(f"| KEPT, turn in the touch bar itself | {cells(k[k.same_bar], s)} |")
    print("\n### SAME EVENTS, v1's way (wait for the hourly candle to close red under the line) vs the turn entry -- X 0.1%, KEPT")
    k = F[(F.X == 0.001) & ~F.in_path]; v = k[k.v1_ok]
    print(f"v1's hour-close trigger qualifies on {len(v)} of {len(k)} turn events ({len(v)/len(k)*100:.0f}%); its entry sits a median {v.v1_below_line.median():.2f}% "
          f"under the line (turn entry {((k.entry / k.line - 1) * 100).median():.2f}%), median stop {v.v1_risk.median():.2f}%")
    print(f"| matched events ({len(v)}) | turn TIGHT {cells(v, 'tight')} |\n| | turn FIXED {cells(v, 'fixed')} |\n| | v1 hour close {cells(v, 'v1')} |")
    print(f"| turn events v1 never triggers ({len(k) - len(v)}) | turn FIXED {cells(k[~k.v1_ok], 'fixed')} |")
    # FIX (2026-10-17, found in the first run): the comparison above conditions on the hour closing red under the line -- known only
    # AFTER the turn entry (hindsight for the turn), and the turn population is far broader than v1's (v1 qualified on 5%). Fair version:
    # v1's own stock-days known at the open (uptrend, gap zone, branch A = opened 0-0.5% below the 1H EMA34, B = opened above and ATR >= 3),
    # every first touch-and-turn that day, no condition on how the hour closed; v1's hour close scored per setup (no trade = Rs0).
    V1 = F[F.up & (((F.ov >= -0.5) & (F.ov < 0)) | ((F.ov >= 0) & (F.atr >= 3)))]
    print("\n### FAIR: v1's own stock-days (uptrend + branch A / B), turn entry vs v1's hour close, per setup (v1 no-trade = Rs0)")
    print("| version | n | target / stall / stop | med stop | net Rs @1L | Rs @1k |\n|---|---|---|---|---|---|")
    for X in XS:
        for path_lab, pp in (("all", None), ("daily 8 not in path", False)):
            x = V1[V1.X == X] if pp is None else V1[(V1.X == X) & (V1.in_path == pp)]
            for s in ("tight", "fixed"): print(f"| turn {X*100:.1f}% {s}, {path_lab} | {cells(x, s)} |")
            v = x[x.v1_ok]; per = ((v.v1_ret - COST) * 1000).sum() / max(len(x), 1)
            print(f"| v1 hour close on the same days, {path_lab} | {cells(v, 'v1')} (traded {len(v)} of {len(x)}; per setup incl. no-trade Rs{per:+.0f}) |")
        for lab, a, b in HOURS:
            x = V1[(V1.X == X) & ~V1.in_path & (V1.t_entry >= a) & (V1.t_entry < b)]
            print(f"| turn {X*100:.1f}% fixed, daily 8 not in path, entry {lab} | {cells(x, 'fixed')} |")
    print("\nHAND CHECKS (no day filters):")
    for t, dd in (("KALYANKJIL", "2026-10-16"), ("BAJFINANCE", "2026-10-15"), ("ABREL", "2026-07-13")):
        h = A[(A.ticker == t) & (A.date == dd)]
        print(h[["ticker", "date", "X", "t_touch", "t_entry", "line", "hi", "entry", "gap", "up", "in_path", "tight_why", "fixed_why", "v1_ok"]].round(2).to_string(index=False) if len(h) else f"  {t} {dd}: NO EVENT")
