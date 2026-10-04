"""RQ-OMD-01 step 2 -- build the full (ticker, bar) panel: prior-move z-score/bucket and all
forward metrics at all pre-declared horizons, for every ticker with a data/intraday_60m/
file. See RQ-OMD-01_PREFLIGHT.md for every convention implemented here (cumulative horizons,
corp-action exclusion, gap-bar vs intraday-bar split, sign convention). No filtering by
F&O/Nifty-500/liquidity -- the full 2,266-ticker universe. One row per bar with a valid prior
return; forward columns are NaN where data is insufficient or a corp action breaks the walk
(never silently dropped -- NaN counts are reported by 03_behaviour_map.py).

Parallelized across ticker chunks (multiprocessing). Usage:
  python3 options_momentum/02_build_panel.py [n_workers]
Output: options_momentum/panel_chunk_<k>.pkl, then combined into panel_full.pkl.
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
W_LIST = (504, 1512, 3024)   # pre-declared robustness windows, ~4mo / ~1y / ~2y of intraday bars
# fo_universe.csv is the CURRENT F&O list, not point-in-time -- reporting split only, per
# the preflight ("F&O classification can be added as a reporting split only, not a filter").
FO_SET = set(pd.read_csv(ROOT / "fo_universe.csv", header=None)[0])


def bucket_label(direction, absz):
    if np.isnan(absz):
        return None
    mag = "unusual" if absz >= 2 else ("elevated" if absz >= 1 else "normal")
    return ("up_" if direction > 0 else "dn_") + mag


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

    # prior-bar log return r_T; NaN if this or the immediately preceding bar's session is
    # corp-action-excluded, or there is no preceding bar.
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.concatenate([[np.nan], np.log(close[1:] / close[:-1])])
    r_excl = ca_excl_bar.copy()
    r_excl[1:] |= ca_excl_bar[:-1]
    r_excl[0] = True
    r = np.where(r_excl, np.nan, r)
    direction = np.sign(r)

    # trailing z-score, intraday bars only, compact-series rolling (see preflight: avoids the
    # gap-bar NaNs distorting a fixed-position rolling window)
    idx_intr = np.where(~is_gap)[0]
    r_compact = pd.Series(r[idx_intr])
    z = {}
    for W in W_LIST:
        rm = r_compact.rolling(W, min_periods=W).mean().shift(1)
        rs = r_compact.rolling(W, min_periods=W).std().shift(1)
        zc = ((r_compact - rm) / rs).values
        zf = np.full(n, np.nan)
        zf[idx_intr] = zc
        z[W] = zf

    out = {
        "ticker": ticker, "session_date": session_date, "bar_of_day": bar_of_day,
        "is_gap": is_gap, "is_fo": ticker in FO_SET, "r": r, "abs_r": np.abs(r), "direction": direction,
    }
    for W in W_LIST:
        out[f"z_{W}"] = z[W]
        out[f"bucket_{W}"] = [bucket_label(di, abz) for di, abz in zip(direction, np.abs(z[W]))]

    # --- fixed horizons H1/H2/H3: cumulative window [i+1 .. i+h] ---
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
            t_max = np.nanargmax(np.nan_to_num(hi_stack, nan=-np.inf), axis=0) + 1
            t_min = np.nanargmin(np.nan_to_num(lo_stack, nan=np.inf), axis=0) + 1
        close_end = np.full(n, np.nan); close_end[:n - h] = close[h:]
        with np.errstate(divide="ignore", invalid="ignore"):
            ret_raw = np.log(close_end / close)
        bad = excl_any | ca_excl_bar | (~avail)
        up = direction > 0
        mfe = np.where(up, path_max, -path_min)
        mae = np.where(up, path_min, -path_max)
        t_mfe = np.where(up, t_max, t_min)
        t_mae = np.where(up, t_min, t_max)
        ret_signed = ret_raw * direction
        for arr, name in ((ret_signed, "ret"), (mfe, "mfe"), (mae, "mae"), (t_mfe, "tmfe"), (t_mae, "tmae")):
            a = arr.astype(float)
            a[bad] = np.nan
            out[f"h{h}_{name}"] = a

    # --- remainder-of-session (cumulative) and next-session (cumulative, superset of eos) ---
    sess_change = np.r_[True, session_date[1:] != session_date[:-1]]
    sess_id = np.cumsum(sess_change) - 1
    n_sess = sess_id[-1] + 1
    sess_start = np.searchsorted(sess_id, np.arange(n_sess))
    sess_end = np.searchsorted(sess_id, np.arange(n_sess), side="right")   # exclusive
    sess_excl = np.array([ca_excl_bar[sess_start[s]] for s in range(n_sess)])

    eos_ret = np.full(n, np.nan); eos_mfe = np.full(n, np.nan); eos_mae = np.full(n, np.nan)
    eos_tmfe = np.full(n, np.nan); eos_tmae = np.full(n, np.nan); eos_nbars = np.zeros(n, int)
    next_ret = np.full(n, np.nan); next_mfe = np.full(n, np.nan); next_mae = np.full(n, np.nan)
    next_tmfe = np.full(n, np.nan); next_tmae = np.full(n, np.nan); next_nbars = np.zeros(n, int)

    for s in range(n_sess):
        a, b = sess_start[s], sess_end[s]   # this session's [a, b)
        has_next = s + 1 < n_sess
        b_next = sess_end[s + 1] if has_next else None
        for i in range(a, b):
            c0 = close[i]
            # remainder of session: [i+1, b)
            if i + 1 < b:
                hi_rel = np.log(high[i + 1:b] / c0); lo_rel = np.log(low[i + 1:b] / c0)
                pmax, pmin = hi_rel.max(), lo_rel.min()
                tmax_, tmin_ = hi_rel.argmax() + 1, lo_rel.argmin() + 1
                ret_raw = np.log(close[b - 1] / c0)
                d_ = direction[i]
                if not sess_excl[s] and not np.isnan(d_):
                    eos_ret[i] = ret_raw * d_
                    eos_mfe[i] = pmax if d_ > 0 else -pmin
                    eos_mae[i] = pmin if d_ > 0 else -pmax
                    eos_tmfe[i] = tmax_ if d_ > 0 else tmin_
                    eos_tmae[i] = tmin_ if d_ > 0 else tmax_
                eos_nbars[i] = b - (i + 1)
            # next session (cumulative: remainder of this session + all of next session)
            if has_next:
                hi_rel = np.log(high[i + 1:b_next] / c0); lo_rel = np.log(low[i + 1:b_next] / c0)
                pmax, pmin = hi_rel.max(), lo_rel.min()
                tmax_, tmin_ = hi_rel.argmax() + 1, lo_rel.argmin() + 1
                ret_raw = np.log(close[b_next - 1] / c0)
                d_ = direction[i]
                if not sess_excl[s] and not sess_excl[s + 1] and not np.isnan(d_):
                    next_ret[i] = ret_raw * d_
                    next_mfe[i] = pmax if d_ > 0 else -pmin
                    next_mae[i] = pmin if d_ > 0 else -pmax
                    next_tmfe[i] = tmax_ if d_ > 0 else tmin_
                    next_tmae[i] = tmin_ if d_ > 0 else tmax_
                next_nbars[i] = b_next - (i + 1)

    out.update(eos_ret=eos_ret, eos_mfe=eos_mfe, eos_mae=eos_mae, eos_tmfe=eos_tmfe, eos_tmae=eos_tmae,
               eos_nbars=eos_nbars, next_ret=next_ret, next_mfe=next_mfe, next_mae=next_mae,
               next_tmfe=next_tmfe, next_tmae=next_tmae, next_nbars=next_nbars)

    df = pd.DataFrame(out)
    df = df[df.r.notna()]   # keep only qualifying events (a valid prior-bar return)
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
    out_path = HERE / f"panel_chunk_{chunk_idx}.pkl"
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
    full.to_pickle(HERE / "panel_full.pkl")
    print(f"panel_full.pkl: {len(full):,} rows, {full.ticker.nunique()} tickers", flush=True)


if __name__ == "__main__":
    main()
