"""User's rule: bullish day -> look for longs, bearish day -> shorts (2026-10-02). Spec fixed before running.
1H-close checklist setups BOTH sides (mirrored: 1H trend with trade, candle rejects 1H EMA34 and closes back within 0.5%,
day's extreme pierces the live daily 8-EMA, VWAP side, daily ADX <= 25), setup 10:15/11:15, 2024-01 .. 2026-09.
Breadth at entry = share of liquid stocks above yesterday's close (h1_cache): bullish > 0.65, bearish < 0.35.
Strategies: longs on bullish days + shorts on bearish days; mixed days -> (a) shorts only (b) both sides (c) skip."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
HERE = Path(__file__).resolve().parent


def one(t):            # identical to 47's breadth builder
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
    bp = HERE / "breadth_1h.csv"
    if bp.exists(): BR = pd.read_csv(bp, parse_dates=["bt"]).set_index("bt")
    else:
        tick = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
        with Pool(6) as p: parts = [r for r in p.map(one, tick, chunksize=20) if r is not None]
        BR = pd.concat(parts).groupby("bt").agg(n=("up", "size"), adv=("up", "mean")); BR = BR[BR.n >= 200]; BR.to_csv(bp)
    X = pd.read_csv(HERE / "gap_live_entry_1h.csv", parse_dates=["date", "bar_ts"])
    K = X[X.bar_ts.dt.strftime("%H:%M").isin(["10:15", "11:15"]) & (X.dadx <= 25) & (X.vwap_with == True) & (X.st_live <= 0)
          & (X.close_past_ema > 0) & (X.close_past_ema <= 0.5)].copy()
    K["adv"] = K.bar_ts.map(BR.adv)
    K["breadth"] = np.select([K.adv > 0.65, K.adv < 0.35], ["bullish", "bearish"], "mixed"); K = K[K.adv.notna()]
    def cell(x):
        return f"{x.ret.mean():+.3f} (n {len(x)})" if len(x) >= 20 else f"n {len(x)}"
    for rr in (False, True):
        D = K[K.stop_pct <= 0.5] if rr else K
        print(f"\n### {'WITH 2:1 RULE' if rr else 'ALL (0.5% cap)'}\n| side, breadth at entry | 2024 | 2025 | 2026 | all |\n|---|---|---|---|---|")
        for sd in ("long", "short"):
            for b in ("bullish", "mixed", "bearish"):
                x = D[(D.side == sd) & (D.breadth == b)]
                print(f"| {sd}, {b} | " + " | ".join(cell(x[x.date.dt.year == y]) for y in (2024, 2025, 2026)) + f" | {cell(x)} |")
        print("\n| strategy | 2024 | 2025 | 2026 | all | trades/day |\n|---|---|---|---|---|---|")
        nd = X.date.nunique()
        base_bull, base_bear = (D.side == "long") & (D.breadth == "bullish"), (D.side == "short") & (D.breadth == "bearish")
        for lab, m in (("shorts only (current)", D.side == "short"),
                       ("switch: long on bullish, short on bearish, SHORT on mixed", base_bull | base_bear | ((D.breadth == "mixed") & (D.side == "short"))),
                       ("switch: long on bullish, short on bearish, BOTH on mixed", base_bull | base_bear | (D.breadth == "mixed")),
                       ("switch: long on bullish, short on bearish, SKIP mixed", base_bull | base_bear),
                       ("both sides always", np.ones(len(D), bool))):
            x = D[m]
            print(f"| {lab} | " + " | ".join(cell(x[x.date.dt.year == y]) for y in (2024, 2025, 2026)) + f" | {cell(x)} | {len(x)/nd:.1f} |")
    print("\nshare of entry hours by breadth:", pd.Series(np.select([BR.adv > 0.65, BR.adv < 0.35], ["bullish", "bearish"], "mixed")).value_counts(normalize=True).round(2).to_dict())
