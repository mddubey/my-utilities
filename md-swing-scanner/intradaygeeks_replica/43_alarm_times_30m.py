"""Alarm timing for the 30-min trigger (user's chosen version, 2026-10-02). Spec fixed before running.
Level = 1H EMA34 as of the last completed hour before the 30m candle's hour; 1H EMA8 < EMA34; higher TF = live daily
8-EMA (price below; day's high so far >= it); daily ADX(yday) <= 25; below session VWAP; liquid; 30m candle red, high
>= level, close < level within 0.5%; 2:1 rule (stop = candle high <= 0.5%). Short at close, target -1%, out 5h/EOD.
Every 30m candle close from 10:15 to 14:45 evaluated independently (5m data Jun 10 - Sep 30 2026)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from market_regime import _compute_adx
HERE = Path(__file__).resolve().parent
H1, M5 = HERE / "h1_cache", HERE.parent / "intraday_cache"; A8 = 2 / 9


def read(p):
    x = pd.read_csv(p, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[(x.Volume > 0) | (x.High != x.Low)]


def run(t):
    if not (H1 / f"{t}.csv").exists() or not (M5 / f"{t}.csv").exists(): return []
    try: d = load(t)
    except Exception: return []
    d = d[d.index < pd.Timestamp.now().normalize()]
    h1, m5 = read(H1 / f"{t}.csv"), read(M5 / f"{t}.csv")
    if len(h1) < 200 or m5.empty: return []
    e34h = h1.Close.ewm(span=34, adjust=False).mean().shift(1); e8h = h1.Close.ewm(span=8, adjust=False).mean().shift(1)
    d8y = d.Close.ewm(span=8, adjust=False).mean().shift(1); adx = _compute_adx(d)[0].shift(1); tv = d.traded_value_sma20.shift(1)
    rows = []
    for day, g in m5.groupby(m5.index.normalize()):
        if len(g) < 70 or day not in d.index or tv.get(day, 0) < 1e8 or bool(d.corp_action_day.get(day, False)): continue
        if abs(g.Close.iloc[-1] / d.Close.loc[day] - 1) > 0.02: continue
        D8, AD = d8y.get(day, np.nan), adx.get(day, np.nan)
        if np.isnan(D8) or np.isnan(AD) or AD > 25: continue
        O, H, L, C, V, T = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.Volume.values, g.index
        vw = np.cumsum((H + L + C) / 3 * V) / np.maximum(np.cumsum(V), 1); hi_day = np.maximum.accumulate(H)
        base = day + pd.Timedelta("9h15min")
        k30 = (T - base) // pd.Timedelta("30min")
        for q in range(1, 11):                                   # candles 09:45-10:15 (q=1) ... 14:15-14:45 (q=10)
            qi = np.where(k30 == q)[0]
            if len(qi) < 6: continue
            cs = base + q * pd.Timedelta("30min"); ce = cs + pd.Timedelta("30min")
            hs = base + ((cs - base) // pd.Timedelta("60min")) * pd.Timedelta("60min")
            E, E8 = e34h.get(hs, np.nan), e8h.get(hs, np.nan)
            if np.isnan(E) or not E8 < E: continue
            qo, qh, qc = O[qi[0]], H[qi].max(), C[qi[-1]]; b = qi[-1]
            if not (qc < qo and qh >= E and qc < E and (E - qc) / E * 100 <= 0.5): continue
            if qc >= D8 or hi_day[b] < A8 * qc + (1 - A8) * D8 or qc >= vw[b]: continue
            stop_pct = (qh - qc) / qc * 100
            if stop_pct > 0.5: continue
            tgt, end = qc * 0.99, T[b] + pd.Timedelta("5h"); px, why, kk = C[-1], "eod", len(C) - 1
            for k in range(b + 1, len(C)):
                if H[k] >= qh: px, why, kk = qh, "stop", k; break
                if L[k] <= tgt: px, why, kk = tgt, "target", k; break
                if T[k] >= end: px, why, kk = C[k], "time", k; break
            rows.append(dict(ticker=t, date=day, alarm=f"{ce:%H:%M}", t_in=ce, t_out=T[kk] + pd.Timedelta("5min"),
                             below_ema=(E - qc) / E * 100, stop_pct=stop_pct, exit=why, ret=(qc - px) / qc * 100))
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    tick = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p: R = pd.DataFrame(sum(p.map(run, tick, chunksize=8), []))
    R.to_csv(HERE / "alarm_times_30m.csv", index=False); nd = max(R.date.nunique(), 1)
    print(f"window {pd.to_datetime(R.date).min():%Y-%m-%d} -> {pd.to_datetime(R.date).max():%Y-%m-%d}, {nd} days with setups")
    print("| alarm (30m close) | setups | per day | median stop | win% | mean % | per 1% of stop | Jun / Jul / Aug / Sep |\n|---|---|---|---|---|---|---|---|")
    for a, x in R.groupby("alarm"):
        m = x.groupby(pd.to_datetime(x.date).dt.month).ret.mean()
        print(f"| {a} | {len(x)} | {len(x)/nd:.1f} | {x.stop_pct.median():.2f}% | {(x.ret>0).mean()*100:.0f} | {x.ret.mean():+.3f} | {x.ret.mean()/x.stop_pct.mean():.2f} | "
              + " / ".join(f"{v:+.2f}" for v in m) + " |")
    print("\nONE TRADE AT A TIME (first setup seen at an alarm, closest to EMA on ties; next only after exit):")
    print("| alarm set | days with a trade | trades/day | mean % | win% | Jun / Jul / Aug / Sep |\n|---|---|---|---|---|---|")
    sets = {"10:45 11:15 11:45 12:15": ["10:45", "11:15", "11:45", "12:15"],
            "10:15 .. 12:15 (5)": ["10:15", "10:45", "11:15", "11:45", "12:15"],
            "10:15 .. 13:15 (7)": ["10:15", "10:45", "11:15", "11:45", "12:15", "12:45", "13:15"],
            "10:15 .. 14:45 (all 10)": sorted(R.alarm.unique())}
    for nm, al in sets.items():
        x = R[R.alarm.isin(al)].sort_values(["date", "t_in", "below_ema"]); keep = []
        for dte, g in x.groupby("date"):
            free = pd.Timestamp.min
            for r in g.itertuples():
                if r.t_in >= free: keep.append(r.Index); free = r.t_out
        k = x.loc[keep]; m = k.groupby(pd.to_datetime(k.date).dt.month).ret.mean()
        print(f"| {nm} | {k.date.nunique()/nd*100:.0f}% | {len(k)/nd:.2f} | {k.ret.mean():+.3f} | {(k.ret>0).mean()*100:.0f} | " + " / ".join(f"{v:+.2f}" for v in m) + " |")
