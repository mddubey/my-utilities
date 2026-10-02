"""LIVE bearish scan (watch-only), short side of 18's 'held' rule, as of now. Scratch only; nothing in production
is touched (fresh 5m pulled into memory, h1_cache read-only history). Rules (same as tested in 18, mirrored):
  liquid: prior-day tv20 >= Rs 10 cr. 1H EMA8 < EMA34 as of the last completed 1H bar; forming hour (from 10:15)
  opened below EMA34; a 5m high touched it; >= 15 min since the touch bar with no new hour high in the last 3 bars;
  price back below EMA34 but less than 1% below. Not above the daily 8-EMA (yesterday's close).
  Entry = that 5m close, stop = hour high so far, target = entry -1%, out by 5h or EOD.
Cues shown (not filters): Nifty since open (with = down), gap (avoid: gapped DOWN > 0.5%), entry before 11:30.
Backtest reminder: this rule was ~breakeven gross (-0.012%/trade, 2026-06..09); best cue combo +0.01-0.02%."""
import sys, warnings, datetime as dt
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from fetch_prices import _chunked_download
import yfinance as yf
HERE = Path(__file__).resolve().parent
NOW = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None)
TODAY = NOW.normalize()


def daily(t):
    try: d = load(t)
    except Exception: return None
    d = d[d.index < pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None).normalize()]   # never use today's row (cache may refresh intraday)
    if len(d) < 50 or d.traded_value_sma20.iloc[-1] < 1e8: return None
    return t, d.Close.ewm(span=8, adjust=False).mean().iloc[-1], d.Close.iloc[-1]


def clean5(x):
    x = x.dropna(subset=["Close"])
    if x.empty: return x
    x.index = (x.index.tz_convert("Asia/Kolkata") if x.index.tz is not None else x.index.tz_localize("Asia/Kolkata")).tz_localize(None)
    x = x[x.index.normalize() == TODAY]
    return x[x.index + pd.Timedelta("5min") <= NOW]                  # completed 5m bars only


