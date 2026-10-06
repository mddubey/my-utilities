"""RQ-EMAPB-01 step 2 -- rebuild on 1H bars, not daily. The two ground-truth examples
(VEDL 2025-12-12, REDINGTON 2026-07-30) were described by the user on the HOURLY chart --
testing on daily bars was testing the wrong resolution, which is why three daily-bar
definitions in a row failed to capture either one. Population restricted to A's from
2023-10-23 onward (data/intraday_60m/ coverage start). Start with the SIMPLEST definition
(any touch, no hold/expand machinery) to re-check against ground truth before adding any
complexity.

Usage: python3 swing_qs_emapb/02_build_touch_panel_1h.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
EMA_PERIODS = (8, 20, 50)
WINDOW_BARS = 70   # ~10 trading days of 1H bars (7 bars/day)
HORIZONS = {"1H": 1, "2H": 2, "3H": 3, "1D": 7, "3D": 21}


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


def process_a(rows, ia, meta):
    out = dict(meta)
    n_rows = len(rows)
    end = min(ia + 1 + WINDOW_BARS, n_rows)

    for N in EMA_PERIODS:
        ema = rows.Close.ewm(span=N, adjust=False).mean()
        touch_i = None
        for k in range(ia + 1, end):
            row_k = rows.iloc[k]
            if row_k.Low <= ema.iloc[k - 1] and row_k.Close >= ema.iloc[k]:
                touch_i = k
                break
        out[f"touched_ema{N}"] = touch_i is not None
        out[f"bars_to_touch_ema{N}"] = (touch_i - ia) if touch_i is not None else None
        if touch_i is not None:
            for hlabel, n_bars in HORIZONS.items():
                m = forward_metrics(rows, touch_i, n_bars)
                if m:
                    out[f"ema{N}_{hlabel}_ret"] = m["ret"]
                    out[f"ema{N}_{hlabel}_mfe"] = m["mfe"]
                    out[f"ema{N}_{hlabel}_mae"] = m["mae"]

    # baseline: fixed-offset bar (window midpoint), independent of any touch
    base_i = ia + WINDOW_BARS // 2
    if base_i < end:
        for hlabel, n_bars in HORIZONS.items():
            m = forward_metrics(rows, base_i, n_bars)
            if m:
                out[f"baseline_{hlabel}_ret"] = m["ret"]
    return out


def main():
    pop = pd.read_csv("swing_qs_bpc/rq_bpc05_a_volume_diagnostics.csv")
    pop = pop[(pop.entry_definition == 10) & (pop.vol_ratio >= 1.5) &
              (pop.a_entry_date >= "2023-10-23")]
    print(f"Population (10-day lookback, vol>=1.5x, A after 2023-10-23): {len(pop):,}", flush=True)

    out_rows = []
    rows_cache = {}
    n_no_bar, n_total = 0, 0
    for n, (ticker, grp) in enumerate(pop.groupby("ticker")):
        if n % 100 == 0:
            print(f"{n}/{pop.ticker.nunique()} tickers", flush=True)
        rows = rows_cache.setdefault(ticker, load_60m(ticker))
        if rows is None:
            continue
        for r in grp.itertuples():
            n_total += 1
            a_date = pd.Timestamp(r.a_entry_date)
            match = rows.index[rows.session_date >= a_date]
            if len(match) == 0:
                n_no_bar += 1
                continue
            ia = int(match[0])
            if rows.iloc[ia].session_date != a_date:
                n_no_bar += 1
                continue  # no 1H data for this exact session (gap in the cache)
            meta = dict(ticker=ticker, a_entry_date=r.a_entry_date, vol_ratio=r.vol_ratio)
            out_rows.append(process_a(rows, ia, meta))

    print(f"A's with no matching 1H bar (cache gap/missing session): {n_no_bar}/{n_total}", flush=True)
    df = pd.DataFrame(out_rows)
    df.to_csv(f"{HERE}/rq_emapb01_panel_1h.csv", index=False)
    print(f"\nSaved {len(df):,} rows -> rq_emapb01_panel_1h.csv", flush=True)
    for N in EMA_PERIODS:
        rate = df[f"touched_ema{N}"].mean() * 100
        med = df.loc[df[f"touched_ema{N}"], f"bars_to_touch_ema{N}"].median()
        print(f"EMA{N} touched within {WINDOW_BARS} bars: {rate:.1f}%  median bars to touch: {med:.1f}")


if __name__ == "__main__":
    main()
