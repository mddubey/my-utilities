"""2026-10-04: at 11:15 / 12:15 the trigger is the FULL hourly bar (10:45 / 11:45 = the hour so far); at 11:45 / 12:15, setups right after a strong green 10:15 hour that closed above the 1H EMA34 (shallow pullback) are skipped.
DEFAULT (2026-10-02, user's choice): 30-min rejection candle as the trigger at the strong levels (1H 34-EMA + live
daily 8-EMA). Alarms 10:45 / 11:15 / 11:45 / 12:15 IST (43: 10:15 and 13:15+ are flat/negative). `--tf 60` = old 1H mode.
Alarm-time scan for the current best SHORT setup (watch/scratch only; nothing in production touched).
Run just after 10:15, 11:15 or 12:15 IST (1H trigger), or with `--tf 30` just after 10:45 / 11:15 / 11:45 / 12:15
(30-min trigger candle, same 1H EMA34 level and daily 8-EMA higher TF -- best in the 4-month 5m test, exploratory): `python3 38_alarm_scan_1h_close.py` (live) or `--replay 2026-10-01 11:15`.
Evaluates the 1H candle that just closed (09:15, 10:15 or 11:15 candle) on every liquid NSE stock.
Reward:risk rule (user): stop <= 1%/RR of entry, default RR 2 (stop <= 0.5%); `--rr 0` shows all.
  red candle, high >= 1H EMA34 (as of previous candle), close < EMA34, close within 0.5% of EMA34;
  1H EMA8 < EMA34; close below daily 8-EMA; day's high so far >= LIVE daily 8-EMA (2/9*close + 7/9*yesterday's EMA8);
  daily ADX(yesterday) <= 25; close below session VWAP; prior-day 20d traded value >= Rs 10 cr.
Entry = candle close, stop = candle high, target = entry -1%, exit by 15:15. Backtest: ~+0.11%/trade gross, ~50% win."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from market_regime import _compute_adx
from fetch_prices import _chunked_download
from data.paths import INTRADAY_5M_DIR
HERE = Path(__file__).resolve().parent; A8 = 2 / 9
M5 = INTRADAY_5M_DIR                   # 5-min cache (data/intraday_5m), refreshed daily by eod_checklist.sh (all ~2,300 NSE names)
SCREEN_DIST = 3.0                       # 59: prior-close screen "1H trend down + within 3% of 1H EMA34" keeps 98% of setups
BREADTH_N = 150                         # breadth from the 150 most liquid stocks (sampling error ~ +/-4%)
MIN_PRICE = 100                         # 2026-10-08 (user): no stocks under Rs100
MIN_ATR_PCT = 2.56                      # 2026-10-03: stocks whose normal daily range (ATR14 % of price, yday) is below this
                                        # rarely reach the 1% target: ~0 in BOTH the 30m (+0.010%) and 3-yr 1H (+0.002%) sets;
                                        # skipping them: 30m +0.089 -> +0.129%, 1H +0.069 -> +0.102% (cut = 30m tercile)
if "--replay" in sys.argv:
    k = sys.argv.index("--replay"); ASOF = pd.Timestamp(f"{sys.argv[k+1]} {sys.argv[k+2]}")
else:
    ASOF = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None)
TODAY = ASOF.normalize()
TF = int(sys.argv[sys.argv.index("--tf") + 1]) if "--tf" in sys.argv else 30   # DEFAULT 30 = 30-min trigger; 60 = 1H candle trigger


def late_status(g, cend, stop):
    """Where the setup stands NOW (you may run the scan minutes after the candle closed). 57 (2026-10-03): up to 20 min
    late costs ~nothing per trade; ~4-17% of setups are already dead (stop touched) -- skip those; enter only if the
    2:1 rule still holds from the current price (stop <= 0.5% above it); target = your fill - 1%."""
    after = g[g.index >= cend]
    now = g.Close.iloc[-1]; now_t = (g.index[-1] + pd.Timedelta("5min")).strftime("%H:%M")
    dead = bool(len(after) and after.High.max() >= stop)
    risk_now = (stop - now) / now * 100
    if dead: st = "DEAD (stop touched)"
    elif risk_now <= 0: st = "DEAD (above stop)"
    elif risk_now <= 0.5: st = "ENTER"
    else: st = "SKIP (2:1 gone at this price)"
    return dict(now=round(now, 2), now_at=now_t, risk_now_pct=round(risk_now, 2), target_now=round(now * 0.99, 2), status=st)


def path_levels(t, entry, upto):
    """2026-10-08 (user, INFO column, not a tested filter): every support / pivot sitting between the entry and the 1%
    target. Pivots = classic (PP, S1, S2) from yesterday (d), last completed week (w) and month (m) -- the sets
    TradingView 'Auto' draws on <=15m / 1H / daily charts. PDL = previous day's low, DL = today's low so far,
    SW = daily swing low of the last 60 sessions (lower than the 2 days on each side)."""
    tgt = entry * 0.99
    try: d = load(t)[["High", "Low", "Close"]].dropna()
    except Exception: return "?"
    d = d[d.index < TODAY]
    if len(d) < 5: return "?"
    lv = []
    def piv(tag, h, l, c):
        p = (h + l + c) / 3; lv.extend([(f"{tag}PP", p), (f"{tag}S1", 2 * p - h), (f"{tag}S2", p - (h - l))])
    piv("d", *d.iloc[-1][["High", "Low", "Close"]])
    wk = d[d.index < TODAY - pd.Timedelta(days=TODAY.weekday())]           # weeks finished before this Monday
    if len(wk):
        w = wk[wk.index >= wk.index[-1] - pd.Timedelta(days=wk.index[-1].weekday())]
        piv("w", w.High.max(), w.Low.min(), w.Close.iloc[-1])
    mo = d[d.index < TODAY.replace(day=1)]
    if len(mo):
        m = mo[mo.index >= mo.index[-1].replace(day=1)]
        piv("m", m.High.max(), m.Low.min(), m.Close.iloc[-1])
    lv.append(("PDL", d.Low.iloc[-1]))
    if len(upto): lv.append(("DL", upto.Low.min()))
    s = d.Low.tail(60).values
    lv += [("SW", s[i]) for i in range(2, len(s) - 2) if s[i] < min(s[i-2], s[i-1], s[i+1], s[i+2])]
    hits = sorted(((n, v) for n, v in lv if tgt < v < entry), key=lambda x: -x[1])
    return " | ".join(f"{n} {v:.2f}" for n, v in hits) or "-"


def read5(t):
    p = M5 / f"{t}.csv"
    if not p.exists(): return pd.DataFrame()
    x = pd.read_csv(p, index_col=0); x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[(x.Volume > 0) | (x.High != x.Low)]


def hour_key(idx):
    day = idx.normalize()
    return day + pd.Timedelta("9h15min") + ((idx - day - pd.Timedelta("9h15min")) // pd.Timedelta("60min")) * pd.Timedelta("60min")


def prep_row(args):
    """Everything known at the previous close, from LOCAL caches only (no download)."""
    t, today, prev_day = args
    try: d = load(t)
    except Exception: return None
    d = d[d.index < today]
    if len(d) < 60 or d.traded_value_sma20.iloc[-1] < 1e8: return None
    daily_ok = d.index[-1] >= prev_day
    m = read5(t); m = m[m.index < today]
    m5_ok = len(m) > 0 and m.index.max().normalize() >= prev_day
    hc = m.Close.groupby(hour_key(m.index)).last() if len(m) else pd.Series(dtype=float)
    e8 = hc.ewm(span=8, adjust=False).mean().iloc[-1] if len(hc) else np.nan
    e34 = hc.ewm(span=34, adjust=False).mean().iloc[-1] if len(hc) else np.nan
    return dict(t=t, d8y=d.Close.ewm(span=8, adjust=False).mean().iloc[-1], adx=_compute_adx(d)[0].iloc[-1], pc=d.Close.iloc[-1],
                atrp=d.atr14.iloc[-1] / d.Close.iloc[-1] * 100,
                tv=d.traded_value_sma20.iloc[-1], trend=bool(e8 < e34) if len(hc) else False,
                dist=abs(hc.iloc[-1] / e34 - 1) * 100 if len(hc) else np.nan, data_ok=bool(daily_ok and m5_ok))


def build_prep(today, prev_day):
    from multiprocessing import Pool
    uni = pd.read_csv(HERE.parent / "nse_equity_universe.csv").ticker.tolist()
    with Pool(6) as p: P = pd.DataFrame([r for r in p.map(prep_row, [(t, today, prev_day) for t in uni], chunksize=20) if r]).set_index("t")
    P["candidate"] = (P.adx <= 25) & P.trend & (P.dist <= SCREEN_DIST) & P.data_ok & (P.atrp >= MIN_ATR_PCT)
    P["breadth"] = P.index.isin(P[P.data_ok].tv.nlargest(BREADTH_N).index)
    return P


if __name__ == "__main__":
    import time; _t0 = time.time()
    REPLAY = "--replay" in sys.argv
    PREV_DAY = load("RELIANCE").loc[:TODAY - pd.Timedelta("1D")].index[-1]
    PREP = HERE / "prep" / f"prep_{TODAY:%Y%m%d}.csv"; PREP.parent.mkdir(exist_ok=True)
    if PREP.exists() and not REPLAY and "--prep" not in sys.argv:
        P = pd.read_csv(PREP, index_col=0)
    else:
        P = build_prep(TODAY, PREV_DAY)
        if not REPLAY: P.to_csv(PREP)
    stale = int((~P.data_ok).sum())
    if "--prep" in sys.argv:
        _wl = int(((P.adx <= 25) & (P.atrp >= MIN_ATR_PCT) & (P.pc >= MIN_PRICE) & P.data_ok).sum())   # same mask as the live watchlist below
        print(f"prep for {TODAY:%Y-%m-%d} (previous session {PREV_DAY:%Y-%m-%d}): {len(P)} liquid stocks, {_wl} on the watchlist "
              f"(daily ADX <= 25, daily range >= {MIN_ATR_PCT}%; 1H trend and EMA34 distance checked live at each alarm), "
              f"breadth sample {int(P.breadth.sum())} | old screen, info only: {int(P.candidate.sum())} already in a 1H downtrend "
              f"within {SCREEN_DIST:g}% of the EMA34 at yesterday's close | {time.time() - _t0:.0f}s")
        if stale: print(f"STALE DATA: {stale} stocks' caches end before {PREV_DAY:%Y-%m-%d} -- run eod_checklist.sh (excluded until then)")
        sys.exit()
    # 2026-10-04 (user): the watchlist uses only the DAILY filters (liquid, daily ADX <= 25, daily ATR >= 2.56%, fresh data)
    # -- those are defined on yesterday's values. The 1H trend and the distance to the 1H EMA34 are NOT pre-screened from
    # yesterday's close any more (that missed ~2% of setups, more on gap / wild mornings); the live checklist checks both
    # on today's bars at every alarm. Costs ~140 more stocks per fetch. `candidate` (old screen) stays in the prep file.
    # 2026-10-08 (user, logic-first universe rule): no stocks under Rs100 (yesterday's close) -- too easy to move / manipulate,
    # one tick is 0.2-0.5% of price vs a 0.3-0.5% stop. Backtest can't see that (exact stop fills); plan unchanged or better:
    # 30m +144 -> +151, 1H +32 -> +35 per trade.
    daily_ok = (P.adx <= 25) & (P.atrp >= MIN_ATR_PCT) & (P.pc >= MIN_PRICE) & P.data_ok
    C = P[daily_ok]; B = P[P.breadth]; need = sorted(set(C.index) | set(B.index))
    print(f"as of {ASOF:%Y-%m-%d %H:%M} | candidates {len(C)} + breadth sample {len(B)} -> {len(need)} stocks "
          f"{'(from cache)' if REPLAY else '| fetching live 5m...'}", flush=True)
    if stale: print(f"STALE DATA: {stale} stocks excluded (caches end before {PREV_DAY:%Y-%m-%d}) -- run eod_checklist.sh", flush=True)
    _t1 = time.time()
    if REPLAY:
        raw = {t: read5(t) for t in need}
    else:
        raw = _chunked_download([f"{t}.NS" for t in need], chunk_size=50, pause=1, period="2d", interval="5m", group_by="ticker")
    _t2 = time.time()

    def today_bars(t):
        g = raw.get(t, pd.DataFrame())
        if g is None or g.empty: return pd.DataFrame()
        g = g.dropna(subset=["Close"])
        if g.index.tz is not None: g.index = g.index.tz_convert("Asia/Kolkata").tz_localize(None)
        return g[(g.index.normalize() == TODAY) & (g.index + pd.Timedelta("5min") <= ASOF)]

    # TELEMETRY (not a filter): breadth = share of the most liquid stocks above yesterday's close (47: shorts weakest
    # when > 65% in the base 1H set; NOT confirmed with the 2:1 rule)
    up = [today_bars(t).Close.iloc[-1] > P.at[t, "pc"] for t in B.index if len(today_bars(t))]
    BREADTH = float(np.mean(up)) if up else float("nan")
    # 2026-10-03 (61): on clean data the breadth effect is inconsistent -- 3-yr 1H: bullish-breadth days weakest on average
    # (+0.051% vs +0.10-0.15%) but not every year; Jun-Sep 2026 30m: bullish-breadth days were the BEST (+0.187%). Info only.
    tag = "bullish" if BREADTH > 0.65 else ("bearish" if BREADTH < 0.35 else "mixed")
    print(f"BREADTH (info only, no consistent effect on this setup): {BREADTH*100:.0f}% of {len(up)} most liquid stocks above "
          f"yesterday's close -> {tag}", flush=True)
    rows = []; not_ready = 0; skipped_green = []; near = []
    for t in C.index:
        g = today_bars(t)
        if len(g) < 12: continue
        hist = read5(t); hist = hist[hist.index < TODAY]
        h = hist.Close.groupby(hour_key(hist.index)).last()        # 1H closes up to yesterday (same as Yahoo 60m, 59b check)
        g = g.assign(hs=hour_key(g.index))
        c1 = g.groupby("hs").agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"))
        c1 = c1[c1.index + pd.Timedelta("60min") <= ASOF]
        if TF == 60:
            if c1.empty: continue
            last = c1.index[-1]; cend = last + pd.Timedelta("60min"); hour0 = last
            if last.strftime("%H:%M") not in ("09:15", "10:15", "11:15"): continue
            o, hi, lo, cl = c1.loc[last, ["Open", "High", "Low", "Close"]]
        else:   # 30-min trigger candle, 1H EMA level of the hour it sits in -- confirmed (closed) candles only
            k30 = TODAY + pd.Timedelta("9h15min") + ((g.index - TODAY - pd.Timedelta("9h15min")) // pd.Timedelta("30min")) * pd.Timedelta("30min")
            c30 = g.groupby(k30).agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"))
            c30 = c30[c30.index + pd.Timedelta("30min") <= ASOF]
            if c30.empty: continue
            last = c30.index[-1]; cend = last + pd.Timedelta("30min")
            if cend.strftime("%H:%M") not in ("10:45", "11:15", "11:45", "12:15"): continue
            hour0 = hour_key(pd.DatetimeIndex([last]))[0]
            o, hi, lo, cl = c30.loc[last, ["Open", "High", "Low", "Close"]]
            if cend == hour0 + pd.Timedelta("60min"):
                # 2026-10-04 (68): at the hour-close alarms (11:15 / 12:15) the setup is the FULL hourly bar -- the
                # rejection is hourly, the 10:45 / 11:45 check is only an early look at the hour so far. Open / high
                # (= stop) / low from the whole hour, so the stop sits above the whole rejection (KNACK 30 Sep: 30-min
                # high 179.97 vs hourly high 180.76). 30m set: all setups +0.128% (same), plan 11:15-else-11:45 +0.120 -> +0.171%.
                seg = g[(g.index >= hour0) & (g.index < cend)]
                o, hi, lo = seg.Open.iloc[0], seg.High.max(), seg.Low.min(); last = hour0
        if cend < ASOF - pd.Timedelta("20min"): continue
        if not (g.index == cend - pd.Timedelta("5min")).any():
            not_ready += 1; continue
        closes = pd.concat([h, c1.Close[c1.index < hour0]])
        E = closes.ewm(span=34, adjust=False).mean().iloc[-1]; E8 = closes.ewm(span=8, adjust=False).mean().iloc[-1]
        # 2026-10-04 (70): don't short the first shallow pullback after a strong green hour. Previous finished hourly
        # bar green AND closed above the 1H EMA34 (E includes that bar) AND our close still above its midpoint = buyers
        # in charge, the EMA is acting as support (KNACK 30 Sep 10:15). Price-action convention; ~1 in 10 setups.
        hO = pd.concat([hist.Open.groupby(hour_key(hist.index)).first(), c1.Open[c1.index < hour0]])
        pO, pC = hO.iloc[-1], closes.iloc[-1]
        # Not after the 09:15 opening bar (gap / covering noise that tends to fade): those setups are fine (30m +Rs179,
        # 1H +Rs93 per trade); after a strong green 10:15 bar they fail (30m -17, 1H -40, 71-83% stopped). So the skip
        # applies only to the 11:45 / 12:15 checks. Plan 11:15-else-11:45: no skip +171 -> narrowed +179; 1H +117 -> +117.
        strong_green_before = hour0.strftime("%H:%M") not in ("09:15", "10:15") and pC > pO and pC > E and cl > (pO + pC) / 2
        upto = g[g.index < cend]
        vwap = ((upto.High + upto.Low + upto.Close) / 3 * upto.Volume).sum() / max(upto.Volume.sum(), 1)
        d8y = P.at[t, "d8y"]; live = A8 * cl + (1 - A8) * d8y; day_hi = upto.High.max()
        dist = (E - cl) / E * 100
        checks = dict(red=cl < o, wick_through_ema=hi >= E, close_below_ema=cl < E, within_0_5=0 < dist <= 0.5,
                      trend_1h=E8 < E, below_daily8=cl < d8y, wick_through_live_d8=day_hi >= live, below_vwap=cl < vwap)
        if all(checks.values()) and strong_green_before:
            skipped_green.append(f"{t} (stop {(hi - cl) / cl * 100:.2f}%)")
        # 2026-10-08 (user, INFO only, script 96): GREEN rejection candles (every check except red) are shown with status
        # "INFO (green candle)" and never picked; 89_eod_review.py logs their outcomes. Backtest: green net 30m -8 / 1H -43
        # vs red +45 / +21; as a later pick after red 30m +190 vs +181 but 1H +23 vs +32 -> decide on ~20 live cases.
        is_green = not checks["red"]
        # 2026-10-08: no longer shown (user: nothing actionable); still saved to the csv. Was: WARNING only -- median Rs per 5-min bar over the hour before the alarm, in lakh.
        # Jumpy / slipping names (PNGJL 12.6, AMAGI 4.9, IPCALAB 12.7) vs smooth (TECHM 182, HINDCOPPER 229); THIN < 25.
        _lh = g[(g.index >= cend - pd.Timedelta("60min")) & (g.index < cend)]
        liq_L = round(float((_lh.Volume * _lh.Close).median()) / 1e5, 1) if len(_lh) else np.nan
        warn = "THIN" if liq_L < 25 else ""
        _miss = [k for k, v in checks.items() if not v and k != "red"]
        if len(_miss) == 1:   # 2026-10-08 (user): near misses, INFO only -- exactly one non-colour check failed
            _e8p = closes.iloc[:-1].ewm(span=8, adjust=False).mean().iloc[-1]
            near.append(dict(ticker=t, cend=f"{cend:%H:%M}", missed=_miss[0], colour="red" if checks["red"] else "green",
                             ema8_falling=bool(E8 < _e8p), high=round(hi, 2), close=round(cl, 2),
                             stop_pct=round((hi - cl) / cl * 100, 2), below_ema_pct=round(dist, 2),
                             ema8_vs_ema34_pct=round((E8 - E) / E * 100, 2), atr_pct=round(P.at[t, "atrp"], 2), liq_L=liq_L, warn=warn))
        if all(v for k, v in checks.items() if k != "red"):
            rows.append(dict(ticker=t, candle=f"{last:%H:%M}-{cend:%H:%M}" + (" (full hour)" if cend - last == pd.Timedelta("60min") else ""), entry=round(cl, 2), stop=round(hi, 2), stop_pct=round((hi - cl) / cl * 100, 2),
                             target=round(cl * 0.99, 2), ema34_1h=round(E, 2), below_ema_pct=round(dist, 2), live_d8=round(live, 2),
                             day_high=round(day_hi, 2), adx=round(P.at[t, "adx"], 1), ema8_1h=round(E8, 2),
                             ema8_below_pct=round((cl - E8) / cl * 100, 2), green_skip=bool(strong_green_before),
                             cend=f"{cend:%H:%M}", liq_L=liq_L, warn=warn, in_path=path_levels(t, cl, upto), **late_status(g, cend, hi)))
            if strong_green_before: rows[-1]["status"] = "SKIP (strong green hour before)"
            if is_green: rows[-1]["status"] = f"INFO (green candle; {rows[-1]['status']})"
        elif cend >= TODAY + pd.Timedelta("10h45min") and not strong_green_before:
            # 2026-10-09 (user, INFO only -- user may still take it after a chart look; script 112): OPENING REJECTION +
            # LOWER HIGH. The 09:15 hour's high reached the live daily 8-EMA and that hour closed below it (opening spike
            # rejected at daily resistance); now a red candle rejects the 1H EMA8 (close below it by <= 0.5%) with a high
            # below the opening hour's high; EMA8 < EMA34, below yesterday's daily 8-EMA, below VWAP. Backtest (setups):
            # 1H +31 net every year (n 1817), 30m +13; best at the 10:45 / 11:15 signals (+44..+63).
            oh = g[(g.index >= TODAY + pd.Timedelta("9h15min")) & (g.index < TODAY + pd.Timedelta("10h15min"))]
            if len(oh) >= 10:
                ohi, ocl = oh.High.max(), oh.Close.iloc[-1]; olive = A8 * ocl + (1 - A8) * d8y
                d8 = (E8 - cl) / E8 * 100
                if (ohi >= olive and ocl < olive and cl < o and hi >= E8 and 0 < d8 <= 0.5 and hi < ohi and E8 < E
                        and cl < d8y and cl < vwap):
                    rows.append(dict(ticker=t, candle=f"{last:%H:%M}-{cend:%H:%M}" + (" (full hour)" if cend - last == pd.Timedelta("60min") else ""), entry=round(cl, 2), stop=round(hi, 2), stop_pct=round((hi - cl) / cl * 100, 2),
                                     target=round(cl * 0.99, 2), ema34_1h=round(E, 2), below_ema_pct=round(dist, 2), live_d8=round(live, 2),
                                     day_high=round(day_hi, 2), adx=round(P.at[t, "adx"], 1), ema8_1h=round(E8, 2),
                                     ema8_below_pct=round((cl - E8) / cl * 100, 2), green_skip=False,
                                     cend=f"{cend:%H:%M}", liq_L=liq_L, warn=warn, in_path=path_levels(t, cl, upto), **late_status(g, cend, hi)))
                    rows[-1]["status"] = f"INFO (opening rejection; {rows[-1]['status']})"
    R = pd.DataFrame(rows)
    if skipped_green:
        _rr = float(sys.argv[sys.argv.index("--rr") + 1]) if "--rr" in sys.argv else 2.0
        _real = [x for x in skipped_green if _rr <= 0 or float(x.split("stop ")[1].rstrip("%)")) <= 1.0 / _rr]
        if _real: print(f"skipped, would otherwise qualify (shallow pullback right after a strong green hour): {', '.join(_real)}")
    if not_ready:
        many = not_ready > 0.2 * max(len(C), 1)
        print(f"{'DATA NOT READY' if many else 'note'}: {not_ready} stocks have no last 5-min bar for the alarm candle yet "
              f"({'Yahoo lag -- run again in a minute' if many else 'a few is normal: no trades in that slot'})", flush=True)
    print(f"[timing] prep {_t1 - _t0:.0f}s | 5m {'cache' if REPLAY else 'fetch'} {_t2 - _t1:.0f}s | setup checks {time.time() - _t2:.0f}s", flush=True)
    RR = float(sys.argv[sys.argv.index("--rr") + 1]) if "--rr" in sys.argv else 2.0
    if RR > 0 and len(R):
        n0 = len(R); R = R[R.stop_pct <= 1.0 / RR]; print(f"reward:risk >= {RR:g}:1 -> kept {len(R)} of {n0} (stop <= {1/RR:.2f}%)")
    if len(R): R["breadth_pct"] = round(BREADTH * 100)
    outdir = HERE / "replays" if REPLAY else HERE; outdir.mkdir(exist_ok=True)   # replays never overwrite live alarm files
    out = outdir / f"alarm_scan_{'30m_' if TF == 30 else ''}{ASOF:%Y%m%d_%H%M}.csv"; R.to_csv(out, index=False)
    def print_near():
        if not near: return
        N = pd.DataFrame(near); N["_ok"] = N.stop_pct <= 0.5; N["_d"] = N.below_ema_pct.abs()
        N = N.sort_values(["_ok", "_d"], ascending=[False, True]).drop(columns=["_ok", "_d"])
        N.to_csv(out.with_name("near_" + out.name), index=False)   # read by 89_eod_review.py
        N = N.drop(columns=["cend", "high", "ema8_falling", "liq_L", "warn"])
        if "--near" not in sys.argv: return   # 2026-10-08 (user): hidden by default; csv still saved for the EOD review
        print(f"\nNEAR MISSES (info only, never a pick): failed exactly one check; stop <= 0.5% first, then closest to the EMA34."
              f" ema8_vs_ema34 > 0 = 1H uptrend\n" + N.head(25).to_string(index=False))
    if R.empty: print("no setups at this alarm"); print_near(); sys.exit()
    R = R.sort_values("below_ema_pct")
    # 2026-10-03 (56): after the checklist + 2:1 rule no further filter reliably separates better from worse setups,
    # so every qualifying setup is shown (user: equal quality -> show them all, watch them, learn). The first-come one
    # (first alarm with a setup; same alarm -> closest to EMA) is marked for days only one trade is taken.
    # 2026-10-04 (user's hard rule, TELEMETRY -- not backtest-proven): 1H EMA8 0.4-0.6% below the candle close lost on all
    # setups in both data sets (more stops); the user skips these, the pick passes to the next ENTER, and the skipped
    # setup is still saved here so its outcome can be checked later.
    zone = (R.ema8_below_pct > 0.4) & (R.ema8_below_pct <= 0.6) & (R.status == "ENTER")
    R.loc[zone, "status"] = "SKIP (EMA8 0.4-0.6% below)"
    live_ix = [i for i, v in enumerate(R.status) if v == "ENTER"]
    R.insert(0, "pick", ["FIRST COME" if i == (live_ix[0] if live_ix else -1) else "" for i in range(len(R))])
    print(f"\n{len(R)} SHORT setup(s), all equal quality after the filters. status = where it stands NOW; enter only 'ENTER' ones,"
          f" target = your fill - 1%. FIRST COME = first ENTER, the one-trade-a-day choice:\n")
    show = ["pick", "status", "ticker", "candle", "now", "now_at", "stop", "risk_now_pct", "target_now", "entry", "in_path"]
    pd.set_option("display.width", 200)
    print(R[show].rename(columns={"risk_now_pct": "stop%_now", "target_now": "target", "entry": "candle_close", "below_ema_pct": "below_ema%", "ema8_below_pct": "ema8_below%"}).to_string(index=False))
    R.to_csv(out, index=False); print(f"saved {out.name}")
    print_near()
