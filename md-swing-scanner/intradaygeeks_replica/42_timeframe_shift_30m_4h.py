"""Shift the whole structure down a step (user, 2026-10-02)? Spec fixed before running. Shorts. 5m data, window
Jul 1 - Sep 30 2026 (30m EMAs need warm-up from Jun 10). Entry candle = a 30-min candle (grid :15/:45) closing
10:45..12:15: red, high >= level, close < level and within 0.5% of it. Stop = its high, target -1%.
  A   : level = 1H EMA34 (last completed hour), trend 1H EMA8<EMA34, higher TF = LIVE daily 8-EMA
        (price below it; day's high so far >= it). Exit 5h / EOD.        A_2h30: same, exit 2.5h / EOD.
  B   : level = 30m EMA34 (last completed 30m), trend 30m EMA8<EMA34, higher TF = LIVE 4H 8-EMA (NSE 4H candles
        09:15-13:15 / 13:15-15:30 built from 1H; live = 2/9*P + 7/9*EMA through last completed 4H candle;
        price below it; current 4H candle's high so far >= it). Exit 5 x 30m = 2.5h / EOD.   B_5h: same, exit 5h.
All: daily ADX(yday) <= 25, close < session VWAP, liquid (tv20 >= Rs 10cr), >= 70 bars. One trade per ticker per day
per variant (first qualifying candle). Reported with and without the 2:1 rule (stop <= 0.5%)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from market_regime import _compute_adx
HERE = Path(__file__).resolve().parent
H1, M5 = HERE / "h1_cache", HERE.parent / "intraday_cache"
A8 = 2 / 9; START = pd.Timestamp("2026-07-01")


def read(p):
    x = pd.read_csv(p, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[(x.Volume > 0) | (x.High != x.Low)]


def bars30(m5):
    day = m5.index.normalize()
    k = ((m5.index - day - pd.Timedelta("9h15min")) // pd.Timedelta("30min"))
    key = day + pd.Timedelta("9h15min") + k * pd.Timedelta("30min")
    return m5.groupby(key).agg(Open=("Open", "first"), High=("High", "max"), Low=("Low", "min"), Close=("Close", "last"))


def bars4h(h1):
    day = h1.index.normalize()
    first = h1.index.strftime("%H:%M").isin(["09:15", "10:15", "11:15", "12:15"])
    key = day + np.where(first, pd.Timedelta("9h15min"), pd.Timedelta("13h15min"))
    return h1.groupby(key).agg(High=("High", "max"), Close=("Close", "last"))


def walk(H, L, C, T, b, entry, stop, hours):
    tgt, end = entry * 0.99, T[b] + pd.Timedelta(hours=hours)
    for k in range(b + 1, len(C)):
        if H[k] >= stop: return stop, "stop"
        if L[k] <= tgt: return tgt, "target"
        if T[k] >= end: return C[k], "time"
    return C[-1], "eod"


def run(t):
    if not (H1 / f"{t}.csv").exists() or not (M5 / f"{t}.csv").exists(): return []
    try: d = load(t)
    except Exception: return []
    d = d[d.index < pd.Timestamp("2026-10-01")]
    h1, m5 = read(H1 / f"{t}.csv"), read(M5 / f"{t}.csv")
    if len(h1) < 200 or len(m5) < 2000: return []
    e34h = h1.Close.ewm(span=34, adjust=False).mean().shift(1); e8h = h1.Close.ewm(span=8, adjust=False).mean().shift(1)
    b30 = bars30(m5); e34m = b30.Close.ewm(span=34, adjust=False).mean().shift(1); e8m = b30.Close.ewm(span=8, adjust=False).mean().shift(1)
    b4 = bars4h(h1); e8_4h = b4.Close.ewm(span=8, adjust=False).mean()           # EMA through each 4H candle
    d8y = d.Close.ewm(span=8, adjust=False).mean().shift(1); adx = _compute_adx(d)[0].shift(1); tv = d.traded_value_sma20.shift(1)
    rows = []
    for day, g in m5.groupby(m5.index.normalize()):
        if day < START or len(g) < 70 or day not in d.index or tv.get(day, 0) < 1e8 or bool(d.corp_action_day.get(day, False)): continue
        if abs(g.Close.iloc[-1] / d.Close.loc[day] - 1) > 0.02: continue
        D8, AD = d8y.get(day, np.nan), adx.get(day, np.nan)
        if np.isnan(D8) or np.isnan(AD) or AD > 25: continue
        prev4 = e8_4h[e8_4h.index < day + pd.Timedelta("9h15min")]
        if prev4.empty: continue
        E4prev = prev4.iloc[-1]
        O, H, L, C, V, T = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.Volume.values, g.index
        vw = np.cumsum((H + L + C) / 3 * V) / np.maximum(np.cumsum(V), 1); hi_day = np.maximum.accumulate(H)
        done = set()
        for q in b30[(b30.index.normalize() == day)].itertuples():
            qend = q.Index + pd.Timedelta("30min")
            if not (pd.Timestamp(f"{day:%Y-%m-%d} 10:45") <= qend <= pd.Timestamp(f"{day:%Y-%m-%d} 12:15")): continue
            bi = np.where(T == qend - pd.Timedelta("5min"))[0]
            if len(bi) == 0: continue
            b = bi[0]; entry, stop = q.Close, q.High
            if not (q.Close < q.Open) or entry >= vw[b]: continue
            hs = q.Index.floor("60min") + pd.Timedelta("15min") if q.Index.minute < 15 else q.Index.floor("60min") + pd.Timedelta("15min")
            hs = pd.Timestamp(f"{day:%Y-%m-%d}") + pd.Timedelta("9h15min") + ((q.Index - pd.Timestamp(f"{day:%Y-%m-%d}") - pd.Timedelta("9h15min")) // pd.Timedelta("60min")) * pd.Timedelta("60min")
            for v, lvl, trend, hi_ok, hours in (
                ("A", e34h.get(hs, np.nan), e8h.get(hs, np.nan) < e34h.get(hs, np.nan),
                 lambda: entry < D8 and hi_day[b] >= A8 * entry + (1 - A8) * D8, 5),
                ("A_2h30", e34h.get(hs, np.nan), e8h.get(hs, np.nan) < e34h.get(hs, np.nan),
                 lambda: entry < D8 and hi_day[b] >= A8 * entry + (1 - A8) * D8, 2.5),
                ("B", e34m.get(q.Index, np.nan), e8m.get(q.Index, np.nan) < e34m.get(q.Index, np.nan),
                 lambda: (live4 := A8 * entry + (1 - A8) * E4prev) and entry < E4prev and hi_day[b] >= live4, 2.5),
                ("B_5h", e34m.get(q.Index, np.nan), e8m.get(q.Index, np.nan) < e34m.get(q.Index, np.nan),
                 lambda: (live4 := A8 * entry + (1 - A8) * E4prev) and entry < E4prev and hi_day[b] >= live4, 5)):
                if v in done or np.isnan(lvl) or not trend: continue
                if not (stop >= lvl and entry < lvl and (lvl - entry) / lvl * 100 <= 0.5): continue
                if not hi_ok(): continue
                px, why = walk(H, L, C, T, b, entry, stop, hours)
                rows.append(dict(variant=v, ticker=t, date=day, entry_time=f"{qend:%H:%M}", stop_pct=(stop - entry) / entry * 100,
                                 exit=why, ret=(entry - px) / entry * 100))
                done.add(v)
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    tick = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p: R = pd.DataFrame(sum(p.map(run, tick, chunksize=8), []))
    R.to_csv(HERE / "timeframe_shift_30m_4h.csv", index=False)
    nd = R.date.nunique()
    lab = {"A": "A: 1H EMA level, daily 8 higher TF, 30m candle, exit 5h", "A_2h30": "A: same, exit 2.5h",
           "B": "B: 30m EMA level, 4H 8 higher TF, 30m candle, exit 2.5h (5 candles)", "B_5h": "B: same, exit 5h"}
    for rr in (False, True):
        print(f"\n{'WITH 2:1 RULE (stop <= 0.5%)' if rr else 'ALL (0.5% cap)'}  -- {nd} days, Jul 1 - Sep 30 2026")
        print("| structure | trades | per day | median stop | target / stopped | win% | mean % | per 1% of stop | Jul / Aug / Sep |\n|---|---|---|---|---|---|---|---|---|")
        for v in ("A", "A_2h30", "B", "B_5h"):
            x = R[(R.variant == v) & ((R.stop_pct <= 0.5) if rr else True)]
            e = x.exit.value_counts(normalize=True); m = x.groupby(pd.to_datetime(x.date).dt.month).ret.mean()
            print(f"| {lab[v]} | {len(x)} | {len(x)/nd:.1f} | {x.stop_pct.median():.2f}% | {e.get('target',0)*100:.0f}% / {e.get('stop',0)*100:.0f}% | {(x.ret>0).mean()*100:.0f} | "
                  f"{x.ret.mean():+.3f} | {x.ret.mean()/x.stop_pct.mean():.2f} | " + " / ".join(f"{a:+.2f}" for a in m) + " |")
    a = R[R.variant == "A"][["ticker", "date"]].drop_duplicates(); b = R[R.variant == "B"][["ticker", "date"]].drop_duplicates()
    both = a.merge(b, on=["ticker", "date"]); print(f"\noverlap: stock-days in both A and B: {len(both)} (A {len(a)}, B {len(b)})")
