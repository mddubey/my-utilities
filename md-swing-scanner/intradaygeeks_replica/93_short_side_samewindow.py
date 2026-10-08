"""Short-side baseline regenerated under the SAME data window as 92_long_side_mirror.py (through 2026-10-05,
not the old 2026-10-01 cutoff used by 60/63) -- for a true apples-to-apples long-vs-short comparison on identical
data, same universe, same day. Logic is an exact copy of 63_ema8_support_and_recent_fall.py's gen_a/gen_b (the
bias-free, ATR-filtered, current-core-checklist engine) -- verified against that source, not reimplemented from
memory."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from backtest import load
from market_regime import _compute_adx
from data.paths import INTRADAY_5M_DIR
A8 = 2 / 9
END = pd.Timestamp("2026-10-07")


def read(p):
    x = pd.read_csv(p, index_col=0); x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[((x.Volume > 0) | (x.High != x.Low)) & (x.index < END)]


def hour_key(idx):
    d = idx.normalize(); return d + pd.Timedelta("9h15min") + ((idx - d - pd.Timedelta("9h15min")) // pd.Timedelta("60min")) * pd.Timedelta("60min")


def daily_inputs(t):
    d = load(t); d = d[d.index < END]
    return d, d.Close.ewm(span=8, adjust=False).mean().shift(1), _compute_adx(d)[0].shift(1), d.traded_value_sma20.shift(1)


def walk(H, L, C, T, b, qh, qc, end_ok):
    tgt, lo, why = qc * 0.99, np.inf, "eod"
    for k in range(b + 1, len(C)):
        if H[k] >= qh: px, why = qh, "stop"; break
        lo = min(lo, L[k])
        if L[k] <= tgt: px, why = tgt, "target"; break
        if end_ok(k): px, why = C[k], "time"; break
    else:
        px = C[-1]
    return px, why, (qc - min(lo, qc)) / qc * 100


def gen_a(t):
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
            rows.append(dict(set="a", ticker=t, date=day, ret=(qc - px) / qc * 100, why=why, mfe=mfe, stop_pct=(qh - qc) / qc * 100))
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
        rows.append(dict(set="b", ticker=t, date=dd, ret=(qc - px) / qc * 100, why=why, mfe=mfe, stop_pct=(qh - qc) / qc * 100))
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in INTRADAY_5M_DIR.glob("*.csv") if not p.stem.startswith("_"))
    t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    with Pool(6) as pool:
        A = pd.DataFrame(sum(pool.map(gen_a, t5, chunksize=10), []))
        B = pd.DataFrame(sum(pool.map(gen_b, t1, chunksize=10), []))
    pd.concat([A, B]).to_csv(HERE / "short_mirror_samewindow.csv", index=False)
    for nm, x in (("a_short (30m)", A), ("b_short (1H)", B)):
        days = x.date.nunique()
        x["per"] = pd.to_datetime(x.date).dt.strftime("%Y-%m") if nm.startswith("a") else pd.to_datetime(x.date).dt.year
        print(f"=== {nm}: n={len(x)}, {days} days, {len(x)/days:.2f}/day ===")
        print(f"mean ret%: {x.ret.mean():+.3f}  win%: {(x.ret>0).mean()*100:.1f}  target%: {(x.why=='target').mean()*100:.1f}  stop%: {(x.why=='stop').mean()*100:.1f}")
        print(x.groupby("per").ret.agg(["count", "mean"]).round(3).to_string())
        print()
