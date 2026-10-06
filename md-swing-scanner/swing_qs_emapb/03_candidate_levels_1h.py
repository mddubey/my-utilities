"""RQ-EMAPB-01 step 3 -- test four literature-derived candidate re-entry levels, one at a
time, on 1H bars: (1) retest of the original breakout level (classic throwback/"change of
polarity"), (2) Fib 38.2%, (3) Fib 50%, (4) Fib 61.8% retracement of the initial impulsive
leg (A's entry price -> the peak reached before the first pullback). Baseline is fixed this
time: each touch's forward return is compared against the population's own TYPICAL return at
that SAME bar-offset (not one arbitrary fixed bar), so "early beats late" can't masquerade as
"this level works." Usage: python3 swing_qs_emapb/03_candidate_levels_1h.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOW_BARS = 70
HORIZONS = {"1H": 1, "3H": 3, "1D": 7, "3D": 21}
FIB_FRACS = {"fib382": 0.382, "fib50": 0.5, "fib618": 0.618}
STALL_BAND_PCT = 1.0  # |3D forward return| < this = "stall", per the predeclared convention


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
    """Decision-time-safe running high, same convention as swing_qs_bpc's 07_rq04a:
    the peak is the running max of High up to the first bar that fails to extend it."""
    running_high = rows.iloc[ia].High
    peak_i = ia
    for k in range(ia + 1, end):
        if rows.iloc[k].corp_action_day if "corp_action_day" in rows.columns else False:
            return peak_i, running_high, k
        if rows.iloc[k].High > running_high:
            running_high = rows.iloc[k].High
            peak_i = k
        else:
            return peak_i, running_high, k  # pullback starts here
    return peak_i, running_high, end  # never failed to extend within the window


def find_touch(rows, start, end, level):
    for k in range(start, end):
        row_k = rows.iloc[k]
        if row_k.Low <= level and row_k.Close >= level:
            return k
    return None


def main():
    pop = pd.read_csv("swing_qs_bpc/rq_bpc05_a_volume_diagnostics.csv")
    pop = pop[(pop.entry_definition == 10) & (pop.vol_ratio >= 1.5) &
              (pop.a_entry_date >= "2023-10-23")]
    print(f"Population: {len(pop):,}", flush=True)

    candidates = {"retest": None, **FIB_FRACS}  # "retest" computed per-row (== a_entry_price)
    out_rows = []
    typical_samples = {h: {} for h in HORIZONS}  # offset -> list of returns, unconditional

    rows_cache = {}
    for n, (ticker, grp) in enumerate(pop.groupby("ticker")):
        if n % 100 == 0:
            print(f"{n}/{pop.ticker.nunique()} tickers", flush=True)
        rows = rows_cache.setdefault(ticker, load_60m(ticker))
        if rows is None:
            continue
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

            rec = dict(ticker=ticker, a_entry_date=r.a_entry_date, vol_ratio=r.vol_ratio,
                       swing_low=swing_low, swing_high=swing_high,
                       swing_pct=(swing_high / swing_low - 1) * 100,
                       pullback_start_offset=pullback_start - ia)

            levels = dict(retest=swing_low)
            for name, frac in FIB_FRACS.items():
                levels[name] = swing_high - frac * (swing_high - swing_low)

            for name, level in levels.items():
                touch_i = find_touch(rows, pullback_start, end, level)
                rec[f"{name}_touched"] = touch_i is not None
                rec[f"{name}_offset"] = (touch_i - ia) if touch_i is not None else None
                if touch_i is not None:
                    for hlabel, n_bars in HORIZONS.items():
                        m = forward_metrics(rows, touch_i, n_bars)
                        if m:
                            rec[f"{name}_{hlabel}_ret"] = m["ret"]
                            rec[f"{name}_{hlabel}_mfe"] = m["mfe"]
                            rec[f"{name}_{hlabel}_mae"] = m["mae"]

            # unconditional typical-return-by-offset samples (every 5th bar, cheap enough)
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
    df.to_csv(f"{HERE}/rq_emapb01_candidate_levels.csv", index=False)
    print(f"\nSaved {len(df):,} rows", flush=True)

    # typical-by-offset median curve, per horizon
    typical_median = {h: {off: np.median(v) for off, v in d.items()} for h, d in typical_samples.items()}

    def nearest_typical(hlabel, offset):
        offs = np.array(sorted(typical_median[hlabel]))
        nearest = offs[np.argmin(np.abs(offs - offset))]
        return typical_median[hlabel][nearest]

    for name in ["retest", "fib382", "fib50", "fib618"]:
        print(f"\n{'='*70}\nCANDIDATE: {name}\n{'='*70}")
        touched = df[df[f"{name}_touched"]].copy()
        print(f"touched: {len(touched):,} / {len(df):,} ({len(touched)/len(df)*100:.1f}%)  "
              f"median offset: {touched[f'{name}_offset'].median():.0f} bars")
        for hlabel in HORIZONS:
            col = f"{name}_{hlabel}_ret"
            if col not in touched.columns:
                continue
            sub = touched.dropna(subset=[col])
            if len(sub) == 0:
                continue
            excess = sub.apply(lambda row: row[col] - nearest_typical(hlabel, row[f"{name}_offset"]), axis=1)
            print(f"  {hlabel}: n={len(sub):,}  median_ret={sub[col].median():+.3f}%  "
                  f"median_excess_vs_typical={excess.median():+.3f}%  %excess>0={(excess>0).mean()*100:.1f}%")
        ret3d = touched[f"{name}_3D_ret"].dropna()
        if len(ret3d):
            stall = (ret3d.abs() < STALL_BAND_PCT).mean() * 100
            resumed = (ret3d >= STALL_BAND_PCT).mean() * 100
            reversed_ = (ret3d <= -STALL_BAND_PCT).mean() * 100
            print(f"  3D outcome: stall(|ret|<{STALL_BAND_PCT}%)={stall:.1f}%  resumed(>=+{STALL_BAND_PCT}%)={resumed:.1f}%  "
                  f"reversed(<=-{STALL_BAND_PCT}%)={reversed_:.1f}%")


if __name__ == "__main__":
    main()
