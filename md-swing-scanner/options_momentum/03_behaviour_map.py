"""RQ-OMD-01 step 3 -- the actual behaviour map: distributions by stock-relative magnitude
bucket x horizon, A/B/C/D classification shares, timing structure, robustness across the
three pre-declared z-windows, gap-bar split, F&O split, year-by-year check. All thresholds
and horizons are the ones frozen in RQ-OMD-01_PREFLIGHT.md before this script was written --
nothing here is tuned to the result. Usage: python3 options_momentum/03_behaviour_map.py
Output: prints every table; also writes behaviour_map_output.txt.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
pd.set_option("display.width", 160)

BUCKET_ORDER = ["dn_unusual", "dn_elevated", "dn_normal", "up_normal", "up_elevated", "up_unusual"]
HORIZONS = ["h1", "h2", "h3", "eos", "next"]
HLABEL = {"h1": "1H", "h2": "2H", "h3": "3H", "eos": "rest-of-session", "next": "next session"}


def summarize(df, bucket_col, horizons=HORIZONS, min_n=200):
    rows = []
    for b in BUCKET_ORDER:
        sub = df[df[bucket_col] == b]
        for h in horizons:
            ret = sub[f"{h}_ret"].dropna()
            mfe = sub[f"{h}_mfe"].dropna()
            mae = sub[f"{h}_mae"].dropna()
            n = len(ret)
            if n < min_n:
                rows.append(dict(bucket=b, horizon=HLABEL[h], n=n, median_ret=np.nan, mean_ret=np.nan,
                                  pct_positive=np.nan, median_mfe=np.nan, median_mae=np.nan))
                continue
            rows.append(dict(bucket=b, horizon=HLABEL[h], n=n, median_ret=ret.median(), mean_ret=ret.mean(),
                              pct_positive=(ret > 0).mean(), median_mfe=mfe.median(), median_mae=mae.median()))
    return pd.DataFrame(rows)


def classify_abcd(df):
    """A/B/C/D per RQ-OMD-01_PREFLIGHT.md: immediate = 2H cumulative window, delayed = best of
    rest-of-session / next-session. Single pre-declared threshold = 0.5x |r_T| everywhere."""
    r_abs = df["abs_r"]
    ret2, mae2 = df["h2_ret"], df["h2_mae"]
    ret_eos, ret_next = df["eos_ret"], df["next_ret"]
    retention2 = ret2 / r_abs
    mae2_ok = mae2 >= -0.5 * r_abs   # didn't give back more than half the move before any continuation
    is_A = (retention2 >= 0.5) & mae2_ok
    is_B = retention2 <= -0.5
    delayed_retention = pd.concat([ret_eos / r_abs, ret_next / r_abs], axis=1).max(axis=1, skipna=True)
    has_delayed = delayed_retention.notna()
    is_D = (~is_A) & (~is_B) & has_delayed & (delayed_retention >= 0.5)
    is_C = (~is_A) & (~is_B) & (~is_D)
    label = np.select([is_A, is_B, is_D, is_C], ["A_immediate_continuation", "B_immediate_reversal",
                       "D_delayed_continuation", "C_stall"], default="censored_no_2H_data")
    label = np.where(retention2.isna(), "censored_no_2H_data", label)
    # flag stalls where we simply never got delayed-window data (right-censored, not a real stall)
    censored_stall = is_C & ~has_delayed
    return pd.Series(label, index=df.index), pd.Series(censored_stall, index=df.index)


def main():
    lines = []
    def p(s=""):
        print(s)
        lines.append(str(s))

    df = pd.read_pickle(HERE / "panel_full.pkl")
    intraday = df[~df.is_gap].copy()
    gap = df[df.is_gap].copy()

    p(f"=== RQ-OMD-01 behaviour map -- {pd.Timestamp.now():%Y-%m-%d %H:%M} ===")
    p(f"Panel: {len(df):,} rows, {df.ticker.nunique()} tickers, {df.session_date.min().date()} -> "
      f"{df.session_date.max().date()}")
    p(f"Intraday-bar events: {len(intraday):,}  |  gap-bar events: {len(gap):,}  "
      f"({len(gap)/len(df):.1%})")
    p(f"F&O share of tickers in panel: {df.groupby('ticker').is_fo.first().mean():.1%} "
      f"(current F&O list, reporting split only, not a filter)")

    # --- 1. headline table: all 6 buckets x all horizons, primary window W=1512 ---
    p("\n--- Table 1: forward behaviour by stock-relative magnitude bucket (W=1512, intraday bars only) ---")
    t1 = summarize(intraday, "bucket_1512")
    p(t1.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # --- 2. robustness: unusual buckets only, across W=504 / 1512 / 3024 ---
    p("\n--- Table 2: robustness check -- 'unusual' buckets only, across the 3 pre-declared windows ---")
    for W in (504, 1512, 3024):
        sub = summarize(intraday, f"bucket_{W}", horizons=["h2", "eos", "next"])
        sub = sub[sub.bucket.isin(["dn_unusual", "up_unusual"])]
        sub.insert(0, "W", W)
        p(sub.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # --- 3. A/B/C/D classification shares by bucket (W=1512) ---
    p("\n--- Table 3: A/B/C/D shares by bucket (W=1512, primary) ---")
    label, censored = classify_abcd(intraday)
    intraday = intraday.assign(abcd=label, censored_stall=censored)
    tab = (intraday[intraday.bucket_1512.notna()]
           .groupby("bucket_1512").abcd.value_counts(normalize=True).unstack(fill_value=0))
    tab = tab.reindex(BUCKET_ORDER)
    counts = intraday[intraday.bucket_1512.notna()].groupby("bucket_1512").size().reindex(BUCKET_ORDER)
    tab.insert(0, "n", counts)
    p(tab.to_string(float_format=lambda x: f"{x:.3f}" if x < 1 else f"{x:.0f}"))
    censor_rate = (intraday[intraday.bucket_1512.notna() & (intraday.abcd == "C_stall")]
                   .groupby("bucket_1512").censored_stall.mean().reindex(BUCKET_ORDER))
    p("\nShare of each bucket's 'C_stall' rows that are actually right-censored (no delayed-window "
      "data yet, i.e. near the end of the dataset) rather than a genuine stall:")
    p(censor_rate.to_string(float_format=lambda x: f"{x:.3f}"))

    # --- 4. timing structure: within A/D (continuation types), time-to-MFE and MAE-before-continuation ---
    p("\n--- Table 4: timing structure within continuation outcomes (W=1512 bucket, unusual only) ---")
    foc = intraday[intraday.bucket_1512.isin(["dn_unusual", "up_unusual"])]
    for outcome in ["A_immediate_continuation", "B_immediate_reversal", "C_stall", "D_delayed_continuation"]:
        sub = foc[foc.abcd == outcome]
        if len(sub) < 50:
            continue
        p(f"{outcome}: n={len(sub):,}  median t_mfe(next-session window, bars)={sub.next_tmfe.median():.1f}  "
          f"median MAE(next-session window)={sub.next_mae.median():.4f}  "
          f"median |r_T| (initial move size)={sub.abs_r.median():.4f}")

    # --- 5. gap-bar descriptive split (no z-bucketing, per preflight's narrowed scope) ---
    p("\n--- Table 5: gap-bar (overnight + first-hour) descriptive split, up-gap vs down-gap ---")
    gap_dir = gap.assign(gdir=np.where(gap.r > 0, "gap_up", "gap_down"))
    grows = []
    for gd in ["gap_up", "gap_down"]:
        sub = gap_dir[gap_dir.gdir == gd]
        for h in HORIZONS:
            ret = sub[f"{h}_ret"].dropna()
            if len(ret) < 200:
                continue
            grows.append(dict(gap=gd, horizon=HLABEL[h], n=len(ret), median_ret=ret.median(),
                               pct_positive=(ret > 0).mean()))
    p(pd.DataFrame(grows).to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # --- 6. F&O vs non-F&O split, unusual buckets, ABCD shares ---
    p("\n--- Table 6: F&O vs non-F&O split -- ABCD shares, unusual buckets only (W=1512) ---")
    foc2 = intraday[intraday.bucket_1512.isin(["dn_unusual", "up_unusual"])]
    tab2 = foc2.groupby(["is_fo", "bucket_1512"]).abcd.value_counts(normalize=True).unstack(fill_value=0)
    n2 = foc2.groupby(["is_fo", "bucket_1512"]).size()
    tab2.insert(0, "n", n2)
    p(tab2.to_string(float_format=lambda x: f"{x:.3f}" if x < 1 else f"{x:.0f}"))

    # --- 7. year-by-year check, unusual buckets, ABCD shares (never pool years) ---
    p("\n--- Table 7: year-by-year ABCD shares, unusual buckets only (W=1512) -- check regime stability ---")
    foc3 = intraday[intraday.bucket_1512.isin(["dn_unusual", "up_unusual"])].copy()
    foc3["year"] = foc3.session_date.dt.year
    tab3 = foc3.groupby(["year", "bucket_1512"]).abcd.value_counts(normalize=True).unstack(fill_value=0)
    n3 = foc3.groupby(["year", "bucket_1512"]).size()
    tab3.insert(0, "n", n3)
    p(tab3.to_string(float_format=lambda x: f"{x:.3f}" if x < 1 else f"{x:.0f}"))

    (HERE / "behaviour_map_output.txt").write_text("\n".join(lines) + "\n")
    p(f"\n[written to {HERE / 'behaviour_map_output.txt'}]")


if __name__ == "__main__":
    main()
