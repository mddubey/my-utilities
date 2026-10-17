"""10:15 WATCH LIST and 10:40-10:45 STATUS for the hourly 34 rejection (user, 2026-10-18: 'at 10:15 a short list; at 10:40 / 10:45 I ask the status
and you give me a smaller list -- the ones actually rejecting, not the ones that never broke through or took support').
  watch   (run after 10:15): liquid (>= Rs15 lakh / 5-min bar, prev day), price >= Rs100, daily ATR >= 3%, and the 09:15 hour CLOSED at / up to 0.5% UNDER
          the 1H EMA34 (the line for the 10:15 hour) -> set up to test the line from below. No ordering.
  status  (run any time in the 10:15 hour, e.g. 10:40-10:45): for each watch stock, the 10:15 candle so far:
          REJECTION FORMING = the high went through the line and the price is back under it -> listed with pierce, upper wick so far, price vs line,
            a reference stop (the high so far + 0.05%) and whether the daily 8 touch sits inside the 1% path.
          dropped (counted only): NOT TESTED (high still under the line) / ABOVE THE LINE (broke through and holding = support).
INFO for the user's discretionary read -- not a backtested rule.
Usage: python3 254_1015_watch.py watch | status   [--replay YYYY-MM-DD --asof HH:MM]"""
import sys, importlib.util, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from data.paths import INTRADAY_5M_DIR

spec = importlib.util.spec_from_file_location("v1scan", HERE / "203_v1_scan.py"); V1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(V1)


def prep(args): return V1.prep_row(args)   # top-level wrapper so multiprocessing can pickle it


def bars_for(tickers, today, replay):
    if replay:
        out = {}
        for t in tickers:
            m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
            out[t] = m[m.index.normalize() == today]
        return out
    raw = V1._chunked_download([f"{t}.NS" for t in tickers], chunk_size=50, pause=1, period="1d", interval="5m", group_by="ticker"); out = {}
    for t, g in raw.items():
        if g is None or g.empty: continue
        g = g.dropna(subset=["Close"])
        if g.index.tz is not None: g.index = g.index.tz_convert("Asia/Kolkata").tz_localize(None)
        out[t] = g[g.index.normalize() == today]
    return out


if __name__ == "__main__":
    MODE = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("watch", "status") else "watch"
    REPLAY = "--replay" in sys.argv
    if REPLAY:
        TODAY = pd.Timestamp(sys.argv[sys.argv.index("--replay") + 1])
        ASOF = TODAY + pd.Timedelta(sys.argv[sys.argv.index("--asof") + 1] + ":00") if "--asof" in sys.argv else TODAY + pd.Timedelta("10h45min")
    else:
        ASOF = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None); TODAY = ASOF.normalize()
    if ASOF < TODAY + pd.Timedelta("10h15min"): print("Too early: the 09:15 hour closes at 10:15."); sys.exit()
    PREP = HERE / "prep" / f"v1_prep4_{TODAY:%Y%m%d}.csv"
    if PREP.exists() and not REPLAY: P = pd.read_csv(PREP, index_col=0)
    else:
        from multiprocessing import Pool
        uni = pd.read_csv(HERE.parent / "nse_equity_universe.csv").ticker.tolist()
        with Pool(6) as p: P = pd.DataFrame([r for r in p.map(prep, [(t, TODAY) for t in uni], chunksize=20) if r]).set_index("t")
        if not REPLAY: P.to_csv(PREP)
    P = P[(P.liq_L >= 15) & (P.atrp >= 3)]
    B = bars_for(list(P.index), TODAY, REPLAY)
    W = []
    for t, r in P.iterrows():
        g = B.get(t)
        if g is None or len(g) == 0: continue
        b1 = g[(g.index >= TODAY + pd.Timedelta("9h15min")) & (g.index < TODAY + pd.Timedelta("10h15min"))]
        if len(b1) < 10: continue
        c915 = b1.Close.iloc[-1]; E = r.e34y + 2 / 35 * (c915 - r.e34y)          # 1H EMA34 for the 10:15 hour
        dist = (c915 / E - 1) * 100
        if -0.5 <= dist <= 0: W.append((t, r, g, E, c915, dist))
    print(f"hourly 34 rejection -- 10:15 WATCH LIST {TODAY:%Y-%m-%d} (as of {ASOF:%H:%M}): {len(W)} stocks whose 09:15 hour closed at / up to 0.5% under the 1H EMA34")
    if MODE == "watch":
        rows = [dict(ticker=t, line_1h34=round(E, 2), close_0915=round(c, 2), under_line=f"{d:.2f}%", d8_touch=round(r.s8, 2), atr=round(r.atrp, 2),
                     trend=("up" if r.up else "down")) for t, r, g, E, c, d in W]
        if rows:
            with pd.option_context("display.width", 200): print(pd.DataFrame(rows).to_string(index=False))
        sys.exit()
    rows, nt, ab = [], 0, 0
    for t, r, g, E, c, d in W:
        c1 = g[(g.index >= TODAY + pd.Timedelta("10h15min")) & (g.index + pd.Timedelta("5min") <= ASOF)]
        if len(c1) == 0: continue
        o, hi, lo, last = c1.Open.iloc[0], c1.High.max(), c1.Low.min(), c1.Close.iloc[-1]
        if hi < E: nt += 1; continue
        if last >= E: ab += 1; continue
        rg = hi - lo; stop = hi * 1.0005
        rows.append(dict(ticker=t, line_1h34=round(E, 2), high_so_far=round(hi, 2), pierce=f"{(hi / E - 1) * 100:+.2f}%", price_now=round(last, 2),
                         now_vs_line=f"{(last / E - 1) * 100:+.2f}%", upper_wick=f"{(hi - max(o, last)) / last * 100:.2f}%",
                         lower_wick=f"{((min(o, last) - lo) / rg * 100) if rg > 0 else 0:.0f}%", ref_stop=round(stop, 2), stop_pct=f"{(stop / last - 1) * 100:.2f}%",
                         d8_touch=round(r.s8, 2), d8_in_1pct_path=("YES" if last * 0.99 < r.s8 < last else ""), atr=round(r.atrp, 2), trend=("up" if r.up else "down")))
    print(f"STATUS at {ASOF:%H:%M}: REJECTION FORMING {len(rows)} | dropped: not tested yet {nt}, broke through and holding above (support) {ab}")
    if rows:
        with pd.option_context("display.width", 250, "display.max_columns", 30): print(pd.DataFrame(rows).to_string(index=False))
    print("(INFO for your read; ref_stop = the high so far + 0.05%. A daily 8 in the 1% path = support in the way.)")
