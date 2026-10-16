"""EARLY WATCHLIST at 10:15 / 10:45 (user, 2026-10-15): stocks heading INTO the 1H EMA34 that have not been rejected / supported yet,
so the user can set alerts at the line and judge the candle live (intrabar entry, the user's style). INFO ONLY -- no trade rule.
Rules declared before running:
  universe : liquid (previous day's median 5-min turnover >= Rs15 lakh), yesterday's close >= Rs100, daily ATR14 >= 2.5%
  line     : 1H EMA34 / EMA8 as of the last COMPLETED hourly bar (at 10:15 and 10:45 = after the 09:15 hour)
  SHORT watch: 1H EMA8 < EMA34, price BELOW the line and within 1% of it, FRESH = fallen < 0.5 ATR from the day's high
  LONG watch : 1H EMA8 > EMA34, price ABOVE the line and within 1% of it, FRESH = risen < 0.5 ATR from the day's low
  list     : the 15 closest to the line per side (FRESH ones); the full lists are printed too
  The side on the list is PROVISIONAL: the candle at the line decides it (MOTILALOFS 2026-10-13: a 'short' that was a support).
Usage: python3 223_watchlist.py              live (run at 10:15-10:20 or 10:45-10:50)
       python3 223_watchlist.py --replay YYYY-MM-DD HH:MM
       python3 223_watchlist.py --coverage   30m-set check: of the CLEAN setups that formed later (half-hour candles 10:15..12:45,
         217 / 218 candle reading: short = high >= line > close, red, close in the bottom 40%, opened <= line + 0.2%; long = mirror),
         how many were on the 10:15 / 10:45 list of the same side, and how many were on the OPPOSITE side's list (the mis-sided ones).
         Bar (declared): the top-15 list catches >= 60% of later setups of its side."""
import sys, time, importlib.util, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from backtest import load
from orb_common import read5_official
from data.paths import DAILY_DIR, INTRADAY_5M_DIR
TOP, NEAR, FRESH, ATR_MIN, LIQ = 15, 1.0, 0.5, 2.5, 15
HALVES = ["10:15", "10:45", "11:15", "11:45", "12:15", "12:45"]


