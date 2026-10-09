"""RE-RUN of 130-135 + 128/129/131/133 under the REVISED frame (user, 2026-10-09 late: 'what we ran for the other target, rerun
for this target'). Spec fixed before running. Frame: plain liquid 1H EMA34 touch (115 v3, prev-day liquidity >= Rs15 lakh /
5-min bar); EXIT target 1%, stop = candle high, trade only if stop <= 0.5%; 5 candles / day's last candle, stop first (h1_cache).
Main candle 10:15 (09:15 shown where cheap). Sections: (1) ATR floor sweep, no layers; (2) layers alone + cumulative (ATR >= 2%):
red | Nifty > 200d | stock daily 8>34 | gap -0.25..+0.5; (3) market filter definitions; (4) drop one layer; (5) pick rule, one a day;
(6) stall anatomy + how far trades go; (7) LUCK test for the best pick. Rs @1L and @1k risk, net of Rs85 per lakh. Results only."""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from data.paths import DAILY_DIR
P = pd.read_csv(HERE / "plain_touch_1h.csv")
B = P[(P.liq_prev >= 15) & P.hour.isin(["09:15", "10:15"]) & (P.stop <= 0.5)].copy(); B["d"] = pd.to_datetime(B.date); B["yr"] = B.date.str[:4]
feat = []
for t, g in B.groupby("ticker"):
    d = load(t); c = d.Close
    f = pd.DataFrame({"atrp": (d.atr14 / c * 100).shift(1), "s8": c.ewm(span=8, adjust=False).mean().shift(1),
                      "s34": c.ewm(span=34, adjust=False).mean().shift(1), "gap": (d.Open / c.shift(1) - 1) * 100,
                      "pdl": d.Low.shift(1), "pdh": d.High.shift(1), "pdc": c.shift(1)})
    x = g[["d"]].join(f, on="d"); x.index = g.index; feat.append(x.drop(columns="d"))
B = B.join(pd.concat(feat))
n = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index(); nc = n["Close"]; s200 = nc.rolling(200).mean()
B = B.join(pd.DataFrame({"n834": (nc.ewm(span=8, adjust=False).mean() > nc.ewm(span=34, adjust=False).mean()).shift(1),
                         "n200": (nc > s200).shift(1), "g50": (nc.rolling(50).mean() > s200).shift(1)}), on="d")
print(f"base: {len(B):,} setups (09:15+10:15, stop <= 0.5%); walking...", flush=True); t0 = time.time()
out = {}
for t, g in B.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    H, L, C, T = h.High.values, h.Low.values, h.Close.values, h.index; day = T.normalize()
    for ix, r in g.iterrows():
        k = pd.Timestamp(f"{r.date} {r.hour}")
        if k not in h.index: continue
        i = h.index.get_loc(k); e = r.entry; tgt = e * 0.99; best, bh, px, o = e, 0, None, "stall"
        for j in range(i + 1, len(C)):
            if day[j] != day[i]: px = C[j - 1]; break
            if H[j] >= r.high: px, o = r.high, "stop"; break
            if L[j] < best: best, bh = L[j], j - i
            if L[j] <= tgt: px, o = tgt, "target"; break
            if j - i >= 5 or j + 1 >= len(C) or day[j + 1] != day[i]: px = C[j]; break
        if px is None: continue
        dl = L[(day == day[i]) & (np.arange(len(L)) <= i)].min()
        out[ix] = ((e - px) / e * 100, o, (e - best) / e * 100, bh, dl)
B = B.loc[list(out)]
for k, c in enumerate(("ret", "o", "best", "bh", "dl")): B[c] = [out[i][k] for i in B.index]
B["rs1L"] = B.ret * 1000 - 85; pos = 1000 / (B.stop / 100); B["rs1k"] = B.ret / 100 * pos - 85 * pos / 1e5
B["trend"] = B.s8 / B.s34 - 1
print(f"walked {len(B):,} in {time.time()-t0:.0f}s")
LAY = {"red": lambda d: d.red, "Nifty > 200d": lambda d: d.n200 == True, "stock daily 8>34": lambda d: d.s8 > d.s34,
       "gap -0.25..+0.5": lambda d: (d.gap > -0.25) & (d.gap <= 0.5)}


