"""Paired visual comparison: A (top row of each pair) vs B/D3 (bottom row), for all
20 pairs, per critic's exact ask -- "does D3 actually produce a different trajectory,
visually/structurally." No metrics computed here, purely for looking at.
"""
import os, sys
sys.path.insert(0, "/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner")
os.chdir("/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from backtest import load
from pivots import daily_pivots
from breakout_failure_confirmation_cost import _load_intraday

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
N_FORWARD_DAYS = 5


def per_bar_trajectory(ticker, entry_date, entry_price, initial_risk_pct, entry_timestamp=None):
    """Same walk as mvp_v1/02_replay.py, but entry_timestamp can be supplied directly
    (for B, which enters at the next day's OPEN -- a known timestamp, not an
    intraday touch to search for)."""
    rows = load(ticker, daily_pivots).reset_index()
    i = rows.index[rows.Date == pd.Timestamp(entry_date)]
    if len(i) == 0:
        return None
    i = i[0]
    idf, naive_day = _load_intraday(ticker)
    if idf is None:
        return None
    entry_day = pd.Timestamp(entry_date)
    day0_bars = idf[naive_day == entry_day].sort_index()
    if len(day0_bars) == 0:
        return None
    if entry_timestamp is None:
        touch = day0_bars[day0_bars.High >= entry_price]
        if len(touch) == 0:
            return None
        entry_ts = touch.index[0]
    else:
        entry_ts = pd.Timestamp(entry_timestamp).tz_localize(day0_bars.index.tz) \
            if pd.Timestamp(entry_timestamp).tzinfo is None else pd.Timestamp(entry_timestamp)
        if entry_ts not in day0_bars.index:
            entry_ts = day0_bars.index[0]  # fall back to first bar of the day (market open)

    day_dates = [rows.iloc[i + k].Date for k in range(0, N_FORWARD_DAYS + 1) if i + k < len(rows)]
    per_bar = []
    for day_num, d in enumerate(day_dates):
        day_bars = idf[naive_day == d].sort_index()
        if day_num == 0:
            day_bars = day_bars[day_bars.index >= entry_ts]
        if len(day_bars) == 0:
            continue
        for ts, bar in day_bars.iterrows():
            close_r = (bar.Close / entry_price - 1) * 100 / initial_risk_pct
            per_bar.append(dict(timestamp=ts, close_r=close_r))
    if not per_bar:
        return None
    return pd.DataFrame(per_bar)


pairs = pd.read_csv(f"{OUT_DIR}/replay20_pairs.csv", parse_dates=["a_entry_date", "b_entry_date"])

fig, axes = plt.subplots(8, 5, figsize=(22, 20))
for col, tr in enumerate(pairs.itertuples()):
    a_risk = (tr.a_entry_price - tr.a_stop_price) / tr.a_entry_price * 100
    b_risk = (tr.b_entry_price - tr.b_stop_price) / tr.b_entry_price * 100
    a_bars = per_bar_trajectory(tr.ticker, tr.a_entry_date, tr.a_entry_price, a_risk)
    # B enters at the next day's OPEN (a known moment, not an intraday touch to search
    # for) -- pass a sentinel time earlier than market open so the fallback in
    # per_bar_trajectory correctly picks the day's first bar (09:15) as B's entry.
    b_bars = per_bar_trajectory(tr.ticker, tr.b_entry_date, tr.b_entry_price, b_risk,
                                 entry_timestamp="1900-01-01 00:00:00")

    row_a, row_b = (col // 5) * 2, (col // 5) * 2 + 1
    col_i = col % 5
    ax_a, ax_b = axes[row_a, col_i], axes[row_b, col_i]

    if a_bars is not None:
        seq = range(len(a_bars))
        ax_a.plot(seq, a_bars.close_r, color="steelblue", linewidth=1)
        ax_a.axhline(0, color="black", linewidth=0.4)
    ax_a.set_title(f"{tr.ticker} A {tr.a_entry_date.date()} ({tr.stratum})", fontsize=8)
    ax_a.tick_params(labelsize=6)

    if b_bars is not None:
        seq = range(len(b_bars))
        ax_b.plot(seq, b_bars.close_r, color="darkorange", linewidth=1)
        ax_b.axhline(0, color="black", linewidth=0.4)
    ax_b.set_title(f"{tr.ticker} B/D3 {tr.b_entry_date.date()} (+{int(tr.d3_days_after_a)}d)", fontsize=8)
    ax_b.tick_params(labelsize=6)

fig.suptitle("QS-A (blue, top of each pair) vs QS-B/D3 (orange, bottom) -- 20 pairs, same tickers", fontsize=13)
fig.tight_layout()
fig.savefig(f"{OUT_DIR}/plot_20_vs_20.png", dpi=110)
print(f"Saved {OUT_DIR}/plot_20_vs_20.png")
