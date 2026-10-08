"""Re-test the long side (user, 2026-10-06): the last long backtest was 2026-10-02 (scripts 48/49/52/53, all
closed-negative), but those numbers came from script 15's 3-year 1H set, which was found to have a
POSITION-BLOCKING BIAS the very next day (60_filter_ablation.py, 2026-10-03) -- "every 3-year 1H figure derived
from 15 (12-49 scripts' 1H sets) is overstated ... directions need re-checking on clean data." That re-check was
done for shorts, never for longs. Longs also predate: the daily ATR>=2.56% filter (10-03), and the bias-free
"clean generator" engine itself (60/63's gen_a/gen_b). This mirrors that exact engine for longs -- same six
filters, same 2:1 rule, same ATR/ADX/liquidity gates, same exit walk, support instead of resistance.

Does NOT yet include the 2026-10-04 refinements (full-hour-bar-at-close trigger, strong-green-hour skip, EMA8-zone
skip) -- those are layered on top of this exact population for shorts (scripts 68/70+); this is the apples-to-
apples re-test of the CORE checklist + bias fix + ATR filter the long side has never been run under. If this
flips or looks promising, the later refinements can be layered in next.

User's own prior: overnight gains / intraday fade (Berkman et al. 2012, Lou/Polk/Skouras 2019) predicts longs
should still lose intraday -- this is a fair re-test, not an expectation this will reverse."""
import sys, warnings
warnings.filterwarnings("ignore")
import importlib.util
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from data.paths import INTRADAY_5M_DIR

spec = importlib.util.spec_from_file_location("gen60", HERE / "60_filter_ablation.py")
gen60 = importlib.util.module_from_spec(spec); spec.loader.exec_module(gen60)
read, hour_key, daily_inputs, A8 = gen60.read, gen60.hour_key, gen60.daily_inputs, gen60.A8
gen60.END = pd.Timestamp("2026-10-07")   # include today (10-06), not just through yesterday


def walk_long(H, L, C, T, b, ql, qc, end_ok):
    tgt, hi, why = qc * 1.01, -np.inf, "eod"
    for k in range(b + 1, len(C)):
        if L[k] <= ql: px, why = ql, "stop"; break
        hi = max(hi, H[k])
        if H[k] >= tgt: px, why = tgt, "target"; break
        if end_ok(k): px, why = C[k], "time"; break
    else:
        px = C[-1]
    return px, why, (max(hi, qc) - qc) / qc * 100


