"""User's follow-up (2026-10-03) on 62: (1) does the 1H 8-EMA below a short entry actually act as SUPPORT -- i.e. does the
trade's low tend to stop AT the 8-EMA level -- and at what distance? (2) RAILTEL / AARTIIND / GOLDIAM had big falls 2 days
earlier: does a recent daily fall (a) put the 1H 8-EMA below entry more often, (b) hurt the trade?
Spec fixed before running. Same population as 62 (60's generators, all six filters + ATR >= 2.56%, no position blocking).
Per trade adds: E8 level at entry (1H EMA8 as of last completed hour, held fixed), exit reason, MFE% = (entry - lowest low
before exit)/entry*100, recent fall = prior-day-known daily Close change over 1d / 2d / 3d (horizons pre-declared: 1,2,3).
Support test: among trades with 8-EMA below entry, share whose lowest low lands within +-0.15% of the 8-EMA, vs a placebo
where each trade's d8 is shuffled (1,000 shuffles) -- if the 8-EMA does nothing, the real share equals the placebo."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
exec(compile(open(HERE / "60_filter_ablation.py").read().split("def gen_a")[0], "60head", "exec"))


def recent(d, day):
    c = d.Close[d.index < day]
    if len(c) < 5: return np.nan, np.nan, np.nan
    return tuple((c.iloc[-1] / c.iloc[-1 - k] - 1) * 100 for k in (1, 2, 3))


def walk(H, L, C, T, b, qh, qc, end_ok):
    tgt, lo, px, why = qc * 0.99, np.inf, C[-1], "eod"
    for k in range(b + 1, len(C)):
        if H[k] >= qh: px, why = qh, "stop"; break
        lo = min(lo, L[k])
        if L[k] <= tgt: px, why = tgt, "target"; break
        if end_ok(k): px, why = C[k], "time"; break
    return px, why, (qc - min(lo, qc)) / qc * 100


def gen_a(t):
    p = M5 / f"{t}.csv"
    if not p.exists(): return []
    try: d, d8y, adx, tv = daily_inputs(t)
    except Exception: return []
    m = read(p)
    if len(m) < 1500: return []
    hc = seeded_hourly(t, m)
    e34 = hc.ewm(span=34, adjust=False).mean().shift(1); e8 = hc.ewm(span=8, adjust=False).mean().shift(1)
    atrp = (d.atr14 / d.Close * 100).shift(1); rows = []
    for day, g in m.groupby(m.index.normalize()):
        if day < pd.Timestamp("2026-06-10") or len(g) < 70 or tv.get(day, 0) < 1e8 or bool(d.corp_action_day.get(day, False)): continue
        D8, AD, AP = d8y.get(day, np.nan), adx.get(day, np.nan), atrp.get(day, np.nan)
        if np.isnan(D8) or np.isnan(AD) or AD > 25 or not AP >= 2.56: continue
        O, H, L, C, V, T = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.Volume.values, g.index
        vw = np.cumsum((H + L + C) / 3 * V) / np.maximum(np.cumsum(V), 1); hi_day = np.maximum.accumulate(H)
        base = day + pd.Timedelta("9h15min"); k30 = (T - base) // pd.Timedelta("30min")
        for q in (2, 3, 4, 5):
            qi = np.where(k30 == q)[0]
            if len(qi) < 6: continue
            hs = base + ((q * 30) // 60) * pd.Timedelta("60min")
            E, E8 = e34.get(hs, np.nan), e8.get(hs, np.nan)
            if np.isnan(E): continue
            b = qi[-1]; qo, qh, qc = O[qi[0]], H[qi].max(), C[b]
            if not (qh >= E and qc < E and (E - qc) / E * 100 <= 0.5 and (qh - qc) / qc * 100 <= 0.5): continue
            if not (E8 < E and qc < qo and qc < D8 and hi_day[b] >= A8 * qc + (1 - A8) * D8 and qc < vw[b]): continue
            end = T[b] + pd.Timedelta("5h")
            px, why, mfe = walk(H, L, C, T, b, qh, qc, lambda k: T[k] >= end)
            r1, r2, r3 = recent(d, day)
            rows.append(dict(set="a", ticker=t, date=day, ret=(qc - px) / qc * 100, why=why, mfe=mfe, d8=(qc - E8) / qc * 100,
                             r1=r1, r2=r2, r3=r3))
    return rows


def gen_b(t):
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
    hi_day = h.High.groupby(day).cummax().values; atrp = (d.atr14 / d.Close * 100).shift(1); rows = []
    for i in range(200, len(C) - 1):
        if T[i] < pd.Timestamp("2024-01-01") or T[i].strftime("%H:%M") not in ("10:15", "11:15"): continue
        dd = day[i]
        if tv.get(dd, 0) < 1e8 or bool(d.corp_action_day.get(dd, False)): continue
        D8, AD, AP = d8y.get(dd, np.nan), adx.get(dd, np.nan), atrp.get(dd, np.nan)
        if np.isnan(D8) or np.isnan(E34[i]) or np.isnan(AD) or AD > 25 or not AP >= 2.56: continue
        E = E34[i]; qh, qc = H[i], C[i]
        if not (qh >= E and qc < E and (E - qc) / E * 100 <= 0.5 and (qh - qc) / qc * 100 <= 0.5): continue
        if not (E8[i] < E and qc < O[i] and qc < D8 and hi_day[i] >= A8 * qc + (1 - A8) * D8 and qc < vw[i]): continue
        j_end = i + 1
        while j_end < len(C) and day[j_end] == dd and not (j_end - i >= 5 or last[j_end]): j_end += 1
        if j_end >= len(C) or day[j_end] != dd: continue
        px, why, mfe = walk(H[:j_end + 1], L[:j_end + 1], C[:j_end + 1], T, i, qh, qc, lambda k: k == j_end)
        r1, r2, r3 = recent(d, dd)
        rows.append(dict(set="b", ticker=t, date=dd, ret=(qc - px) / qc * 100, why=why, mfe=mfe, d8=(qc - E8[i]) / qc * 100,
                         r1=r1, r2=r2, r3=r3))
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_")); t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    with Pool(6) as p:
        A = pd.DataFrame(sum(p.map(gen_a, t5, chunksize=10), [])); B = pd.DataFrame(sum(p.map(gen_b, t1, chunksize=10), []))
    pd.concat([A, B]).to_csv(HERE / "ema8_support.csv", index=False)
    print(len(A), A.ret.mean() * 1000, len(B), B.ret.mean() * 1000)
