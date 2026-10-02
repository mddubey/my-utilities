"""Same-day market direction vs shorts over 3 years incl. the 2024/2025 up years (2026-10-02). Spec fixed before running.
Trades: 1H-close checklist shorts (setup 10:15/11:15 -> entry 11:15/12:15, wick through live daily 8-EMA, daily ADX
<= 25, VWAP side, close within 0.5% of 1H EMA34), 2024-01 .. 2026-09; also with the 2:1 rule (stop <= 0.5%).
At entry (setup candle close): Nifty green/red vs yesterday's close (Yahoo 1H Nifty); breadth = share of liquid stocks
(prior-day tv20 >= Rs 10cr) above yesterday's close at that hour close, from h1_cache. Bullish > 0.65, bearish < 0.35."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
HERE = Path(__file__).resolve().parent


def one(t):
    try: d = load(t)
    except Exception: return None
    d = d[d.index < pd.Timestamp("2026-10-01")]
    pc, tv = d.Close.shift(1), d.traded_value_sma20.shift(1)
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0)
    h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    h = h[(h.index >= "2024-01-01") & h.index.strftime("%H:%M").isin(["10:15", "11:15"])]
    if h.empty: return None
    day = h.index.normalize()
    prev = pd.Series(day, index=h.index).map(pc).values; liq = pd.Series(day, index=h.index).map(tv).fillna(0).values >= 1e8
    return pd.DataFrame({"bt": h.index[liq], "up": (h.Close.values > prev)[liq]})


if __name__ == "__main__":
    from multiprocessing import Pool
    tick = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    with Pool(6) as p: parts = [r for r in p.map(one, tick, chunksize=20) if r is not None]
    BR = pd.concat(parts).groupby("bt").agg(n=("up", "size"), adv=("up", "mean")); BR = BR[BR.n >= 200]
    N = pd.read_csv(HERE / "index_1h" / "_NIFTY_1h.csv", index_col=0); N.index = pd.to_datetime(N.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    NDp = pd.read_csv(HERE.parent / "data_cache" / "_NIFTY.csv", parse_dates=["Date"]).set_index("Date").Close.shift(1)
    X = pd.read_csv(HERE / "gap_live_entry_1h.csv", parse_dates=["date", "bar_ts"])
    K = X[(X.side == "short") & X.bar_ts.dt.strftime("%H:%M").isin(["10:15", "11:15"]) & (X.dadx <= 25) & (X.vwap_with == True)
          & (X.st_live <= 0) & (X.close_past_ema > 0) & (X.close_past_ema <= 0.5)].copy()
    K["nifty_green"] = [N.Close.get(b, np.nan) > NDp.get(d_, np.nan) if b in N.index else np.nan for b, d_ in zip(K.bar_ts, K.date)]
    K["adv"] = K.bar_ts.map(BR.adv)
    K["breadth"] = np.select([K.adv > 0.65, K.adv < 0.35], ["bullish", "bearish"], "mixed"); K.loc[K.adv.isna(), "breadth"] = np.nan
    for rr in (False, True):
        D = K[K.stop_pct <= 0.5] if rr else K
        print(f"\n### {'WITH 2:1 RULE' if rr else 'ALL (0.5% cap)'}  (n={len(D)})")
        print("| market at entry | 2024 (Nifty +8.8%) | 2025 (Nifty +10.5%) | 2026 (Nifty -14.2%) | all |\n|---|---|---|---|---|")
        for lab, m in (("all trades", np.ones(len(D), bool)), ("Nifty GREEN on the day", D.nifty_green == True), ("Nifty RED on the day", D.nifty_green == False),
                       ("breadth bullish (>65% up)", D.breadth == "bullish"), ("breadth mixed", D.breadth == "mixed"), ("breadth bearish (<35% up)", D.breadth == "bearish")):
            x = D[m]; cells = []
            for y in (2024, 2025, 2026):
                z = x[x.date.dt.year == y]; cells.append(f"{z.ret.mean():+.3f} (n {len(z)})" if len(z) >= 20 else f"n {len(z)}")
            print(f"| {lab} | " + " | ".join(cells) + f" | {x.ret.mean():+.3f} (n {len(x)}) |")
    print("\nshare of trades on Nifty-green days by year:", K.groupby(K.date.dt.year).nifty_green.mean().round(2).to_dict())