def full(d, skip=None):
    m = d.atrp >= 2.0
    for k, f in LAY.items():
        if k != skip: m &= f(d)
    return d[m]


def row(lab, g, extra=True):
    if len(g) < 20: return f"| {lab} | {len(g)} | | | | | | | |"
    parts = []
    for o in ("target", "stall", "stop"):
        x = g[g.o == o]; parts.append(f"{len(x)/len(g)*100:.0f}% ({x.rs1L.mean():+,.0f})" if len(x) else "0%")
    y = " / ".join(f"{g[g.yr == k].rs1L.mean():+.0f}" if (g.yr == k).sum() >= 20 else "-" for k in ("2024", "2025", "2026"))
    return f"| {lab} | {len(g):,} | {g.date.nunique()} | " + " | ".join(parts) + f" | {g.rs1L.mean():+.0f} | {g.rs1k.mean():+.0f} | {y} |"


H = "| group | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
T10 = B[B.hour == "10:15"]
print("\n# (1) ATR floor sweep, 10:15, NO layers (cumulative floors)\n" + H)
print(row("no ATR filter", T10))
for a in (1.5, 2.0, 2.5, 3.0, 3.5): print(row(f"ATR >= {a}", T10[T10.atrp >= a]))
print("\n# (1b) ATR floor sweep, 10:15, WITH the 4 layers\n" + H)
F4 = lambda d: d[d.red & (d.n200 == True) & (d.s8 > d.s34) & (d.gap > -0.25) & (d.gap <= 0.5)]
for a in (0, 1.5, 2.0, 2.5, 3.0, 3.5): print(row(f"ATR >= {a}", F4(T10[T10.atrp >= a])))
for HR, X in (("10:15", T10), ("09:15", B[B.hour == "09:15"])):
    X2 = X[X.atrp >= 2.0]
    print(f"\n# (2) {HR}: layers ALONE on the base (ATR >= 2%)\n" + H); print(row("BASE", X2))
    for k, f in LAY.items(): print(row(f"+ {k} only", X2[f(X2)]))
    print(f"\n# (2) {HR}: CUMULATIVE\n" + H); Y = X2; print(row("BASE", Y))
    for k, f in LAY.items(): Y = Y[f(Y)]; print(row(f"+ {k}", Y))
X2 = T10[T10.atrp >= 2.0]; NL = X2[X2.red & (X2.s8 > X2.s34) & (X2.gap > -0.25) & (X2.gap <= 0.5)]
print("\n# (3) market filter definitions, 10:15 (other 3 layers + ATR >= 2 on)\n" + H)
for nm, f in (("none", lambda d: d.red == d.red), ("Nifty 8>34", lambda d: d.n834 == True), ("close > 200d", lambda d: d.n200 == True),
              ("50 > 200", lambda d: d.g50 == True), ("8>34 AND > 200d", lambda d: (d.n834 == True) & (d.n200 == True))):
    print(row(nm, NL[f(NL)]))
print("\n# (4) drop one layer, 10:15\n" + H); print(row("FULL", full(T10)))
for k in LAY: print(row(f"without {k}", full(T10, k)))
print("\n# (4b) drop one layer, 09:15\n" + H); print(row("FULL", full(B[B.hour == "09:15"])))
for k in LAY: print(row(f"without {k}", full(B[B.hour == "09:15"], k)))
Z = full(T10)


def path(g):
    g = g.sort_values("date"); x = g.rs1L.values; eq = np.cumsum(x); dd = (eq - np.maximum.accumulate(eq)).min(); best = cur = 0
    for v in (x <= 0): cur = cur + 1 if v else 0; best = max(best, cur)
    return f"{g.rs1L.sum():+,.0f} | {dd:,.0f} | {best}"


