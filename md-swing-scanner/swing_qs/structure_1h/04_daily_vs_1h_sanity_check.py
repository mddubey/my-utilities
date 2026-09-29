"""Structural sanity check, per critic's revised recommendation (2026-09-28 late) --
NOT a backtest, NOT a threshold search. Purely visual: does the 1H chart make a QS
swing visibly/mechanically coherent, across BOTH winners and failures, compared side
by side against the same period's daily chart?

Sample: the 6 already-confirmed winners (fixed earlier) + 6 failures selected by an
objective, mechanical, disclosed rule (worst D5_close_r in the 96-trade replay pool) --
not eyeballed, to avoid selection-after-seeing-result bias. No metrics computed here,
no swing definition designed -- look, don't fit.
"""
import os
import sys

sys.path.insert(0, "/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner")
os.chdir("/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, "swing_qs/structure_1h")
from importlib.util import spec_from_file_location, module_from_spec
spec = spec_from_file_location("plot_examples", "swing_qs/structure_1h/02_plot_examples.py")
pe = module_from_spec(spec)
spec.loader.exec_module(pe)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS = "swing_qs/trajectory_replay/mvp_v1/events.csv"
TWO_AXES = "swing_qs/trajectory_replay/mvp_v1/two_axes_all_96.csv"
PRIOR_DAILY_BARS = 15


def draw_daily(ax, ticker, entry_date, trigger, title):
    daily = pd.read_csv(f"data_cache/{ticker}.csv", index_col="Date", parse_dates=True)
    window = daily[daily.index <= pd.Timestamp(entry_date)].tail(PRIOR_DAILY_BARS)
    x = range(len(window))
    for i, (_, b) in enumerate(window.iterrows()):
        color = "tab:green" if b.Close >= b.Open else "tab:red"
        ax.plot([i, i], [b.Low, b.High], color=color, linewidth=1)
        ax.plot([i, i], [b.Open, b.Close], color=color, linewidth=5, solid_capstyle="butt")
    ax.axhline(trigger, color="black", linestyle="--", linewidth=0.8)
    ax.set_xticks(list(x)[::3])
    ax.set_xticklabels([str(d.date())[5:] for d in window.index[::3]], fontsize=6, rotation=45)
    ax.set_title(title, fontsize=8)
    ax.tick_params(axis="y", labelsize=6)


def main():
    ev = pd.read_csv(EVENTS, parse_dates=["entry_date", "entry_timestamp"])
    ev["entry_timestamp"] = ev.entry_timestamp.dt.tz_convert(pe.TZ)
    ev = ev.merge(pd.read_csv(TWO_AXES)[["trade_id", "is_confirmed"]], on="trade_id")

    winners = ev[ev.is_confirmed].drop_duplicates(subset=["ticker", "entry_date"])
    failures_all = ev.drop_duplicates(subset=["ticker", "entry_date"]).nsmallest(6, "D5_close_r")
    examples = [dict(r, group="WINNER") for r in winners.to_dict("records")] + \
               [dict(r, group="FAILURE") for r in failures_all.to_dict("records")]

    fig, axes = plt.subplots(4, 6, figsize=(24, 13))
    for col, e in enumerate(examples):
        ax_daily, ax_1h = axes[0 if e["group"] == "WINNER" else 2, col % 6], \
                          axes[1 if e["group"] == "WINNER" else 3, col % 6]
        bars_1h = pe.window_for(e)
        title = f"[{e['group']}] {e['ticker']} {e['entry_date'].date()}"
        draw_daily(ax_daily, e["ticker"], e["entry_date"], e["entry_price"], title + " -- DAILY")
        pe.draw(ax_1h, bars_1h, e["entry_price"], title + " -- 1H")

    fig.suptitle("Daily (top of each pair) vs 1H (bottom) -- 6 WINNERS (rows 1-2), 6 FAILURES (rows 3-4)."
                 " Purely visual, no metrics computed.", fontsize=12)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/plot_daily_vs_1h_sanity.png", dpi=110)
    print(f"saved {OUT_DIR}/plot_daily_vs_1h_sanity.png")


if __name__ == "__main__":
    main()
