"""Full parity re-test (user, 2026-10-06): apply the SAME 2026-10-04 refinements that the live short system
uses -- full-hour-bar-at-close trigger (script 68: at 11:15/12:15 the candle is the WHOLE hour, stop = whole-hour
extreme, not just the half-hour slice) and the strong-hour-before skip (script 70: skip a shallow pullback right
after a strong hour in the opposing direction that closed beyond the EMA, checked only at the 11:45/12:15 pair,
never at 10:45/11:15) -- to BOTH sides, built the identical way, so neither side gets an advantage from being
more refined than the other. Runs long and short through the exact same function (side parameter) to remove any
asymmetric-implementation risk. Reports both the full population and the ONE-TRADE-A-DAY plan (10:45 else 11:15
else 11:45, first qualifying alarm, matching live Plan B) for both sides, both sets."""
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


def walk(H, L, C, T, b, stop_px, tgt, is_long, end_ok):
    extreme, why = (-np.inf if is_long else np.inf), "eod"
    for k in range(b + 1, len(C)):
        if (is_long and L[k] <= stop_px) or (not is_long and H[k] >= stop_px): px, why = stop_px, "stop"; break
        extreme = max(extreme, H[k]) if is_long else min(extreme, L[k])
        hit_tgt = (H[k] >= tgt) if is_long else (L[k] <= tgt)
        if hit_tgt: px, why = tgt, "target"; break
        if end_ok(k): px, why = C[k], "time"; break
    else:
        px = C[-1]
    return px, why