def h1(t):
    p = HERE / "h1_cache" / f"{t}.csv"
    if not p.exists(): return None
    h = pd.read_csv(p, index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return h[~h.index.duplicated()]


def classify(o, hi, lo, c, line):
    """217 / 218 candle reading at the line -> 'short' (clean rejection), 'long' (clean support) or None."""
    if hi <= lo: return None
    cp = (c - lo) / (hi - lo)
    if hi >= line > c and c < o and cp <= 0.4 and o <= line * 1.002: return "short"
    if lo <= line < c and c > o and cp >= 0.6 and o >= line * 0.998: return "long"
    return None


def watch_side(e8, e34, px, dh, dl, atr_px):
    """-> (side, dist % to the line, fresh flag) or None."""
    d = (px / e34 - 1) * 100
    if e8 < e34 and -NEAR <= d < 0: return "SHORT", -d, (dh - px) / atr_px < FRESH
    if e8 > e34 and 0 < d <= NEAR: return "LONG", d, (px - dl) / atr_px < FRESH
    return None


# ---------------------------------------------------------------- coverage check (30m set, cache only)
def cov_ticker(t):
    try:
        d = load(t); m = read5_official(t); h = h1(t)
    except Exception: return [], []
    if h is None or len(h) < 60: return [], []
    e34 = h.Close.ewm(span=34, adjust=False).mean().shift(1); e8 = h.Close.ewm(span=8, adjust=False).mean().shift(1)
    days = sorted(set(m.index.normalize())); W, S = [], []
    for i in range(1, len(days)):
        D, P = days[i], days[i - 1]
        dd = d[d.index < D]
        if len(dd) < 60: continue
        pc = dd.Close.iloc[-1]; atrp = dd.atr14.iloc[-1] / pc * 100
        pv = m[(m.index.normalize() == P) & (m.Volume > 0)]
        liq = (pv.Volume * pv.Close).median() / 1e5 if len(pv) else 0
        if pc < 100 or atrp < ATR_MIN or liq < LIQ: continue
        g = m[m.index.normalize() == D]
        if len(g) < 60: continue
        hk = D + pd.Timedelta("10h15min")
        if hk not in e34.index or np.isnan(e34[hk]): continue
        for T in ("10:15", "10:45"):
            TT = D + pd.Timedelta(hours=int(T[:2]), minutes=int(T[3:])); b = g[g.index < TT]
            w = watch_side(e8[hk], e34[hk], b.Close.iloc[-1], b.High.max(), b.Low.min(), atrp / 100 * pc)
            if w: W.append(dict(ticker=t, date=D, T=T, side=w[0], dist=w[1], fresh=w[2]))
        for s in HALVES:
            ss = D + pd.Timedelta(hours=int(s[:2]), minutes=int(s[3:])); c = g[(g.index >= ss) & (g.index < ss + pd.Timedelta("30min"))]
            hkk = ss if s.endswith("15") else ss - pd.Timedelta("30min")
            if len(c) < 6 or hkk not in e34.index: continue
            k = classify(c.Open.iloc[0], c.High.max(), c.Low.min(), c.Close.iloc[-1], e34[hkk])
            if k: S.append(dict(ticker=t, date=D, start=s, side=k.upper(), trend_ok=(e8[hkk] < e34[hkk]) == (k == "short")))
    return W, S


def coverage():
    from multiprocessing import Pool
    uni = [f.stem for f in INTRADAY_5M_DIR.glob("*.csv") if not f.stem.startswith("_")]
    with Pool(6) as p: R = p.map(cov_ticker, uni, chunksize=10)
    W = pd.DataFrame([x for r in R for x in r[0]]); S = pd.DataFrame([x for r in R for x in r[1]])
    S = S.sort_values("start").groupby(["ticker", "date", "side"]).head(1)        # first clean setup per stock-day-side
    W["rank_all"] = W.groupby(["date", "T", "side"]).dist.rank(method="first")
    F = W[W.fresh].copy(); F["rank"] = F.groupby(["date", "T", "side"]).dist.rank(method="first")
    nd = W.date.nunique()
    print(f"30m set {W.date.min():%Y-%m-%d} .. {W.date.max():%Y-%m-%d}, {nd} days | clean later setups: SHORT {sum(S.side == 'SHORT')}, LONG {sum(S.side == 'LONG')}")
    print("\nList size per day (median / max):")
    for (T, sd), g in W.groupby(["T", "side"]):
        a = g.groupby("date").size(); f = g[g.fresh].groupby("date").size()
        print(f"  {T} {sd:5s}: all {a.median():.0f} / {a.max()} | fresh {f.median():.0f} / {f.max()}")
    print("\n| list | side | later setups (from the list time on) | caught, same side | on the OPPOSITE side's list | not on any list |\n|---|---|---|---|---|---|")
    for T, A in (("10:15", S), ("10:45", S), ("10:15", S[S.trend_ok]), ("10:45", S[S.trend_ok])):
        later = A[A.start >= T]; T_ = T + (" TREND-MATCHED setups only" if len(A) < len(S) else "")
        for nm, L in (("top-15 fresh", F[(F["T"] == T) & (F["rank"] <= TOP)]), ("all fresh", F[F["T"] == T]), ("all, no fresh filter", W[W["T"] == T])):
            keys = {(r.ticker, r.date, r.side) for r in L.itertuples()}
            for sd, op in (("SHORT", "LONG"), ("LONG", "SHORT")):
                x = later[later.side == sd]
                same = np.array([(r.ticker, r.date, sd) in keys for r in x.itertuples()]); opp = np.array([(r.ticker, r.date, op) in keys for r in x.itertuples()])
                print(f"| {T_} {nm} | {sd} | {len(x)} | {same.mean()*100:.0f}% | {opp.mean()*100:.0f}% | {(~same & ~opp).mean()*100:.0f}% |")
    print("\nLater setups whose own 1H trend matched their side (EMA8 < 34 for shorts): "
          + ", ".join(f"{sd} {S[S.side == sd].trend_ok.mean()*100:.0f}%" for sd in ("SHORT", "LONG")))
    for T in ("10:15", "10:45"):
        L = F[(F["T"] == T) & (F["rank"] <= TOP)].merge(S[S.start >= T], on=["ticker", "date"], how="left", suffixes=("", "_got"))
        got = L.groupby(["ticker", "date", "side"]).side_got.agg(lambda z: "+".join(sorted(set(z.dropna()))) or "nothing").reset_index()
        got["k"] = got.side + " list -> " + got.side_got
        print(f"\n{T} top-15 fresh names ({len(got)} name-days): what formed later (clean setups)")
        print((got.k.value_counts(normalize=True) * 100).round(0).to_string())
    print("\nHAND CHECK MOTILALOFS 2026-10-13:")
    print(W[(W.ticker == "MOTILALOFS") & (W.date == "2026-10-13")].round(2).to_string(index=False) or "  not on any list")
    print(S[(S.ticker == "MOTILALOFS") & (S.date == "2026-10-13")].to_string(index=False) or "  no clean setup")


# ---------------------------------------------------------------- live / replay list
_V1 = None


def _prep_row(args):   # 203's prep_row, loaded inside each worker (a module whose name starts with a digit can't be imported)
    global _V1
    if _V1 is None:
        spec = importlib.util.spec_from_file_location("v1scan", HERE / "203_v1_scan.py"); _V1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(_V1)
    return _V1.prep_row(args)


def prep(today):
    from multiprocessing import Pool
    uni = pd.read_csv(HERE.parent / "nse_equity_universe.csv").ticker.tolist()
    with Pool(6) as p: P = pd.DataFrame([r for r in p.map(_prep_row, [(t, today) for t in uni], chunksize=20) if r]).set_index("t")
    P = P[(P.liq_L >= LIQ) & (P.atrp >= ATR_MIN)]
    e8 = {}
    for t in P.index:
        h = h1(t); h = h[h.index < today]; e8[t] = h.Close.ewm(span=8, adjust=False).mean().iloc[-1]
    P["e8y"] = pd.Series(e8); return P


def live(today, asof, replay):
    t0 = time.time(); pf = HERE / "prep" / f"watch_prep_{today:%Y%m%d}.csv"
    if pf.exists(): P = pd.read_csv(pf, index_col=0)
    else:
        P = prep(today)
        if not replay: P.to_csv(pf)
    bars, dopen = {}, {}
    if replay:
        for t in P.index:
            m = read5_official(t); bars[t] = m[(m.index.normalize() == today) & (m.index + pd.Timedelta("5min") <= asof)]
    else:
        from fetch_prices import _chunked_download
        raw = _chunked_download([f"{t}.NS" for t in P.index], chunk_size=50, pause=1, period="1d", interval="5m", group_by="ticker")
        dl = _chunked_download([f"{t}.NS" for t in P.index], chunk_size=50, pause=1, period="5d", interval="1d", group_by="ticker")
        for t, g in dl.items():
            if g is not None and not g.empty:
                gi = g.index.tz_localize(None) if g.index.tz is not None else g.index; dopen[t] = pd.Series(g.Open.values, gi.normalize()).get(today, np.nan)
        for t, g in raw.items():
            if g is None or g.empty: continue
            g = g.dropna(subset=["Close"])
            if g.index.tz is not None: g.index = g.index.tz_convert("Asia/Kolkata").tz_localize(None)
            g = g[(g.index.normalize() == today) & (g.index + pd.Timedelta("5min") <= asof)].copy()
            if len(g) and dopen.get(t) == dopen.get(t):   # official open fix, as read5_official
                i0 = g.index[0]; o = dopen[t]; g.loc[i0, "Open"] = o; g.loc[i0, "High"] = max(g.High.iloc[0], o); g.loc[i0, "Low"] = min(g.Low.iloc[0], o)
            bars[t] = g
    rows = []
    for t, r in P.iterrows():
        g = bars.get(t)
        if g is None or len(g) < 6: continue
        e34, e8, hs = r.e34y, r.e8y, today + pd.Timedelta("9h15min")
        while hs + pd.Timedelta("60min") <= asof:                         # update through every completed hour today
            hb = g[(g.index >= hs) & (g.index < hs + pd.Timedelta("60min"))]
            if len(hb) < 12: break
            e34 += 2 / 35 * (hb.Close.iloc[-1] - e34); e8 += 2 / 9 * (hb.Close.iloc[-1] - e8); hs += pd.Timedelta("60min")
        px = g.Close.iloc[-1]; atr_px = r.atrp / 100 * r.pc
        w = watch_side(e8, e34, px, g.High.max(), g.Low.min(), atr_px)
        if not w: continue
        l30 = g[g.index >= g.index[-1] - pd.Timedelta("25min")]
        rows.append(dict(side=w[0], ticker=t, price=round(px, 2), ema34_1h=round(e34, 2), dist_pct=round(w[1], 2), ema8_1h=round(e8, 2),
                         d8_touch=round(r.s8, 2), day_high=round(g.High.max(), 2), day_low=round(g.Low.min(), 2),
                         moved_atr=round(((g.High.max() - px) if w[0] == "SHORT" else (px - g.Low.min())) / atr_px, 2), fresh=w[2],
                         last30_to_line=round(((l30.Close.iloc[-1] / l30.Open.iloc[0] - 1) * 100) * (1 if w[0] == "SHORT" else -1), 2),
                         atr=round(r.atrp, 2), liq5_L=round(r.get("liq5_L", np.nan), 1)))
    X = pd.DataFrame(rows)
    print(f"WATCHLIST {today:%Y-%m-%d} as of {asof:%H:%M} | universe {len(P)} (liquid, >= Rs100, ATR >= {ATR_MIN}%) | {time.time()-t0:.0f}s")
    print("Set an alert AT ema34_1h. The candle at the line decides the side: clean rejection (red, closes in the bottom 40%) = short,"
          " clean support (green, top 40%) = long. last30_to_line = % moved toward the line in the last 30 min (a strong push tends to break it, 222).")
    if X.empty: print("no names within 1% of the line"); return
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    for sd in ("SHORT", "LONG"):
        x = X[X.side == sd].sort_values("dist_pct"); f = x[x.fresh].head(TOP)
        print(f"\n{sd} watch -- {len(f)} fresh shown (of {len(x[x.fresh])} fresh, {len(x)} in total):")
        print(f.drop(columns=["side", "fresh"]).to_string(index=False) if len(f) else "  none")
    if not replay: X.to_csv(HERE / "prep" / f"watchlist_{today:%Y%m%d}_{asof:%H%M}.csv", index=False)


if __name__ == "__main__":
    if "--coverage" in sys.argv: coverage(); sys.exit()
    if "--replay" in sys.argv:
        i = sys.argv.index("--replay"); today = pd.Timestamp(sys.argv[i + 1]); asof = pd.Timestamp(f"{sys.argv[i + 1]} {sys.argv[i + 2]}")
        live(today, asof, True)
    else:
        asof = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None).floor("min"); live(asof.normalize(), asof, False)
