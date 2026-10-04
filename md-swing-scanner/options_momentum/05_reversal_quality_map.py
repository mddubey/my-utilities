"""RQ-OMD-02 step 2 -- the reversal-quality report: retracement depth/speed by magnitude
bucket x origin (intraday vs overnight) x direction, the F&O-unusual-vs-F&O-normal comparison
the critic flagged as missing from OMD-01, robustness across calendar-matched window pairs,
year-by-year check. Usage: python3 options_momentum/05_reversal_quality_map.py
Output: prints every table; also writes reversal_quality_output.txt.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
pd.set_option("display.width", 160)

BUCKET_ORDER = ["dn_unusual", "dn_elevated", "dn_normal", "up_normal", "up_elevated", "up_unusual"]
RETR_PCTS = (25, 50, 75, 100)


def retracement_table(df, bucket_col, label):
    rows = []
    for b in BUCKET_ORDER:
        sub = df[df[bucket_col] == b]
        n_elig = sub.next_mfe.notna().sum()   # rows where the next-session window exists at all
        if n_elig < 100:
            continue
        row = dict(group=label, bucket=b, n=n_elig)
        for pct in RETR_PCTS:
            reached = sub[f"reached{pct}"]
            row[f"reached{pct}_pct"] = reached[sub.next_mfe.notna()].mean()
            t = sub[f"t_retr{pct}"].dropna()
            row[f"median_t{pct}"] = t.median() if len(t) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def pre_reversal_table(df, bucket_col, label):
    """Among cases where pre-reversal continuation is actually measurable (t_retr25 > 1, i.e.
    the 25% checkpoint wasn't crossed in the very first forward bar)."""
    rows = []
    for b in BUCKET_ORDER:
        sub = df[(df[bucket_col] == b) & (df.t_retr25 > 1)]
        if len(sub) < 50:
            continue
        rows.append(dict(group=label, bucket=b, n=len(sub),
                          median_pre_reversal_mfe=sub.pre_reversal_mfe.median(),
                          share_of_eligible=len(sub) / max(1, (df[bucket_col] == b).sum())))
    return pd.DataFrame(rows)


def main():
    lines = []
    def p(s=""):
        print(s)
        lines.append(str(s))

    df = pd.read_pickle(HERE / "reversal_panel_full.pkl")
    intraday = df[df.origin == "intraday"].copy()
    overnight = df[df.origin == "overnight"].copy()

    p(f"=== RQ-OMD-02 reversal quality map -- {pd.Timestamp.now():%Y-%m-%d %H:%M} ===")
    p(f"Panel: {len(df):,} rows, {df.ticker.nunique()} tickers, {df.session_date.min().date()} -> "
      f"{df.session_date.max().date()}")
    p(f"intraday-originated: {len(intraday):,}  |  overnight-originated: {len(overnight):,}")

    # --- Table 1: retracement depth/speed by bucket x origin, primary windows ---
    p("\n--- Table 1: retracement checkpoint reach-rate and median time-to-reach, by bucket x origin ---")
    p("(primary windows: intraday z=1512 bars ~1y, gap z=252 sessions ~1y -- calendar-matched)")
    t1a = retracement_table(intraday, "bucket_intraday_1512", "intraday")
    t1b = retracement_table(overnight, "bucket_gap_252", "overnight")
    t1 = pd.concat([t1a, t1b], ignore_index=True)
    cols = ["group", "bucket", "n"] + [f"{m}{pct}" for pct in RETR_PCTS for m in ("reached", "median_t")]
    cols = ["group", "bucket", "n"] + [c for pct in RETR_PCTS for c in (f"reached{pct}_pct", f"median_t{pct}")]
    p(t1[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # --- Table 2: pre-reversal max continuation, conditional on being measurable ---
    p("\n--- Table 2: pre-reversal max continuation (median, log-return units), where measurable ---")
    p("(excludes the ~79% of cases where the 25% checkpoint is crossed in the very first forward")
    p(" bar -- there, 'continuation before reversal' isn't computable from 1H OHLC; reported as")
    p(" its own share below, not silently dropped)")
    t2a = pre_reversal_table(intraday, "bucket_intraday_1512", "intraday")
    t2b = pre_reversal_table(overnight, "bucket_gap_252", "overnight")
    t2 = pd.concat([t2a, t2b], ignore_index=True)
    p(t2.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # --- Table 3: robustness across calendar-matched window pairs, unusual buckets only ---
    p("\n--- Table 3: robustness -- unusual buckets, across calendar-matched window pairs ---")
    for w_i, w_g, label in [(504, 84, "~4mo"), (1512, 252, "~1y (primary)"), (3024, 504, "~2y")]:
        sub_i = retracement_table(intraday, f"bucket_intraday_{w_i}", f"intraday W={w_i}")
        sub_i = sub_i[sub_i.bucket.isin(["dn_unusual", "up_unusual"])]
        sub_g = retracement_table(overnight, f"bucket_gap_{w_g}", f"overnight W={w_g}")
        sub_g = sub_g[sub_g.bucket.isin(["dn_unusual", "up_unusual"])]
        both = pd.concat([sub_i, sub_g], ignore_index=True)
        p(f"[{label}]")
        p(both[["group", "bucket", "n", "reached50_pct", "median_t50", "reached100_pct", "median_t100"]]
          .to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # --- Table 4: THE critical missing comparison -- F&O-unusual vs F&O-normal (within F&O only) ---
    p("\n--- Table 4: F&O-unusual vs F&O-normal (within F&O only) -- the comparison OMD-01's Table 6 lacked ---")
    fo_intraday = intraday[intraday.is_fo]
    t4 = retracement_table(fo_intraday, "bucket_intraday_1512", "F&O intraday")
    p(t4[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    p("\nFor comparison, non-F&O intraday (same cut):")
    t4b = retracement_table(intraday[~intraday.is_fo], "bucket_intraday_1512", "non-F&O intraday")
    p(t4b[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # --- Table 5: year-by-year, unusual buckets, intraday ---
    p("\n--- Table 5: year-by-year retracement speed, unusual buckets, intraday-originated ---")
    intraday["year"] = intraday.session_date.dt.year
    rows = []
    for yr in sorted(intraday.year.unique()):
        sub = intraday[(intraday.year == yr) & intraday.bucket_intraday_1512.isin(["dn_unusual", "up_unusual"])]
        t = retracement_table(sub, "bucket_intraday_1512", str(yr))
        rows.append(t)
    p(pd.concat(rows, ignore_index=True)[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    (HERE / "reversal_quality_output.txt").write_text("\n".join(lines) + "\n")
    p(f"\n[written to {HERE / 'reversal_quality_output.txt'}]")


if __name__ == "__main__":
    main()
