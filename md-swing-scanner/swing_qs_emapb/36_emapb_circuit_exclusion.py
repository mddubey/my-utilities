"""EMAPB circuit-run exclusion (2026-10-11). Chart audit on INDOTHAI (v2 pipeline sample) found
the "advance" was actually a near-continuous series of NSE upper-circuit hits (>15 separate days
closing within ~5% of a circuit tier across a 6-week run) -- not organic price discovery. A
"biggest single day" trigger is meaningless when many days are tied at the same circuit ceiling,
and real two-sided liquidity is doubtful during a circuit lock even when reported volume looks
large. User's framing: this is news/mania-driven, not the breakout-continuation mechanism EMAPB is
meant to capture.

Rule (pre-declared, hand-verified before adoption per Rule #22): a day is flagged `is_circuit` if
its close-to-close day_gain_pct is within 0.3 percentage points of 5%, 10%, or 20% (the standard
NSE equity circuit tiers). An episode is EXCLUDED if the fraction of circuit days within its
swing-low-to-peak advance window is >= 0.3 (roughly a third or more of the advance's days pinned at
a circuit ceiling).

Usage: python3 swing_qs_emapb/36_emapb_circuit_exclusion.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CIRCUIT_TIERS = [5, 10, 20]
TOL = 0.3
EXCLUDE_FRAC_THRESHOLD = 0.3


def main():
    bo = pd.read_csv(f"{HERE}/rq_emapb_v2_episodes.csv")
    bo = bo[bo.outcome == "breakout"].copy()

    cache, rows = {}, []
    for r in bo.itertuples():
        daily = cache.get(r.ticker)
        if daily is None:
            f = f"data/daily/{r.ticker}.csv"
            if not os.path.exists(f):
                cache[r.ticker] = None
                continue
            daily = pd.read_csv(f)
            daily["Date"] = pd.to_datetime(daily.Date)
            daily = daily.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)
            daily["day_gain_pct"] = (daily.Close / daily.Close.shift(1) - 1) * 100
            cache[r.ticker] = daily
        if daily is None:
            continue
        sl, pk = pd.Timestamp(r.swing_low_date), pd.Timestamp(r.peak_date)
        window = daily[(daily.Date >= sl) & (daily.Date <= pk)]
        if window.empty:
            continue
        is_circuit = window.day_gain_pct.apply(
            lambda g: any(abs(g - t) < TOL for t in CIRCUIT_TIERS) if pd.notna(g) else False)
        n_circuit = is_circuit.sum()
        rows.append(dict(ticker=r.ticker, breakout_date=r.breakout_date, window_len=len(window),
                          n_circuit=n_circuit, frac_circuit=n_circuit / len(window),
                          track_b_d1_ret=r.track_b_d1_ret))

    df = pd.DataFrame(rows)
    df["excluded"] = df.frac_circuit >= EXCLUDE_FRAC_THRESHOLD
    df.to_csv(f"{HERE}/rq_emapb_circuit_check.csv", index=False)

    print(f"n breakout episodes checked: {len(df):,}")
    print(f"excluded as circuit-driven (frac_circuit >= {EXCLUDE_FRAC_THRESHOLD}): "
          f"{df.excluded.sum():,} ({df.excluded.mean()*100:.1f}%)")
    clean = df[~df.excluded]
    print(f"\nTrack B, circuit-cleaned (n={len(clean):,}), descriptive only:")
    print(f"median={clean.track_b_d1_ret.median():+.2f}%  pct_positive={(clean.track_b_d1_ret>0).mean()*100:.1f}%")


if __name__ == "__main__":
    main()
