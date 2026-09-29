"""RQ-67A (2026-09-19): does market/sector CONTEXT at breach time -- not the breakout
candle's own shape, which RQ-66 exhausted without a signal -- predict which EMA34=2
Delta trades become Immediate Fade / true-Unique(15d) losers?

Critic's own read on RQ-66's null result: every successful feature this project has
found so far describes the setup BEFORE entry (Freshness, EMA persistence, Fragility),
not the fate of the setup afterward, and every RQ-66 feature only knew about the single
stock in isolation. This tests the opposite: does it matter what the market AROUND the
stock is doing at breach time. Reuses real production formulas directly (not
re-derived): relative_strength.rs_rating() (stock vs full universe, 126-day RS,
Minervini/IBD percentile), sector_strength.sector_rs() (stock's SECTOR vs all other
sectors), breadth.breadth_pct() (% of Nifty500 above own 200-SMA), plus Nifty's own
trailing 5-day return (simple market-tailwind proxy) from market_regime.py's cached
Nifty file.

Same Research Integrity Rule as RQ-66 (Measurement Anchor Rule): forward returns must
be anchored to the point the feature is knowable. None of these four features are
price-ratios relative to trigger (unlike RQ-66 Stage 1's voided ones), so they aren't
mechanically exposed to that specific artifact -- but every result below is still
checked against Close-anchored forward returns before being trusted.
"""
import warnings
warnings.filterwarnings("ignore")

import sys

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from breakout_failure_confirmation_cost import TRIGGER_CLEARANCE, simulate_swing, simulate_day1
from relative_strength import rs_rating
from sector_strength import sector_rs
from breadth import breadth_pct
from market_regime import NIFTY_FILE
from daily_scan import _fo_tickers
from research.metrics import expectancy, win_rate

FEATURES = ["rs_rating", "sector_rs_pct", "breadth_pct", "nifty_ret5"]


def _nifty_ret5_series():
    df = pd.read_csv(NIFTY_FILE, index_col="Date", parse_dates=True)
    return df.Close.pct_change(5) * 100


def gather(tickers, verbose=False):
    fo = _fo_tickers()
    nifty_ret5 = _nifty_ret5_series()
    signals.EMA34_RISING_DAYS_MIN = 2
    rows = []
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  {n}/{len(tickers)}", file=sys.stderr)
        try:
            df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        for i in range(3, len(df) - 3):
            row = df.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior):
                continue
            if not signals.base_filters_pass(row):
                continue
            trigger = row.high10_prior * TRIGGER_CLEARANCE
            if row.High < trigger:
                continue
            if row.ema34_rising10 >= 9:
                continue  # Delta only

            date = row.Date
            rs = rs_rating(t, date)
            _, sec_pct = sector_rs(t, date)
            bp = breadth_pct(date)
            pos = nifty_ret5.index.searchsorted(date, side="right") - 1
            nret5 = nifty_ret5.iloc[pos] if pos >= 0 else None

            d1 = (df.iloc[i + 1].Close / trigger - 1) * 100
            d2 = (df.iloc[i + 2].Close / trigger - 1) * 100
            d3 = (df.iloc[i + 3].Close / trigger - 1) * 100
            immediate_fade = d1 < 0 and d2 < d1 and d3 < d2

            max_h = min(15, len(df) - i - 1)
            d3_from_close = (df.iloc[i + 3].Close / row.Close - 1) * 100 if max_h >= 3 else None
            d15_from_close = (df.iloc[i + max_h].Close / row.Close - 1) * 100 if max_h >= 1 else None

            rows.append(dict(
                ticker=t, i=i,
                rs_rating=rs, sector_rs_pct=sec_pct, breadth_pct=bp, nifty_ret5=nret5,
                immediate_fade=immediate_fade,
                swing_pnl=simulate_swing(df, i, trigger),
                day1_pnl=simulate_day1(df, i, trigger) if t in fo else None,
                d3_from_close=d3_from_close, d15_from_close=d15_from_close,
            ))
    signals.EMA34_RISING_DAYS_MIN = 9
    return pd.DataFrame(rows)


def report(df, n_buckets=4):
    print(f"\nEMA34=2 Delta population, n={len(df)}")
    print(f"Immediate Fade rate (overall): {df.immediate_fade.mean()*100:.1f}%")
    for feat in FEATURES:
        d = df.dropna(subset=[feat]).copy()
        try:
            d["bucket"] = pd.qcut(d[feat], n_buckets, duplicates="drop")
        except ValueError:
            print(f"\n=== {feat}: not enough distinct values ===")
            continue
        print(f"\n=== {feat} (n={len(d)}, trigger-anchored trade outcome) ===")
        for b, g in d.groupby("bucket", observed=True):
            go = g.dropna(subset=["day1_pnl"])
            print(f"  {str(b):<20} n={len(g):<6} fade={g.immediate_fade.mean()*100:5.1f}%  "
                  f"swing win={win_rate(g.swing_pnl):5.1f}%/exp={expectancy(g.swing_pnl):+.3f}%  "
                  f"opt win={win_rate(go.day1_pnl):5.1f}%/exp={expectancy(go.day1_pnl):+.3f}% (n={len(go)})")
        print(f"  --- sanity check: re-anchored to own Close ---")
        for b, g in d.groupby("bucket", observed=True):
            gg = g.dropna(subset=["d3_from_close"])
            print(f"  {str(b):<20} n={len(gg):<6} d3_from_own_close mean={gg.d3_from_close.mean():+.3f}% "
                  f"median={gg.d3_from_close.median():+.3f}%  d15 mean={gg.d15_from_close.mean():+.3f}%")


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    df = gather(tickers, verbose=True)
    df.to_csv("rq67a_relative_context.csv", index=False)
    report(df)
