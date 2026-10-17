"""WHERE IS THE DAILY 8-EMA vs v1's ENTRY? (user, 2026-10-17 weekend chart review of 12 v1 trades: HAL / EMAMILTD / HAVELLS bounced
right at the daily 8 below the entry; 'the 8 EMA is always below in these trades'. Script 231's 12: daily 8 beyond the 1% target 3/3
targets, inside it 3 targets / 6 stops.) Spec fixed before running:
  Population: v1 rules (script 164: liquid, >= Rs100, ATR >= 2, gap -0.25..+0.5, 10:15 red candle at the 1H EMA34, branch A / B, no
    doji cut by the line, converged-lines skip, both regimes) with the STOCK DAILY 8 > 34 FILTER REMOVED (the trend filter mostly
    decides where the daily 8 sits: 85% of v1's trades have it below the entry, 83% of the added downtrend trades above), 3-year 1H set.
  Level = the daily 8 TOUCH price = yesterday's daily EMA8 (where the live daily 8 meets price; same as the 185 scan and the 231 review).
  Buckets vs the entry: below > 1% / 0.5-1% / 0-0.5%, above 0-0.5% / 0.5-1% / > 1%. Columns: daily uptrend (v1) vs downtrend.
  'In the target path' = touch between the entry and the target (E1: 0-1% below; E2: 0..max(1%, 0.35 x ATR) below).
  Also (FACT read): the trigger candle CLOSED ON THE LINE (< 0.05% under the 1H EMA34) vs clearly under.
  Report net Rs @1L (and @1k), target / stall / stop, E1 and E2, Nifty above / below the 200-day, each year; v1 baseline, kept, removed."""
import sys, os, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.argv = ["x"]
P148 = open("148_clean_shape_0915.py").read().replace("(B.s8 > B.s34) & ", "")
src = open("164_v1_without_nifty200.py").read().replace('src = open(Path(__file__).resolve().parent / "148_clean_shape_0915.py").read()', "src = P148").split("\nH = ")[0]
G = {"__file__": os.path.join(HERE, "164_v1_without_nifty200.py"), "P148": P148, "__name__": "x"}
with contextlib.redirect_stdout(io.StringIO()): exec(src, G)
V, B = G["V"], G["B"]
import pandas as pd, numpy as np

for c in ("s8", "s34", "entry", "ema34", "ticker", "atrp"): V[c] = V.ix.map(B[c]) if c not in V else V[c]
V["up"] = V.s8 > V.s34
V["d8"] = (V.s8 / V.entry - 1) * 100
V["bucket"] = pd.cut(V.d8, [-99, -1, -0.5, 0, 0.5, 1, 99], labels=["below > 1%", "below 0.5-1%", "below 0-0.5%", "above 0-0.5%", "above 0.5-1%", "above > 1%"], right=False)
V["tgt"] = np.where(V.ex.str.startswith("E1"), 1.0, np.maximum(1.0, 0.35 * V.atrp))
V["in_path"] = (V.d8 < 0) & (V.d8 > -V.tgt)
V["on_line"] = (V.entry / V.ema34 - 1) * 100 > -0.05
V["yr"] = V.yr.astype(str)
assert V.groupby("ex").size().min() > 0


def cell(x):
    if not len(x): return "0"
    return f"{len(x)} / {(x.o=='stop').mean()*100:.0f}% stop / {x.rs1L.mean():+.0f}"


def row(lab, x):
    if not len(x): return f"| {lab} | 0 | | | | | | |"
    yrs = " / ".join(f"{x[x.yr == y].rs1L.mean():+.0f} ({(x.yr == y).sum()})" if (x.yr == y).any() else "- (0)" for y in ("2024", "2025", "2026"))
    return (f"| {lab} | {len(x)} | {(x.o=='target').mean()*100:.0f} / {(x.o=='stall').mean()*100:.0f} / {(x.o=='stop').mean()*100:.0f}% | "
            f"{x.rs1L.mean():+.0f} | {x.rs1k.mean():+.0f} | {cell(x[x.n200 == True])} | {cell(x[x.n200 == False])} | {yrs} |")


HDR = "| group | trades | target / stall / stop | Rs @1L | Rs @1k | Nifty ABOVE 200d: n / stop / Rs @1L | BELOW 200d | by year 2024 / 2025 / 2026 (n) |\n|---|---|---|---|---|---|---|---|"
for en in sorted(V.ex.unique()):
    X = V[V.ex == en]; U = X[X.up]; D = X[~X.up]
    print(f"\n## {en}\n### Daily 8 touch vs the entry, by the stock's daily trend\n{HDR}")
    for b in V.bucket.cat.categories:
        print(row(f"{b} | UPTREND (v1)", U[U.bucket == b]))
    for b in V.bucket.cat.categories:
        print(row(f"{b} | downtrend (added)", D[D.bucket == b]))
    print(f"\n### v1 (uptrend) -- baseline / kept / removed\n{HDR}")
    print(row("v1 BASELINE (all uptrend)", U))
    print(row("KEPT: daily 8 NOT in the target path", U[~U.in_path])); print(row("REMOVED: daily 8 between entry and target", U[U.in_path]))
    print(row("daily 8 below, beyond the target", U[(U.d8 < 0) & ~U.in_path])); print(row("daily 8 above the entry", U[U.d8 >= 0]))
    print(row("closed ON the line (< 0.05% under)", U[U.on_line])); print(row("closed clearly under the line", U[~U.on_line]))
    print(f"\n### Whole population without the trend filter: daily 8 position decides, trend ignored\n{HDR}")
    print(row("ALL (up + down)", X)); print(row("daily 8 in the target path", X[X.in_path])); print(row("daily 8 below, beyond the target", X[(X.d8 < 0) & ~X.in_path]))
    print(row("daily 8 above the entry", X[X.d8 >= 0]))
print("\nHAND CHECK vs the 231 review (E1, touch % vs entry):")
for t, d in (("HAL", "2024-07-01"), ("HAVELLS", "2025-04-28"), ("PTC", "2025-04-04"), ("GABRIEL", "2026-08-07"), ("FACT", "2024-09-03")):
    h = V[(V.ticker == t) & (V.date.astype(str).str[:10] == d) & V.ex.str.startswith("E1")]
    print(f"  {t} {d}: " + (f"d8 {h.d8.iloc[0]:+.2f}% in_path {bool(h.in_path.iloc[0])} on_line {bool(h.on_line.iloc[0])} up {bool(h.up.iloc[0])} {h.o.iloc[0]}" if len(h) else "NOT FOUND"))

print("\nSHUFFLE TEST (v1 uptrend, KEPT - REMOVED mean Rs @1L, in_path labels shuffled 5,000x):")
rng = np.random.default_rng(7)
for en in sorted(V.ex.unique()):
    U = V[(V.ex == en) & V.up]; r = U.rs1L.values; m = U.in_path.values
    obs = r[~m].mean() - r[m].mean(); sims = np.array([(lambda s: r[~s].mean() - r[s].mean())(rng.permutation(m)) for _ in range(5000)])
    kept_profit = r[~m].sum() / r.sum() * 100
    print(f"  {en}: diff {obs:+.0f}, p = {(sims >= obs).mean():.3f} | kept {(~m).sum()} of {len(m)} trades ({(~m).mean()*100:.0f}%), {kept_profit:.0f}% of total profit")
