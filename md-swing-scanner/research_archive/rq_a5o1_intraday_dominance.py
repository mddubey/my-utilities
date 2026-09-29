"""RQ-A5-O1 -- intraday dominance-loss event study on the canonical options-entry/
breach population (2026-09-22 handoff). The single approved next action for the
A5-Options branch: establish whether actionable intraday information exists that the
daily A5 framework misses, before touching any threshold, indicator, or exit rule.

Explicitly OUT of scope here (guardrails from the handoff): no exit rule, no
theta-derived threshold, no EMA8 promotion, no option-price estimator, no production
changes. This is purely a measurement pass.

Reuses A5-Stock's own event construction and outcomes (rq_a5_retest_dominance.csv --
same breakout/retest definitions, same Rule #10-compliant Close-anchored outcomes:
ret_d1/ret_d2 stock close-to-close, opt_d1_open the project's standard stock-based
day+1-open proxy for an option's PnL -- NOT a real option price, matches the
established convention used everywhere else in this project, e.g.
breakout_failure_confirmation_cost.simulate_day1()). Restricted to F&O-eligible
tickers with BOTH the breakout day and the retest day inside intraday_cache's real
coverage window (2026-06-10..2026-09-19, the last date with a complete trading day of
5-min bars) -- n=656 (637 breakout_cont, 19 coiled_spring), a small-sample caveat
this project always attaches to intraday-only work (matches RQ-66B's n=303 precedent).

Method: for each retest event, walk the RETEST day's real 5-min bars and compute, at
several checkpoints through the trading day (10/25/50/75/100% of the day elapsed --
checkpoints chosen to span the day, not swept/optimized), the SAME two ingredients
A5-Stock already validated as the dominance-loss concept, but as RUNNING (as-of-that-
bar) values instead of end-of-day values:
  - running Volume Dominance: cumulative volume so far today / cumulative volume by
    the SAME bar-index on the original breakout day (bar-index alignment, not clock-
    time alignment -- trading days run ~72-73 five-min bars, close enough that index
    alignment approximates same-time-of-day without presupposing exact minute).
  - running Price Failure: how far the current price sits below the day's OWN running
    high so far (off_high_pct), and where it sits within the day's own running range
    (price_pos_pct) -- an intraday analog of close_position_pct.

At each checkpoint, correlate the running values against BOTH outcomes (ret_d1 stock,
opt_d1_open options) to build an "information arrival" curve across the day --
answering Q-A (does it show up earlier than the daily EOD picture) and Q-C (is the
options curve actually different from the stock curve, or the same information on the
same timeline). Q-B (is earlier detection useful) is checked via the halfway-point
quartile table -- same false-exit-risk framing as this project's other early-detection
diagnostics (RQ-77 style: does the weak half-day quartile still contain real
recoveries).
"""
import warnings
warnings.filterwarnings("ignore")

import sys
from pathlib import Path

import pandas as pd

from daily_scan import _fo_tickers
from research.metrics import win_rate, expectancy

INTRADAY_CACHE_DIR = Path(__file__).parent / "intraday_cache"
INTRADAY_LO = pd.Timestamp("2026-06-10")
INTRADAY_HI = pd.Timestamp("2026-09-19")   # last date with a full trading day of bars
FRAC_CHECKPOINTS = [0.10, 0.25, 0.50, 0.75, 1.00]


def _load_intraday(ticker):
    path = INTRADAY_CACHE_DIR / f"{ticker}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["Datetime"])
    if df.empty:
        return None
    df["Datetime"] = df["Datetime"].dt.tz_convert("Asia/Kolkata")
    df["day"] = df["Datetime"].dt.normalize()
    return df


def _day_bars(intraday_df, date):
    target = pd.Timestamp(date).normalize().tz_localize("Asia/Kolkata")
    d = intraday_df[intraday_df.day == target]
    return d.reset_index(drop=True) if len(d) else None


def load_events():
    df = pd.read_csv("rq_a5_retest_dominance.csv", parse_dates=["breakout_date", "retest_date"])
    fo = set(_fo_tickers())
    df = df[df.ticker.isin(fo)]
    df = df[(df.retest_date >= INTRADAY_LO) & (df.retest_date <= INTRADAY_HI)
            & (df.breakout_date >= INTRADAY_LO)]
    return df.reset_index(drop=True)


