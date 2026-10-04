"""RQ-OMD-02 step 1 -- build the reversal-quality panel: everything 02_build_panel.py builds
(prior-move z-score/bucket, cumulative forward metrics at all horizons), PLUS the two things
new to OMD-02 per RQ-OMD-02_PREFLIGHT.md:
  (a) gap-bar magnitude bucketing (3 calendar-matched windows: 84/252/504 sessions), so the
      overnight-originated split can finally be compared on equal footing to intraday bars;
  (b) continuous retracement measurement over the next-session window -- time to first reach
      25/50/75/100% of the initial move given back, and the max favorable excursion reached
      before any reversal begins.
Rebuilt from raw data/intraday_60m/ (not from OMD-01's saved panel, which doesn't carry raw
High/Low). Parallelized across ticker chunks. Usage:
  python3 options_momentum/04_build_reversal_panel.py [n_workers]
Output: options_momentum/reversal_chunk_<k>.pkl, combined into reversal_panel_full.pkl.
"""
import multiprocessing as mp
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", message="All-NaN (slice|axis) encountered")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from options_momentum._lib import trading_calendar, price_affecting_ca_sessions, load_60m  # noqa: E402

HERE = Path(__file__).resolve().parent
W_INTRADAY = (504, 1512, 3024)     # pre-declared, same as OMD-01: ~4mo / ~1y / ~2y of intraday bars
W_GAP = (84, 252, 504)             # new for OMD-02: calendar-matched, ~4mo / ~1y / ~2y of gap bars (1/session)
RETR_FRACS = (0.25, 0.50, 0.75, 1.00)
FO_SET = set(pd.read_csv(ROOT / "fo_universe.csv", header=None)[0])


def bucket_label(direction, absz):
    if np.isnan(absz):
        return None
    mag = "unusual" if absz >= 2 else ("elevated" if absz >= 1 else "normal")
    return ("up_" if direction > 0 else "dn_") + mag


def rolling_z(r_full, mask, W):
    """Trailing z-score of r_full[mask] against its own compact (no-gap) history, window W,
    mapped back to the full-length array (NaN outside `mask`). Same method OMD-01 uses for
    the intraday bucketing; reused here for the gap-bar bucketing too."""
    idx = np.where(mask)[0]
    compact = pd.Series(r_full[idx])
    rm = compact.rolling(W, min_periods=W).mean().shift(1)
    rs = compact.rolling(W, min_periods=W).std().shift(1)
    zc = ((compact - rm) / rs).values
    zf = np.full(len(r_full), np.nan)
    zf[idx] = zc
    return zf


