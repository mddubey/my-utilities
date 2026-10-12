"""LIVE scan for CANDIDATE v1 (STRATEGY 8k + later additions; user, 2026-10-12). Run after 11:15 IST (the 10:15-11:15 hourly candle).
v1 rules: liquid (prev-day median 5-min turnover >= Rs15 lakh), price >= Rs100, daily ATR >= 2%, stock daily EMA8 > EMA34 (yesterday),
gap -0.25..+0.5% (OFFICIAL open vs yesterday's close); the 10:15 hourly candle touches the 1H EMA34 (high >= EMA34 as of the 09:15
hour's close) and closes RED below it; branch A = day opened 0-0.5% BELOW that EMA34, branch B = opened above with ATR >= 3%; skip a
doji cut by the line (body < 25% of range AND candle open >= EMA34); skip converged lines (live daily 8-EMA within 0.25% of the 1H
EMA34). Exits: E1 = 1% target, stop = candle high, only if stop <= 0.5%; E2 = max(1%, 0.35x ATR), stop <= half the target. Pick =
highest ATR. NIFTY GATE: v1 only trades when Nifty closed above its 200-day SMA yesterday -- below it every setup is INFO.
Below-200 LEAD flag (202, NOT proven): entry >= 3% (or 2.5%) below yesterday's high.
Day open = official open (Yahoo 1d bar, = NSE open), not the first bar's open (2026-10-12 fix).
Usage: python3 203_v1_scan.py [--replay YYYY-MM-DD]"""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from fetch_prices import _chunked_download
from data.paths import DAILY_DIR, INTRADAY_5M_DIR


def h1(t):
    p = HERE / "h1_cache" / f"{t}.csv"
    if not p.exists(): return pd.DataFrame()
    h = pd.read_csv(p, index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None); return h


def prep_row(args):
    t, today = args
    try: d = load(t)
    except Exception: return None
    d = d[d.index < today]
    if len(d) < 60: return None
    pc = d.Close.iloc[-1]; atrp = d.atr14.iloc[-1] / pc * 100
    if pc < 100 or atrp < 2 or d.traded_value_sma20.iloc[-1] < 1e8: return None
    s8 = d.Close.ewm(span=8, adjust=False).mean().iloc[-1]; s34 = d.Close.ewm(span=34, adjust=False).mean().iloc[-1]
    if not s8 > s34: return None
    m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True) if (INTRADAY_5M_DIR / f"{t}.csv").exists() else None
    if m is None: return None
    m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None); m = m[m.index < today]
    last = m[m.index.normalize() == m.index.normalize().max()]; liq = (last.Volume * last.Close)[last.Volume > 0].median() / 1e5
    hh = h1(t); hh = hh[hh.index < today]
    if len(hh) < 60: return None
    e34y = hh.Close.ewm(span=34, adjust=False).mean().iloc[-1]   # 1H EMA34 through yesterday's last hourly close
    return dict(t=t, pc=pc, ph=d.High.iloc[-1], atrp=atrp, s8=s8, s34=s34, liq_L=liq, e34y=e34y)


