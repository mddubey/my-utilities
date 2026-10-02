"""DEFAULT (2026-10-02, user's choice): 30-min rejection candle as the trigger at the strong levels (1H 34-EMA + live
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
HERE = Path(__file__).resolve().parent; A8 = 2 / 9
if "--replay" in sys.argv:
    k = sys.argv.index("--replay"); ASOF = pd.Timestamp(f"{sys.argv[k+1]} {sys.argv[k+2]}")
else:
    ASOF = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None)
TODAY = ASOF.normalize()
TF = int(sys.argv[sys.argv.index("--tf") + 1]) if "--tf" in sys.argv else 30   # DEFAULT 30 = 30-min trigger; 60 = 1H candle trigger


def daily(t):
    try: d = load(t)
    except Exception: return None
    d = d[d.index < TODAY]
    if len(d) < 60 or d.traded_value_sma20.iloc[-1] < 1e8: return None
    return t, d.Close.ewm(span=8, adjust=False).mean().iloc[-1], _compute_adx(d)[0].iloc[-1], d.Close.iloc[-1]


if __name__ == "__main__":
    from multiprocessing import Pool
    uni = pd.read_csv(HERE.parent / "nse_equity_universe.csv").ticker.tolist()
    with Pool(6) as p: DA = pd.DataFrame([r for r in p.map(daily, uni) if r], columns=["t", "d8y", "adx", "pc"]).set_index("t")
    D = DA[DA.adx <= 25]
    print(f"as of {ASOF:%Y-%m-%d %H:%M} | liquid: {len(DA)} (breadth) | liquid & daily ADX <= 25: {len(D)} (setups) | fetching 5m...", flush=True)
    raw = _chunked_download([f"{t}.NS" for t in DA.index], period="5d", interval="5m", group_by="ticker")
    # TELEMETRY (not a filter): breadth = share of liquid stocks above yesterday's close as of now (test 47: shorts
    # weakest when > 65%, ordered in all 3 years in the base 1H set; NOT confirmed with the 2:1 rule)
    up = []
    for t in DA.index:
        gb = raw.get(t, pd.DataFrame()).dropna(subset=["Close"])
        if gb.empty: continue
        gb.index = gb.index.tz_convert("Asia/Kolkata").tz_localize(None)
        gb = gb[(gb.index.normalize() == TODAY) & (gb.index + pd.Timedelta("5min") <= ASOF)]
        if len(gb): up.append(gb.Close.iloc[-1] > DA.at[t, "pc"])
    BREADTH = float(np.mean(up)) if up else float("nan")
    tag = "BULLISH breadth -> be cautious with shorts" if BREADTH > 0.65 else ("bearish breadth" if BREADTH < 0.35 else "mixed breadth")
    print(f"BREADTH: {BREADTH*100:.0f}% of {len(up)} liquid stocks above yesterday's close -> {tag}", flush=True)
    rows = []
    for t in D.index:
        g = raw.get(t, pd.DataFrame()).dropna(subset=["Close"])
        if g.empty: continue
        g.index = g.index.tz_convert("Asia/Kolkata").tz_localize(None)
        g = g[(g.index.normalize() == TODAY) & (g.index + pd.Timedelta("5min") <= ASOF)]
        if len(g) < 12: continue
        hp = HERE / "h1_cache" / f"{t}.csv"
        if not hp.exists(): continue
        h = pd.read_csv(hp, index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
        h = h[h.index < TODAY].Close
        hs = TODAY + pd.Timedelta("9h15min") + ((g.index - TODAY - pd.Timedelta("9h15min")) // pd.Timedelta("60min")) * pd.Timedelta("60min")
        g = g.assign(hs=hs)
        c1 = g.groupby("hs").agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"))
        c1 = c1[c1.index + pd.Timedelta("60min") <= ASOF]
        if TF == 60:
            if c1.empty: continue
            last = c1.index[-1]; cend = last + pd.Timedelta("60min"); hour0 = last
            if last.strftime("%H:%M") not in ("09:15", "10:15", "11:15"): continue
            o, hi, lo, cl = c1.loc[last, ["Open", "High", "Low", "Close"]]
        else:   # 30-min trigger candle, 1H EMA level of the hour it sits in
            k30 = TODAY + pd.Timedelta("9h15min") + ((g.index - TODAY - pd.Timedelta("9h15min")) // pd.Timedelta("30min")) * pd.Timedelta("30min")
            c30 = g.groupby(k30).agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"))
            c30 = c30[c30.index + pd.Timedelta("30min") <= ASOF]
            if c30.empty: continue
            last = c30.index[-1]; cend = last + pd.Timedelta("30min")
            if cend.strftime("%H:%M") not in ("10:45", "11:15", "11:45", "12:15"): continue
            hour0 = TODAY + pd.Timedelta("9h15min") + ((last - TODAY - pd.Timedelta("9h15min")) // pd.Timedelta("60min")) * pd.Timedelta("60min")
            o, hi, lo, cl = c30.loc[last, ["Open", "High", "Low", "Close"]]
        if cend < ASOF - pd.Timedelta("20min"): continue
        closes = pd.concat([h, c1.Close[c1.index < hour0]])
        e34 = closes.ewm(span=34, adjust=False).mean(); e8 = closes.ewm(span=8, adjust=False).mean()
        E, E8 = e34.iloc[-1], e8.iloc[-1]
        upto = g[g.index < cend]
        vwap = ((upto.High + upto.Low + upto.Close) / 3 * upto.Volume).sum() / max(upto.Volume.sum(), 1)
        d8y = D.at[t, "d8y"]; live = A8 * cl + (1 - A8) * d8y; day_hi = upto.High.max()
        dist = (E - cl) / E * 100
        checks = dict(red=cl < o, wick_through_ema=hi >= E, close_below_ema=cl < E, within_0_5=0 < dist <= 0.5,
                      trend_1h=E8 < E, below_daily8=cl < d8y, wick_through_live_d8=day_hi >= live, below_vwap=cl < vwap)
        if all(checks.values()):
            rows.append(dict(ticker=t, candle=f"{last:%H:%M}-{cend:%H:%M}", entry=round(cl, 2), stop=round(hi, 2), stop_pct=round((hi - cl) / cl * 100, 2),
                             target=round(cl * 0.99, 2), ema34_1h=round(E, 2), below_ema_pct=round(dist, 2), live_d8=round(live, 2),
                             day_high=round(day_hi, 2), adx=round(D.at[t, "adx"], 1)))
    R = pd.DataFrame(rows)
    RR = float(sys.argv[sys.argv.index("--rr") + 1]) if "--rr" in sys.argv else 2.0
    if RR > 0 and len(R):
        n0 = len(R); R = R[R.stop_pct <= 1.0 / RR]; print(f"reward:risk >= {RR:g}:1 -> kept {len(R)} of {n0} (stop <= {1/RR:.2f}%)")
    if len(R): R["breadth_pct"] = round(BREADTH * 100)
    out = HERE / f"alarm_scan_{'30m_' if TF == 30 else ''}{ASOF:%Y%m%d_%H%M}.csv"; R.to_csv(out, index=False)
    if R.empty: print("no setups at this alarm"); sys.exit()
    R = R.sort_values("below_ema_pct")
    print(f"\n{len(R)} SHORT setups (first = closest to EMA; one trade/day -> take the top one if nothing is open):\n")
    pd.set_option("display.width", 220); print(R.to_string(index=False)); print(f"\nsaved {out.name}")