print(f"\n# (5) pick rule, 10:15, one a day ({Z.date.nunique()} days, {len(Z)/Z.date.nunique():.1f} setups/day)\n| pick | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 | total @1L | max DD | longest losing streak |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
picks = {}
for nm, col, asc in (("closest to EMA34", "dist", True), ("highest ATR", "atrp", False), ("strongest stock uptrend", "trend", False), ("tightest stop", "stop", True)):
    g = Z.sort_values(col, ascending=asc).groupby("date").head(1); picks[nm] = g; print(row(nm, g) + f" {path(g)} |")
rng = np.random.default_rng(3)
r1 = [Z.groupby("date").sample(1, random_state=int(rng.integers(1e9))) for _ in range(300)]
print(f"| RANDOM (300 draws) | | | | | | {np.mean([x.rs1L.mean() for x in r1]):+.0f} (5th {np.percentile([x.rs1L.mean() for x in r1],5):+.0f}) | {np.mean([x.rs1k.mean() for x in r1]):+.0f} | | | | |")
Z = Z.copy(); Z["frac"] = Z.best / 1.0; Z["give"] = (Z.best - Z.ret)
Z["stype"] = np.where(Z.o != "stall", Z.o, np.where(Z.frac < 0.25, "stall: went nowhere", np.where((Z.frac >= 0.5) & (Z.give >= Z.frac / 2), "stall: out of steam",
             np.where(Z.give <= 0.25, "stall: out of time", "stall: other"))))
print(f"\n# (6) stall anatomy, 10:15 full stack ({len(Z)} trades)\n| outcome | share | avg Rs @1L | avg best move % | median hour of best |\n|---|---|---|---|---|")
for sname, g in Z.groupby("stype"): print(f"| {sname} | {len(g)/len(Z)*100:.0f}% | {g.rs1L.mean():+,.0f} | {g.best.mean():.2f} | {g.bh.median():.0f} |")
print("\n# (6b) how far the trades went (best price before the exit)\n| reached | 0.25% | 0.5% | 0.75% | 1.0% |\n|---|---|---|---|---|")
print("| share | " + " | ".join(f"{(Z.best >= x).mean()*100:.0f}%" for x in (0.25, 0.5, 0.75, 1.0)) + " |")
PP = (Z.pdh + Z.pdl + Z.pdc) / 3; S1 = 2 * PP - Z.pdh; tg = Z.entry * 0.99
print("\n# (6c) obstacles between entry and target\n| level in path | share | target % in / out | stall % in / out | Rs in / out |\n|---|---|---|---|---|")
for nm, lv in (("previous day low", Z.pdl), ("day's low so far", Z.dl), ("daily PP", PP), ("daily S1", S1)):
    m = (lv < Z.entry) & (lv > tg); a, b = Z[m], Z[~m]
    print(f"| {nm} | {m.mean()*100:.0f}% | {(a.o=='target').mean()*100:.0f} / {(b.o=='target').mean()*100:.0f} | {(a.o=='stall').mean()*100:.0f} / {(b.o=='stall').mean()*100:.0f} | {a.rs1L.mean():+.0f} / {b.rs1L.mean():+.0f} |")


def luck(g, runs=2000):
    days = sorted(g.date.unique()); by = [g[g.date == d].rs1L.values for d in days]; tot, dd, st = [], [], []
    for _ in range(runs):
        x = np.array([b[rng.integers(len(b))] for b in by]); eq = np.cumsum(x); tot.append(eq[-1]); dd.append((eq - np.maximum.accumulate(eq)).min())
        best = cur = 0
        for v in (x <= 0): cur = cur + 1 if v else 0; best = max(best, cur)
        st.append(best)
    q = np.percentile
    return f"total {q(tot,5):+,.0f} / {q(tot,50):+,.0f} / {q(tot,95):+,.0f} | DD {q(dd,50):,.0f} / {q(dd,5):,.0f} | streak {q(st,50):.0f} / {q(st,95):.0f}"


print(f"\n# (7) LUCK, 10:15 full stack, one RANDOM setup a day, 2,000 paths (@1L): bad / typical / good")
print(luck(full(T10)))