if __name__ == "__main__":
    REPLAY = "--replay" in sys.argv
    if REPLAY: TODAY = pd.Timestamp(sys.argv[sys.argv.index("--replay") + 1]); ASOF = TODAY + pd.Timedelta("11h16min")
    else: ASOF = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None); TODAY = ASOF.normalize()
    if not REPLAY and ASOF < TODAY + pd.Timedelta("11h15min"): print("Too early: the 10:15 hourly candle closes at 11:15."); sys.exit()
    t0 = time.time()
    N = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index(); N = N[N.index < TODAY]
    n200 = N.Close.iloc[-1] > N.Close.rolling(200).mean().iloc[-1]
    print(f"v1 scan {TODAY:%Y-%m-%d} | NIFTY GATE: yesterday {N.Close.iloc[-1]:.0f} vs 200d {N.Close.rolling(200).mean().iloc[-1]:.0f} -> "
          + ("ON (v1 trades)" if n200 else "OFF -- every setup is INFO only (v1 loses below the 200-day)"))
    PREP = HERE / "prep" / f"v1_prep_{TODAY:%Y%m%d}.csv"
    if PREP.exists() and not REPLAY: P = pd.read_csv(PREP, index_col=0)
    else:
        from multiprocessing import Pool
        uni = pd.read_csv(HERE.parent / "nse_equity_universe.csv").ticker.tolist()
        with Pool(6) as p: P = pd.DataFrame([r for r in p.map(prep_row, [(t, TODAY) for t in uni], chunksize=20) if r]).set_index("t")
        if not REPLAY: P.to_csv(PREP)
    P = P[P.liq_L >= 15]
    print(f"candidates (liquid, >= Rs100, ATR >= 2%, daily 8 > 34): {len(P)} | prep {time.time()-t0:.0f}s", flush=True)
    if REPLAY:
        bars, dopen = {}, {}
        for t in P.index:
            m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
            bars[t] = m[m.index.normalize() == TODAY]
            dopen[t] = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).Open.get(TODAY, np.nan)
    else:
        raw = _chunked_download([f"{t}.NS" for t in P.index], chunk_size=50, pause=1, period="1d", interval="5m", group_by="ticker")
        dl = _chunked_download([f"{t}.NS" for t in P.index], chunk_size=50, pause=1, period="5d", interval="1d", group_by="ticker")
        bars, dopen = {}, {}
        for t, g in raw.items():
            if g is None or g.empty: continue
            g = g.dropna(subset=["Close"])
            if g.index.tz is not None: g.index = g.index.tz_convert("Asia/Kolkata").tz_localize(None)
            bars[t] = g[g.index.normalize() == TODAY]
        for t, g in dl.items():
            if g is None or g.empty: continue
            gi = g.index.tz_localize(None) if g.index.tz is not None else g.index; g.index = gi.normalize(); dopen[t] = g.Open.get(TODAY, np.nan)
    rows = []
    for t, r in P.iterrows():
        g = bars.get(t, pd.DataFrame())
        if g is None or len(g) == 0: continue
        hm = g.index.strftime("%H:%M")
        h915 = g[(hm >= "09:15") & (hm < "10:15")]; c = g[(hm >= "10:15") & (hm < "11:15") & (g.index + pd.Timedelta("5min") <= ASOF)]
        if len(h915) < 10 or len(c) < 12: continue
        E = r.e34y + 2 / 35 * (h915.Close.iloc[-1] - r.e34y)          # 1H EMA34 as of the 09:15 hour's close
        o, hi, lo, cl = c.Open.iloc[0], c.High.max(), c.Low.min(), c.Close.iloc[-1]
        if not (hi >= E and cl < E and cl < o): continue
        oo = dopen.get(t, np.nan)
        if oo != oo: continue
        gap = (oo / r.pc - 1) * 100
        if not (-0.25 < gap <= 0.5): continue
        ov = (oo / E - 1) * 100
        br = "A" if -0.5 <= ov < 0 else ("B" if ov >= 0 and r.atrp >= 3 else None)
        if br is None: continue
        rng = hi - lo; bodyp = (o - cl) / rng if rng > 0 else 0
        if bodyp < 0.25 and o >= E: continue                              # doji cut by the line
        d8 = 2 / 9 * cl + 7 / 9 * r.s8
        if abs(E - d8) / cl * 100 < 0.25: continue                         # converged lines
        stop = (hi - cl) / cl * 100; tp2 = max(1.0, 0.35 * r.atrp)
        e1 = stop <= 0.5; e2 = stop <= tp2 / 2
        if not (e1 or e2): continue
        dyh = (cl / r.ph - 1) * 100
        lead = "LEAD >= 3%" if dyh <= -3 else ("lead >= 2.5%" if dyh <= -2.5 else "")
        rows.append(dict(ticker=t, branch=br, atr=round(r.atrp, 2), entry=round(cl, 2), stop=round(hi, 2), stop_pct=round(stop, 2),
                         E1_target=round(cl * 0.99, 2) if e1 else None, E2_target=round(cl * (1 - tp2 / 100), 2) if e2 else None,
                         ema34_1h=round(E, 2), open_vs_ema=round(ov, 2), gap=round(gap, 2), below_yday_high=round(dyh, 2), lead=lead,
                         status=("ENTER" if n200 else "INFO (Nifty < 200d)")))
    R = pd.DataFrame(rows)
    if R.empty: print("no v1 setups this hour"); sys.exit()
    R = R.sort_values("atr", ascending=False)
    print(f"\n{len(R)} v1 setup(s) -- pick = highest ATR: {R.ticker.iloc[0]} | below-200 lead (>= 3% under yesterday's high): {', '.join(R[R.lead == 'LEAD >= 3%'].ticker) or 'none'}")
    with pd.option_context("display.width", 250, "display.max_columns", 30): print(R.to_string(index=False))
    out = HERE / "v1_scans"; out.mkdir(exist_ok=True); R.to_csv(out / f"v1_scan_{ASOF:%Y%m%d_%H%M}{'_replay' if REPLAY else ''}.csv", index=False)
