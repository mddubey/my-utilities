"""His 'SELL | VOLUME STRATEGY | 8 EMA' 15-min scanner as a short trade (user: shorts only). Spec fixed 2026-10-03.
Scanner: 15m close < EMA200 and close > EMA150 (EMAs incl. the candle). Displayed trigger '8 EMA rejection': red 15m
candle, high >= 15m EMA8 (as of previous candle), close < it. 15m bars from the 5m cache (09:15 grid). Ticker needs
>= 250 prior 15m bars (EMA200 warm-up). Entries on 15m closes 10:15..12:15, liquid (prior-day tv20 >= Rs 10cr).
Short at close, stop = candle high, target -1%, out at 5h or the day's last 5m close (stop first). One per ticker/day.
Window Jul 1 - Sep 30 2026. Compared with 43's 34-EMA 30m shorts (2:1) in the same months."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
HERE = Path(__file__).resolve().parent; M5 = HERE.parent / "intraday_cache"


def run(t):
    try: d = load(t)
    except Exception: return []
    tv = d.traded_value_sma20.shift(1)
    x = pd.read_csv(M5 / f"{t}.csv", index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    x = x[((x.Volume > 0) | (x.High != x.Low)) & (x.index < "2026-10-01")]
    if len(x) < 1500: return []
    day = x.index.normalize(); k = (x.index - day - pd.Timedelta("9h15min")) // pd.Timedelta("15min")
    key = day + pd.Timedelta("9h15min") + k * pd.Timedelta("15min")
    b = x.groupby(key).agg(Open=("Open", "first"), High=("High", "max"), Close=("Close", "last"))
    e200 = b.Close.ewm(span=200, adjust=False).mean(); e150 = b.Close.ewm(span=150, adjust=False).mean()
    e8p = b.Close.ewm(span=8, adjust=False).mean().shift(1)
    sig = (b.Close < e200) & (b.Close > e150) & (b.Close < b.Open) & (b.High >= e8p) & (b.Close < e8p)
    sig &= np.arange(len(b)) >= 250
    end = b.index + pd.Timedelta("15min"); et = end.strftime("%H:%M")
    sig &= (et >= "10:15") & (et <= "12:15") & (b.index >= "2026-07-01")
    H, L, C, T = x.High.values, x.Low.values, x.Close.values, x.index
    rows, done = [], set()
    for i in np.where(sig.values)[0]:
        dd = b.index[i].normalize()
        if dd in done or tv.get(dd, 0) < 1e8: continue
        bi = np.where(T == end[i] - pd.Timedelta("5min"))[0]
        if len(bi) == 0: continue
        j0 = bi[0]; e = b.Close.iloc[i]; st = b.High.iloc[i]
        if st <= e: continue
        tgt, lim = e * 0.99, T[j0] + pd.Timedelta("5h"); px = None
        for j in range(j0 + 1, len(C)):
            if T[j].normalize() != dd: px = C[j - 1]; break
            if H[j] >= st: px = st; break
            if L[j] <= tgt: px = tgt; break
            if T[j] >= lim: px = C[j]; break
        if px is None: px = C[-1]
        rows.append(dict(ticker=t, date=dd, t_in=end[i], stop_pct=(st - e) / e * 100, ret=(e - px) / e * 100))
        done.add(dd)
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    tick = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p: R = pd.DataFrame(sum(p.map(run, tick, chunksize=10), []))
    R.to_csv(HERE / "volume_strategy_15m_sell.csv", index=False); R["date"] = pd.to_datetime(R.date)
    E = pd.read_csv(HERE / "alarm_times_30m.csv", parse_dates=["date", "t_in"])
    E = E[E.alarm.isin(["10:45", "11:15", "11:45", "12:15"]) & (E.date >= "2026-07-01")]
    nd = R.date.nunique()
    def line(x, lab):
        m = x.groupby(x.date.dt.month).ret.mean()
        print(f"| {lab} | {len(x)} | {len(x)/nd:.1f} | {x.stop_pct.median():.2f}% | {(x.ret>0).mean()*100:.0f} | {x.ret.mean():+.3f} | "
              + " / ".join(f"{v:+.2f}" for v in m) + f" | {x.ret.mean()-0.06:+.3f} |")
    print(f"window {R.date.min():%Y-%m-%d} -> {R.date.max():%Y-%m-%d}, {nd} days\n| shorts, Jul-Sep 2026 | trades | per day | median stop | win% | mean % | Jul / Aug / Sep | net @0.06 |\n|---|---|---|---|---|---|---|---|")
    line(R, "VOLUME STRATEGY sell, all stops"); line(R[R.stop_pct <= 0.5], "VOLUME STRATEGY sell, 2:1 rule")
    line(E, "our 34-EMA 30m shorts, 2:1 (reference)")
    for nm, D in (("VOLUME STRATEGY 2:1", R[R.stop_pct <= 0.5]), ("our 34-EMA 30m 2:1", E)):
        one = D.sort_values(["date", "t_in", "stop_pct"]).groupby("date").head(1)
        line(one, f"ONE PER DAY: {nm}")
