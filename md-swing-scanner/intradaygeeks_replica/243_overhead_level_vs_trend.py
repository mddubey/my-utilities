"""OVERHEAD-LEVEL RULE vs the UPTREND FILTER (user, 2026-10-18: 'test it, but only keep it if it also helps overall'). Spec and pass bar fixed before running.
Trades: v1 simplified (241: hourly 11:15 close entry, stop = 10:15 candle high <= 0.5%, 1% target / 15:15; liquid, >= Rs100, doji skip, ATR >= 3%, daily 8
not between entry and target), both Nifty regimes, E1.
OVERHEAD RULE: skip when any of {daily 8 touch, yesterday's high, the day's high before 11:15, the 1H EMA8 at entry} lies ABOVE the stop and within 1% of it
(stop < level <= stop x 1.01) -- a level the candle has not reached that price can still go and tag.
Versions: (a) uptrend filter (the current candidate) | (b) no uptrend filter + overhead rule | (c) neither | (d) both.
PASS: (b) replaces (a) only if per trade AND one-a-day total are >= (a), top-10-days-removed >= (a), and neither regime is worse than (a)."""
import sys, os, io, contextlib, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, os.path.dirname(HERE))
import pandas as pd, numpy as np
from data.paths import DAILY_DIR, INTRADAY_60M_DIR
WIN = float(sys.argv[1]) if len(sys.argv) > 1 else 0.01      # read BEFORE running 241 (it resets sys.argv)
with contextlib.redirect_stdout(io.StringIO()): G = runpy.run_path("241_v1_simplified.py")
N = G["NEW"].copy(); B = G["B"]; N["ema8"] = N.ix.map(B["ema8"])
yh, dh = [], []
cache = {}
for _, r in N.iterrows():
    D = pd.Timestamp(str(r.date)[:10]); t = r.ticker
    if t not in cache:
        d = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).sort_index(); d = d[~d.index.duplicated()].dropna(subset=["Close"])
        h = pd.read_csv(INTRADAY_60M_DIR / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
        cache[t] = (d, h[~h.index.duplicated()].sort_index())
    d, h = cache[t]
    p = d[d.index < D]; yh.append(p.High.iloc[-1] if len(p) else np.nan)
    pre = h[(h.index.normalize() == D) & (h.index < D + pd.Timedelta("11h15min"))]; dh.append(pre.High.max() if len(pre) else np.nan)
N["yh"], N["dh"] = yh, dh
lv = np.vstack([N.s8, N.yh, N.dh, N.ema8]).T; st = N.high.values[:, None]
N["overhead"] = ((lv > st) & (lv <= st * (1 + WIN))).any(axis=1)
print(f"overhead window: level above the stop and within {WIN*100:.1f}% of it")
d = pd.to_datetime(N.date.astype(str).str[:10]); months = (d.max() - d.min()).days / 30.4
def row(lab, x):
    t10 = x.groupby("date").rs1L.sum().nlargest(10).index
    o = x.sort_values(["date", "atrp"], ascending=[True, False]).drop_duplicates("date"); eq = o.rs1L.cumsum()
    return (f"| {lab} | {len(x)} ({len(x)/months:.1f}/mo) | {(x.o=='target').mean()*100:.0f} / {(x.o=='stall').mean()*100:.0f} / {(x.o=='stop').mean()*100:.0f}% | {x.rs1L.mean():+.0f} | "
            f"{x[~x.date.isin(t10)].rs1L.mean():+.0f} | {x[x.n200==True].rs1L.mean():+.0f} ({(x.n200==True).sum()}) / {x[x.n200==False].rs1L.mean():+.0f} ({(x.n200==False).sum()}) | "
            + " / ".join(f"{x[x.yr==y].rs1L.mean():+.0f}" for y in ("2024", "2025", "2026")) + f" | {len(o)}, {o.rs1L.mean():+.0f}, {eq.iloc[-1]:+,.0f}, {(eq-eq.cummax()).min():,.0f} |")
print("| version | setups | target / stall / stop | net Rs @1L | top-10 days removed | above / below 200d | 2024 / 2025 / 2026 | one a day: trades, per trade, total, max DD |\n|---|---|---|---|---|---|---|---|")
print(row("(a) uptrend filter (current candidate)", N[N.up]))
print(row("(b) NO trend filter + overhead rule", N[~N.overhead]))
print(row("(c) neither", N))
print(row("(d) both", N[N.up & ~N.overhead]))
print(row("removed by the overhead rule (from c)", N[N.overhead]))
print(f"\noverlap: of the downtrend setups, the overhead rule removes {N[~N.up].overhead.mean()*100:.0f}%; of the uptrend setups {N[N.up].overhead.mean()*100:.0f}%")
print(row("downtrend setups the overhead rule KEEPS", N[~N.up & ~N.overhead]))
print("\n### Treating the CAUSE inside each set (kept vs removed by the overhead rule)\n| set | n | target / stall / stop | net | top-10 removed | above / below 200d | 2024 / 2025 / 2026 | one a day |\n|---|---|---|---|---|---|---|---|")
for lab, x in (("UPTREND, overhead level present (removed)", N[N.up & N.overhead]), ("UPTREND, no overhead level (kept)", N[N.up & ~N.overhead]),
               ("DOWNTREND, overhead level present (removed)", N[~N.up & N.overhead]), ("DOWNTREND, no overhead level (kept)", N[~N.up & ~N.overhead])):
    print(row(lab, x))
for k, nm in ((0, "daily 8"), (1, "yesterday's high"), (2, "morning high"), (3, "1H EMA8")):
    m = (lv[:, k] > st[:, 0]) & (lv[:, k] <= st[:, 0] * (1 + WIN)); x = N[m]
    print(f"  only this level counted -- {nm}: present on {m.mean()*100:.0f}% of setups, those net {x.rs1L.mean():+.0f} (stop {(x.o=='stop').mean()*100:.0f}%) vs absent {N[~m].rs1L.mean():+.0f}")