if __name__ == "__main__":
    from multiprocessing import Pool
    uni = pd.read_csv(HERE.parent / "nse_equity_universe.csv").ticker.tolist()
    with Pool(6) as p: D = [r for r in p.map(daily, uni) if r]
    D = pd.DataFrame(D, columns=["ticker", "d8", "prev_close"]).set_index("ticker")
    print(f"{NOW:%Y-%m-%d %H:%M} IST | liquid tickers: {len(D)} | fetching today's 5m...", flush=True)
    raw = _chunked_download([f"{t}.NS" for t in D.index], period="1d", interval="5m", group_by="ticker", progress=True)
    n5 = clean5(yf.download("^NSEI", period="1d", interval="5m", progress=False, auto_adjust=False).droplevel(1, axis=1))
    nifty_so = n5.Close.iloc[-1] / n5.Open.iloc[0] - 1
    rows = []
    for t in D.index:
        g = clean5(raw.get(t, pd.DataFrame()))
        if len(g) < 6: continue
        hp = HERE / "h1_cache" / f"{t}.csv"
        if not hp.exists(): continue
        h = pd.read_csv(hp, index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
        h = h[h.index < TODAY].Close
        hs = TODAY + pd.Timedelta("9h15min") + ((g.index - TODAY - pd.Timedelta("9h15min")) // pd.Timedelta("60min")) * pd.Timedelta("60min")
        g = g.assign(hs=hs)
        done = g.groupby("hs").Close.last()
        done = done[done.index + pd.Timedelta("60min") <= NOW]
        closes = pd.concat([h, done])
        e34s, e8s = closes.ewm(span=34, adjust=False).mean(), closes.ewm(span=8, adjust=False).mean()
        cur_hs = g.hs.iloc[-1]
        prior = e34s[e34s.index < cur_hs]
        if prior.empty: continue
        E, e8 = prior.iloc[-1], e8s[e8s.index < cur_hs].iloc[-1]
        px = g.Close.iloc[-1]; d8 = D.at[t, "d8"]
        if not (e8 < E) or px > d8: continue
        hr = g[g.hs == cur_hs]; H, C = hr.High.values, hr.Close.values
        ho = hr.Open.iloc[0]
        gap = (g.Open.iloc[0] / D.at[t, "prev_close"] - 1) * 100
        base = dict(ticker=t, price=round(px, 2), ema34_1h=round(E, 2), d8=round(d8, 2),
                    dist_below_ema_pct=round((E - px) / E * 100, 2), gap_pct=round(gap, 2),
                    day_high_near_d8=bool(g.High.max() >= d8 * 0.995), hour=f"{cur_hs:%H:%M}")
        if cur_hs.hour * 60 + cur_hs.minute < 615 or ho >= E:
            continue
        tb = next((k for k in range(len(H)) if H[k] >= E), None)
        if tb is None:
            if 0 < base["dist_below_ema_pct"] <= 0.5: rows.append({**base, "stage": "approaching"})
            continue
        trig = None
        for k in range(tb + 3, len(C)):
            hh = H[:k + 1].max()
            if H[k - 2:k + 1].max() >= hh: continue
            if not (0 < (E - C[k]) / E * 100 < 1): continue
            trig = k; break
        if trig is None:
            rows.append({**base, "stage": "touched, waiting", "touch_at": f"{hr.index[tb]:%H:%M}", "hour_high": round(H.max(), 2)}); continue
        entry, stop = C[trig], H[:trig + 1].max()
        rows.append({**base, "stage": "TRIGGERED", "touch_at": f"{hr.index[tb]:%H:%M}", "entry_at": f"{hr.index[trig]:%H:%M}",
                     "entry": round(entry, 2), "stop": round(stop, 2), "stop_pct": round((stop - entry) / entry * 100, 2),
                     "target": round(entry * 0.99, 2), "now_vs_entry_pct": round((entry - px) / entry * 100, 2),
                     "stopped_since": bool(g[g.index > hr.index[trig]].High.max() >= stop) if trig < len(C) - 1 else False})
    R = pd.DataFrame(rows)
    # follow-up: every trigger from today's earlier scans, graded on 5m bars since its entry
    prev = [pd.read_csv(f) for f in sorted(HERE.glob(f"live_bearish_{NOW:%Y%m%d}_*.csv")) if f.stat().st_size > 5]
    prev = pd.concat(prev) if prev else pd.DataFrame()
    if len(prev) and "stage" in prev:
        T = prev[prev.stage == "TRIGGERED"].drop_duplicates(["ticker", "entry_at"])
        fu = []
        for r in T.itertuples():
            gg = clean5(raw.get(r.ticker, pd.DataFrame()))
            after = gg[gg.index > TODAY + pd.Timedelta(r.entry_at + ":00")]
            out, px = "open", gg.Close.iloc[-1] if len(gg) else np.nan
            for b in after.itertuples():
                if b.High >= r.stop: out, px = f"STOPPED {b.Index:%H:%M}", r.stop; break
                if b.Low <= r.target: out, px = f"TARGET {b.Index:%H:%M}", r.target; break
            fu.append(dict(ticker=r.ticker, entry_at=r.entry_at, entry=r.entry, stop=r.stop, target=r.target,
                           gap_pct=r.gap_pct, status=out, pnl_pct=round((r.entry - px) / r.entry * 100, 2)))
        FU = pd.DataFrame(fu)
        print(f"\n== EARLIER TRIGGERS TODAY ({len(FU)}): " + FU.status.str.split().str[0].value_counts().to_dict().__repr__()
              + f" | avg pnl {FU.pnl_pct.mean():+.2f}% (gross, short)")
        print(FU.sort_values("entry_at").to_string(index=False))
    R.to_csv(HERE / f"live_bearish_{NOW:%Y%m%d_%H%M}.csv", index=False)
    print(f"\nNifty since open: {nifty_so*100:+.2f}%  ({'WITH shorts' if nifty_so < 0 else 'AGAINST shorts'}) | "
          f"forming hour {g.hs.iloc[-1]:%H:%M} | entries before 11:30 were the better bucket")
    if R.empty: print("nothing"); sys.exit()
    print(R.stage.value_counts().to_dict())
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    for s in ("TRIGGERED", "touched, waiting", "approaching"):
        x = R[R.stage == s]
        if len(x): print(f"\n== {s} ({len(x)})"); print(x.drop(columns="stage").dropna(axis=1, how="all").to_string(index=False))
