"""The LIVE rules of 2026-10-12, replayed day by day (user: 'show me some dates of our current baseline'). At 09:30 each day: in-play
(relvol >= 1, top 20), not broken before 09:30; shorts first (skip if yesterday's close is within 1% below the 09:15 low), longs as
fallback; pick the 2 highest relvol. Each pick: stop order at the 09:15 level, stop 10% ATR, hold to 15:15 (5-min mid rule, 175).
A pick that never triggers = no trade. Rs at Rs1,000 risk per trade, net. Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from data.paths import INTRADAY_5M_DIR
A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
P = A[(A.rv >= 1) & (A["rank"] <= 20)].copy()
P = P[~(P.traded & (P.et < "09:30"))]                      # broken before 09:30 -> skipped
lv = {}
for t, g in P[P.side < 0].groupby("ticker"):              # 09:15 low + yesterday's close for the gap-fill check
    m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
    d0 = load(t)
    for _, r in g.iterrows():
        dd = pd.Timestamp(r.date); b = m[m.index == dd + pd.Timedelta("9h15min")]; prev = d0.Close[d0.index < dd]
        if len(b) and len(prev): lv[(t, r.date)] = (b.Low.iloc[0] - prev.iloc[-1]) / b.Low.iloc[0] * 100
P["room"] = [lv.get((t, d), np.nan) if s < 0 else np.nan for t, d, s in zip(P.ticker, P.date, P.side)]
P = P[~((P.side < 0) & (P.room >= 0) & (P.room < 1))]      # gap fill within 1% below -> skip
picks = []
for d, g in P.groupby("date"):
    sh = g[g.side < 0].sort_values("rv", ascending=False); lo = g[g.side > 0].sort_values("rv", ascending=False)
    picks.append(pd.concat([sh, lo]).head(2))
K = pd.concat(picks)
K["result"] = np.where(K.traded, K.o10mid, "not triggered"); K["Rk"] = np.where(K.traded, K.r1k10mid, 0.0); K["RR"] = np.where(K.traded, K.R10mid, np.nan)
days = K.groupby("date").agg(trades=("traded", "sum"), rs=("Rk", "sum"))
print(f"days {len(days)} | picks {len(K)} | triggered {int(K.traded.sum())} | days with >= 1 trade {(days.trades > 0).sum()} | stopped {(K.result == 'stop').sum()} | held to close {(K.result == 'close').sum()}")
print(f"TOTAL Rs {K.Rk.sum():+,.0f} at Rs1,000 risk/trade | per trade {K[K.traded].Rk.mean():+.0f} | per day {days.rs.mean():+.0f} | winning days {(days.rs > 0).sum()} / losing {(days.rs < 0).sum()} / flat {(days.rs == 0).sum()}")
eq = days.rs.cumsum(); print(f"worst drawdown Rs {(eq - eq.cummax()).min():,.0f} | best day {days.rs.max():+,.0f} ({days.rs.idxmax()}) | worst day {days.rs.min():+,.0f} ({days.rs.idxmin()})")
print("\nby month: " + " | ".join(f"{m}: {g.Rk.sum():+,.0f} ({int(g.traded.sum())} trades)" for m, g in K.groupby(K.date.str[:7])))
print("\n| date | pick | side | relvol | entry time | result | R | Rs @1k | day total |\n|---|---|---|---|---|---|---|---|---|")
for d, g in K[K.date >= "2026-09-01"].groupby("date"):
    first = True
    for _, r in g.iterrows():
        print(f"| {d if first else ''} | {r.ticker} | {'short' if r.side < 0 else 'long'} | {r.rv:.1f} | {r.et if r.traded else '-'} | {r.result} | {r.RR:+.1f} | {r.Rk:+,.0f} | {format(days.rs[d], '+,.0f') if first else ''} |".replace("| nan |", "| - |").replace("+nan", "-"))
        first = False