def process_ticker(ticker, cal, ca_sessions):
    d = load_60m(ticker)
    if d is None:
        return None
    n = len(d)
    close = d.Close.values.astype(float)
    high = d.High.values.astype(float)
    low = d.Low.values.astype(float)
    bar_of_day = d.bar_of_day.values
    session_date = d.session_date.values
    cal_pos = np.searchsorted(cal.values, session_date)
    excl_set = ca_sessions.get(ticker, set())
    ca_excl_bar = np.array([p in excl_set for p in cal_pos]) if excl_set else np.zeros(n, bool)
    is_gap = bar_of_day == 0

    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.concatenate([[np.nan], np.log(close[1:] / close[:-1])])
    r_excl = ca_excl_bar.copy()
    r_excl[1:] |= ca_excl_bar[:-1]
    r_excl[0] = True
    r = np.where(r_excl, np.nan, r)
    direction = np.sign(r)
    abs_r = np.abs(r)

    out = {
        "ticker": ticker, "session_date": session_date, "bar_of_day": bar_of_day,
        "is_gap": is_gap, "is_fo": ticker in FO_SET, "r": r, "abs_r": abs_r, "direction": direction,
    }

    # --- magnitude bucketing: intraday (unchanged from OMD-01) and gap-bar (new) ---
    for W in W_INTRADAY:
        z = rolling_z(r, ~is_gap, W)
        out[f"z_intraday_{W}"] = z
        out[f"bucket_intraday_{W}"] = [bucket_label(di, abz) for di, abz in zip(direction, np.abs(z))]
    for W in W_GAP:
        z = rolling_z(r, is_gap, W)
        out[f"z_gap_{W}"] = z
        out[f"bucket_gap_{W}"] = [bucket_label(di, abz) for di, abz in zip(direction, np.abs(z))]
    # unified primary label: whichever origin applies, using the two calendar-matched (~1y) windows
    out["origin"] = np.where(is_gap, "overnight", "intraday")
    out["magnitude_primary"] = np.where(is_gap, out["bucket_gap_252"], out["bucket_intraday_1512"])

    # --- fixed horizons H1/H2/H3: cumulative window [i+1 .. i+h] (unchanged from OMD-01) ---
    for h in (1, 2, 3):
        hi_stack = np.full((h, n), np.nan)
        lo_stack = np.full((h, n), np.nan)
        excl_any = np.zeros(n, bool)
        avail = np.ones(n, bool)
        for o in range(1, h + 1):
            shifted_hi = np.full(n, np.nan); shifted_hi[:n - o] = high[o:]
            shifted_lo = np.full(n, np.nan); shifted_lo[:n - o] = low[o:]
            shifted_excl = np.zeros(n, bool); shifted_excl[:n - o] = ca_excl_bar[o:]
            with np.errstate(divide="ignore", invalid="ignore"):
                hi_stack[o - 1] = np.log(shifted_hi / close)
                lo_stack[o - 1] = np.log(shifted_lo / close)
            excl_any |= shifted_excl
            avail &= (np.arange(n) < n - o)
        with np.errstate(invalid="ignore"):
            path_max = np.nanmax(hi_stack, axis=0)
            path_min = np.nanmin(lo_stack, axis=0)
        close_end = np.full(n, np.nan); close_end[:n - h] = close[h:]
        with np.errstate(divide="ignore", invalid="ignore"):
            ret_raw = np.log(close_end / close)
        bad = excl_any | ca_excl_bar | (~avail)
        up = direction > 0
        mfe = np.where(up, path_max, -path_min)
        mae = np.where(up, path_min, -path_max)
        ret_signed = ret_raw * direction
        for arr, name in ((ret_signed, "ret"), (mfe, "mfe"), (mae, "mae")):
            a = arr.astype(float)
            a[bad] = np.nan
            out[f"h{h}_{name}"] = a

    # --- remainder-of-session, next-session (cumulative), PLUS the new retracement walk over
    #     the next-session window ---
    sess_change = np.r_[True, session_date[1:] != session_date[:-1]]
    sess_id = np.cumsum(sess_change) - 1
    n_sess = sess_id[-1] + 1
    sess_start = np.searchsorted(sess_id, np.arange(n_sess))
    sess_end = np.searchsorted(sess_id, np.arange(n_sess), side="right")
    sess_excl = np.array([ca_excl_bar[sess_start[s]] for s in range(n_sess)])

    eos_ret = np.full(n, np.nan); eos_mfe = np.full(n, np.nan); eos_mae = np.full(n, np.nan)
    next_ret = np.full(n, np.nan); next_mfe = np.full(n, np.nan); next_mae = np.full(n, np.nan)
    retr_t = {f: np.full(n, np.nan) for f in RETR_FRACS}
    pre_reversal_mfe = np.full(n, np.nan)

    for s in range(n_sess):
        a, b = sess_start[s], sess_end[s]
        has_next = s + 1 < n_sess
        b_next = sess_end[s + 1] if has_next else None
        for i in range(a, b):
            c0 = close[i]
            d_ = direction[i]
            if i + 1 < b:
                hi_rel = np.log(high[i + 1:b] / c0); lo_rel = np.log(low[i + 1:b] / c0)
                if not sess_excl[s] and not np.isnan(d_):
                    eos_ret[i] = np.log(close[b - 1] / c0) * d_
                    eos_mfe[i] = hi_rel.max() if d_ > 0 else -lo_rel.min()
                    eos_mae[i] = lo_rel.min() if d_ > 0 else -hi_rel.max()
            if has_next:
                hi_rel = np.log(high[i + 1:b_next] / c0); lo_rel = np.log(low[i + 1:b_next] / c0)
                if not sess_excl[s] and not sess_excl[s + 1] and not np.isnan(d_):
                    pmax, pmin = hi_rel.max(), lo_rel.min()
                    next_ret[i] = np.log(close[b_next - 1] / c0) * d_
                    next_mfe[i] = pmax if d_ > 0 else -pmin
                    next_mae[i] = pmin if d_ > 0 else -pmax
                    # retracement walk: adverse/favorable excursion per bar, running max, first
                    # crossing time for each pre-declared checkpoint fraction of |r_T|
                    adverse_path = -lo_rel if d_ > 0 else hi_rel
                    favorable_path = hi_rel if d_ > 0 else -lo_rel
                    adverse_cummax = np.maximum.accumulate(adverse_path)
                    favorable_cummax = np.maximum.accumulate(favorable_path)
                    abs_ri = abs_r[i]
                    t25 = np.nan
                    for f in RETR_FRACS:
                        idxs = np.where(adverse_cummax >= f * abs_ri)[0]
                        if len(idxs):
                            retr_t[f][i] = idxs[0] + 1
                            if f == 0.25:
                                t25 = idxs[0] + 1
                    if not np.isnan(t25):
                        k = int(t25)
                        # k==1: the 25% crossing happens in the very first forward bar -- there
                        # is no prior bar to measure "continuation before reversal" over, and a
                        # single 1H bar's High/Low carry no reliable intrabar ordering, so this
                        # is honestly "not computable" (NaN), not a 0.0 we can't actually support
                        # (caught via the pre_reversal_mfe<=next_mfe invariant: next_mfe can be
                        # legitimately negative when the whole window is a total failure, which
                        # made the old 0.0 sentinel read as a false "violation").
                        pre_reversal_mfe[i] = favorable_cummax[k - 2] if k >= 2 else np.nan
                    else:
                        pre_reversal_mfe[i] = next_mfe[i]

    out.update(eos_ret=eos_ret, eos_mfe=eos_mfe, eos_mae=eos_mae,
               next_ret=next_ret, next_mfe=next_mfe, next_mae=next_mae,
               pre_reversal_mfe=pre_reversal_mfe)
    for f in RETR_FRACS:
        pct = int(f * 100)
        out[f"t_retr{pct}"] = retr_t[f]
        out[f"reached{pct}"] = ~np.isnan(retr_t[f])

    df = pd.DataFrame(out)
    # r==0 (flat bar) is not a directional move -- see 02_build_panel.py's matching comment
    # for how this was caught (this script's own pre_reversal_mfe<=next_mfe invariant check).
    # Kept in the rolling z-score baselines above (legitimate "sometimes this stock doesn't
    # move" data), excluded only from being emitted as a bucketed directional event here.
    df = df[df.r.notna() & (df.r != 0)]
    return df


