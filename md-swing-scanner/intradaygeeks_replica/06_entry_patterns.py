"""What did the market look like at the moment of each real channel entry?
Descriptive only. All features use information available at call time:
hourly bars strictly completed before the call, daily data up to the prior day.
"""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf
from backtest import load

HERE = Path(__file__).parent
_c = {}


def h60(t):
    if t not in _c:
        d = yf.download(f"{t}.NS" if not t.startswith("^") else t, period="730d", interval="60m",
                        progress=False, auto_adjust=False)
        if not d.empty:
            d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
            d.index = d.index.tz_convert("Asia/Kolkata").tz_localize(None)
            d["ema8"] = d.Close.ewm(span=8, adjust=False).mean()
            d["ema34"] = d.Close.ewm(span=34, adjust=False).mean()
        _c[t] = d
    return _c[t]


def features(c, nifty):
    h = h60(c.ticker)
    if h.empty:
        return None
    done = h[h.index + pd.Timedelta(hours=1) <= c.ts]          # fully completed bars only
    today = h[(h.index.date == c.ts.date()) & (h.index < c.ts)]  # bars started today before the call
    if done.empty or today.empty:
        return None
    last = done.iloc[-1]
    rng_hi, rng_lo, day_open = today.High.max(), today.Low.min(), today.Open.iloc[0]
    body = abs(last.Close - last.Open); up = last.High - max(last.Close, last.Open)
    lo = min(last.Close, last.Open) - last.Low; tot = last.High - last.Low
    shape = "bull_pin" if tot > 0 and lo >= 2 * body and up <= body else \
            "bear_pin" if tot > 0 and up >= 2 * body and lo <= body else "other"
    try:
        dd = load(c.ticker).reset_index()
    except FileNotFoundError:
        return None
    dd = dd[dd.Date < pd.Timestamp(c.ts.date())]
    if len(dd) < 40:
        return None
    dd["ema34"] = dd.Close.ewm(span=34, adjust=False).mean()
    prev = dd.iloc[-1]
    wk = dd.set_index("Date")
    wk = wk[wk.index < pd.Timestamp(c.ts.date()) - pd.Timedelta(days=pd.Timestamp(c.ts.date()).weekday())]
    wkb = wk.resample("W-FRI").agg({"High": "max", "Low": "min", "Close": "last"}).dropna().iloc[-1]
    PP = (wkb.High + wkb.Low + wkb.Close) / 3
    lvls = {"PP": PP, "R1": 2 * PP - wkb.Low, "S1": 2 * PP - wkb.High, "R2": PP + wkb.High - wkb.Low, "S2": PP - (wkb.High - wkb.Low)}
    near_name, near_val = min(lvls.items(), key=lambda kv: abs(kv[1] - c.entry))
    nt = nifty[(nifty.index.date == c.ts.date()) & (nifty.index < c.ts)]
    nprev = nifty[nifty.index.date < c.ts.date()]
    n_move = (nt.Close.iloc[-1] / nprev.Close.iloc[-1] - 1) * 100 if len(nt) and len(nprev) else np.nan
    s = 1 if c.direction == "long" else -1
    return dict(
        hour=c.ts.hour + c.ts.minute / 60,
        gap_pct=(day_open / prev.Close - 1) * 100 * s,          # + = gap in the trade's direction
        move_from_open_pct=(c.entry / day_open - 1) * 100 * s,  # + = already moved in trade direction today
        pos_in_range=(c.entry - rng_lo) / (rng_hi - rng_lo) if rng_hi > rng_lo else np.nan,
        vs_ema8_1h_pct=(c.entry / last.ema8 - 1) * 100 * s,
        vs_ema34_1h_pct=(c.entry / last.ema34 - 1) * 100 * s,
        h1_trend_with=int((last.ema8 > last.ema34) == (s == 1)),
        daily_trend_with=int((prev.Close > prev.ema34) == (s == 1)),
        last_1h_shape=shape,
        nearest_wk_pivot=near_name,
        dist_wk_pivot_pct=abs(c.entry / near_val - 1) * 100,
        nifty_move_pct=n_move * s,                               # + = Nifty moving the trade's way
    )


if __name__ == "__main__":
    sc = pd.read_csv(HERE / "telegram_calls_scored.csv", parse_dates=["ts"]).dropna(subset=["r60"])
    nifty = h60("^NSEI")
    rows = []
    for c in sc.itertuples():
        f = features(c, nifty)
        if f:
            rows.append({**c._asdict(), **f})
    out = pd.DataFrame(rows).drop(columns=["Index"])
    out.to_csv(HERE / "telegram_entry_features.csv", index=False)
    print("featurized", len(out), "of", len(sc))
