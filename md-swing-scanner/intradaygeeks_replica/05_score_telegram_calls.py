"""Score the channel's real intraday stock calls against real price data.

Rules (simple, literal, no add-more scaling):
- Fill: assumed at the called entry price at the call time (calls were posted near market).
- Walk bars strictly AFTER the call time on the same day. Long: Low<=SL -> loss at SL;
  High>=target1 -> win at target1; same bar hits both -> counted as SL (conservative).
  Short mirrored. Neither by the last bar -> exit at that day's last close.
- R = (exit - entry) / |entry - SL|, sign-adjusted for shorts.
Hourly bars (yfinance 60m, ~2y history) for all calls; the hourly bar that CONTAINS the
call time is skipped (it includes pre-call prices), so very fast hits are recorded late.
5-minute bars (intraday_cache) used as an exact cross-check where coverage exists.
Read-only; outputs stay in this folder.
"""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import pandas as pd
import yfinance as yf

HERE = Path(__file__).parent
CACHE5 = HERE.parent / "intraday_cache"


def score(bars, call):
    e, sl, t1, d = call.entry, call.sl, call.target1, call.direction
    risk = abs(e - sl)
    if bars.empty or risk <= 0:
        return None
    for _, b in bars.iterrows():
        if d == "long":
            hit_sl, hit_t = b.Low <= sl, b.High >= t1
        else:
            hit_sl, hit_t = b.High >= sl, b.Low <= t1
        if hit_sl:
            return ("sl_same_bar_as_target" if hit_t else "sl", -1.0)
        if hit_t:
            return ("target1", abs(t1 - e) / risk)
    last = bars.Close.iloc[-1]
    r = (last - e) / risk if d == "long" else (e - last) / risk
    return ("eod", r)


def day_bars(df, call):
    day = df[df.index.date == call.ts.date()]
    return day[day.index > call.ts]


def load_60m(ticker, cache={}):
    if ticker not in cache:
        d = yf.download(f"{ticker}.NS", period="730d", interval="60m", progress=False, auto_adjust=False)
        if not d.empty:
            d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
            d.index = d.index.tz_convert("Asia/Kolkata").tz_localize(None)
        cache[ticker] = d
    return cache[ticker]


def load_5m(ticker):
    p = CACHE5 / f"{ticker}.csv"
    if not p.exists():
        return pd.DataFrame()
    d = pd.read_csv(p, index_col="Datetime", parse_dates=True)
    d.index = pd.to_datetime(d.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return d


if __name__ == "__main__":
    calls = pd.read_csv(HERE / "telegram_calls.csv", parse_dates=["ts"])
    calls = calls[calls.sane & ~calls.options & (calls["style"] == "intraday")].reset_index(drop=True)
    rows = []
    for c in calls.itertuples():
        h = load_60m(c.ticker)
        r60 = score(day_bars(h, c), c) if not h.empty else None
        m5 = load_5m(c.ticker)
        r5 = score(day_bars(m5, c), c) if not m5.empty and (m5.index.date == c.ts.date()).any() else None
        rows.append(dict(msg_id=c.msg_id, ts=c.ts, ticker=c.ticker, direction=c.direction,
                         entry=c.entry, sl=c.sl, target1=c.target1,
                         out60=r60[0] if r60 else None, r60=r60[1] if r60 else None,
                         out5=r5[0] if r5 else None, r5=r5[1] if r5 else None))
    out = pd.DataFrame(rows)
    out.to_csv(HERE / "telegram_calls_scored.csv", index=False)
    print(out.head())
