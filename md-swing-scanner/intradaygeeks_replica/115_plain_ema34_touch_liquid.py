"""PLAIN 1H EMA34 touch, liquid names only, 3-year 1H set (user, 2026-10-09: 'as plain as possible to start with').
Spec fixed before running:
  Setup: an hourly candle (09:15-aligned) whose HIGH >= the 1H EMA34 (as of the previous completed hour) and whose CLOSE < it.
  Nothing else applied -- distance below the EMA is recorded, not limited.
  Trade: short at the candle close, stop = candle high, target = close - 1%, out after 5 candles or at the day's last candle
  (stop first if both in one candle). Net = ret x Rs1000 - Rs85 per Rs1 lakh.
  Universe: h1_cache names with prior-day 20-day traded value >= Rs10 cr (data-quality floor) AND the signal hour's
  turnover / 12 x 0.72 >= Rs15 lakh (the live liquidity rule; 0.72 = median/mean ratio from script 114). Thin ones are
  saved too (liq column) for contrast only.
  Recorded flags, NONE applied: red (close < open), trend (1H EMA8 < EMA34), below_d8 (close < yesterday's daily 8-EMA),
  pierce_d8 (day's high so far >= live daily 8-EMA), adx_ok (daily ADX yday <= 25), below_vwap (hourly-typical-price VWAP,
  approximation), atr_ok (daily ATR14 yday >= 2.56%), rr_ok (stop <= 0.5%), price_ok (close >= Rs100); plus dist %, stop %,
  hour, year, liq.
  Period 2024-01 .. 2026-09. Output: plain_touch_1h.csv; report in 115_report section of the run log."""
import sys, warnings, time
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
exec(compile(open(HERE / "60_filter_ablation.py").read().split("def gen_a")[0], "60head", "exec"))
LIQ_RATIO = 0.72


def gen(t):
    p = HERE / "h1_cache" / f"{t}.csv"
    if not p.exists(): return []
    try:
        d, d8y, adx, tv = daily_inputs(t); atrp = (d.atr14 / d.Close * 100).shift(1)
    except Exception: return []
    h = read(p)
    if len(h) < 300: return []
    O, H, L, C, V, T = h.Open.values, h.High.values, h.Low.values, h.Close.values, h.Volume.values, h.index
    E34 = h.Close.ewm(span=34, adjust=False).mean().shift(1).values; E8 = h.Close.ewm(span=8, adjust=False).mean().shift(1).values
    day = T.normalize(); last = np.r_[day[1:] != day[:-1], True]
    tp = (h.High + h.Low + h.Close) / 3
    vw = ((tp * h.Volume).groupby(day).cumsum() / h.Volume.groupby(day).cumsum().replace(0, np.nan)).values
    hi_day = h.High.groupby(day).cummax().values
    rows = []
    for i in range(200, len(C) - 1):
        if T[i] < pd.Timestamp("2024-01-01") or last[i]: continue
        dd = day[i]
        if tv.get(dd, 0) < 1e8 or bool(d.corp_action_day.get(dd, False)): continue
        D8, AD, AT = d8y.get(dd, np.nan), adx.get(dd, np.nan), atrp.get(dd, np.nan)
        E = E34[i]; qh, qc = H[i], C[i]
        if np.isnan(D8) or np.isnan(E) or not (qh >= E and qc < E): continue
        tgt = qc * 0.99; px, why = None, None
        for j in range(i + 1, len(C)):
            if day[j] != dd: px, why = C[j - 1], "stall"; break
            if H[j] >= qh: px, why = qh, "stop"; break
            if L[j] <= tgt: px, why = tgt, "target"; break
            if j - i >= 5 or last[j]: px, why = C[j], "stall"; break
        if px is None: continue
        stop = (qh - qc) / qc * 100
        rows.append(dict(ticker=t, date=dd.strftime("%Y-%m-%d"), hour=T[i].strftime("%H:%M"), entry=qc, high=qh, ema34=E,
                         ret=(qc - px) / qc * 100, out=why, dist=(E - qc) / E * 100, stop=stop,
                         liq=V[i] * qc / 12 / 1e5 * LIQ_RATIO,
                         red=qc < O[i], trend=E8[i] < E, below_d8=qc < D8, pierce_d8=hi_day[i] >= A8 * qc + (1 - A8) * D8,
                         adx_ok=(AD <= 25) if not np.isnan(AD) else False, below_vwap=qc < vw[i],
                         atr_ok=(AT >= 2.56) if not np.isnan(AT) else False, rr_ok=stop <= 0.5, price_ok=qc >= 100))
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv")); out, t0 = [], time.time()
    with Pool(6) as p:
        for k, r in enumerate(p.imap_unordered(gen, t1, chunksize=8), 1):
            out += r
            if k % 200 == 0 or k == len(t1): print(f"{k}/{len(t1)} stocks, {len(out)} touches, {time.time()-t0:.0f}s", flush=True)
    pd.DataFrame(out).to_csv(HERE / "plain_touch_1h.csv", index=False)
    print("saved plain_touch_1h.csv")
