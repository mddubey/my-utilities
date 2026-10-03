"""His SWING 1H scanner (CHARTINK_QUERIES.md s.1) as a tradable rule. Spec fixed 2026-10-02 before running.
Scanner: BUY = 1H close > EMA34 and close < EMA8 (EMAs incl. that candle, as chartink evaluates); SELL = mirror
(close < 2500). Signal = FIRST hour the condition becomes true (transition), setup candle 10:15 or 11:15
(entry 11:15 / 12:15 = the user's alarms). Variants: (raw) any candle; (turn) candle closes in trade direction.
Entry = candle close, stop = candle low (buy) / high (sell), target 1%, out after 5 candles or the day's last candle,
stop first. Liquid (prior-day tv20 >= Rs 10cr), no corp action, 1H/daily close within 2%. One trade per ticker per day.
2024-01 .. 2026-09. Reported by side and year, with/without the 2:1 rule, gross and net @0.06% / 0.10%."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
HERE = Path(__file__).resolve().parent


def run(t):
    p = HERE / "h1_cache" / f"{t}.csv"
    if not p.exists(): return []
    try: d = load(t)
    except Exception: return []
    d = d[d.index < pd.Timestamp("2026-10-01")]
    h = pd.read_csv(p, index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    h = h[((h.Volume > 0) | (h.High != h.Low)) & (h.index < "2026-10-01")]
    if len(h) < 300: return []
    O, H, L, C, T = h.Open.values, h.High.values, h.Low.values, h.Close.values, h.index
    e8 = h.Close.ewm(span=8, adjust=False).mean().values; e34 = h.Close.ewm(span=34, adjust=False).mean().values
    buy = (C > e34) & (C < e8); sell = (C < e34) & (C > e8) & (C < 2500)
    day = T.normalize(); last = np.r_[day[1:] != day[:-1], True]
    tv = d.traded_value_sma20.shift(1); ca = d.corp_action_day.fillna(False)
    dcl = h.Close.groupby(day).last()
    okd = {dd: (tv.get(dd, 0) >= 1e8) and not bool(ca.get(dd, False)) and dd in d.index and abs(dcl[dd] / d.Close.loc[dd] - 1) <= 0.02 for dd in dcl.index}
    rows, done = [], set()
    for i in range(200, len(C) - 1):
        if T[i] < pd.Timestamp("2024-01-01") or T[i].strftime("%H:%M") not in ("10:15", "11:15") or not okd.get(day[i], False): continue
        for s, cond in ((1, buy), (-1, sell)):
            if not cond[i] or cond[i - 1]: continue
            turn = (C[i] - O[i]) * s > 0
            for var in ("raw", "turn"):
                if var == "turn" and not turn: continue
                if (day[i], s, var) in done: continue
                entry = C[i]; stop = L[i] if s == 1 else H[i]; risk = (entry - stop) * s
                if risk <= 0: continue
                tgt = entry * (1 + s * 0.01); px = None
                for j in range(i + 1, len(C)):
                    if day[j] != day[i]: px = C[j - 1]; break
                    if (L[j] <= stop) if s == 1 else (H[j] >= stop): px = stop; break
                    if (H[j] >= tgt) if s == 1 else (L[j] <= tgt): px = tgt; break
                    if j - i >= 5 or last[j]: px = C[j]; break
                if px is None: continue
                rows.append(dict(ticker=t, date=day[i], hour=T[i].strftime("%H:%M"), side="long" if s == 1 else "short", var=var,
                                 stop_pct=risk / entry * 100, ret=(px - entry) / entry * 100 * s))
                done.add((day[i], s, var))
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    tick = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    with Pool(6) as p: R = pd.DataFrame(sum(p.map(run, tick, chunksize=10), []))
    R.to_csv(HERE / "swing_1h_pullback.csv", index=False)
    nd = R.date.nunique()
    def cell(x): return f"{x.ret.mean():+.3f} (n {len(x)})" if len(x) >= 30 else f"n {len(x)}"
    for rr in (False, True):
        print(f"\n### SWING 1H pullback {'WITH 2:1 RULE' if rr else '(all stops)'}\n| variant | side | 2024 | 2025 | 2026 | all | per day | median stop | win% | net @0.06 | net @0.10 |\n|---|---|---|---|---|---|---|---|---|---|---|")
        D = R[R.stop_pct <= 0.5] if rr else R
        for v in ("raw", "turn"):
            for sd in ("long", "short"):
                x = D[(D["var"] == v) & (D.side == sd)]
                if len(x) < 30: continue
                print(f"| {v} | {sd} | " + " | ".join(cell(x[x.date.dt.year == y]) for y in (2024, 2025, 2026)) +
                      f" | {cell(x)} | {len(x)/nd:.1f} | {x.stop_pct.median():.2f}% | {(x.ret>0).mean()*100:.0f} | {x.ret.mean()-0.06:+.3f} | {x.ret.mean()-0.10:+.3f} |")
