"""RQ-TA Family E -- once the trigger is touched, does the stock get enough FOLLOW-ON
buying to continue price discovery, or does participation simply fail to show up?
Distinct question from Family D (was there activity without progress) -- here the focus
is the shape of the bars immediately after the touch bar closes, not the touch bar
itself. Same population/outcome join as 03/04/05.

Features (next bar = the bar immediately after the touch bar; next3 = the 3 bars after):
- next_bar_ret_atr: (Close[t+1] - Close[t]) / ATR
- next_bar_clv: close-location-value of bar t+1, (Close-Low)/(High-Low) -- how strong it
  closed within its own range (0 = closed at the low, 1 = closed at the high)
- excursion3_atr: (max(High, bars t+1..t+3) - trigger) / ATR -- best price reached in the
  15 min after the touch bar closes
- successive_highs: how many of the next 3 bars make a new High vs the bar before it
  (0-3) -- a plain continuation count, not a composite
- held30: RQ-PB-2's own convention (02_intraday_features.py) -- every 5-min Close in the
  next 30 min stays >= trigger*0.998. Recomputed fresh here for this population.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PB = ROOT / "pre_breach"
sys.path.insert(0, str(ROOT))

from data.paths import INTRADAY_5M_DIR  # noqa: E402

WINDOW_LO, WINDOW_HI = pd.Timestamp("2026-06-10"), pd.Timestamp("2026-09-29")


def load_5m(ticker):
    p = INTRADAY_5M_DIR / f"{ticker}.csv"
    if not p.exists():
        return None
    d = pd.read_csv(p)
    d["dt"] = pd.to_datetime(d.Datetime, utc=True).dt.tz_convert("Asia/Kolkata")
    d["day"] = d.dt.dt.normalize().dt.tz_localize(None)
    return d


def main():
    panel = pd.read_csv(PB / "panel.csv", parse_dates=["date"])
    panel = panel[(panel.touched) & (~panel.gap_through) &
                  (panel.date >= WINDOW_LO) & (panel.date <= WINDOW_HI)]
    outcomes = pd.read_pickle(PB / "rq_pb2" / "pivot_feats.pkl")[
        ["ticker", "date", "cls", "r5", "atr_abs"]
    ].drop_duplicates(["ticker", "date"])
    panel = panel.merge(outcomes[["ticker", "date", "atr_abs"]], on=["ticker", "date"], how="inner")

    rows = []
    for tk, g in panel.groupby("ticker"):
        bars = load_5m(tk)
        if bars is None:
            continue
        by_day = {k: gg.reset_index(drop=True) for k, gg in bars.groupby("day")}
        for r in g.itertuples():
            day = by_day.get(r.date)
            if day is None or len(day) < 10 or not r.atr_abs:
                continue
            atr = r.atr_abs
            touch_idx = day.index[day.High >= r.trigger]
            if len(touch_idx) == 0:
                continue
            t_i = int(touch_idx[0])
            if t_i + 1 >= len(day):
                continue
            touch_close = day.Close.iloc[t_i]
            nxt = day.iloc[t_i + 1]
            rng = nxt.High - nxt.Low
            next_bar_ret_atr = (nxt.Close - touch_close) / atr
            next_bar_clv = (nxt.Close - nxt.Low) / rng if rng > 0 else np.nan

            next3 = day.iloc[t_i + 1: t_i + 4]
            excursion3_atr = ((next3.High.max() - r.trigger) / atr) if len(next3) else np.nan
            prior_high = day.High.iloc[t_i]
            succ = 0
            for _, b in next3.iterrows():
                if b.High > prior_high:
                    succ += 1
                prior_high = max(prior_high, b.High)

            held_window = day.iloc[t_i:t_i + 7]  # touch bar + next 6 = 30 min
            held30 = bool(len(held_window) == 7 and (held_window.Close >= r.trigger * 0.998).all())

            rows.append(dict(
                ticker=tk, date=r.date,
                next_bar_ret_atr=next_bar_ret_atr, next_bar_clv=next_bar_clv,
                excursion3_atr=excursion3_atr, successive_highs=succ, held30=held30,
            ))

    R = pd.DataFrame(rows).merge(outcomes, on=["ticker", "date"], how="left")
    R.to_csv(Path(__file__).resolve().parent / "post_touch_participation.csv", index=False)

    def st(g):
        return pd.Series({
            "n": len(g), "BLAST%": (g.cls == "BLAST").mean() * 100,
            "FAIL%": (g.cls == "FAIL").mean() * 100, "r5_mean": g.r5.mean(),
        })

    print(f"n={len(R)}")

    for col in ["next_bar_ret_atr", "next_bar_clv", "excursion3_atr"]:
        valid = R[col].replace([np.inf, -np.inf], np.nan).notna()
        b = pd.qcut(R.loc[valid, col].rank(method="first"), 3, labels=["T1 low", "T2", "T3 high"])
        t = R.loc[valid].groupby(b, observed=True).apply(st, include_groups=False).round(3)
        t["range"] = R.loc[valid].groupby(b, observed=True)[col].agg(lambda s: f"{s.min():.2f}..{s.max():.2f}")
        print(f"\n{col}"); print(t)

    print("\nsuccessive_highs (0-3 of the next 3 bars making a new High)")
    print(R.groupby("successive_highs", observed=True).apply(st, include_groups=False).round(3))

    print("\nheld30 (every close, touch bar through +30min, stayed >= trigger*0.998)")
    print(R.groupby("held30", observed=True).apply(st, include_groups=False).round(3))


if __name__ == "__main__":
    main()
