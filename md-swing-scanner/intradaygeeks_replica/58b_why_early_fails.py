"""Why do ~1/3 of 25-min early setups stop qualifying at the full 30-min close? (follow-up to 58, 2026-10-03)
Re-checks each condition at bar 5 vs bar 6 of the candle for the n=5 setups and records which one(s) broke."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import importlib.util, os
HERE = Path(__file__).resolve().parent
src = open(HERE / "58_partial_candle.py").read().split("def run(t):")[0]
exec(compile(src, "58h", "exec"))


def run(t):
    if not (H1 / f"{t}.csv").exists() or not (M5 / f"{t}.csv").exists(): return []
    try: d = load(t)
    except Exception: return []
    d = d[d.index < pd.Timestamp("2026-10-01")]
    h1, m5 = read(H1 / f"{t}.csv"), read(M5 / f"{t}.csv"); h1 = h1[h1.index < "2026-10-01"]
    if len(h1) < 200 or m5.empty: return []
    e34h = h1.Close.ewm(span=34, adjust=False).mean().shift(1); e8h = h1.Close.ewm(span=8, adjust=False).mean().shift(1)
    d8y = d.Close.ewm(span=8, adjust=False).mean().shift(1); adx = _compute_adx(d)[0].shift(1); tv = d.traded_value_sma20.shift(1)
    out = []
    for day, g in m5.groupby(m5.index.normalize()):
        if day >= pd.Timestamp("2026-10-01") or len(g) < 70 or day not in d.index or tv.get(day, 0) < 1e8 or bool(d.corp_action_day.get(day, False)): continue
        if abs(g.Close.iloc[-1] / d.Close.loc[day] - 1) > 0.02: continue
        D8, AD = d8y.get(day, np.nan), adx.get(day, np.nan)
        if np.isnan(D8) or np.isnan(AD) or AD > 25: continue
        O, H, L, C, V, T = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.Volume.values, g.index
        vw = np.cumsum((H + L + C) / 3 * V) / np.maximum(np.cumsum(V), 1); hi_day = np.maximum.accumulate(H)
        base = day + pd.Timedelta("9h15min"); k30 = (T - base) // pd.Timedelta("30min")
        for q in (2, 3, 4, 5):
            qi = np.where(k30 == q)[0]
            if len(qi) < 6: continue
            cs = base + q * pd.Timedelta("30min"); hs = base + ((cs - base) // pd.Timedelta("60min")) * pd.Timedelta("60min")
            E, E8 = e34h.get(hs, np.nan), e8h.get(hs, np.nan)
            if np.isnan(E) or not E8 < E: continue
            def checks(n):
                bi = qi[:n]; b = bi[-1]; qo, qh, qc = O[bi[0]], H[bi].max(), C[b]
                return {"red": qc < qo, "high touches EMA": qh >= E, "close back below EMA": qc < E,
                        "within 0.5% of EMA": (E - qc) / E * 100 <= 0.5, "below daily 8-EMA": qc < D8,
                        "wick through live daily 8": hi_day[b] >= A8 * qc + (1 - A8) * D8, "below VWAP": qc < vw[b],
                        "stop <= 0.5% (2:1)": (qh - qc) / qc * 100 <= 0.5}
            c5 = checks(5)
            if not all(c5.values()): continue
            c6 = checks(6)
            out.append({k: (not v) for k, v in c6.items()})
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    tick = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p: R = pd.DataFrame(sum(p.map(run, tick, chunksize=8), []))
    failed = R[R.any(axis=1)]
    print(f"25-min setups {len(R)} | failed at the close {len(failed)} ({len(failed)/len(R)*100:.0f}%)\n")
    print("| condition that broke in the last 5 min | share of the failures | what it means |\n|---|---|---|")
    meaning = {"close back below EMA": "price climbed back above the EMA -- rejection failed",
               "red": "candle turned green", "stop <= 0.5% (2:1)": "a new high widened the stop past 0.5%",
               "within 0.5% of EMA": "price fell more than 0.5% below the EMA (moved away)",
               "below VWAP": "price rose back above VWAP", "below daily 8-EMA": "price rose above the daily 8-EMA",
               "wick through live daily 8": "daily-8 condition flipped", "high touches EMA": "-"}
    for k, v in failed.mean().sort_values(ascending=False).items():
        if v > 0: print(f"| {k} | {v*100:.0f}% | {meaning[k]} |")
