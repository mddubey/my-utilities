"""LIVE scan: in-play opening-range-break SHORT (scripts 175-184; user, 2026-10-11). Run ~09:21-09:29 IST for the list, again any
time after 09:30 to see status. Rules as backtested (183/184 = the user's version):
  universe   NSE EQ, yesterday's close >= Rs100, 20-day traded value >= Rs10 cr, daily ATR >= 2%, previous day's median 5-min bar
             turnover >= Rs15 lakh (the live liquidity rule), fresh caches.
  in play    relative volume = today's 09:15-09:20 volume / its 14-day average (>= 10 days), >= 1 AND top 20 of the day.
             Yahoo's 09:15 5-min bar has 0 volume, so: first-bar volume = today's running DAY volume (Yahoo 1d bar) - the 5-min bars
             from 09:20 on (same estimate as the backtest: day volume - other bars; checked median 1.01 vs real).
  setup      09:15 candle RED -> short a break of its low (green = long, shown for info only: longs failed the 1-min check).
  orders     ONLY FROM 09:30 (183): if the low already broke 09:20-09:29 -> SKIP. Else place a SELL-STOP (SL) at the trigger
             (= 09:15 low), protective BUY SL-M at the stop. Stop = trigger x (1 + k x ATR%), k = 0.10 (tight) or 0.20 (wide) --
             not chosen yet, both shown. Qty for Rs1,000 risk.
  exit       stop, or square off at ~14:15-15:15 (184: 14:15 ~ 15:15; nothing before ~12:15). NO target.
Telemetry column `room` (2026-10-12): distance from the trigger to yesterday's close below a short (gap fill; NEAR < 1% = the group that
lost in 191/192) / to yesterday's high above a long. Info only, not a skip.
Log every fill: trigger vs actual fill, stop vs actual stop fill (182: the edge survives ~0.05% slip per side, not 0.15%).
Usage: python3 185_orb_inplay_scan.py --prep [--date YYYY-MM-DD]   (evening before / before 09:15; local caches only)
       python3 185_orb_inplay_scan.py                              (live)
       python3 185_orb_inplay_scan.py --replay YYYY-MM-DD HH:MM     (past day from caches, to check the scan against 175)"""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from fetch_prices import _chunked_download
from data.paths import DAILY_DIR, INTRADAY_5M_DIR
from data.fetch_nse_mtf import latest_before as mtf_latest_before

TOP_N, MIN_RV, MIN_PRICE, MIN_TV, MIN_ATR, MIN_LIQ_L = 20, 1.0, 100, 1e8, 2.0, 15
K_TIGHT, K_WIDE, RISK_RS, MAX_TRADES = 0.10, 0.20, 1000, 2


def read5(t):
    p = INTRADAY_5M_DIR / f"{t}.csv"
    if not p.exists(): return pd.DataFrame()
    x = pd.read_csv(p, index_col=0); x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x


def prep_row(args):
    """Known at the previous close, local caches only."""
    t, today, prev_day = args
    try: d = load(t)
    except Exception: return None
    d = d[d.index < today]
    if len(d) < 60 or d.traded_value_sma20.iloc[-1] < MIN_TV or d.Close.iloc[-1] < MIN_PRICE: return None
    atrp = d.atr14.iloc[-1] / d.Close.iloc[-1] * 100
    if atrp < MIN_ATR: return None
    raw = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).Volume
    m = read5(t); m = m[m.index < today]
    if len(m) == 0: return None
    m = m.assign(day=m.index.normalize(), hm=m.index.strftime("%H:%M"))
    v0 = {}
    for dd, g in m.groupby("day"):
        if g.hm.iloc[0] == "09:15" and len(g) >= 70 and dd in raw.index:
            x = raw[dd] - g.Volume.iloc[1:].sum()
            if x > 0: v0[dd] = x
    v0 = pd.Series(v0).sort_index().tail(14)
    last = m[m.day == m.day.max()]; liq = (last.Volume * last.Close)[last.Volume > 0].median() / 1e5
    mv = m[m.Volume > 0]; liq5 = ((mv.Volume * mv.Close).groupby(mv.day).median() / 1e5).tail(5).median()   # 2026-10-13 CHECK: one busy day can't vouch for a thin stock
    # 2026-10-13 (user): yesterday's daily EMA8 / EMA21 = TODAY'S TOUCH PRICES (the live daily EMA meets price exactly there; fixed all day)
    e8y = d.Close.ewm(span=8, adjust=False).mean().iloc[-1]; e21y = d.Close.ewm(span=21, adjust=False).mean().iloc[-1]
    return dict(t=t, pc=d.Close.iloc[-1], ph=d.High.iloc[-1], atrp=atrp, e8y=e8y, e21y=e21y, tv=d.traded_value_sma20.iloc[-1], liq_L=liq, liq5_L=liq5,
                v0avg=v0.mean() if len(v0) >= 10 else np.nan, n_v0=len(v0),
                data_ok=bool(d.index[-1] >= prev_day and m.day.max() >= prev_day))


