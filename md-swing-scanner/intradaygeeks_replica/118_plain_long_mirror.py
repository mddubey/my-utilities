"""LONG mirror of the plain liquid 1H EMA34 touch (user, 2026-10-09: 'we never tested longs under the right conditions').
Spec fixed before running, exact mirror of 115 v3: hourly candle whose LOW <= the 1H EMA34 (previous completed hour) and CLOSE
above it; long at the close, stop = candle low, target = close + 1%, out after 5 candles / the day's last candle (stop first
if both in one candle). Liquidity = previous day's median hourly turnover / 12 x 0.72 >= Rs15 lakh / 5-min bar. 2024-01..2026-09.
Layers (mirror of the short stack, declared): early candle (09:15/10:15); Nifty daily 8 < 34 (yday) -- falling market bounces
intraday; stock daily 8 < 34 (yday) -- its own trend reverses intraday; green candle; ATR >= 2.56%. Contrast (declared):
the with-trend long (early, Nifty up, stock up, green, ATR). Net = Rs per Rs1 lakh after Rs85. Results only."""
import sys, warnings, time
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
exec(compile(open(HERE / "60_filter_ablation.py").read().split("def gen_a")[0], "60head", "exec"))


def gen(t):
    p = HERE / "h1_cache" / f"{t}.csv"
    if not p.exists(): return []
    try:
        d, d8y, adx, tv = daily_inputs(t); atrp = (d.atr14 / d.Close * 100).shift(1)
        d34y = d.Close.ewm(span=34, adjust=False).mean().shift(1)
    except Exception: return []
    h = read(p)
    if len(h) < 300: return []
    O, H, L, C, V, T = h.Open.values, h.High.values, h.Low.values, h.Close.values, h.Volume.values, h.index
    E34 = h.Close.ewm(span=34, adjust=False).mean().shift(1).values
    day = T.normalize(); last = np.r_[day[1:] != day[:-1], True]
    prev_med = (h.Volume * h.Close).where(h.Volume > 0).groupby(day).median().shift(1)
    rows = []
    for i in range(200, len(C) - 1):
        if T[i] < pd.Timestamp("2024-01-01") or last[i]: continue
        dd = day[i]
        if tv.get(dd, 0) < 1e8 or bool(d.corp_action_day.get(dd, False)): continue
        E = E34[i]; ql, qc = L[i], C[i]
        if np.isnan(E) or not (ql <= E and qc > E): continue
        tgt = qc * 1.01; px, why = None, None
        for j in range(i + 1, len(C)):
            if day[j] != dd: px, why = C[j - 1], "stall"; break
            if L[j] <= ql: px, why = ql, "stop"; break
            if H[j] >= tgt: px, why = tgt, "target"; break
            if j - i >= 5 or last[j]: px, why = C[j], "stall"; break
        if px is None: continue
        AT = atrp.get(dd, np.nan)
        rows.append(dict(ticker=t, date=dd.strftime("%Y-%m-%d"), hour=T[i].strftime("%H:%M"), ret=(px - qc) / qc * 100, out=why,
                         green=qc > O[i], atr_ok=(AT >= 2.56) if not np.isnan(AT) else False, d8y=d8y.get(dd, np.nan),
                         d34y=d34y.get(dd, np.nan), liq_prev=prev_med.get(dd, np.nan) / 12 / 1e5 * 0.72))
    return rows


def row(lab, g):
    o = g.out; y = " / ".join(f"{g[g.yr == k].ret.mean()*1000 - 85:+.0f}" if (g.yr == k).any() else "-" for k in ("2024", "2025", "2026"))
    return f"| {lab} | {len(g)} | {(o == 'target').mean()*100:.0f} / {(o == 'stall').mean()*100:.0f} / {(o == 'stop').mean()*100:.0f} | {g.ret.mean()*1000 - 85:+.0f} | {y} |"


if __name__ == "__main__":
    out_csv = HERE / "plain_touch_1h_long.csv"
    if "--report" not in sys.argv:
        from multiprocessing import Pool
        t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv")); out, t0 = [], time.time()
        with Pool(6) as p:
            for k, r in enumerate(p.imap_unordered(gen, t1, chunksize=8), 1):
                out += r
                if k % 500 == 0 or k == len(t1): print(f"{k}/{len(t1)} stocks, {len(out)} touches, {time.time()-t0:.0f}s", flush=True)
        pd.DataFrame(out).to_csv(out_csv, index=False)
    sys.path.insert(0, str(HERE.parent)); from data.paths import DAILY_DIR
    n = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index(); c = n["Close"]
    nup = (c.ewm(span=8, adjust=False).mean() > c.ewm(span=34, adjust=False).mean()).shift(1).rename("nup")
    P = pd.read_csv(out_csv); Lq = P[P.liq_prev >= 15].copy(); Lq["d"] = pd.to_datetime(Lq.date); Lq = Lq.join(nup, on="d")
    Lq["yr"] = Lq.date.str[:4]; Lq["sdown"] = Lq.d8y < Lq.d34y
    print("\n## LONG, liquid plain touch, layer by layer\n| layer | n | target / stall / stop % | Rs net | 2024 / 2025 / 2026 |\n|---|---|---|---|---|")
    print(row("baseline plain long touch", Lq))
    for hr, g in Lq.groupby("hour"): print(row(f"  candle {hr}", g))
    s1 = Lq[Lq.hour.isin(["09:15", "10:15"])]; print(row("1 early candle (09:15/10:15)", s1))
    s2 = s1[s1.nup == False]; print(row("2 + Nifty DOWNtrend", s2))
    s3 = s2[s2.sdown]; print(row("3 + stock daily DOWNtrend", s3))
    s4 = s3[s3.green]; print(row("4 + green candle", s4))
    s5 = s4[s4.atr_ok]; print(row("5 + ATR >= 2.56 (COUNTER-TREND LONG)", s5))
    print(row("   5, 09:15 only", s5[s5.hour == "09:15"])); print(row("   5, 10:15 only", s5[s5.hour == "10:15"]))
    w = s1[(s1.nup == True) & (~s1.sdown) & s1.green & s1.atr_ok]; print(row("contrast: WITH-TREND long (Nifty up, stock up, green, ATR)", w))
