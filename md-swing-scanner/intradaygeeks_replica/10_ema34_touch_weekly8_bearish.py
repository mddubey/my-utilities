"""Mirror of 09: bearish daily 34-EMA rejection + weekly 8-EMA, all NSE EQ (pattern test only,
tradability ignored on purpose). Spec fixed before running:
Setup candle t: High_t >= EMA34_{t-1} and Close_t < EMA34_{t-1} and Close_t < Open_t.
Daily trend: EMA8_{t-1} < EMA34_{t-1} = downtrend (take); else contrast group.
Weekly 8-EMA from last completed week: touch = week-to-date high >= wEMA8*0.995 and Close_t <= wEMA8;
below = not yet tested; above = Close_t > wEMA8 (avoid).
Short at Close_t, stop High_t, target nearest prior confirmed swing LOW below entry (K=3, 252d),
stop trails down to newly confirmed swing highs, 60-day cap, one position per ticker.
"""
import warnings
warnings.filterwarnings("ignore")
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
from backtest import load

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("m9", HERE / "09_ema34_touch_weekly8.py")
m9 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m9)
K, LOOKBACK, MAX_HOLD = 3, 252, 60


def simulate_short(i, sh, sl, h, l, c):
    entry, stop = c[i], h[i]
    risk = stop - entry
    if risk <= 0:
        return None
    tgt = next((l[j] for j in range(i - 1, max(0, i - LOOKBACK), -1) if sl[j] and l[j] < entry), None)
    n = len(c)
    for d in range(1, MAX_HOLD + 1):
        j = i + d
        if j >= n:
            return "data_end", c[n - 1], d - 1
        if h[j] >= stop:
            return "stop", stop, d
        if tgt is not None and l[j] <= tgt:
            return "target", tgt, d
        cj = j - K
        if cj > i and sh[cj] and h[cj] < stop:
            stop = h[cj]
    return "max_hold", c[i + MAX_HOLD], MAX_HOLD


def run(tickers):
    rows = []
    for k, t in enumerate(tickers, 1):
        if k % 300 == 0:
            print(f"  {k}/{len(tickers)}", flush=True)
        try:
            df = load(t).reset_index()
        except FileNotFoundError:
            continue
        if len(df) < LOOKBACK + 40:
            continue
        o, h, l, c = df.Open.values, df.High.values, df.Low.values, df.Close.values
        e8 = df.Close.ewm(span=8, adjust=False).mean().shift(1).values
        e34 = df.Close.ewm(span=34, adjust=False).mean().shift(1).values
        s = df.set_index("Date").Close
        wk = s.resample("W-FRI").last().dropna()
        we8 = wk.ewm(span=8, adjust=False).mean().shift(1).reindex(s.index, method="ffill").values
        wtd_high = df.groupby(df.Date.dt.to_period("W-FRI")).High.cummax().values
        sh, slw = m9.swings(h, l)
        busy = -1
        for i in range(LOOKBACK, len(df) - K):
            if i <= busy or np.isnan(e34[i]) or np.isnan(we8[i]):
                continue
            if not (h[i] >= e34[i] > c[i] and c[i] < o[i]):
                continue
            down = e8[i] < e34[i]
            if c[i] > we8[i]:
                ws = "above"
            elif wtd_high[i] >= we8[i] * 0.995:
                ws = "touch"
            else:
                ws = "below"
            res = simulate_short(i, sh, slw, h, l, c)
            if res is None:
                continue
            reason, px, days = res
            risk = h[i] - c[i]
            rows.append(dict(ticker=t, date=df.Date.iloc[i], downtrend=down, weekly=ws,
                             exit=reason, days=days, R=(c[i] - px) / risk, ret_pct=(c[i] - px) / c[i] * 100))
            busy = i + days
    return pd.DataFrame(rows)


if __name__ == "__main__":
    uni = pd.read_csv(HERE.parent / "nse_equity_universe.csv").ticker.tolist()
    res = run(uni)
    res.to_csv(HERE / "ema34_touch_weekly8_bearish_results.csv", index=False)
    print(f"\nbearish setup candles traded: {len(res)}\n")
    m9.report(res, "ALL daily 34-EMA bearish rejections")
    m9.report(res[~res.downtrend], "  daily 8-EMA ABOVE 34 (not a downtrend)")
    d = res[res.downtrend]
    m9.report(d, "  daily 8-EMA BELOW 34 (downtrend)")
    for w in ("touch", "below", "above"):
        m9.report(d[d.weekly == w], f"    downtrend + weekly {w}")
