"""RQ-EMAPB-01 step 4 -- the full, fair side-by-side comparison. Every candidate "support"
level the literature or the user raised, tested with the SAME corrected methodology (timing-
matched baseline, not a fixed bar): retest (orig. breakout level), Fib 38.2/50/61.8%,
EMA8/20/50 on 1H bars, and the project's own PRODUCTION daily indicators (ema8/ema21/ema34,
sma21/sma50, floor-trader pivot S1) reused unchanged from pivots.py/signals.py -- not
reinvented. Daily-level indicators use the PRIOR trading day's value (decision-time-safe,
matching daily_pivots' own convention), held constant through that day's 1H bars.

Usage: python3 swing_qs_emapb/04_full_comparison.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

from data.paths import INTRADAY_60M_DIR
from backtest import load, daily_pivots

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOW_BARS = 70
HORIZONS = {"1H": 1, "3H": 3, "1D": 7, "3D": 21}
FIB_FRACS = {"fib382": 0.382, "fib50": 0.5, "fib618": 0.618}
DAILY_COLS = ["ema8", "ema21", "ema34", "sma21", "sma50", "s1"]  # production columns, reused as-is


def load_60m(ticker):
    f = INTRADAY_60M_DIR / f"{ticker}.csv"
    if not f.exists():
        return None
    d = pd.read_csv(f, index_col=0)
    if d.empty:
        return None
    d.index = pd.to_datetime(d.index, utc=True).tz_convert("Asia/Kolkata")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    d = d.dropna(subset=["Close", "High", "Low"])
    if len(d) < 100:
        return None
    d["session_date"] = d.index.normalize().tz_localize(None)
    return d.reset_index(drop=True)


def attach_daily_levels(rows_1h, ticker):
    """Map each 1H bar to its session's PRIOR trading day's daily indicator values
    (decision-time-safe -- known before that day's own session starts)."""
    try:
        daily = load(ticker, daily_pivots)
    except FileNotFoundError:
        return rows_1h
    daily = daily.reset_index()
    daily["session_date"] = pd.to_datetime(daily.Date).dt.normalize()
    shifted = daily[["session_date"] + DAILY_COLS].copy()
    shifted[DAILY_COLS] = shifted[DAILY_COLS].shift(1)  # prior day's value
    rows_1h = rows_1h.merge(shifted, on="session_date", how="left")
    return rows_1h


def forward_metrics(rows, i0, n):
    end = min(i0 + 1 + n, len(rows))
    if end - (i0 + 1) < n:
        return None
    span = rows.iloc[i0 + 1:end]
    c0 = rows.iloc[i0].Close
    return dict(ret=(span.Close.iloc[-1] / c0 - 1) * 100,
                mfe=(span.High.max() / c0 - 1) * 100,
                mae=(span.Low.min() / c0 - 1) * 100)


def find_peak(rows, ia, end):
    running_high = rows.iloc[ia].High
    peak_i = ia
    for k in range(ia + 1, end):
        if rows.iloc[k].High > running_high:
            running_high = rows.iloc[k].High
            peak_i = k
        else:
            return peak_i, running_high, k
    return peak_i, running_high, end


def find_touch(rows, start, end, level_series):
    """level_series: either a scalar (fixed level) or a pandas-indexable series aligned to
    rows (time-varying level). Decision-time-safe: Low vs level AS OF THE PRIOR BAR."""
    for k in range(start, end):
        lvl_prior = level_series if np.isscalar(level_series) else level_series.iloc[k - 1]
        lvl_today = level_series if np.isscalar(level_series) else level_series.iloc[k]
        if pd.isna(lvl_prior) or pd.isna(lvl_today):
            continue
        row_k = rows.iloc[k]
        if row_k.Low <= lvl_prior and row_k.Close >= lvl_today:
            return k
    return None


def main():
    pop = pd.read_csv("swing_qs_bpc/rq_bpc05_a_volume_diagnostics.csv")
    pop = pop[(pop.entry_definition == 10) & (pop.vol_ratio >= 1.5) &
              (pop.a_entry_date >= "2023-10-23")]
    print(f"Population: {len(pop):,}", flush=True)

    out_rows = []
    typical_samples = {h: {} for h in HORIZONS}
    rows_cache = {}

    for n, (ticker, grp) in enumerate(pop.groupby("ticker")):
        if n % 100 == 0:
            print(f"{n}/{pop.ticker.nunique()} tickers", flush=True)
        rows = rows_cache.get(ticker)
        if rows is None and ticker not in rows_cache:
            rows = load_60m(ticker)
            if rows is not None:
                rows = attach_daily_levels(rows, ticker)
            rows_cache[ticker] = rows
        if rows is None:
            continue

        ema8_1h = rows.Close.ewm(span=8, adjust=False).mean()
        ema20_1h = rows.Close.ewm(span=20, adjust=False).mean()
        ema50_1h = rows.Close.ewm(span=50, adjust=False).mean()

        for r in grp.itertuples():
            a_date = pd.Timestamp(r.a_entry_date)
            match = rows.index[rows.session_date >= a_date]
            if len(match) == 0:
                continue
            ia = int(match[0])
            if rows.iloc[ia].session_date != a_date:
                continue
            end = min(ia + 1 + WINDOW_BARS, len(rows))
            if end - ia < 10:
                continue

            peak_i, swing_high, pullback_start = find_peak(rows, ia, end)
            swing_low = r.a_entry_price
            if swing_high <= swing_low:
                continue

            levels = dict(retest=swing_low)
            for name, frac in FIB_FRACS.items():
                levels[name] = swing_high - frac * (swing_high - swing_low)
            levels["ema8_1h"] = ema8_1h
            levels["ema20_1h"] = ema20_1h
            levels["ema50_1h"] = ema50_1h
            levels["ema8_d"] = rows.ema8
            levels["ema21_d"] = rows.ema21
            levels["ema34_d"] = rows.ema34
            levels["sma21_d"] = rows.sma21
            levels["sma50_d"] = rows.sma50
            levels["pivot_s1_d"] = rows.s1

            rec = dict(ticker=ticker, a_entry_date=r.a_entry_date,
                       pullback_start_offset=pullback_start - ia)
            for name, level in levels.items():
                touch_i = find_touch(rows, pullback_start, end, level)
                rec[f"{name}_touched"] = touch_i is not None
                rec[f"{name}_offset"] = (touch_i - ia) if touch_i is not None else None
                if touch_i is not None:
                    for hlabel, n_bars in HORIZONS.items():
                        m = forward_metrics(rows, touch_i, n_bars)
                        if m:
                            rec[f"{name}_{hlabel}_ret"] = m["ret"]

            for off in range(1, end - ia, 5):
                i0 = ia + off
                if i0 >= end:
                    continue
                for hlabel, n_bars in HORIZONS.items():
                    m = forward_metrics(rows, i0, n_bars)
                    if m:
                        typical_samples[hlabel].setdefault(off, []).append(m["ret"])

            out_rows.append(rec)

    df = pd.DataFrame(out_rows)
    df.to_csv(f"{HERE}/rq_emapb01_full_comparison.csv", index=False)
    print(f"\nSaved {len(df):,} rows", flush=True)

    typical_median = {h: {off: np.median(v) for off, v in d.items()} for h, d in typical_samples.items()}

    def nearest_typical(hlabel, offset):
        offs = np.array(sorted(typical_median[hlabel]))
        nearest = offs[np.argmin(np.abs(offs - offset))]
        return typical_median[hlabel][nearest]

    names = ["retest", "fib382", "fib50", "fib618", "ema8_1h", "ema20_1h", "ema50_1h",
             "ema8_d", "ema21_d", "ema34_d", "sma21_d", "sma50_d", "pivot_s1_d"]
    print(f"\n{'candidate':12} {'touch%':>7} {'medoff':>7} {'3D_ret':>8} {'3D_excess':>10} {'%exc>0':>7} {'resumed':>8} {'reversed':>9}")
    for name in names:
        touched = df[df[f"{name}_touched"]].dropna(subset=[f"{name}_offset"])
        col3d = f"{name}_3D_ret"
        sub = touched.dropna(subset=[col3d]) if col3d in touched.columns else touched.iloc[0:0]
        if len(sub) < 30:
            print(f"{name:12} {'--':>7} insufficient n")
            continue
        excess = sub.apply(lambda row: row[col3d] - nearest_typical("3D", row[f"{name}_offset"]), axis=1)
        resumed = (sub[col3d] >= 1).mean() * 100
        reversed_ = (sub[col3d] <= -1).mean() * 100
        print(f"{name:12} {len(touched)/len(df)*100:6.1f}% {touched[f'{name}_offset'].median():7.0f} "
              f"{sub[col3d].median():+7.3f}% {excess.median():+9.3f}% {(excess>0).mean()*100:6.1f}% "
              f"{resumed:7.1f}% {reversed_:8.1f}%")


if __name__ == "__main__":
    main()
