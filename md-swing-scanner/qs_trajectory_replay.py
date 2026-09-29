"""QS Trajectory Replay v0.1 (2026-09-28) — observational only, per critic's exact spec.

NOT a classifier, NOT a filter, NOT an exit rule. For a given real trade (ticker,
entry_date, entry_price, stop_price — all supplied by hand, this script invents
nothing), reconstructs a day-by-day trajectory (always available, 5 years of daily
bars) and, for any day that falls inside the intraday cache window (~2026-06-10 to
2026-09-23), a 5-minute event timeline showing WHEN key R-thresholds were first
crossed and when the day's high/low actually happened — precise timing the daily
bars alone can't show.

Entry universe stays the daily bars (Rule #18) — this tool never redefines entry,
it only replays what already happened to a trade you're telling it about. No
thresholds are optimized here; this is the "Observe" step, not "Measure/Decide".
"""
import sys
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')

import pandas as pd

from backtest import load
from pivots import daily_pivots
from breakout_failure_confirmation_cost import _load_intraday

MAX_REPLAY_DAYS = 15
R_EVENTS = [0.25, 0.5, 1.0, 1.5, 2.0]


def _day_descriptors(rows, i, prev_close_i):
    """Day-level descriptors — raw price/% alongside R, not R-only, per critic's
    explicit guardrail against re-deriving the same R-only framework."""
    row = rows.iloc[i]
    prev = rows.iloc[i - 1]
    higher_high = row.High > prev.High
    lower_low = row.Low < prev.Low
    overlap = (row.Low <= prev.High) and (row.High >= prev.Low)
    close_vs_prev_close_pct = (row.Close / prev_close_i - 1) * 100
    rng = row.High - row.Low
    close_location = ((row.Close - row.Low) / rng) if rng else None
    return dict(
        higher_high=higher_high, lower_low=lower_low, overlaps_prior_range=overlap,
        close_vs_prev_close_pct=round(close_vs_prev_close_pct, 2),
        close_location=round(close_location, 2) if close_location is not None else None,
    )


def _intraday_event_timeline(ticker, date, entry_price, initial_risk_pct):
    """5-min event timeline for ONE day, if cached. Returns None if not available.
    Detects first-touch time for each R_EVENTS threshold plus the day's actual
    high/low timestamps — the precision daily bars can't give."""
    idf, naive_day = _load_intraday(ticker)
    if idf is None:
        return None
    day_bars = idf[naive_day == pd.Timestamp(date)].sort_index()
    if len(day_bars) < 3:
        return None

    events = []
    seen = set()
    running_high, running_high_time = -float("inf"), None
    running_low, running_low_time = float("inf"), None
    for ts, bar in day_bars.iterrows():
        high_r = (bar.High / entry_price - 1) * 100 / initial_risk_pct
        low_r = (bar.Low / entry_price - 1) * 100 / initial_risk_pct
        if bar.High > running_high:
            running_high, running_high_time = bar.High, ts
        if bar.Low < running_low:
            running_low, running_low_time = bar.Low, ts
        for thresh in R_EVENTS:
            if thresh not in seen and high_r >= thresh:
                events.append((ts.strftime("%H:%M"), f"first touch +{thresh}R", round(high_r, 2)))
                seen.add(thresh)
    events.append((running_high_time.strftime("%H:%M"), "day's High", round(
        (running_high / entry_price - 1) * 100 / initial_risk_pct, 2)))
    events.append((running_low_time.strftime("%H:%M"), "day's Low", round(
        (running_low / entry_price - 1) * 100 / initial_risk_pct, 2)))
    events.sort(key=lambda e: e[0])
    return events


