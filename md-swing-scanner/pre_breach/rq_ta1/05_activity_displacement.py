"""RQ-TA Family D -- is there unusually high activity around the trigger WITHOUT
corresponding price progress? This is the closest honest proxy this project's OHLCV data
can build toward "absorption" -- it is a volume/price proxy, never a Level 1-4 order-book
claim (brief sec. 17). Same population/outcome join as 03/04 (touched & non-gap-through,
2026-06-10..09-29, n up to 1,475).

Four proxies, all pre-declared before looking at outcomes:
1. touch-bar volume ratio: touch bar's Volume / that DAY's own median 5-min bar volume
   (excludes the 09:15 bar, which is ~97% zero-volume per rq_pb2's own data-quirk note).
2. touch-bar progress: (High_touch - trigger) / ATR -- how far past the trigger the touch
   bar itself pushed, always >= 0 by definition of "touch".
3. post-touch 15-min net progress: (Close[touch_i+2] - trigger) / ATR -- can be negative
   (price already back below the trigger 15 min later).
4. post/pre volume ratio: sum(Volume, 3 bars after touch) / sum(Volume, 3 bars before).

"Flagged" = top-tercile touch-bar volume AND bottom-tercile touch-bar progress
simultaneously -- high activity, little displacement, in the same bar.
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
    # atr_abs is rq_pb2's own T-1-known ATR (shift(1) applied) -- same basis the BLAST/
    # STALL/FAIL labels were built on. Using it here keeps this script's ATR-scaled
    # features on the same, already-verified footing instead of re-deriving a new one.

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
            day_vol = day.Volume.iloc[1:]  # exclude the 09:15 bar (near-zero volume quirk)
            day_med_vol = day_vol.median() if len(day_vol) else np.nan
            if not day_med_vol or day_med_vol <= 0:
                continue

            touch_bar = day.iloc[t_i]
            touch_vol_ratio = touch_bar.Volume / day_med_vol
            touch_progress_atr = (touch_bar.High - r.trigger) / atr if atr else np.nan

            post3 = day.iloc[t_i:t_i + 3]
            pre3 = day.iloc[max(0, t_i - 3):t_i]
            post_vol = post3.Volume.sum()
            pre_vol = pre3.Volume.sum()
            post_pre_ratio = post_vol / pre_vol if pre_vol > 0 else np.nan

            if t_i + 2 < len(day):
                net_progress_atr = (day.Close.iloc[t_i + 2] - r.trigger) / atr if atr else np.nan
            else:
                net_progress_atr = np.nan

            rows.append(dict(
                ticker=tk, date=r.date,
                touch_vol_ratio=touch_vol_ratio, touch_progress_atr=touch_progress_atr,
                post_pre_vol_ratio=post_pre_ratio, net_progress_15m_atr=net_progress_atr,
            ))

    R = pd.DataFrame(rows).merge(outcomes, on=["ticker", "date"], how="left")
    R.to_csv(Path(__file__).resolve().parent / "activity_displacement.csv", index=False)

    def st(g):
        return pd.Series({
            "n": len(g), "BLAST%": (g.cls == "BLAST").mean() * 100,
            "FAIL%": (g.cls == "FAIL").mean() * 100, "r5_mean": g.r5.mean(),
        })

    print(f"n={len(R)}")

    for col in ["touch_vol_ratio", "touch_progress_atr", "post_pre_vol_ratio", "net_progress_15m_atr"]:
        valid = R[col].replace([np.inf, -np.inf], np.nan).notna()
        b = pd.qcut(R.loc[valid, col].rank(method="first"), 3, labels=["T1 low", "T2", "T3 high"])
        t = R.loc[valid].groupby(b, observed=True).apply(st, include_groups=False).round(3)
        t["range"] = R.loc[valid].groupby(b, observed=True)[col].agg(lambda s: f"{s.min():.2f}..{s.max():.2f}")
        print(f"\n{col}"); print(t)

    # "flagged": top-tercile touch-bar volume AND bottom-tercile touch-bar progress together
    valid = R.touch_vol_ratio.notna() & R.touch_progress_atr.notna()
    vt = pd.qcut(R.loc[valid, "touch_vol_ratio"].rank(method="first"), 3, labels=[0, 1, 2])
    pt = pd.qcut(R.loc[valid, "touch_progress_atr"].rank(method="first"), 3, labels=[0, 1, 2])
    flagged = (vt == 2) & (pt == 0)
    Rv = R.loc[valid].copy(); Rv["flagged"] = flagged.values
    print("\nFLAGGED: high touch-bar volume (top tercile) + low touch-bar progress (bottom tercile)")
    print(Rv.groupby("flagged", observed=True).apply(st, include_groups=False).round(3))


if __name__ == "__main__":
    main()
