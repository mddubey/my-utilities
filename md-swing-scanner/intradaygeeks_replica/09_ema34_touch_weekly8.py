"""User's bullish setup, daily (lower TF) + weekly (higher TF), spec fixed before running:

Setup candle t (daily): Low_t <= EMA34_{t-1} and Close_t > EMA34_{t-1} and Close_t > Open_t
  (any bullish shape -- touched the daily 34-EMA and closed back above it).
Daily trend: EMA8_{t-1} > EMA34_{t-1} (uptrend = fast above slow; else skip).
Weekly 8-EMA from the last COMPLETED week (forward-filled). Graded:
  touch = week-to-date low <= wEMA8 * 1.005 and Close_t >= wEMA8 (support on the higher TF)
  above = week-to-date low  > wEMA8 * 1.005 (above, not yet tested)
  below = Close_t < wEMA8 (downtrend on the higher TF -- avoid)
Entry Close_t, stop Low_t, exit: nearest prior confirmed swing high above entry (K=3,
252-day lookback), stop trails to newly confirmed swing lows, 60-day cap.
One open position per ticker. Read-only against backtest.load(); outputs in this folder.
"""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import pandas as pd
from backtest import load

HERE = Path(__file__).parent
K, LOOKBACK, MAX_HOLD = 3, 252, 60


def swings(h, l, k=K):
    n = len(h); sh = np.zeros(n, bool); sl = np.zeros(n, bool)
    for i in range(k, n - k):
        if h[i] == h[i - k:i + k + 1].max(): sh[i] = True
        if l[i] == l[i - k:i + k + 1].min(): sl[i] = True
    return sh, sl


def simulate(i, sh, sl, h, l, c):
    entry, stop = c[i], l[i]
    risk = entry - stop
    if risk <= 0:
        return None
    tgt = next((h[j] for j in range(i - 1, max(0, i - LOOKBACK), -1) if sh[j] and h[j] > entry), None)
    n = len(c)
    for d in range(1, MAX_HOLD + 1):
        j = i + d
        if j >= n:
            return "data_end", c[n - 1], d - 1
        if l[j] <= stop:
            return "stop", stop, d
        if tgt is not None and h[j] >= tgt:
            return "target", tgt, d
        cj = j - K
        if cj > i and sl[cj] and l[cj] > stop:
            stop = l[cj]
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
        wkey = df.Date.dt.to_period("W-FRI")
        wtd_low = df.groupby(wkey).Low.cummin().values
        sh, slw = swings(h, l)
        busy_until = -1
        for i in range(LOOKBACK, len(df) - K):
            if i <= busy_until or np.isnan(e34[i]) or np.isnan(we8[i]):
                continue
            if not (l[i] <= e34[i] < c[i] and c[i] > o[i]):
                continue
            aligned = e8[i] > e34[i]
            if c[i] < we8[i]:
                wstate = "below"
            elif wtd_low[i] <= we8[i] * 1.005:
                wstate = "touch"
            else:
                wstate = "above"
            res = simulate(i, sh, slw, h, l, c)
            if res is None:
                continue
            reason, px, days = res
            risk = c[i] - l[i]
            rows.append(dict(ticker=t, date=df.Date.iloc[i], aligned=aligned, weekly=wstate,
                             d34_above_w8=bool(e34[i] > we8[i]), d34_vs_w8_pct=(e34[i] / we8[i] - 1) * 100,
                             risk_pct=risk / c[i] * 100, exit=reason, days=days,
                             R=(px - c[i]) / risk, ret_pct=(px / c[i] - 1) * 100))
            busy_until = i + days
    return pd.DataFrame(rows)


def report(x, label):
    if len(x) < 30:
        print(f"{label:52s} n={len(x)} (too few)"); return
    srt = x.sort_values("ret_pct", ascending=False); tot = srt.ret_pct.sum()
    yrs = x.groupby(x.date.dt.year).ret_pct.mean().round(2).to_dict()
    print(f"{label:52s} n={len(x):5d}  win {(x.R>0).mean()*100:4.1f}%  >=1R {(x.R>=1).mean()*100:4.1f}%  "
          f"meanR {x.R.mean():+.3f}  medR {x.R.median():+.2f}  mean% {x.ret_pct.mean():+.3f}  med% {x.ret_pct.median():+.3f}  "
          f"top10 {srt.head(10).ret_pct.sum()/tot*100 if tot else float('nan'):5.0f}%  days {x.days.median():.0f}\n"
          f"{'':52s} by year mean%: {yrs}")


if __name__ == "__main__":
    uni = pd.read_csv(HERE.parent / "nse_equity_universe.csv").ticker.tolist()
    res = run(uni)
    res.to_csv(HERE / "ema34_touch_weekly8_results.csv", index=False)
    print(f"\nsetup candles traded: {len(res)}\n")
    report(res, "ALL daily 34-EMA touch-and-hold")
    report(res[~res.aligned], "  daily 8-EMA BELOW 34 (no uptrend)")
    a = res[res.aligned]
    report(a, "  daily 8-EMA ABOVE 34 (uptrend)")
    for w in ("touch", "above", "below"):
        report(a[a.weekly == w], f"    uptrend + weekly {w}")
    print("\nUSER'S CONDITION: daily 34-EMA vs weekly 8-EMA")
    report(res[res.d34_above_w8], "  daily 34 ABOVE weekly 8")
    report(res[~res.d34_above_w8], "  daily 34 BELOW weekly 8 (user: avoid)")
    print("\nBOTH RULES TOGETHER")
    for a1 in (True, False):
        for b1 in (True, False):
            report(res[(res.aligned == a1) & (res.d34_above_w8 == b1)], f"  daily 8>34={a1}, daily34>weekly8={b1}")
    print("\nhow often the two lines are within 0.5% of each other at the setup:",
          round((res.d34_vs_w8_pct.abs() <= 0.5).mean() * 100, 1), "%")
