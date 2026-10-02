"""(1) Add the 09:15 setup candle back (entry at its 10:15 close -- user: no ENTRY before 10:15, the 09:15 candle can be
the setup). (2) User's reward:risk rule as a filter: with a 1% target, keep only setups whose stop <= 0.5% (>= 2:1) or
<= 0.33% (>= 3:1). Spec fixed 2026-10-02 before running. Same checklist as 38 (shorts): 1H trend, red candle rejecting
1H EMA34, close within 0.5% of EMA34, close below daily 8-EMA, day's high so far >= live daily 8-EMA, daily ADX <= 25,
close below session VWAP (first hour: VWAP of the 09:15 candle = its typical price). Outcomes = 15's stored results."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from market_regime import _compute_adx
HERE = Path(__file__).resolve().parent; A8 = 2 / 9; SPLIT = pd.Timestamp("2025-07-01")


def feats(args):
    t, g = args
    try: d = load(t)
    except Exception: return []
    d = d[d.index < pd.Timestamp("2026-10-01")]
    d8y = d.Close.ewm(span=8, adjust=False).mean().shift(1); adx = _compute_adx(d)[0].shift(1)
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0)
    h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    out = []
    for r in g.itertuples():
        if r.bt not in h.index: continue
        b = h.loc[r.bt]; D8 = d8y.get(r.date, np.nan)
        s = 1 if r.side == "long" else -1
        ext = D8 * (1 + s * r.d8_ext_vs_d8_pct / 100); live = A8 * r.price + (1 - A8) * D8
        st_live = (live - ext) / live * 100 if s == -1 else (ext - live) / live * 100
        vw = (b.High + b.Low + b.Close) / 3
        out.append(dict(key=r.Index, dadx=adx.get(r.date, np.nan), st_live=st_live, vwap_with=bool((r.price - vw) * s > 0)))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    A = pd.read_csv(HERE / "intraday_1h34_daily8_results.csv", parse_dates=["date"])
    A["bt"] = pd.to_datetime(A.ts, utc=True).dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    A = A[A.trend & (A.dstate != "wrong") & (A.date >= "2024-01-01")]
    F9 = A[A.bt.dt.strftime("%H:%M") == "09:15"]
    with Pool(6) as p: f = sum(p.map(feats, list(F9.groupby("ticker"))), [])
    F9 = F9.join(pd.DataFrame(f).set_index("key"))
    X = pd.read_csv(HERE / "gap_live_entry_1h.csv", parse_dates=["date", "bar_ts"]).rename(columns={"bar_ts": "bt"})
    cols = ["ticker", "date", "bt", "side", "price", "stop_pct", "ret", "close_past_ema", "dadx", "st_live", "vwap_with"]
    U = pd.concat([F9[cols], X[cols]], ignore_index=True)
    U = U[(U.side == "short") & (U.dadx <= 25) & (U.vwap_with == True) & (U.st_live <= 0) & (U.close_past_ema > 0) & (U.close_past_ema <= 0.5)
          & (U.bt.dt.strftime("%H:%M") <= "11:15")].copy()
    U["entry_time"] = (U.bt + pd.Timedelta("60min")).dt.strftime("%H:%M")
    U.to_csv(HERE / "checklist_shorts_with_0915.csv", index=False)
    days = pd.Index(sorted(pd.concat([A.date]).unique())); nd = len(days); ndu = (days >= SPLIT).sum()
    def line(x, lab):
        y = x.groupby(x.date.dt.year).ret.mean(); u = x[x.date >= SPLIT]
        print(f"| {lab} | {len(x)} | {len(x)/nd:.1f} | {x.stop_pct.median():.2f}% | {(x.ret>0).mean()*100:.0f} | {x.ret.mean():+.3f} | "
              + " / ".join(f"{v:+.2f}" for v in y) + f" | {u.ret.mean():+.3f} |")
    H = "| group | trades | per day | median stop | win% | mean % | 2024 / 2025 / 2026 | unseen |\n|---|---|---|---|---|---|---|---|"
    print("(1) BY ALARM (checklist shorts, 0.5% cap)\n" + H)
    for t, g in U.groupby("entry_time"): line(g, f"alarm {t}")
    print("\n(2) REWARD:RISK FILTER (1% target), alarms 10:15 + 11:15 + 12:15\n" + H)
    line(U, "all (as scanned)")
    line(U[U.stop_pct <= 0.5], "stop <= 0.5%  (reward:risk >= 2:1)")
    line(U[U.stop_pct <= 0.333], "stop <= 0.33% (reward:risk >= 3:1)")
    line(U[U.stop_pct > 0.5], "stop > 0.5%   (what the 2:1 rule skips)")
    print("\nONE TRADE AT A TIME (first setup, closest to EMA on ties), reward:risk >= 2:1:")
    V = U[U.stop_pct <= 0.5].sort_values(["date", "entry_time", "close_past_ema"])
    first = V.groupby("date").head(1)
    print(f"  days with a trade {len(first)/nd*100:.0f}% | mean {first.ret.mean():+.3f}% | win {(first.ret>0).mean()*100:.0f}% | unseen {first[first.date>=SPLIT].ret.mean():+.3f}% | first-trade alarm mix {first.entry_time.value_counts(normalize=True).round(2).to_dict()}")


if __name__ == "__main__":
    print("\n(3) 2:1 FILTER BY ALARM, and one-trade-a-day by alarm set (2:1 filter on)\n" + H)
    W = U[U.stop_pct <= 0.5]
    for t, g in W.groupby("entry_time"): line(g, f"2:1, alarm {t}")
    print("| alarms | days with a trade | mean % | win% | unseen mean % |\n|---|---|---|---|---|")
    for al in (["10:15", "11:15", "12:15"], ["11:15", "12:15"], ["10:15", "11:15"]):
        f = W[W.entry_time.isin(al)].sort_values(["date", "entry_time", "close_past_ema"]).groupby("date").head(1)
        print(f"| {' + '.join(al)} | {len(f)/nd*100:.0f}% | {f.ret.mean():+.3f} | {(f.ret>0).mean()*100:.0f} | {f[f.date>=SPLIT].ret.mean():+.3f} |")
