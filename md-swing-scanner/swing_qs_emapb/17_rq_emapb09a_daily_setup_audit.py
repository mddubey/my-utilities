"""RQ-EMAPB-09A -- Daily setup semantics audit, before any 1H resumption-trigger design
(critic-specified, 2026-10-06, following the WIPRO/CIPLA chart review -> ADX/O'Neil tests).

Descriptive only, on the CLV>=0.80 population that reaches a valid daily box
(outcome=='consolidation_resumption'):

A. TIMING + MECHANISM of the first qualifying resumption (Close > box_high, same trigger as
   RQ-09b): bucketed by bar position within its session (1st/2nd/3rd+), and whether it was a
   gap-open (session's Open already above box_high) or an intrabar close (price closed above
   box_high during the bar without having gapped above it at the open). These are explicitly
   NOT the same mechanism -- critic's caution.

B. VOLUME CHARACTER: compares breakout-day-volume/prior-day-volume against the existing
   breakout-day-volume/10-day-average gate -- descriptive question (do these select materially
   different populations), not a new threshold.

C. TREND CONTEXT, descriptive fields only, no gates: price vs EMA34, EMA34 slope, price vs
   SMA50/150/200.

Usage: python3 swing_qs_emapb/17_rq_emapb09a_daily_setup_audit.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_1H_DATE = pd.Timestamp("2023-10-23")


def load_60m(ticker):
    f = INTRADAY_60M_DIR / f"{ticker}.csv"
    if not f.exists():
        return None
    d = pd.read_csv(f, index_col=0)
    if d.empty:
        return None
    d.index = pd.to_datetime(d.index, utc=True).tz_convert("Asia/Kolkata")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    d = d.dropna(subset=["Close", "High", "Low", "Open"])
    d["session_date"] = d.index.normalize().tz_localize(None)
    return d.reset_index(drop=True)


def load_daily(ticker):
    f = f"data/daily/{ticker}.csv"
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f)
    if d.empty:
        return None
    d["Date"] = pd.to_datetime(d.Date)
    d = d.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)
    d["prev_day_vol"] = d.Volume.shift(1)
    return d


def main():
    pop = pd.read_csv(f"{HERE}/rq_emapb08_joint.csv")
    pop = pop[(pop.outcome == "consolidation_resumption") & (pop.clv >= 0.80) &
              (pd.to_datetime(pop.a_entry_date) >= MIN_1H_DATE)].copy()
    print(f"CLV>=0.80, valid daily box, 1H coverage: {len(pop):,}")

    rows = []
    cache_d, cache_h = {}, {}
    for n, r in enumerate(pop.itertuples()):
        daily = cache_d.setdefault(r.ticker, load_daily(r.ticker))
        h1 = cache_h.setdefault(r.ticker, load_60m(r.ticker))
        if daily is None or h1 is None:
            continue
        peak_date = pd.Timestamp(r.peak_date)
        pm = daily.index[daily.Date == peak_date]
        if len(pm) == 0 or pd.isna(r.resolution_days_from_peak):
            continue
        peak_i = int(pm[0]); resolution_i = peak_i + int(r.resolution_days_from_peak)
        if resolution_i >= len(daily):
            continue
        resolution_date = daily.Date.iloc[resolution_i]
        box_high = r.box_high

        # --- Part A: locate the exact 1H resolution bar, classify position + mechanism ---
        dsm = h1.index[h1.session_date >= resolution_date - pd.Timedelta(days=1)]
        if len(dsm) == 0:
            continue
        search = h1.iloc[dsm[0]:dsm[0] + 20]
        bi = search.index[search.Close > box_high]
        if len(bi) == 0:
            continue
        break_i = int(bi[0])
        break_session = h1.session_date.iloc[break_i]
        session_bars = h1[h1.session_date == break_session].reset_index(drop=True)
        bar_position = int((h1.iloc[:break_i + 1].session_date == break_session).sum())  # 1 = first bar
        is_gap_open = bool(h1.Open.iloc[break_i] > box_high)

        # --- Part B: volume character ---
        a_date = pd.Timestamp(r.a_entry_date)
        am = daily.index[daily.Date == a_date]
        vol_ratio_prevday = None
        if len(am):
            ia = int(am[0])
            if pd.notna(daily.prev_day_vol.iloc[ia]) and daily.prev_day_vol.iloc[ia] > 0:
                vol_ratio_prevday = daily.Volume.iloc[ia] / daily.prev_day_vol.iloc[ia]

        rows.append(dict(
            ticker=r.ticker, a_entry_date=r.a_entry_date, clv=r.clv,
            bar_position=min(bar_position, 4),  # cap at 4+ for bucketing
            is_gap_open=is_gap_open,
            vol_ratio_10day=r.a_vol_ratio, vol_ratio_prevday=vol_ratio_prevday,
        ))
        if (n + 1) % 2000 == 0:
            print(f"  ...{n+1}/{len(pop):,}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb09a_audit.csv", index=False)
    print(f"\nn processed: {len(df):,}\n")

    print("=== A. Timing: bar position of the first qualifying resumption within its session ===")
    label_map = {1: "1st bar", 2: "2nd bar", 3: "3rd bar", 4: "4th+ bar"}
    vc = df.bar_position.map(label_map).value_counts(normalize=True).mul(100).round(1)
    print(vc.reindex(["1st bar", "2nd bar", "3rd bar", "4th+ bar"]))

    print("\n=== A. Mechanism, split by bar position ===")
    for pos, label in label_map.items():
        sub = df[df.bar_position == pos]
        if sub.empty:
            continue
        print(f"  {label:10} (n={len(sub):5,}): gap-open={sub.is_gap_open.mean()*100:5.1f}%  "
              f"intrabar-close={(~sub.is_gap_open).mean()*100:5.1f}%")

    print("\n=== B. Volume character: 10-day-avg ratio vs prior-day ratio ===")
    vb = df[df.vol_ratio_prevday.notna()]
    print(f"n={len(vb):,}")
    print(f"correlation (Spearman): {vb.vol_ratio_10day.corr(vb.vol_ratio_prevday, method='spearman'):.3f}")
    print(f"median vol_ratio_10day: {vb.vol_ratio_10day.median():.2f}x")
    print(f"median vol_ratio_prevday: {vb.vol_ratio_prevday.median():.2f}x")
    print(f"% with vol_ratio_prevday < 1.2x (clears 10-day gate but NOT a real day-over-day jump): "
          f"{(vb.vol_ratio_prevday < 1.2).mean()*100:.1f}%")
    print(f"% with vol_ratio_prevday >= 1.5x (genuine day-over-day spike too): "
          f"{(vb.vol_ratio_prevday >= 1.5).mean()*100:.1f}%")

    print(f"\nWritten: {HERE}/rq_emapb09a_audit.csv")


if __name__ == "__main__":
    main()
