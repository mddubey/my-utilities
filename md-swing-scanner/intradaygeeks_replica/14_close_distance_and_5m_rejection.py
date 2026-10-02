"""On daily 34-EMA support days: (A) how far is the close already past the EMA, i.e. is a ~1% target
already spent by the time the daily candle confirms? (B) on 1H: after the touch hour, how far does price run
the same day? (C) the user's actual intraday trade on 5m: touch EMA34_{t-1}, buy the first 5m close back
across it, stop = day's extreme so far (the wick, thin), target +1% from entry, flat at the close.
Spec fixed before running (2026-10-01). Day filters identical to 12 (all known at T-1): 8/34 trend side,
ADX14>25, open on the trend side of EMA34_{t-1}, intraday touch of EMA34_{t-1}. Both sides. Weekly-8 state
not used here (it changed little in 12). Same-bar stop+target = stop. Gross of costs.
"""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from market_regime import _compute_adx
HERE = Path(__file__).parent
H1, M5 = HERE / "h1_cache", HERE.parent / "intraday_cache"


def bars(p):
    if not p.exists(): return None
    x = pd.read_csv(p, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata")
    x = x[(x.Volume > 0) | (x.High != x.Low)]
    x["day"] = x.index.normalize().tz_localize(None)
    return {d: g for d, g in x.groupby("day")}


def run(t):
    try: df = load(t).reset_index()
    except FileNotFoundError: return []
    if len(df) < 300: return []
    o, h, l, c = (df[k].values for k in ("Open", "High", "Low", "Close"))
    e8 = df.Close.ewm(span=8, adjust=False).mean().shift(1).values
    e34 = df.Close.ewm(span=34, adjust=False).mean().shift(1).values
    adx = _compute_adx(df.set_index("Date"))[0].shift(1).values
    h1, m5 = bars(H1 / f"{t}.csv") or {}, bars(M5 / f"{t}.csv") or {}
    out = []
    for i in range(252, len(df)):
        if np.isnan(adx[i]) or adx[i] <= 25: continue
        if e8[i] > e34[i] and o[i] > e34[i] and l[i] <= e34[i]: s = 1
        elif e8[i] < e34[i] and o[i] < e34[i] and h[i] >= e34[i]: s = -1
        else: continue
        E, dt = e34[i], df.Date.iloc[i]
        r = dict(ticker=t, date=dt, side="long" if s == 1 else "short", px=c[i],
                 close_vs_ema=(c[i] / E - 1) * 100 * s,
                 dayext_vs_ema=((h[i] if s == 1 else l[i]) / E - 1) * 100 * s,
                 confirmed=bool((c[i] - E) * s > 0 and (c[i] - o[i]) * s > 0))
        g = h1.get(dt)
        if g is not None and abs(g.Close.iloc[-1] / c[i] - 1) <= 0.02:
            H, L = g.High.values, g.Low.values
            tb = np.argmax(L <= E) if s == 1 else np.argmax(H >= E)
            if (L[tb] <= E) if s == 1 else (H[tb] >= E):
                after = np.nan if tb + 1 >= len(H) else (H[tb + 1:].max() if s == 1 else L[tb + 1:].min())
                r.update(h1_touch_hour=g.index[tb].strftime("%H:%M"),
                         h1_mfe_after_touch=(after / E - 1) * 100 * s if not np.isnan(after) else np.nan)
        g = m5.get(dt)
        if g is not None and abs(g.Close.iloc[-1] / c[i] - 1) <= 0.02:
            H, L, C = g.High.values, g.Low.values, g.Close.values
            tb = np.argmax(L <= E) if s == 1 else np.argmax(H >= E)
            if (L[tb] <= E) if s == 1 else (H[tb] >= E):
                for b in range(tb, len(C)):
                    if (C[b] - E) * s > 0:
                        entry = C[b]; stop = L[:b + 1].min() if s == 1 else H[:b + 1].max()
                        tgt = entry * (1 + s * 0.01); px, why = C[-1], "eod"
                        for j in range(b + 1, len(C)):
                            if (L[j] <= stop) if s == 1 else (H[j] >= stop): px, why = stop, "stop"; break
                            if (H[j] >= tgt) if s == 1 else (L[j] <= tgt): px, why = tgt, "target"; break
                        risk = abs(entry - stop)
                        r.update(m5_entry_time=g.index[b].strftime("%H:%M"), m5_entry_vs_ema=(entry / E - 1) * 100 * s,
                                 m5_stop_pct=risk / entry * 100, m5_stop_rs=risk, m5_exit=why,
                                 m5_ret=(px - entry) / entry * 100 * s, m5_R=(px - entry) * s / risk if risk else np.nan)
                        break
        out.append(r)
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    uni = pd.read_csv(HERE.parent / "nse_equity_universe.csv").ticker.tolist()
    rows = []
    with Pool(6) as p:
        for k, x in enumerate(p.imap_unordered(run, uni, chunksize=8), 1):
            rows += x
            if k % 400 == 0: print(f"  {k}/{len(uni)}", flush=True)
    R = pd.DataFrame(rows); R.to_csv(HERE / "close_distance_5m_rejection.csv", index=False)
    print("rows", len(R), "| h1 rows", R.h1_mfe_after_touch.notna().sum(), "| 5m trades", R.m5_exit.notna().sum())
