"""Stage A — eyeball step. 1H bars for the five sessions before each confirmed
example's breakout plus the entry-day bars closed before the breach, with the
trigger drawn. AEGISLOG (real trigger 2026-09-09, per RQ-QS-01) is drawn as the
explicitly illustrative sanity example it has always been — it is not one of the
96 and stays out of every inference table.

Look, don't fit: the question is only whether a common 1H setup is visible that
the daily bars hid. No rule is designed here.
"""
import os
import sys

sys.path.insert(0, "/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner")
os.chdir("/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from resample_1h import load_1h, TZ

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS = "swing_qs/trajectory_replay/mvp_v1/events.csv"
TWO_AXES = "swing_qs/trajectory_replay/mvp_v1/two_axes_all_96.csv"
PRIOR_SESSIONS = 5
TRIGGER_CLEARANCE = 1.005
AEGISLOG_DATE = pd.Timestamp("2026-09-09")


def aegislog_illustrative():
    daily = pd.read_csv("data_cache/AEGISLOG.csv", index_col="Date", parse_dates=True)
    prior10 = daily[daily.index < AEGISLOG_DATE].tail(10)
    trigger = prior10.High.max() * TRIGGER_CLEARANCE
    five = pd.read_csv("intraday_cache/AEGISLOG.csv", index_col=0, parse_dates=True).tz_convert(TZ)
    day = five[five.index.normalize() == AEGISLOG_DATE.tz_localize(TZ)]
    touch = day[day.High >= trigger]
    return dict(ticker="AEGISLOG (illustrative)", entry_date=AEGISLOG_DATE, entry_price=trigger,
                entry_timestamp=touch.index[0] if len(touch) else None)


def closed_before(bars, ts):
    is_stub = bars.index.strftime("%H:%M") == "15:15"
    close_ts = bars.index + pd.to_timedelta([15 if s else 60 for s in is_stub], unit="m")
    return bars[close_ts <= ts]


def window_for(e):
    h = load_1h(e["ticker"].split()[0])
    entry_session = e["entry_date"].date()
    prior = [s for s in sorted(h.session.unique()) if s < entry_session][-PRIOR_SESSIONS:]
    w = h[h.session.isin(prior + [entry_session])]
    return closed_before(w, e["entry_timestamp"]) if e["entry_timestamp"] is not None else w[w.session.isin(prior)]


def draw(ax, bars, trigger, title):
    x = range(len(bars))
    for i, (_, b) in enumerate(bars.iterrows()):
        color = "tab:green" if b.Close >= b.Open else "tab:red"
        ax.plot([i, i], [b.Low, b.High], color=color, linewidth=1)
        ax.plot([i, i], [b.Open, b.Close], color=color, linewidth=4, solid_capstyle="butt")
    ax.axhline(trigger, color="black", linestyle="--", linewidth=0.8)
    starts = [i for i in x if i == 0 or bars.session.iloc[i] != bars.session.iloc[i - 1]]
    for s in starts[1:]:
        ax.axvline(s - 0.5, color="grey", linewidth=0.5, alpha=0.6)
    ax.set_xticks(starts)
    ax.set_xticklabels([str(bars.session.iloc[s])[5:] for s in starts], fontsize=7)
    ax.set_title(title, fontsize=9)
    ax.tick_params(axis="y", labelsize=7)


def main():
    ev = pd.read_csv(EVENTS, parse_dates=["entry_date", "entry_timestamp"])
    ev["entry_timestamp"] = ev.entry_timestamp.dt.tz_convert(TZ)
    ev = ev.merge(pd.read_csv(TWO_AXES)[["trade_id", "is_confirmed"]], on="trade_id")
    six = ev[ev.is_confirmed].drop_duplicates(subset=["ticker", "entry_date"]).to_dict("records")
    examples = six + [aegislog_illustrative()]

    fig, axes = plt.subplots(2, 4, figsize=(18, 8))
    for ax, e in zip(axes.flat, examples):
        bars = window_for(e)
        title = f"{e['ticker']}  {e['entry_date'].date()}  breach {e['entry_timestamp'].strftime('%H:%M') if e['entry_timestamp'] is not None else 'n/a'}"
        draw(ax, bars, e["entry_price"], title)
    for ax in axes.flat[len(examples):]:
        ax.axis("off")
    fig.suptitle("1H bars: 5 sessions before breakout + entry-day bars closed before the breach (dashed = trigger)", fontsize=11)
    fig.tight_layout()
    fig.savefig(f"{OUT_DIR}/plot_confirmed_six_1h.png", dpi=110)
    print(f"saved {OUT_DIR}/plot_confirmed_six_1h.png")


if __name__ == "__main__":
    main()