def gather(events, verbose=False):
    rows = []
    cache = {}
    n_skipped_no_data = 0
    for n, ev in enumerate(events.itertuples()):
        if verbose and n % 100 == 0:
            print(f"  {n}/{len(events)} events, {len(rows)} checkpoint-rows so far", file=sys.stderr)
        t = ev.ticker
        if t not in cache:
            cache[t] = _load_intraday(t)
        idf = cache[t]
        if idf is None:
            n_skipped_no_data += 1
            continue
        bo_bars = _day_bars(idf, ev.breakout_date)
        rt_bars = _day_bars(idf, ev.retest_date)
        if bo_bars is None or rt_bars is None or len(bo_bars) < 10 or len(rt_bars) < 10:
            n_skipped_no_data += 1
            continue

        n_bars = min(len(bo_bars), len(rt_bars))
        bo_cum_vol = bo_bars.Volume.iloc[:n_bars].cumsum().reset_index(drop=True)
        rt_cum_vol = rt_bars.Volume.iloc[:n_bars].cumsum().reset_index(drop=True)
        rt_high_run = rt_bars.High.iloc[:n_bars].cummax().reset_index(drop=True)
        rt_low_run = rt_bars.Low.iloc[:n_bars].cummin().reset_index(drop=True)
        rt_close = rt_bars.Close.iloc[:n_bars].reset_index(drop=True)

        for frac in FRAC_CHECKPOINTS:
            bar_idx = max(0, min(n_bars - 1, int(round(frac * (n_bars - 1)))))
            bo_v = bo_cum_vol.iloc[bar_idx]
            vol_ratio = rt_cum_vol.iloc[bar_idx] / bo_v if bo_v else None
            hi, lo, cl = rt_high_run.iloc[bar_idx], rt_low_run.iloc[bar_idx], rt_close.iloc[bar_idx]
            rng = hi - lo
            price_pos = (cl - lo) / rng * 100 if rng > 0 else None
            off_high = (cl / hi - 1) * 100 if hi else None

            rows.append(dict(
                ticker=t, retest_date=ev.retest_date, pattern=ev.pattern, frac=frac,
                bars_in_day=n_bars, vol_ratio=vol_ratio, price_pos=price_pos, off_high=off_high,
                ret_d1=ev.ret_d1, ret_d2=ev.ret_d2, opt_d1_open=ev.opt_d1_open,
            ))
    print(f"\nEvents with no usable intraday data (skipped): {n_skipped_no_data}/{len(events)}",
          file=sys.stderr)
    return pd.DataFrame(rows)


def _line(label, g):
    d1 = g.ret_d1.dropna()
    opt = g.opt_d1_open.dropna()
    print(f"  {label:<20} n={len(g):<4} d1 win={win_rate(d1):5.1f}%/exp={expectancy(d1):+.3f}%  "
          f"opt win={win_rate(opt):5.1f}%/exp={expectancy(opt):+.3f}%")


def report_information_curve(df):
    print("\n" + "=" * 78)
    print("Information-arrival curve -- correlation of the RUNNING intraday signal with")
    print("each outcome, at successive fractions of the trading day elapsed")
    print("=" * 78)
    feats = ["vol_ratio", "off_high", "price_pos"]
    header = f"  {'frac-of-day':<12}" + "".join(f"{f+'/d1':>14}{f+'/opt':>14}" for f in feats)
    print(header)
    for frac in FRAC_CHECKPOINTS:
        d = df[df.frac == frac]
        cells = []
        for f in feats:
            sub = d.dropna(subset=[f, "ret_d1"])
            c_d1 = sub[f].corr(sub.ret_d1) if len(sub) > 5 else float("nan")
            sub2 = d.dropna(subset=[f, "opt_d1_open"])
            c_opt = sub2[f].corr(sub2.opt_d1_open) if len(sub2) > 5 else float("nan")
            cells.append(f"{c_d1:>14.3f}{c_opt:>14.3f}")
        print(f"  {frac*100:>10.0f}%" + "".join(cells))
    print("\n  (n at each checkpoint = same event population throughout, see population size below)")


def report_quartiles_at(df, frac, feat):
    d = df[(df.frac == frac)].dropna(subset=[feat])
    if len(d) < 20:
        print(f"\n=== {feat} @ {frac*100:.0f}% of day: n={len(d)}, too thin to bucket ===")
        return
    d = d.copy()
    try:
        d["bucket"] = pd.qcut(d[feat], 4, duplicates="drop")
    except ValueError:
        print(f"\n=== {feat} @ {frac*100:.0f}% of day: not enough distinct values ===")
        return
    print(f"\n=== {feat}, quartiles, @ {frac*100:.0f}% of the trading day elapsed ===")
    for b, g in d.groupby("bucket", observed=True):
        _line(str(b), g)


def report(df, events):
    print(f"\nRQ-A5-O1 event population: {events.ticker.nunique()} unique tickers, "
          f"{len(events)} retest events (F&O + intraday-window, {events.pattern.value_counts().to_dict()})")
    print(f"Checkpoint-rows built: {len(df)} ({df[df.frac==1.0].ticker.nunique()} events reached the "
          f"100% checkpoint -- see skip count above for data gaps)")

    report_information_curve(df)

    print("\n" + "=" * 78)
    print("Q-B check: quartile outcomes at the HALFWAY point of the retest day")
    print("(if you had to decide by roughly midday, what would each quartile's real")
    print("options outcome have looked like -- false-exit-risk framing)")
    print("=" * 78)
    for feat in ["vol_ratio", "off_high", "price_pos"]:
        report_quartiles_at(df, 0.50, feat)

    print("\n" + "=" * 78)
    print("For comparison: quartile outcomes at the FULL-DAY (100%) checkpoint --")
    print("this should approximately reproduce A5-Stock's own daily-bar finding as an")
    print("internal consistency check (recomputed independently from raw 5-min bars)")
    print("=" * 78)
    for feat in ["vol_ratio", "off_high", "price_pos"]:
        report_quartiles_at(df, 1.00, feat)


if __name__ == "__main__":
    events = load_events()
    checkpoint_df = gather(events, verbose=True)
    checkpoint_df.to_csv("rq_a5o1_intraday_dominance.csv", index=False)
    print("\nRaw checkpoint table saved to rq_a5o1_intraday_dominance.csv")
    report(checkpoint_df, events)
