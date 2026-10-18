"""WHICH SETUPS GO TO TARGET vs GET STOPPED -- only what is KNOWN AT 11:15 (user, 2026-10-18: 'with one trade a day, how do I pick the 46% and not the 26%').
Population: the hourly 34 rejection as the scan trades it (245's X: all 728 setups, scan stop rules, 1% target). Features fixed before running, each with a reason:
  F1 likely-clean: the 09:15 hour closed at / under the 1H 34 (price tests the line from below)            yes / no
  F2 A = pierce: how far the 10:15 high went ABOVE the line (% of entry)                                    above / below the median
  F3 B = late:   how far the 11:15 entry sits BELOW the line (% of entry)                                    above / below the median
  F4 Nifty's 10:15 hour (close vs open, %)                                                                   up / down
  F5 stock vs Nifty since the open (stock open -> 11:15 minus Nifty open -> 11:15)                          weaker / stronger than Nifty
  F6 an earlier high today 0.5-1.5% above the 10:15 candle (within reach, beyond the stop)                  yes / no
  F7 the 1H EMA8 just above the 10:15 high (within 0.5%) -- hourly trend turning up                          yes / no
  F8 10:15 hour volume vs the median of the previous 10 days' 10:15 hours                                    above / below the median
Report per side: n, target / stall / stop, net Rs @1L, each year, and a 5,000x label-shuffle p for the net difference. CHAT ONLY -- nothing recorded."""
import sys, os, io, contextlib, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, os.path.dirname(HERE))
import pandas as pd, numpy as np
from data.paths import INTRADAY_60M_DIR, INDEX_INTRADAY_DIR
sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()): G = runpy.run_path("245_hourly34_stats.py")
X = G["X"].copy(); N = G["G"]["N"].reset_index(drop=True); BB = G["G"]["G"]["B"]
n = N.loc[X.index]
NF = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_1h.csv", index_col=0); NF.index = pd.to_datetime(NF.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
NF = NF[~NF.index.duplicated()].sort_index()
cache = G["G"]["cache"]; feats = []
for idx, r in n.iterrows():
    t = r.ticker; D = pd.Timestamp(str(r.date)[:10])
    if t not in cache:
        h = pd.read_csv(INTRADAY_60M_DIR / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None); cache[t] = h[~h.index.duplicated()].sort_index()
    h = cache[t]; a = h[h.index == D + pd.Timedelta("9h15min")]; c = h[h.index == D + pd.Timedelta("10h15min")]
    prev = h[(h.index.strftime("%H:%M") == "10:15") & (h.index < D)].tail(10)
    nd = NF[NF.index.normalize() == D]; n1015 = nd[nd.index == D + pd.Timedelta("10h15min")]
    dayopen = BB.at[r.ix, "dayopen"]
    feats.append(dict(idx=idx,
        F1=bool(len(a) and a.Close.iloc[0] <= r.ema34),
        F2=(r.high / r.ema34 - 1) * 100, F3=(1 - r.entry / r.ema34) * 100,
        F4=(n1015.Close.iloc[0] / n1015.Open.iloc[0] - 1) * 100 if len(n1015) else np.nan,
        F5=((r.entry / dayopen - 1) - (n1015.Close.iloc[0] / nd.Open.iloc[0] - 1)) * 100 if len(n1015) and len(nd) else np.nan,
        F6=bool((r.dh > r.high * 1.005) and (r.dh <= r.high * 1.015)),
        F7=bool((r.ema8 > r.high) and (r.ema8 <= r.high * 1.005)),
        F8=(c.Volume.iloc[0] / prev.Volume.median()) if len(c) and len(prev) >= 5 and prev.Volume.median() > 0 else np.nan))
F = pd.DataFrame(feats).set_index("idx"); X = X.join(F)
rng = np.random.default_rng(11)
def side(x): return f"{len(x)} | {(x.o=='target').mean()*100:.0f} / {(x.o=='stall').mean()*100:.0f} / {(x.o=='stop').mean()*100:.0f}% | {x.rs1L.mean():+.0f} | " + " / ".join(f"{x[x.yr == y].rs1L.mean():+.0f}" for y in ("2024", "2025", "2026"))
def shuffle(m):
    r = X.rs1L.values; mm = m.values; ok = ~pd.isna(m).values if m.dtype != bool else np.ones(len(m), bool)
    r, mm = r[ok], mm[ok].astype(bool); obs = r[mm].mean() - r[~mm].mean()
    sims = np.array([(lambda s: r[s].mean() - r[~s].mean())(rng.permutation(mm)) for _ in range(5000)])
    return obs, (np.abs(sims) >= abs(obs)).mean()
print(f"{len(X)} setups (all, both regimes). Baseline: {side(X)}\n")
print("| feature (known at 11:15) | side | n | target / stall / stop | net @1L | 2024 / 2025 / 2026 | difference, shuffle p (two-sided) |\n|---|---|---|---|---|---|---|")
SPEC = [("F1 likely-clean (09:15 closed at/under the line)", X.F1 == True, "yes", "no"),
        ("F2 A: pierce above the line", X.F2 > X.F2.median(), f"> {X.F2.median():.2f}%", f"<= {X.F2.median():.2f}%"),
        ("F3 B: entry below the line (late)", X.F3 > X.F3.median(), f"> {X.F3.median():.2f}%", f"<= {X.F3.median():.2f}%"),
        ("F4 Nifty's 10:15 hour", X.F4 > 0, "up", "down"),
        ("F5 stock vs Nifty since the open", X.F5 < 0, "weaker than Nifty", "stronger"),
        ("F6 earlier high 0.5-1.5% above the candle", X.F6 == True, "yes", "no"),
        ("F7 1H EMA8 just above the candle high", X.F7 == True, "yes", "no"),
        ("F8 10:15 hour volume vs its usual", X.F8 > X.F8.median(), f"above median ({X.F8.median():.2f}x)", "below")]
for lab, m, a, b in SPEC:
    obs, p = shuffle(m)
    print(f"| {lab} | {a} | {side(X[m])} | {obs:+.0f}, p {p:.3f} |"); print(f"| | {b} | {side(X[~m])} | |")