def build_prep(today, prev_day):
    from multiprocessing import Pool
    uni = pd.read_csv(HERE.parent / "nse_equity_universe.csv").ticker.tolist()
    with Pool(6) as p: P = pd.DataFrame([r for r in p.map(prep_row, [(t, today, prev_day) for t in uni], chunksize=20) if r]).set_index("t")
    return P


if __name__ == "__main__":
    t0 = time.time(); REPLAY = "--replay" in sys.argv
    if REPLAY:
        i = sys.argv.index("--replay"); TODAY = pd.Timestamp(sys.argv[i + 1]); ASOF = pd.Timestamp(f"{sys.argv[i + 1]} {sys.argv[i + 2]}")
    elif "--date" in sys.argv:
        TODAY = pd.Timestamp(sys.argv[sys.argv.index("--date") + 1]); ASOF = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None)
    else:
        ASOF = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None); TODAY = ASOF.normalize()
    PREV_DAY = load("RELIANCE").loc[:TODAY - pd.Timedelta("1D")].index[-1]
    PREP = HERE / "prep" / f"orb_prep_{TODAY:%Y%m%d}.csv"; PREP.parent.mkdir(exist_ok=True)
    if PREP.exists() and not REPLAY and "--prep" not in sys.argv: P = pd.read_csv(PREP, index_col=0)
    else:
        P = build_prep(TODAY, PREV_DAY)
        if not REPLAY: P.to_csv(PREP)
    stale = int((~P.data_ok).sum())
    # 2026-10-22 (user, after PRIVISCL): thin stocks are FILTERED, not just flagged -- yesterday AND the 5-day median must pass
    U = P[P.data_ok & (P.liq_L >= MIN_LIQ_L) & (P.liq5_L >= MIN_LIQ_L) & P.v0avg.notna()]
    if "--prep" in sys.argv:
        print(f"ORB prep for {TODAY:%Y-%m-%d} (previous session {PREV_DAY:%Y-%m-%d}): {len(P)} stocks pass price/value/ATR, "
              f"{len(U)} also liquid (>= Rs{MIN_LIQ_L} lakh/5m) with a first-bar volume history | {time.time()-t0:.0f}s")
        if stale: print(f"STALE DATA: {stale} stocks' caches end before {PREV_DAY:%Y-%m-%d} -- run eod_checklist.sh first")
        sys.exit()
    if stale > len(P) * 0.2: print(f"WARNING: {stale} of {len(P)} stocks have STALE caches (before {PREV_DAY:%Y-%m-%d}) -- run eod_checklist.sh", flush=True)
    if not REPLAY and ASOF < TODAY + pd.Timedelta("9h20min"):
        print("Too early: the 09:15 candle closes at 09:20. Run again after ~09:21."); sys.exit()
    need = list(U.index)
    print(f"as of {ASOF:%Y-%m-%d %H:%M} | {len(need)} liquid stocks | {'replay from cache' if REPLAY else 'fetching live 5-min + day volume...'}", flush=True)
    if REPLAY:
        bars = {t: read5(t) for t in need}
        _dd = {t: pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True) for t in need}
        dayvol = {t: x.Volume.get(TODAY, np.nan) for t, x in _dd.items()}; dayopen = {t: x.Open.get(TODAY, np.nan) for t, x in _dd.items()}
    else:
        bars = _chunked_download([f"{t}.NS" for t in need], chunk_size=50, pause=1, period="1d", interval="5m", group_by="ticker")
        dl = _chunked_download([f"{t}.NS" for t in need], chunk_size=50, pause=1, period="5d", interval="1d", group_by="ticker")
        dayvol, dayopen = {}, {}
        for t, g in dl.items():
            if g is None or g.empty: continue
            g = g.dropna(subset=["Close"]); gi = g.index.tz_localize(None) if g.index.tz is not None else g.index
            g.index = gi.normalize(); dayvol[t] = g.Volume.get(TODAY, np.nan); dayopen[t] = g.Open.get(TODAY, np.nan)
    t1 = time.time(); rows = []; neg = 0
    for t in need:
        g = bars.get(t, pd.DataFrame())
        if g is None or g.empty: continue
        g = g.dropna(subset=["Close"])
        if g.index.tz is not None: g.index = g.index.tz_convert("Asia/Kolkata").tz_localize(None)
        g = g[(g.index.normalize() == TODAY) & (g.index < ASOF)]          # includes the bar in progress (its volume is in day volume too)
        g = g.assign(hm=g.index.strftime("%H:%M"))
        if len(g) == 0 or g.hm.iloc[0] != "09:15": continue
        f = g.iloc[0].copy()
        # 2026-10-12 (user caught ADANIENT 2026-09-01 green on Dhan, red here): use the OFFICIAL open (Yahoo 1d bar = NSE open) for
        # the 09:15 candle, and extend its high/low to it -- the candle as Dhan / TradingView draw it.
        oo = dayopen.get(t, np.nan)
        if oo == oo: f["Open"] = oo; f["High"] = max(f.High, oo); f["Low"] = min(f.Low, oo)
        if TODAY + pd.Timedelta("9h20min") > ASOF: continue
        dv = dayvol.get(t, np.nan)
        if REPLAY:   # full-day volume minus every other bar of the day (the backtest's estimate)
            full = read5(t); full = full[full.index.normalize() == TODAY]; v0 = dv - full.Volume.iloc[1:].sum()
        else: v0 = dv - g.Volume.iloc[1:].sum()
        if not (v0 > 0): neg += 1; continue
        done = g[g.index + pd.Timedelta("5min") <= ASOF]; after = g.iloc[1:]
        side = "SHORT" if f.Close < f.Open else ("long (info)" if f.Close > f.Open else "doji")
        if side == "doji": continue
        trig = f.Low if side == "SHORT" else f.High
        brk = after[after.Low < trig] if side == "SHORT" else after[after.High > trig]
        first_brk = brk.hm.iloc[0] if len(brk) else None
        if first_brk is None: status = "ARMED: place order at 09:30" if ASOF < TODAY + pd.Timedelta("9h30min") else "ARMED (not triggered yet)"
        elif first_brk < "09:30": status = f"SKIP: broke {first_brk} (before 09:30)"
        else: status = f"TRIGGERED {first_brk}"
        k = 1 if side == "SHORT" else -1; atr = U.at[t, "atrp"]
        st1, st2 = trig * (1 + k * K_TIGHT * atr / 100), trig * (1 + k * K_WIDE * atr / 100)
        last = g.Close.iloc[-1]
        # TELEMETRY (2026-10-12, user; scripts 191-193): room to yesterday's close below a short (the gap-fill level -- within 1%
        # it turned price 83% of the time vs 41-62% placebo, -524/trade) and to yesterday's high above a long (weak effect). Info only.
        if side == "SHORT":
            yc = U.at[t, "pc"]; room = (trig - yc) / trig * 100 if yc < trig else None; lvl_name = "y_close"
        else:
            yh = U.at[t, "ph"] if "ph" in U.columns else np.nan; room = (yh - trig) / trig * 100 if yh > trig else None; lvl_name = "y_high"
        room_s = f"{lvl_name} {room:.2f}% away" + (" (NEAR <1%)" if room < 1 else "") if room is not None else f"{lvl_name}: not in the way"
        rows.append(dict(ticker=t, side=side, relvol=v0 / U.at[t, "v0avg"], status=status, room=room_s, trigger=round(trig, 2), now=round(last, 2),
                         stop_tight=round(st1, 2), qty_tight=int(RISK_RS / abs(st1 - trig)) if st1 != trig else 0,
                         stop_wide=round(st2, 2), qty_wide=int(RISK_RS / abs(st2 - trig)) if st2 != trig else 0,
                         atr=round(atr, 2), liq_L=round(U.at[t, "liq_L"], 1), liq5_L=round(U.at[t, "liq5_L"], 1) if "liq5_L" in U else np.nan,
                         d8_touch=round(U.at[t, "e8y"], 2) if "e8y" in U else np.nan, d8_touch_pct=round((U.at[t, "e8y"] / last - 1) * 100, 2) if "e8y" in U else np.nan,
                         d21_touch=round(U.at[t, "e21y"], 2) if "e21y" in U else np.nan, c915=f"{f.Open:.2f}->{f.Close:.2f} (L {f.Low:.2f} H {f.High:.2f})",
                         o915=f.Open, h915=f.High, l915=f.Low, cl915=f.Close))
    R = pd.DataFrame(rows)
    print(f"[timing] fetch {t1 - t0:.0f}s, checks {time.time() - t1:.0f}s | first-bar volume could not be estimated for {neg} stocks (negative / missing day volume)")
    if R.empty: print("no data -- market not open yet, Yahoo lagging, or caches stale"); sys.exit()
    R = R[R.relvol >= MIN_RV].sort_values("relvol", ascending=False).head(TOP_N)
    R.insert(0, "rank", range(1, len(R) + 1))
    # 2026-10-12 LIVE RULES (user): tight stop (10% ATR), Rs1,000 risk, MAX 2 trades; SHORTS first, skip a short whose gap fill
    # (yesterday's close) is < 1% below (191-192); LONGS only as a fallback when fewer than 2 shorts are valid. Pick = highest relvol
    # (177: relvol rank <= 5 was the one filter that passed). Arm only the picks -- no need to cancel orders later.
    valid = R.status.str.startswith(("ARMED", "TRIGGERED"))
    S = R[R.side == "SHORT"]; near = S.room.str.contains("NEAR")
    shorts_ok = S[valid[S.index] & ~near]; longs_ok = R[(R.side != "SHORT") & valid]
    picks = pd.concat([shorts_ok, longs_ok]).head(MAX_TRADES)
    print(f"\nIN PLAY (relvol >= {MIN_RV:g}, top {TOP_N}): {len(R)} | red 09:15 = SHORT setups {len(S)}, valid (not broken before 09:30) {int(valid[S.index].sum())}, "
          f"of which gap fill NEAR (skipped) {int((valid[S.index] & near).sum())} | long fallbacks valid {len(longs_ok)}")
    if len(picks):
        print(f"SUMMARY -- ARM these {len(picks)} (max {MAX_TRADES}; Rs{RISK_RS:,} risk each, TIGHT stop = 10% ATR; from 09:30; exit ~14:15-15:15, no target):")
        for _, r in picks.iterrows():
            kind = "SELL-STOP (short)" if r.side == "SHORT" else "BUY-STOP (long, fallback)"
            print(f"  #{r['rank']} {r.ticker}: {kind} trigger {r.trigger} | stop {r.stop_tight} (SL-M) | qty {r.qty_tight} (position ~Rs{r.qty_tight * r.trigger / 1e5:.1f} lakh) | {r.status} | {r.room}")
    else: print("SUMMARY -- nothing to arm right now.")
    if (valid[S.index] & near).any():
        print("  skipped (gap fill NEAR): " + ", ".join(f"{r.ticker} ({r.room})" for _, r in S[valid[S.index] & near].iterrows()))
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print("\n" + R.to_string(index=False, formatters={"relvol": "{:.1f}".format}))
        if "liq5_L" in R: th = R[R.liq5_L < MIN_LIQ_L]; print("THIN on a normal day (5-day median 5-min turnover < Rs%d lakh -- yesterday may have been unusually busy): " % MIN_LIQ_L + (", ".join(f"{a_} ({b_:.1f}L)" for a_, b_ in zip(th.ticker, th.liq5_L)) or "none"))
    # 2026-10-18 (user): FADE LEVELS for the 09:20-09:40 read -- every level known now, above the current price, named; STACK = two within 0.3%;
    # targets = the 09:15 close, then the 09:15 low (evidence on red 09:15 candles: close reached ~64% in ~10 min, low ~46% in ~30 min).
    # 2026-10-25 (user): MTF telemetry, INFO only (no filter, no ranking). Latest NSE MTF file before today (usually T-2, published
    # the evening after its date). mtf_under = yesterday's close vs the average funded price (amount / shares); mtf_days = funded
    # shares / 20-day average volume; trapped = YES at <= -30% underwater after a >= 3% fall yesterday, "near" at <= -20%.
    MTF_DATE, MTF = mtf_latest_before(PREV_DAY)                     # a file dated PREV_DAY is not out yet at 09:21 (also keeps --replay honest)
    fl = []; mtf_cols = {}
    for _, r in R.iterrows():
        try:
            dd = pd.read_csv(DAILY_DIR / f"{r.ticker}.csv", index_col=0, parse_dates=True).sort_index(); dd = dd[~dd.index.duplicated()].dropna(subset=["Close"])
            y = dd[dd.index < TODAY].iloc[-1]
        except Exception: continue
        h = dd[dd.index < TODAY]; fall = (y.Close / h.Close.iat[-2] - 1) * 100
        under = days = None
        if MTF is not None and r.ticker in MTF.index and MTF.at[r.ticker, "qty"] > 0:
            m = MTF.loc[r.ticker]; under = (y.Close / (m.amt_lakh * 1e5 / m.qty) - 1) * 100; days = m.qty / h.Volume.tail(20).mean()
        trapped = "" if under is None else "YES" if (under <= -30 and fall <= -3) else "near" if under <= -20 else ""
        mtf_cols[r.ticker] = dict(mtf_under=None if under is None else round(under, 1), mtf_days=None if days is None else round(days, 1),
                                  yday_fall=round(fall, 2), trapped=trapped)
        pp = (y.High + y.Low + y.Close) / 3
        lv = {"09:15 high": r.h915, "R1": 2 * pp - y.Low, "R2": pp + y.High - y.Low, "daily 8": r.d8_touch, "yday high": y.High, "yday close": y.Close}
        above = sorted([(v, k) for k, v in lv.items() if v == v and v > r.now])
        stk = [f"{a[1]}+{b[1]} ~{a[0]:.2f}" for a, b in zip(above, above[1:]) if b[0] / a[0] - 1 <= 0.003]
        red = r.cl915 < r.o915
        fl.append(dict(ticker=r.ticker, now=r.now, c0915=f"{r.o915:.2f} / {r.h915:.2f} / {r.l915:.2f} / {r.cl915:.2f}" + (" red" if red else " green"),
                       levels_above=" | ".join(f"{v:.2f} {k}" for v, k in above[:4]) or "none above", stacked=("; ".join(stk) or ""),
                       target1_0915close=((f"{r.cl915:.2f} ({(r.cl915 / r.now - 1) * 100:+.2f}%)" if r.cl915 < r.now else "already below") if red else ""),
                       target2_0915low=((f"{r.l915:.2f} ({(r.l915 / r.now - 1) * 100:+.2f}%)" if r.l915 < r.now else "already below") if red else ""),
                       **mtf_cols[r.ticker]))
    if fl:
        with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_colwidth", 80):
            print("\nFADE LEVELS (for your 09:20-09:40 read; nearest 4 levels above the price; INFO):")
            print(pd.DataFrame(fl).to_string(index=False))
        print(f"  MTF file used: {MTF_DATE:%Y-%m-%d}" if MTF_DATE is not None else "  MTF: no file on disk (run data/fetch_nse_mtf.py)")
        print("  with a level: a turn AT it counts, even mid-bar | no level: a doji / stall, then a bar red from its open (no new high) | skip pushes made of full green bars\n"
              "  and trades with no room to the targets | a level alone is ~50/50 (first touches break ~56-60%); the 09:15 high alone is the weakest, the daily 8 /\n"
              "  yesterday's high / two stacked levels the strongest | gap-down stock: yesterday's close above is a magnet")
    out = HERE / "orb_scans"; out.mkdir(exist_ok=True)
    if mtf_cols: R = R.join(pd.DataFrame(R.ticker.map(mtf_cols).dropna().tolist(), index=R.ticker[R.ticker.isin(mtf_cols)].index))
    fn = out / f"orb_scan_{ASOF:%Y%m%d_%H%M}{'_replay' if REPLAY else ''}.csv"; R.to_csv(fn, index=False); print(f"saved {fn.name}")
