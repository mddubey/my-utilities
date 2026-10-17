"""(REBUILT 2026-10-17 on the fixed 233 events.) CHART PACK: failures of the turn entry that the GAP ZONE removes (user, 2026-10-17: 'do we need these many filters? the chart reader
would filter these by instinct -- let's look at failures'). Random, fixed seed, chosen before looking: from 238's ATR >= 3% population
(turn 0.1%, 0.5% stop, uptrend, branch A / B, daily 8 not in path), STOPPED trades only: 5 gap-down (< -0.25%) + 5 gap-up (> +0.5%).
Prints date, ticker, entry time / price, stop, 1H EMA34, gap, daily 8 touch, yesterday's close, ATR, and when the stop hit."""
import sys, importlib.util, io, contextlib
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from orb_common import read5_official
spec = importlib.util.spec_from_file_location("m", HERE / "238_turn_entry_drop_gap.py"); m = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(m)
X = m.A3[m.A3.fixed_why == "stop"]
P = pd.concat([X[X.gap <= -0.25].sample(5, random_state=21), X[X.gap > 0.5].sample(5, random_state=21)])
from data.paths import DAILY_DIR
def daily_cols(r):   # everything the user needs without leaving the 1H chart (2026-10-17)
    d = pd.read_csv(DAILY_DIR / f"{r.ticker}.csv", index_col=0, parse_dates=True).sort_index(); d = d[~d.index.duplicated()].dropna(subset=["Close"])
    p = d[d.index < pd.Timestamp(r.date)]; y = p.iloc[-1]; e34 = p.Close.ewm(span=34, adjust=False).mean().iloc[-1]; d8 = (r.s8 / r.entry - 1) * 100
    return dict(d8_vs_entry=f"{d8:+.2f}%", d34=round(e34, 2), y_hlc=f"{y.High:.2f}/{y.Low:.2f}/{y.Close:.2f}")
rows = []
for _, r in P.iterrows():
    x = read5_official(r.ticker); x = x[x.index.normalize() == pd.Timestamp(r.date)]; hm = x.index.strftime("%H:%M").values
    j = np.where(hm == r.t_entry)[0][0]; s = r.entry * 1.005; hit = x.iloc[j + 1:][x.High.iloc[j + 1:] >= s]
    rows.append(dict(n=len(rows) + 1, date=r.date, ticker=r.ticker, gap=f"{r.gap:+.2f}%", open=round(x.Open.iloc[0], 2), y_close=round(r.pc, 2),
                     touch=r.t_touch, entry_time=r.t_entry, entry=round(r.entry, 2), stop=round(s, 2), line_1h34=round(r.line, 2),
                     d8_touch=round(r.s8, 2), atr=f"{r.atr:.2f}%", branch=r.branch, stop_hit=hit.index[0].strftime("%H:%M") if len(hit) else "?",
                     day_high=round(x.High.max(), 2), day_close=round(x.Close.iloc[-1], 2), **daily_cols(r)))
pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string(index=False))