def replay(ticker, entry_date, entry_price, stop_price, entry_time=None, max_days=MAX_REPLAY_DAYS):
    """entry_time (e.g. "09:29"), if given, checks the ENTRY DAY itself for an
    intraday stop breach AFTER that moment — the real-world blind spot this tool
    would otherwise share with the production model's own EOD-only check (see
    trade_journal.csv's JSWINFRA note: real broker SL fired intraday same-day,
    the model's close-based check never got to evaluate it at all)."""
    entry_date = pd.Timestamp(entry_date)
    initial_risk_pct = (entry_price - stop_price) / entry_price * 100
    rows = load(ticker, daily_pivots).reset_index()
    m = rows.index[rows.Date == entry_date]
    if len(m) == 0:
        print(f"{ticker}: entry_date {entry_date.date()} not found in cached daily bars.")
        return
    i0 = m[0]

    print(f"\n{'='*100}\n{ticker} — entry {entry_date.date()} @ ₹{entry_price}  "
          f"stop ₹{stop_price}  (risk {initial_risk_pct:.2f}%)\n{'='*100}")

    if entry_time is not None:
        idf, naive_day = _load_intraday(ticker)
        if idf is not None:
            day_bars = idf[naive_day == entry_date].sort_index()
            after_entry = day_bars[day_bars.index.time >= pd.Timestamp(entry_time).time()]
            if len(after_entry) > 0:
                min_low = after_entry.Low.min()
                min_low_time = after_entry.Low.idxmin().strftime("%H:%M")
                low_r = (min_low / entry_price - 1) * 100 / initial_risk_pct
                print(f"D0 ({entry_date.date()}, from {entry_time} entry): "
                      f"lowest print after entry ₹{min_low:.2f} ({low_r:+.2f}R) at {min_low_time}")
                if low_r <= -1.0:
                    print(f"    *** SAME-DAY stop (-1R) breach — the production model's own "
                          f"EOD-only check would have missed this entirely ***\n")
                    return
            else:
                print(f"D0: no intraday bars after {entry_time} for {entry_date.date()}.")

    prev_close = entry_price
    for day_idx, i in enumerate(range(i0 + 1, min(i0 + 1 + max_days, len(rows))), start=1):
        row = rows.iloc[i]
        if row.corp_action_day:
            print(f"D{day_idx}: corp action day, stopping replay here.")
            break
        close_r = (row.Close / entry_price - 1) * 100 / initial_risk_pct
        high_r = (row.High / entry_price - 1) * 100 / initial_risk_pct
        low_r = (row.Low / entry_price - 1) * 100 / initial_risk_pct
        desc = _day_descriptors(rows, i, prev_close)
        prev_close = row.Close

        flags = []
        if desc["higher_high"]:
            flags.append("HH")
        if desc["lower_low"]:
            flags.append("LL")
        if desc["overlaps_prior_range"]:
            flags.append("overlap")
        flag_str = ",".join(flags) if flags else "-"

        print(f"\nD{day_idx} ({row.Date.date()}): Close ₹{row.Close:.2f} ({close_r:+.2f}R)  "
              f"High ₹{row.High:.2f} ({high_r:+.2f}R)  Low ₹{row.Low:.2f} ({low_r:+.2f}R)  "
              f"vs-prev-close {desc['close_vs_prev_close_pct']:+.2f}%  close_loc={desc['close_location']}  [{flag_str}]")

        timeline = _intraday_event_timeline(ticker, row.Date, entry_price, initial_risk_pct)
        if timeline:
            for t, label, r in timeline:
                print(f"    {t}  {label:<18} ({r:+.2f}R)")
        if low_r <= -1.0:
            print(f"    *** stop (-1R) breached this day ***")
            break

    print()


if __name__ == "__main__":
    # Sanity-check set: real trades from trade_journal.csv, spanning the intraday window
    replay("AEGISLOG", "2026-09-16", entry_price=1376.0, stop_price=1265.92)
    replay("MAXHEALTH", "2026-09-21", entry_price=1063.70, stop_price=1063.70 * 0.95)
    replay("DIVISLAB", "2026-09-08", entry_price=9500.50, stop_price=9500.50 * 0.95)
    replay("VIJAYA", "2026-09-09", entry_price=1525.0, stop_price=1384.83)
    replay("JSWINFRA", "2026-09-15", entry_price=344.5, stop_price=326.75, entry_time="09:29")
