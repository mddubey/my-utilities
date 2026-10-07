"""RQ-EMAPB-D1-EXIT -- hourly exit-timing sweep through D1 (2026-10-06).

Follow-up to RQ-EMAPB-3PM-01. User wants to see how the position actually moves hour by hour
through D1 (not just open vs close) to pick a candidate exit time -- D1 open, midday, or end of
day. This is purely descriptive: no exit RULE is being defined yet (that's the next, separate step
-- failure/invalidation), just the raw shape of the move at each fixed hourly checkpoint.

Same realistic entry clock as 21_rq_emapb_3pm_entry.py: entry = the 14:15 bar's Close on the day a
box_high break is first confirmed by 3pm (fully unfiltered population, no CLV/gap condition).

Usage: python3 swing_qs_emapb/24_rq_emapb_d1_exit_sweep.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_1H_DATE = pd.Timestamp("2023-10-23")
ENTRY_BAR_TIME = "14:15"
EXTENSION_OUTLIER_CUTOFF = 50
D1_BAR_TIMES = ["09:15", "10:15", "11:15", "12:15", "13:15", "14:15", "15:15"]


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
    d["bar_time"] = d.index.strftime("%H:%M")
    return d.reset_index(drop=True)


def load_daily(ticker):
    f = f"data/daily/{ticker}.csv"
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f)
    if d.empty:
        return None
    d["Date"] = pd.to_datetime(d.Date)
    return d.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)


def main():
    pop = pd.read_csv(f"{HERE}/rq_emapb08_joint.csv")
    pop_all = pop[(pop.outcome == "consolidation_resumption") &
                  (pd.to_datetime(pop.a_entry_date) >= MIN_1H_DATE)].copy()
    print(f"Fully unfiltered resumption population with 1H coverage: {len(pop_all):,}")

    rows = []
    cache_d, cache_h = {}, {}
    for n, r in enumerate(pop_all.itertuples()):
        daily = cache_d.setdefault(r.ticker, load_daily(r.ticker))
        h1 = cache_h.setdefault(r.ticker, load_60m(r.ticker))
        if daily is None or h1 is None:
            continue
        peak_date = pd.Timestamp(r.peak_date)
        pm = daily.index[daily.Date == peak_date]
        if len(pm) == 0 or pd.isna(r.consolidation_start_days):
            continue
        peak_i = int(pm[0]); consolidation_start_i = peak_i + int(r.consolidation_start_days)
        box_span_end = consolidation_start_i + 3
        if box_span_end >= len(daily):
            continue
        obs_start_date = daily.Date.iloc[box_span_end]
        box_high = r.box_high

        osm = h1.index[h1.session_date >= obs_start_date]
        if len(osm) == 0:
            continue
        search = h1.iloc[osm[0]:osm[0] + 300]
        search_upto3 = search[search.bar_time <= ENTRY_BAR_TIME]
        ci = search_upto3.index[search_upto3.Close > box_high]
        if len(ci) == 0:
            continue
        entry_day = h1.session_date.iloc[int(ci[0])]
        pm3 = h1.index[(h1.session_date == entry_day) & (h1.bar_time == ENTRY_BAR_TIME)]
        if len(pm3) == 0:
            continue
        entry_i = int(pm3[0])
        entry_price = h1.Close.iloc[entry_i]

        dm = daily.index[daily.Date == entry_day]
        if len(dm) == 0:
            continue
        iD = int(dm[0])
        if iD + 1 >= len(daily):
            continue
        d1_date = daily.Date.iloc[iD + 1]

        d1_bars = h1[h1.session_date == d1_date]
        if d1_bars.empty:
            continue
        d1_open = d1_bars.Open.iloc[0]

        row = dict(ticker=r.ticker, a_entry_date=r.a_entry_date, box_high=box_high,
                   entry_price=entry_price, d1_open_ret=(d1_open / entry_price - 1) * 100)
        for bt in D1_BAR_TIMES:
            bar = d1_bars[d1_bars.bar_time == bt]
            if not bar.empty:
                row[f"d1_{bt.replace(':', '')}_close_ret"] = (bar.Close.iloc[0] / entry_price - 1) * 100
        rows.append(row)
        if (n + 1) % 5000 == 0:
            print(f"  ...{n + 1:,}/{len(pop_all):,}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb_d1_exit_sweep.csv", index=False)
    already_run_pct = (df.entry_price / df.box_high - 1) * 100
    df = df[already_run_pct.abs() <= EXTENSION_OUTLIER_CUTOFF].copy()
    print(f"\nn={len(df):,} (after excluding corp-action artifacts)\n")

    print("=== Full population: return at each D1 checkpoint ===")
    print(f"{'checkpoint':<20}{'median':>10}{'mean':>10}{'%positive':>12}")
    print(f"{'D1 open':<20}{df.d1_open_ret.median():>9.2f}%{df.d1_open_ret.mean():>9.2f}%{(df.d1_open_ret>0).mean()*100:>11.1f}%")
    for bt in D1_BAR_TIMES:
        col = f"d1_{bt.replace(':', '')}_close_ret"
        if col in df.columns:
            s = df[col].dropna()
            print(f"{'D1 ' + bt + ' close':<20}{s.median():>9.2f}%{s.mean():>9.2f}%{(s>0).mean()*100:>11.1f}%")


if __name__ == "__main__":
    main()
