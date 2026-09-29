"""RQ-QS-07A-1 -- Neutral Event Matrix (2026-09-29, critic-specified, pre-registered
before running).

Objective (critic's exact wording): "Across the full eligible universe, what types
of short-horizon price paths naturally precede and follow unusually large 1-, 2-,
and 3-day moves?" This script builds ONLY the event matrix and characterizes its
natural distribution -- no "fast mover" threshold is chosen here, no feature is
tested as a predictor, no model, no score, no filter. That comes later, and only
after this distribution is actually looked at.

POPULATION: every ticker in `nse_equity_universe.csv` (2,327, RQ-QS-07U), NOT
restricted to NIFTY 500 or F&O eligibility -- both attached as METADATA tags only.
No QS-A gate, no breakout requirement.

ELIGIBILITY (pre-declared): a stock-day T is eligible if (a) at least 60 trading
days of prior history exist (matches this project's own MIN_HISTORY convention
elsewhere), (b) T itself is not a corp_action_day, (c) at least 3 more real trading
days exist after T with no corp_action_day in T+1..T+3 (the forward window must be
clean -- a split/bonus inside the window would fabricate the forward return, the
exact bug RQ-QS-06 caught and fixed earlier tonight).

FORWARD OUTCOMES per eligible stock-day T (all computed strictly from T+1 onward,
vectorized per ticker -- NOT a python loop over 2M+ rows):
  max_return_D1/D2/D3   High-based max favorable move over the next 1/2/3 sessions,
                        % of Close_T (matches this project's raw-trigger convention
                        -- "did the opportunity exist", not "did we act on it")
  adverse_D1/D2/D3      Low-based max adverse move over the same windows (MAE)
  close_ret_D1/D2/D3    close-to-close % return at each horizon (the SUSTAINED
                        outcome, kept explicitly separate from the max/MFE view --
                        critic's own point: "a large positive move can be followed
                        by continuation or reversal... looking only at the eventual
                        maximum would manufacture a winner population")
  day_of_max            which day (1, 2, or 3) the D1-D3 window's peak High occurs

PATH-SHAPE CATEGORY, pre-declared BEFORE running, priority order (mutually
exclusive by construction -- earlier rules checked first):
  spike_and_fade   day_of_max==1 AND max_return_D1>0 AND close_ret_D3 <=
                   0.5*max_return_D1  (a real early high, more than half given
                   back by D3's close -- the MAX-effect-style caution from the
                   literature check: an extreme one-day move is not automatically
                   a continuation signal)
  burst            day_of_max==1, not spike_and_fade (early move, holds up)
  delayed          max_return_D1<=0 AND max_return_D3>max_return_D1  (no early
                   upside at all; the real move only shows up on day 2 or 3)
  progressive      day_of_max==3 AND max_return_D1>0 AND max_return_D2>max_return_D1
                   (steadily extending across the whole window)
  other            everything else (day_of_max==2 cases and anything not matching
                   cleanly above) -- a real bucket, not swept under one of the above

METADATA (not filters): nifty500_member (current membership, `nifty500_universe.csv`
-- NOT point-in-time correct, v1 limitation inherited from RQ-QS-07U, disclosed),
fo_eligible (current membership, `fo_universe.csv`, same caveat).

No threshold on move SIZE is applied anywhere in this script -- every eligible
stock-day is included regardless of how big or small its forward move turned out
to be. Deciding what counts as a "fast mover" is the next, separate step.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
MIN_HISTORY = 60


def event_matrix_for(ticker, nifty500_set, fo_set):
    try:
        df = load(ticker, daily_pivots)
    except FileNotFoundError:
        return None
    n = len(df)
    if n < MIN_HISTORY + 4:
        return None
    df = df.reset_index()

    close = df.Close.values
    open_ = df.Open.values
    high = df.High.values
    low = df.Low.values
    corp = df.corp_action_day.values
    liquidity = df.traded_value_sma20.values  # (Close*Volume) 20d avg, decision-time-safe at T

    h1, h2, h3 = np.roll(high, -1), np.roll(high, -2), np.roll(high, -3)
    l1, l2, l3 = np.roll(low, -1), np.roll(low, -2), np.roll(low, -3)
    c1, c2, c3 = np.roll(close, -1), np.roll(close, -2), np.roll(close, -3)
    o1, o2, o3 = np.roll(open_, -1), np.roll(open_, -2), np.roll(open_, -3)
    corp1, corp2, corp3 = np.roll(corp, -1), np.roll(corp, -2), np.roll(corp, -3)

    # circuit-lock day: Open==High==Low==Close (within a tiny float tolerance) -- the
    # exact signature found by hand-verifying KOTYARK (RQ-QS-07A-1's extreme-tail
    # example), a genuine no-real-intraday-range price-band-hit day, not a computation
    # artifact. Counted per forward day, not blended into the return math itself.
    def _is_circuit(o, h, l, c):
        with np.errstate(invalid="ignore"):
            rng = np.maximum(h, c) - np.minimum(l, c)
            return (rng / np.where(c != 0, c, np.nan)) < 0.0005
    circ1, circ2, circ3 = _is_circuit(o1, h1, l1, c1), _is_circuit(o2, h2, l2, c2), _is_circuit(o3, h3, l3, c3)

    max_h_d1 = h1
    max_h_d2 = np.maximum(h1, h2)
    max_h_d3 = np.maximum(max_h_d2, h3)
    min_l_d1 = l1
    min_l_d2 = np.minimum(l1, l2)
    min_l_d3 = np.minimum(min_l_d2, l3)

    with np.errstate(divide="ignore", invalid="ignore"):
        max_return_d1 = (max_h_d1 / close - 1) * 100
        max_return_d2 = (max_h_d2 / close - 1) * 100
        max_return_d3 = (max_h_d3 / close - 1) * 100
        adverse_d1 = (min_l_d1 / close - 1) * 100
        adverse_d2 = (min_l_d2 / close - 1) * 100
        adverse_d3 = (min_l_d3 / close - 1) * 100
        close_ret_d1 = (c1 / close - 1) * 100
        close_ret_d2 = (c2 / close - 1) * 100
        close_ret_d3 = (c3 / close - 1) * 100

    day_of_max = np.where(h1 >= max_h_d3, 1, np.where(np.maximum(h1, h2) >= max_h_d3, 2, 3))

    valid_history = np.arange(n) >= MIN_HISTORY
    valid_future = np.arange(n) <= n - 4  # need T+1..T+3 to exist
    clean_forward = ~corp1.astype(bool) & ~corp2.astype(bool) & ~corp3.astype(bool)
    eligible = valid_history & valid_future & ~corp.astype(bool) & clean_forward

    circuit_days_in_window = circ1.astype(int) + circ2.astype(int) + circ3.astype(int)

    out = pd.DataFrame({
        "ticker": ticker, "date": df.Date.dt.date, "close": close,
        "max_return_d1": max_return_d1, "max_return_d2": max_return_d2, "max_return_d3": max_return_d3,
        "adverse_d1": adverse_d1, "adverse_d2": adverse_d2, "adverse_d3": adverse_d3,
        "close_ret_d1": close_ret_d1, "close_ret_d2": close_ret_d2, "close_ret_d3": close_ret_d3,
        "day_of_max": day_of_max, "traded_value_sma20": liquidity,
        "circuit_days_in_window": circuit_days_in_window,
    })[eligible].reset_index(drop=True)
    if out.empty:
        return out

    spike_and_fade = (out.day_of_max == 1) & (out.max_return_d1 > 0) & \
                      (out.close_ret_d3 <= 0.5 * out.max_return_d1)
    burst = (out.day_of_max == 1) & ~spike_and_fade
    delayed = (out.max_return_d1 <= 0) & (out.max_return_d3 > out.max_return_d1) & ~burst & ~spike_and_fade
    progressive = (out.day_of_max == 3) & (out.max_return_d1 > 0) & (out.max_return_d2 > out.max_return_d1) & \
                  ~burst & ~spike_and_fade & ~delayed
    out["path_shape"] = "other"
    out.loc[delayed, "path_shape"] = "delayed"
    out.loc[progressive, "path_shape"] = "progressive"
    out.loc[burst, "path_shape"] = "burst"
    out.loc[spike_and_fade, "path_shape"] = "spike_and_fade"

    # burst_clean (2026-09-29, critic's exact instruction): burst_v0 (path_shape=="burst")
    # kept as originally pre-registered, NOT rewritten -- 69% of it turned out to have no
    # real day-1 upside at all. burst_clean is a secondary, explicitly-separate descriptive
    # label requiring genuine max_return_d1>0, carried alongside, not replacing, the original.
    out["burst_clean"] = burst & (out.max_return_d1 > 0)

    out["nifty500_member"] = ticker in nifty500_set
    out["fo_eligible"] = ticker in fo_set
    return out


if __name__ == "__main__":
    uni = pd.read_csv("nse_equity_universe.csv")
    tickers = uni.ticker.tolist()
    nifty500_set = set(pd.read_csv("nifty500_universe.csv", header=None)[0])
    fo_set = set(pd.read_csv("fo_universe.csv", header=None)[0])
    print(f"Universe: {len(tickers)} tickers")

    parts = []
    total_rows = 0
    for n, t in enumerate(tickers):
        if n % 200 == 0:
            print(f"{n}/{len(tickers)}  ({total_rows:,} eligible stock-days so far)", flush=True)
        r = event_matrix_for(t, nifty500_set, fo_set)
        if r is not None and not r.empty:
            parts.append(r)
            total_rows += len(r)

    df = pd.concat(parts, ignore_index=True)
    print(f"\nTotal eligible stock-days: {len(df):,} across {df.ticker.nunique():,} tickers")
    df.to_csv(f"{OUT_DIR}/event_matrix.csv", index=False)
    print(f"saved event_matrix.csv ({os.path.getsize(f'{OUT_DIR}/event_matrix.csv')/1e6:.0f} MB)")

    # a manageable, reproducible-seed sample for quick inspection/hand-verification,
    # alongside the full parquet (kept, not a substitute for it)
    df.sample(n=min(200_000, len(df)), random_state=42).to_csv(f"{OUT_DIR}/event_matrix_sample_200k.csv", index=False)
