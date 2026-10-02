"""Intraday version of the user's setup: SAME structure as 09 (daily 34 + weekly 8), one timeframe down.
Spec fixed before running (2026-10-01):
Lower TF = 1H (Yahoo 60m, Oct 2023 - Sep 2026). EMA8/EMA34 on the continuous 1H close series, value as of
  the PRIOR 1H bar. Setup bar i: Low_i <= EMA34 < Close_i and Close_i > Open_i (short mirror).
  1H trend: EMA8 > EMA34 (long) / < (short); counter-trend reported only as contrast.
Higher TF = daily 8-EMA as of yesterday's close (live-known). State at the setup bar's close:
  wrong side (Close below dEMA8 for long) = avoid; touch = day's extreme so far within 0.5% of dEMA8; else untested.
Entry = setup bar close. Stop = setup bar low (long) / high (short). Target = entry +/-1%.
Exit: stop / target / close of the 5th 1H bar after entry / the day's last bar, whichever first (intraday, flat EOD).
  Both stop and target inside one hour: resolved on 5m bars when they exist (Jun-Sep 2026), else stop first.
Setup bar must not be the day's last bar. One position per ticker. Days dropped: corp action, 1H-vs-daily close
  >2% off (Yahoo rescaling), prior-day tv20 < Rs 10 cr. 1H ADX14 (prior bar) > 25 reported as a split.
"""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from market_regime import _compute_adx
HERE = Path(__file__).resolve().parent
H1, M5 = HERE / "h1_cache", HERE.parent / "intraday_cache"
TGT, MAXBARS, TV_MIN = 0.01, 5, 1e8


def read(p):
    x = pd.read_csv(p, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata")
    return x[(x.Volume > 0) | (x.High != x.Low)]


def run(t):
    p = H1 / f"{t}.csv"
    if not p.exists(): return []
    try: d = load(t)
    except FileNotFoundError: return []
    hb = read(p)
    if len(hb) < 200: return []
    day = hb.index.normalize().tz_localize(None)
    dcl = hb.Close.groupby(day).last()
    ok = (dcl / d.Close.reindex(dcl.index) - 1).abs() <= 0.02
    ok &= ~d.corp_action_day.reindex(dcl.index).fillna(True).astype(bool)
    ok &= d.traded_value_sma20.shift(1).reindex(dcl.index) >= TV_MIN
    de8 = d.Close.ewm(span=8, adjust=False).mean().shift(1).reindex(dcl.index).values
    di = pd.Series(np.arange(len(dcl)), index=dcl.index)[day].values
    m5 = read(M5 / f"{t}.csv") if (M5 / f"{t}.csv").exists() else None
    O, H, L, C = (hb[k].values for k in ("Open", "High", "Low", "Close"))
    e8 = hb.Close.ewm(span=8, adjust=False).mean().shift(1).values
    e34 = hb.Close.ewm(span=34, adjust=False).mean().shift(1).values
    adx = _compute_adx(hb)[0].shift(1).values
    lo_sofar = hb.Low.groupby(day).cummin().values
    hi_sofar = hb.High.groupby(day).cummax().values
    last = np.r_[di[1:] != di[:-1], True]           # last bar of its day
    okv = ok.values
    rng = ((hb.High - hb.Low) / hb.Close * 100).values
    avg_rng = pd.Series(rng).rolling(35).mean().shift(1).values      # stock's normal 1H range, prior ~5 days
    first = np.r_[True, di[1:] != di[:-1]]
    prev_close = np.r_[np.nan, C[:-1]]
    rows, busy = [], -1
    for i in range(100, len(C)):
        if i <= busy or last[i] or not okv[di[i]] or np.isnan(de8[di[i]]): continue
        if L[i] <= e34[i] < C[i] and C[i] > O[i]: s = 1
        elif H[i] >= e34[i] > C[i] and C[i] < O[i]: s = -1
        else: continue
        D8 = de8[di[i]]
        if (C[i] - D8) * s < 0: dstate = "wrong"
        elif (s == 1 and lo_sofar[i] <= D8 * 1.005) or (s == -1 and hi_sofar[i] >= D8 * 0.995): dstate = "touch"
        else: dstate = "untested"
        entry, stop = C[i], (L[i] if s == 1 else H[i])
        risk = (entry - stop) * s
        if risk <= 0: continue
        tgt = entry * (1 + s * TGT)
        px, why, j = None, None, i
        for j in range(i + 1, min(i + MAXBARS, len(C) - 1) + 1):
            hs = (L[j] <= stop) if s == 1 else (H[j] >= stop)
            ht = (H[j] >= tgt) if s == 1 else (L[j] <= tgt)
            if hs and ht:
                why = "stop_ambig"; px = stop
                if m5 is not None:
                    w = m5[(m5.index >= hb.index[j]) & (m5.index < hb.index[j] + pd.Timedelta("60min"))]
                    for _, b in w.iterrows():
                        if (b.Low <= stop) if s == 1 else (b.High >= stop): why = "stop_5m"; break
                        if (b.High >= tgt) if s == 1 else (b.Low <= tgt): why, px = "target_5m", tgt; break
                break
            if hs: px, why = stop, "stop"; break
            if ht: px, why = tgt, "target"; break
            if last[j]: px, why = C[j], "eod"; break
        if px is None: px, why = C[j], "time5"
        ret = (px - entry) / entry * 100 * s
        rows.append(dict(ticker=t, ts=hb.index[i], date=day[i], side="long" if s == 1 else "short",
                         trend=bool((e8[i] - e34[i]) * s > 0), dstate=dstate, adx=adx[i],
                         close_past_ema=(C[i] / e34[i] - 1) * 100 * s, stop_pct=risk / entry * 100, stop_rs=risk,
                         exit=why, bars=j - i, ret=ret, R=ret / (risk / entry * 100),
                         price=entry, bar_range_pct=rng[i], avg_1h_range_pct=avg_rng[i],
                         wick_past_ema_pct=((e34[i] - stop) * s) / entry * 100,
                         entry_past_ema_pct=((entry - e34[i]) * s) / entry * 100,
                         gap_pct=((O[i] / prev_close[i] - 1) * 100 * s) if first[i] else 0.0,
                         d8_ext_vs_d8_pct=(((lo_sofar[i] if s == 1 else hi_sofar[i]) / D8 - 1) * 100 * s)))
        busy = j
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    tick = sorted(p.stem for p in H1.glob("*.csv"))
    out = []
    with Pool(6) as pool:
        for k, r in enumerate(pool.imap_unordered(run, tick, chunksize=8), 1):
            out += r
            if k % 500 == 0: print(f"  {k}/{len(tick)}", flush=True)
    R = pd.DataFrame(out); R.to_csv(HERE / "intraday_1h34_daily8_results.csv", index=False)
    print("trades", len(R), R.date.min(), R.date.max())