def gen_a_long(t):
    p = INTRADAY_5M_DIR / f"{t}.csv"
    if not p.exists(): return []
    try: d, d8y, adx, tv = daily_inputs(t)
    except Exception: return []
    m = read(p)
    if len(m) < 1500: return []
    hc = m.Close.groupby(hour_key(m.index)).last()
    e34 = hc.ewm(span=34, adjust=False).mean().shift(1); e8 = hc.ewm(span=8, adjust=False).mean().shift(1)
    atrp = (d.atr14 / d.Close * 100).shift(1); rows = []
    for day, g in m.groupby(m.index.normalize()):
        if day < pd.Timestamp("2026-06-10") or len(g) < 70 or tv.get(day, 0) < 1e8 or bool(d.corp_action_day.get(day, False)): continue
        D8, AD, AP = d8y.get(day, np.nan), adx.get(day, np.nan), atrp.get(day, np.nan)
        if np.isnan(D8) or np.isnan(AD) or AD > 25 or not AP >= 2.56: continue
        O, H, L, C, V, T = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.Volume.values, g.index
        vw = np.cumsum((H + L + C) / 3 * V) / np.maximum(np.cumsum(V), 1); lo_day = np.minimum.accumulate(L)
        base = day + pd.Timedelta("9h15min"); k30 = (T - base) // pd.Timedelta("30min")
        for q in (2, 3, 4, 5):
            qi = np.where(k30 == q)[0]
            if len(qi) < 6: continue
            hs = base + ((q * 30) // 60) * pd.Timedelta("60min")
            E, E8 = e34.get(hs, np.nan), e8.get(hs, np.nan)
            if np.isnan(E): continue
            b = qi[-1]; qo, ql, qc = O[qi[0]], L[qi].min(), C[b]
            if not (ql <= E and qc > E and (qc - E) / E * 100 <= 0.5 and (qc - ql) / qc * 100 <= 0.5): continue
            if not (E8 > E and qc > qo and qc > D8 and lo_day[b] <= A8 * qc + (1 - A8) * D8 and qc > vw[b]): continue
            end = T[b] + pd.Timedelta("5h")
            px, why, mfe = walk_long(H, L, C, T, b, ql, qc, lambda k: T[k] >= end)
            rows.append(dict(set="a", ticker=t, date=day, ret=(px - qc) / qc * 100, why=why, mfe=mfe, stop_pct=(qc - ql) / qc * 100))
    return rows


def gen_b_long(t):
    p = HERE / "h1_cache" / f"{t}.csv"
    if not p.exists(): return []
    try: d, d8y, adx, tv = daily_inputs(t)
    except Exception: return []
    h = read(p)
    if len(h) < 300: return []
    O, H, L, C, V, T = h.Open.values, h.High.values, h.Low.values, h.Close.values, h.Volume.values, h.index
    E34 = h.Close.ewm(span=34, adjust=False).mean().shift(1).values; E8 = h.Close.ewm(span=8, adjust=False).mean().shift(1).values
    day = T.normalize(); last = np.r_[day[1:] != day[:-1], True]
    tp = (h.High + h.Low + h.Close) / 3
    vw = ((tp * h.Volume).groupby(day).cumsum() / h.Volume.groupby(day).cumsum().replace(0, np.nan)).values
    lo_day = h.Low.groupby(day).cummin().values; atrp = (d.atr14 / d.Close * 100).shift(1); rows = []
    for i in range(200, len(C) - 1):
        if T[i] < pd.Timestamp("2024-01-01") or T[i].strftime("%H:%M") not in ("10:15", "11:15"): continue
        dd = day[i]
        if tv.get(dd, 0) < 1e8 or bool(d.corp_action_day.get(dd, False)): continue
        D8, AD, AP = d8y.get(dd, np.nan), adx.get(dd, np.nan), atrp.get(dd, np.nan)
        if np.isnan(D8) or np.isnan(E34[i]) or np.isnan(AD) or AD > 25 or not AP >= 2.56: continue
        E = E34[i]; ql, qc = L[i], C[i]
        if not (ql <= E and qc > E and (qc - E) / E * 100 <= 0.5 and (qc - ql) / qc * 100 <= 0.5): continue
        if not (E8[i] > E and qc > O[i] and qc > D8 and lo_day[i] <= A8 * qc + (1 - A8) * D8 and qc > vw[i]): continue
        j_end = i + 1
        while j_end < len(C) and day[j_end] == dd and not (j_end - i >= 5 or last[j_end]): j_end += 1
        if j_end >= len(C) or day[j_end] != dd: continue
        px, why, mfe = walk_long(H[:j_end + 1], L[:j_end + 1], C[:j_end + 1], T, i, ql, qc, lambda k: k == j_end)
        rows.append(dict(set="b", ticker=t, date=dd, ret=(px - qc) / qc * 100, why=why, mfe=mfe, stop_pct=(qc - ql) / qc * 100))
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in INTRADAY_5M_DIR.glob("*.csv") if not p.stem.startswith("_"))
    t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    print(f"scanning {len(t5)} tickers (30m/5m set) + {len(t1)} tickers (1H set)...")
    with Pool(6) as pool:
        A = pd.DataFrame(sum(pool.map(gen_a_long, t5, chunksize=10), []))
        B = pd.DataFrame(sum(pool.map(gen_b_long, t1, chunksize=10), []))
    pd.concat([A, B]).to_csv(HERE / "long_mirror.csv", index=False)

    for nm, x in (("a_long (30m, Jun-Sep 2026)", A), ("b_long (1H, 2024-26)", B)):
        if not len(x):
            print(f"\n{nm}: 0 setups"); continue
        days = x.date.nunique()
        x["per"] = pd.to_datetime(x.date).dt.strftime("%Y-%m") if nm.startswith("a") else pd.to_datetime(x.date).dt.year
        print(f"\n=== {nm}: n={len(x)}, {days} days, {len(x)/days:.2f}/day ===")
        print(f"mean ret%: {x.ret.mean():+.3f}  win%: {(x.ret>0).mean()*100:.1f}  "
              f"target%: {(x.why=='target').mean()*100:.1f}  stop%: {(x.why=='stop').mean()*100:.1f}  "
              f"median stop%: {x.stop_pct.median():.2f}")
        print(x.groupby("per").ret.agg(["count", "mean"]).round(3).to_string())