def gen_a(t, is_long):
    p = INTRADAY_5M_DIR / f"{t}.csv"
    if not p.exists(): return []
    try: d, d8y, adx, tv = daily_inputs(t)
    except Exception: return []
    m = read(p)
    if len(m) < 1500: return []
    hc = m.Close.groupby(hour_key(m.index)).last(); ho = m.Open.groupby(hour_key(m.index)).first()
    e34 = hc.ewm(span=34, adjust=False).mean().shift(1); e8 = hc.ewm(span=8, adjust=False).mean().shift(1)
    atrp = (d.atr14 / d.Close * 100).shift(1); rows = []
    for day, g in m.groupby(m.index.normalize()):
        if day < pd.Timestamp("2026-06-10") or len(g) < 70 or tv.get(day, 0) < 1e8 or bool(d.corp_action_day.get(day, False)): continue
        D8, AD, AP = d8y.get(day, np.nan), adx.get(day, np.nan), atrp.get(day, np.nan)
        if np.isnan(D8) or np.isnan(AD) or AD > 25 or not AP >= 2.56: continue
        O, H, L, C, V, T = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.Volume.values, g.index
        vw = np.cumsum((H + L + C) / 3 * V) / np.maximum(np.cumsum(V), 1)
        day_extreme = np.maximum.accumulate(H) if is_long == False else np.minimum.accumulate(L)
        base = day + pd.Timedelta("9h15min"); k30 = (T - base) // pd.Timedelta("30min")
        for q in (2, 3, 4, 5):
            qi = np.where((k30 == q) | ((k30 == q - 1) & (q % 2 == 1)))[0]   # full hour for q in (3,5), half for (2,4) -- script 68
            if len(qi) < 6: continue
            hs = base + ((q * 30) // 60) * pd.Timedelta("60min")
            E, E8 = e34.get(hs, np.nan), e8.get(hs, np.nan)
            if np.isnan(E): continue
            b = qi[-1]; qo = O[qi[0]]; qc = C[b]
            qext = L[qi].min() if is_long else H[qi].max()
            if is_long:
                core = qext <= E and qc > E and (qc - E) / E * 100 <= 0.5 and (qc - qext) / qc * 100 <= 0.5
                side = E8 > E and qc > qo and qc > D8 and day_extreme[b] <= A8 * qc + (1 - A8) * D8 and qc > vw[b]
            else:
                core = qext >= E and qc < E and (E - qc) / E * 100 <= 0.5 and (qext - qc) / qc * 100 <= 0.5
                side = E8 < E and qc < qo and qc < D8 and day_extreme[b] >= A8 * qc + (1 - A8) * D8 and qc < vw[b]
            if not (core and side): continue
            skip = False
            if hs.strftime("%H:%M") not in ("09:15", "10:15"):   # strong-hour-before skip, only at the 11:45/12:15 pair -- script 70
                ph = hs - pd.Timedelta("60min"); pO, pC = ho.get(ph, np.nan), hc.get(ph, np.nan)
                if not np.isnan(pO):
                    if is_long: skip = (pC < pO) and (pC < E) and (qc < (pO + pC) / 2)
                    else: skip = (pC > pO) and (pC > E) and (qc > (pO + pC) / 2)
            stop_px = qext; tgt = qc * (1.01 if is_long else 0.99)
            end = T[b] + pd.Timedelta("5h")
            px, why = walk(H, L, C, T, b, stop_px, tgt, is_long, lambda k: T[k] >= end)
            ret = (px - qc) / qc * 100 if is_long else (qc - px) / qc * 100
            rows.append(dict(set="a", ticker=t, date=day, q=q, ret=ret, why=why, skip=skip, stop_pct=abs(qc - qext) / qc * 100))
    return rows


def gen_b(t, is_long):
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
    day_extreme = (h.High.groupby(day).cummax().values if not is_long else h.Low.groupby(day).cummin().values)
    atrp = (d.atr14 / d.Close * 100).shift(1); rows = []
    for i in range(200, len(C) - 1):
        if T[i] < pd.Timestamp("2024-01-01") or T[i].strftime("%H:%M") not in ("10:15", "11:15"): continue
        dd = day[i]
        if tv.get(dd, 0) < 1e8 or bool(d.corp_action_day.get(dd, False)): continue
        D8, AD, AP = d8y.get(dd, np.nan), adx.get(dd, np.nan), atrp.get(dd, np.nan)
        if np.isnan(D8) or np.isnan(E34[i]) or np.isnan(AD) or AD > 25 or not AP >= 2.56: continue
        E = E34[i]; qext = L[i] if is_long else H[i]; qc = C[i]
        if is_long:
            core = qext <= E and qc > E and (qc - E) / E * 100 <= 0.5 and (qc - qext) / qc * 100 <= 0.5
            side = E8[i] > E and qc > O[i] and qc > D8 and day_extreme[i] <= A8 * qc + (1 - A8) * D8 and qc > vw[i]
        else:
            core = qext >= E and qc < E and (E - qc) / E * 100 <= 0.5 and (qext - qc) / qc * 100 <= 0.5
            side = E8[i] < E and qc < O[i] and qc < D8 and day_extreme[i] >= A8 * qc + (1 - A8) * D8 and qc < vw[i]
        if not (core and side): continue
        skip = False
        if T[i].hour == 11 and i >= 1:   # the hour closing at 12:15; previous hour = 10:15-11:15
            pO, pC = O[i - 1], C[i - 1]
            if is_long: skip = (pC < pO) and (pC < E34[i - 1] if not np.isnan(E34[i - 1]) else False) and (qc < (pO + pC) / 2)
            else: skip = (pC > pO) and (pC > E34[i - 1] if not np.isnan(E34[i - 1]) else False) and (qc > (pO + pC) / 2)
        j_end = i + 1
        while j_end < len(C) and day[j_end] == dd and not (j_end - i >= 5 or last[j_end]): j_end += 1
        if j_end >= len(C) or day[j_end] != dd: continue
        stop_px = qext; tgt = qc * (1.01 if is_long else 0.99)
        px, why = walk(H[:j_end + 1], L[:j_end + 1], C[:j_end + 1], T, i, stop_px, tgt, is_long, lambda k: k == j_end)
        ret = (px - qc) / qc * 100 if is_long else (qc - px) / qc * 100
        rows.append(dict(set="b", ticker=t, date=dd, q=(3 if T[i].hour == 10 else 5), ret=ret, why=why, skip=skip, stop_pct=abs(qc - qext) / qc * 100))
    return rows


def plan_pick(x):
    """one trade a day: first qualifying alarm in order 10:45(2), 11:15(3), 11:45(4) -- matches live Plan B (never 12:15)."""
    x = x[~x.skip].copy()
    picks = []
    for (s, dt), g in x[x.q.isin([2, 3, 4])].groupby(["set", "date"]):
        row = g.sort_values("q").iloc[0]
        picks.append(row)
    return pd.DataFrame(picks)


if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in INTRADAY_5M_DIR.glob("*.csv") if not p.stem.startswith("_"))
    t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    for side, is_long in (("SHORT", False), ("LONG", True)):
        print(f"\n########## {side} (full-hour trigger + strong-hour-before skip, matching live refinements) ##########")
        with Pool(6) as pool:
            A = pd.DataFrame(sum(pool.starmap(gen_a, [(t, is_long) for t in t5], chunksize=10), []))
            B = pd.DataFrame(sum(pool.starmap(gen_b, [(t, is_long) for t in t1], chunksize=10), []))
        full = pd.concat([A, B], ignore_index=True)
        full.to_csv(HERE / f"full_refined_{side.lower()}.csv", index=False)
        for nm, x in (("a (30m)", A), ("b (1H)", B)):
            if not len(x): print(f"{nm}: 0 setups"); continue
            kept = x[~x.skip]
            days = kept.date.nunique()
            per = pd.to_datetime(kept.date).dt.strftime("%Y-%m") if nm.startswith("a") else pd.to_datetime(kept.date).dt.year
            kept = kept.assign(per=per)
            print(f"\n=== {side} {nm}: baseline (skip-excluded) n={len(kept)}, {days} days, {len(kept)/max(days,1):.2f}/day ===")
            print(f"mean ret%: {kept.ret.mean():+.3f}  win%: {(kept.ret>0).mean()*100:.1f}  target%: {(kept.why=='target').mean()*100:.1f}  stop%: {(kept.why=='stop').mean()*100:.1f}")
            print(kept.groupby("per").ret.agg(["count", "mean"]).round(3).to_string())
            pp = plan_pick(x[x.set == nm[0]])
            if len(pp):
                print(f"PLAN (10:45 else 11:15 else 11:45), n={len(pp)}: mean ret% {pp.ret.mean():+.3f}  win% {(pp.ret>0).mean()*100:.1f}  target% {(pp.why=='target').mean()*100:.1f}  stop% {(pp.why=='stop').mean()*100:.1f}")