def worker(args):
    tickers, chunk_idx = args
    cal = trading_calendar()
    ca_sessions = price_affecting_ca_sessions(cal)
    frames = []
    t0 = time.time()
    for i, t in enumerate(tickers):
        try:
            df = process_ticker(t, cal, ca_sessions)
            if df is not None and len(df):
                frames.append(df)
        except Exception as e:
            print(f"  [chunk {chunk_idx}] {t} FAILED: {e}", flush=True)
        if (i + 1) % 50 == 0:
            print(f"  [chunk {chunk_idx}] {i + 1}/{len(tickers)} tickers, {time.time() - t0:.0f}s", flush=True)
    full = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    out_path = HERE / f"reversal_chunk_{chunk_idx}.pkl"
    full.to_pickle(out_path)
    print(f"[chunk {chunk_idx}] done: {len(full):,} rows -> {out_path.name}, {time.time() - t0:.0f}s", flush=True)
    return str(out_path)


def main():
    n_workers = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    uni = pd.read_csv(ROOT / "nse_equity_universe.csv").ticker.tolist()
    from data.paths import INTRADAY_60M_DIR
    tickers = [t for t in uni if (INTRADAY_60M_DIR / f"{t}.csv").exists()]
    print(f"{len(tickers)} tickers to process across {n_workers} workers", flush=True)
    chunks = [(tickers[k::n_workers], k) for k in range(n_workers)]
    t0 = time.time()
    with mp.Pool(n_workers) as pool:
        paths = pool.map(worker, chunks)
    print(f"all chunks done in {time.time() - t0:.0f}s, combining...", flush=True)
    frames = [pd.read_pickle(p) for p in paths]
    full = pd.concat(frames, ignore_index=True)
    full.to_pickle(HERE / "reversal_panel_full.pkl")
    print(f"reversal_panel_full.pkl: {len(full):,} rows, {full.ticker.nunique()} tickers", flush=True)


if __name__ == "__main__":
    main()
