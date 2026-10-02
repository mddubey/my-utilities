"""Pre-breach detector, step 3b -- intraday opening features for panel rows inside the 5-min
cache window (2026-06-10 .. 2026-09-23, ~74 sessions).

Data quirk (checked 2026-09-30): the 09:15 bar's Volume is 0 in ~97% of rows in this
yfinance cache, so a first-5-minute RVOL is NOT computable here. The earliest usable volume
is the 09:20-09:25 bar, known at 09:25. Features are therefore split by clock:
  09:20 : first-bar return / close-location / distance-to-trigger at 09:20 (price only)
  09:25 : rvol_0925 = (09:20 bar volume) / median of that ticker's own 09:20-bar volume over
          its prior 20 sessions (strictly prior -- no same-day or future sessions)
Outcomes (never features): touched_after_0920/0925, first_touch time, held30 (after first
touch, every 5-min close in the next 30 minutes >= trigger*0.998, the swing_qs convention),
already_touched_by_0920 (fire happened inside the first bar -- decision is moot for those).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent


def load_5m(t):
    p = ROOT / "intraday_cache" / f"{t}.csv"
    if not p.exists():
        return None
    d = pd.read_csv(p)
    d["dt"] = pd.to_datetime(d.Datetime, utc=True).dt.tz_convert("Asia/Kolkata")
    d["day"] = d.dt.dt.normalize().dt.tz_localize(None)
    d["hm"] = d.dt.dt.strftime("%H:%M")
    return d


def features_for(t, prow, bars):
    """prow: panel rows for ticker t; bars: that ticker's 5-min bars."""
    by_day = {k: g.reset_index(drop=True) for k, g in bars.groupby("day")}
    days = sorted(by_day)
    v0920 = pd.Series({d: by_day[d].loc[by_day[d].hm == "09:20", "Volume"].sum() for d in days})
    out = []
    for r in prow.itertuples():
        g = by_day.get(r.date)
        if g is None or len(g) < 10 or g.hm.iloc[0] != "09:15":
            continue
        trig = r.trigger
        b1 = g.iloc[0]
        b2 = g.iloc[1] if g.hm.iloc[1] == "09:20" else None
        prior = v0920[[d for d in days if d < r.date]].tail(20)
        rng1 = b1.High - b1.Low
        hit = g.index[g.High >= trig]
        first_touch = int(hit[0]) if len(hit) else None
        held30 = None
        if first_touch is not None:
            nxt = g.iloc[first_touch + 1:first_touch + 7]
            held30 = bool(len(nxt) == 6 and (nxt.Close >= trig * 0.998).all())
        rec = dict(
            ticker=t, date=r.date,
            # 09:20 features
            open_5m=b1.Open, px_0920=b1.Close,
            dist_0920_pct=(trig / b1.Close - 1) * 100,
            bar1_ret_pct=(b1.Close / b1.Open - 1) * 100,
            bar1_clv=(b1.Close - b1.Low) / rng1 if rng1 > 0 else np.nan,
            bar1_range_atr=rng1 / (r.atr_pct / 100 * r.open_) if r.atr_pct else np.nan,
            # 09:25 features
            px_0925=b2.Close if b2 is not None else np.nan,
            dist_0925_pct=(trig / b2.Close - 1) * 100 if b2 is not None else np.nan,
            rvol_0925=(b2.Volume / prior.median()) if (b2 is not None and len(prior) >= 10 and prior.median() > 0) else np.nan,
            # outcomes
            already_touched_by_0920=bool(first_touch == 0),
            already_touched_by_0925=bool(first_touch is not None and first_touch <= 1),
            touched_5m=first_touch is not None,
            first_touch_hm=g.hm.iloc[first_touch] if first_touch is not None else None,
            held30=held30,
        )
        out.append(rec)
    return out


def main():
    panel = pd.read_csv(OUT / "panel.csv", parse_dates=["date"])
    panel = panel[panel.date >= "2026-06-10"]
    recs = []
    for k, (t, prow) in enumerate(panel.groupby("ticker")):
        bars = load_5m(t)
        if bars is None:
            continue
        recs += features_for(t, prow, bars)
        if k % 50 == 0:
            print(k, t, len(recs), flush=True)
    pd.DataFrame(recs).to_csv(OUT / "intraday_features.csv", index=False)
    print("done", len(recs))


if __name__ == "__main__":
    main()
