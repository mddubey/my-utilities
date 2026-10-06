"""RQ-EMAPB-02 -- critic-specified audit (2026-10-04). See RQ-EMAPB-02_SPEC.md for the full,
verbatim critic design. This script builds the event-level panel Tracks 1-8's tables are
computed from. Primary structural pipeline (Tracks 2-9) runs on the Fib 50% touch population
(explicit scope cut, flagged to the user/critic, not silent) -- Track 1 covers all four
retracement depths. D1 = the next full trading session after each anchor point (touch, end of
stabilization span, C1, C2), using real intraday 1H bars for D1 Open/Peak/Close, not the
coarser daily file. NO stop/exit optimization (Track 9's explicit guardrail).

Usage: python3 swing_qs_emapb/05_critic_audit.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOW_BARS = 70
SPAN_K = 3                    # stabilization span length, literature floor (3-5 bars)
RANGE_COMPRESSION_MULT = 0.5  # span width <= this x swing height
ATR_CONTRACTION_MULT = 0.75   # span avg bar range <= this x impulse avg bar range
VOL_CONTRACTION_MULT = 0.75   # span avg volume <= this x impulse avg volume
CONTAIN_TOL_MULT = 0.2        # span low can't undercut touch bar's low by more than this x impulse avg range
FIB_FRACS = {"fib382": 0.382, "fib50": 0.5, "fib618": 0.618}


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


def find_touch(rows, start, end, level):
    for k in range(start, end):
        row_k = rows.iloc[k]
        if row_k.Low <= level and row_k.Close >= level:
            return k
    return None


def d1_metrics(rows, anchor_i):
    """D1 = next full trading session after anchor_i's own session. Returns Open/Peak(High
    max)/Close/MAE(Low min), all relative to anchor's own Close, using real 1H bars."""
    if anchor_i is None or anchor_i >= len(rows):
        return None
    d0_date = rows.iloc[anchor_i].session_date
    c0 = rows.iloc[anchor_i].Close
    future_dates = rows.loc[rows.session_date > d0_date, "session_date"]
    if future_dates.empty:
        return None
    d1_date = future_dates.iloc[0]
    d1_bars = rows[rows.session_date == d1_date]
    if d1_bars.empty:
        return None
    return dict(
        d1_open_pct=(d1_bars.Open.iloc[0] / c0 - 1) * 100,
        d1_peak_pct=(d1_bars.High.max() / c0 - 1) * 100,
        d1_close_pct=(d1_bars.Close.iloc[-1] / c0 - 1) * 100,
        d1_mae_pct=(d1_bars.Low.min() / c0 - 1) * 100,
    )


def main():
    pop = pd.read_csv("swing_qs_bpc/rq_bpc05_a_volume_diagnostics.csv")
    pop = pop[(pop.entry_definition == 10) & (pop.vol_ratio >= 1.5) &
              (pop.a_entry_date >= "2023-10-23")]
    print(f"Population: {len(pop):,}", flush=True)

    out_rows = []
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
            swing_height = swing_high - swing_low
            impulse = rows.iloc[ia:peak_i + 1]
            impulse_avg_range = (impulse.High - impulse.Low).mean()
            impulse_avg_vol = impulse.Volume.mean()

            rec = dict(ticker=ticker, a_entry_date=r.a_entry_date, year=a_date.year,
                       swing_pct=(swing_high / swing_low - 1) * 100,
                       pullback_start_offset=pullback_start - ia)

            # --- Track 1: all four retracement depths, D1 metrics at the touch itself ---
            levels = dict(retest=swing_low)
            for name, frac in FIB_FRACS.items():
                levels[name] = swing_high - frac * (swing_high - swing_low)
            for name, level in levels.items():
                touch_i = find_touch(rows, pullback_start, end, level)
                rec[f"{name}_touched"] = touch_i is not None
                rec[f"{name}_offset"] = (touch_i - ia) if touch_i is not None else None
                if touch_i is not None:
                    m = d1_metrics(rows, touch_i)
                    if m:
                        for k, v in m.items():
                            rec[f"{name}_{k}"] = v

            # --- Tracks 2-9: full structural pipeline on Fib 50% only (scope cut, flagged) ---
            touch_i = find_touch(rows, pullback_start, end, levels["fib50"])
            if touch_i is None or touch_i + SPAN_K > end:
                out_rows.append(rec)
                continue
            span = rows.iloc[touch_i:touch_i + SPAN_K]
            span_width = span.High.max() - span.Low.min()
            span_high = span.High.max()
            span_avg_range = (span.High - span.Low).mean()
            span_avg_vol = span.Volume.mean()
            touch_low = rows.iloc[touch_i].Low

            range_compression = span_width <= RANGE_COMPRESSION_MULT * swing_height
            atr_contraction = span_avg_range <= ATR_CONTRACTION_MULT * impulse_avg_range
            vol_contraction = span_avg_vol <= VOL_CONTRACTION_MULT * impulse_avg_vol
            after_touch_low = rows.iloc[touch_i + 1:touch_i + SPAN_K].Low.min() if SPAN_K > 1 else touch_low
            contained = after_touch_low >= touch_low - CONTAIN_TOL_MULT * impulse_avg_range
            combined_base = range_compression and atr_contraction and vol_contraction
            is_B = range_compression and contained

            span_end = touch_i + SPAN_K - 1
            c1_i = None
            for k in range(span_end + 1, end):
                if rows.iloc[k].Close > rows.iloc[k].Open:
                    c1_i = k
                    break
            c2_i = None
            for k in range(span_end + 1, end):
                if rows.iloc[k].High > span_high:
                    c2_i = k
                    break
            is_C = is_B and (c2_i is not None)

            rec.update(dict(
                range_compression=range_compression, atr_contraction=atr_contraction,
                vol_contraction=vol_contraction, combined_base=combined_base, contained=contained,
                is_B_stabilized=is_B, is_C_resumed=is_C,
                touch_offset_f50=touch_i - ia, span_end_offset=span_end - ia,
                c1_offset=(c1_i - ia) if c1_i is not None else None,
                c2_offset=(c2_i - ia) if c2_i is not None else None,
            ))
            for label, anchor in [("c0", touch_i), ("spanend", span_end), ("c1", c1_i), ("c2", c2_i)]:
                m = d1_metrics(rows, anchor)
                if m:
                    for k, v in m.items():
                        rec[f"{label}_{k}"] = v

            out_rows.append(rec)

    df = pd.DataFrame(out_rows)
    df.to_csv(f"{HERE}/rq_emapb02_audit_panel.csv", index=False)
    print(f"\nSaved {len(df):,} rows -> rq_emapb02_audit_panel.csv", flush=True)
    print(f"fib50 touched: {df.fib50_touched.sum():,}")
    print(f"of those, span fits in window: {df.is_B_stabilized.notna().sum():,}")
    print(f"B (stabilized): {df.is_B_stabilized.sum():,} ({df.is_B_stabilized.mean()*100:.1f}%)")
    print(f"C (stabilized + structural resumption): {df.is_C_resumed.sum():,} ({df.is_C_resumed.mean()*100:.1f}%)")
    print(f"combined_base (all 3 components): {df.combined_base.mean()*100:.1f}%")
    print(f"range_compression alone: {df.range_compression.mean()*100:.1f}%  "
          f"atr_contraction alone: {df.atr_contraction.mean()*100:.1f}%  "
          f"vol_contraction alone: {df.vol_contraction.mean()*100:.1f}%")


if __name__ == "__main__":
    main()
