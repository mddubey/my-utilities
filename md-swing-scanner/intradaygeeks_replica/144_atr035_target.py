"""0.35 x ATR target on the current stack (user, 2026-10-10: 'check 0.35 x ATR -- though what if I end up with all the bad trades').
Spec fixed before running. Population: plain liquid touch, 10:15 candle, ATR >= 2%, layers red / Nifty > 200d / stock daily 8>34 /
gap -0.25..+0.5. Exits (stop = candle high, take only if stop <= half the target, i.e. >= 1:2): (a) target 0.35 x ATR; (b) target
max(1%, 0.35 x ATR) (the user's 1% minimum); reference: 1% / stop <= 0.5% (current). For each: setups, days, target / stall / stop
with avg Rs, Rs @1L and @1k risk, by year; chance-vs-actual target odds; one-a-day highest-ATR pick; LUCK (2,000 paths of one random
setup a day). Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
exec(open(Path(__file__).resolve().parent / "130_rebaseline_frozen_frame.py").read().split('B["tp"] = 0.5 * B.atrp')[0])
B = B[(B.hour == "10:15") & (B.atrp >= 2.0) & B.red & (B.n200 == True) & (B.s8 > B.s34) & (B.gap > -0.25) & (B.gap <= 0.5)].copy()
EX = {"0.35 x ATR": lambda r: 0.35 * r.atrp, "max(1%, 0.35 x ATR)": lambda r: max(1.0, 0.35 * r.atrp), "1% (current, stop <= 0.5%)": lambda r: 1.0}
res = []
for t, g in B.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    H, L, C, T = h.High.values, h.Low.values, h.Close.values, h.index; day = T.normalize()
    for ix, r in g.iterrows():
        k = pd.Timestamp(f"{r.date} 10:15")
        if k not in h.index: continue
        i = h.index.get_loc(k)
        for nm, f in EX.items():
            tp = f(r)
            if r.stop > tp / 2: continue
            tgt = r.entry * (1 - tp / 100); px, o = None, "stall"
            for j in range(i + 1, len(C)):
                if day[j] != day[i]: px = C[j - 1]; break
                if H[j] >= r.high: px, o = r.high, "stop"; break
                if L[j] <= tgt: px, o = tgt, "target"; break
                if j - i >= 5 or j + 1 >= len(C) or day[j + 1] != day[i]: px = C[j]; break
            if px is None: continue
            ret = (r.entry - px) / r.entry * 100; pos = 1000 / (r.stop / 100)
            res.append(dict(ex=nm, date=r.date, yr=r.yr, atrp=r.atrp, stop=r.stop, tp=tp, o=o, rs1L=ret * 1000 - 85, rs1k=ret / 100 * pos - 85 * pos / 1e5))
R = pd.DataFrame(res); rng = np.random.default_rng(11)


def luck(g, runs=2000):
    days = sorted(g.date.unique()); by = [g[g.date == d].rs1L.values for d in days]; tot, dd = [], []
    for _ in range(runs):
        x = np.array([b[rng.integers(len(b))] for b in by]); eq = np.cumsum(x); tot.append(eq[-1]); dd.append((eq - np.maximum.accumulate(eq)).min())
    return f"{np.percentile(tot,5):+,.0f} / {np.percentile(tot,50):+,.0f} / {np.percentile(tot,95):+,.0f} | DD {np.percentile(dd,50):,.0f} / {np.percentile(dd,5):,.0f}"


print("| exit | setups | days | median target % | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 | chance vs actual target-first |\n|---|---|---|---|---|---|---|---|---|---|---|")
for nm in EX:
    g = R[R.ex == nm]; parts = []
    for o in ("target", "stall", "stop"):
        x = g[g.o == o]; parts.append(f"{len(x)/len(g)*100:.0f}% ({x.rs1L.mean():+,.0f})")
    d = g[g.o != "stall"]; ch = (d.stop / (d.stop + d.tp)).mean() * 100; ac = (d.o == "target").mean() * 100
    y = " / ".join(f"{g[g.yr == k].rs1L.mean():+.0f}" if (g.yr == k).sum() >= 20 else "-" for k in ("2024", "2025", "2026"))
    print(f"| {nm} | {len(g):,} | {g.date.nunique()} | {g.tp.median():.2f} | " + " | ".join(parts) + f" | {g.rs1L.mean():+.0f} | {g.rs1k.mean():+.0f} | {y} | {ch:.0f}% vs {ac:.0f}% |")
print("\n| exit | ONE A DAY, highest-ATR pick: Rs/trade @1L / @1k, total @1L | LUCK (random pick, 2,000 paths) total bad / typical / good, max DD typical / bad |\n|---|---|---|")
for nm in EX:
    g = R[R.ex == nm]; pk = g.sort_values("atrp", ascending=False).groupby("date").head(1)
    print(f"| {nm} | {pk.rs1L.mean():+.0f} / {pk.rs1k.mean():+.0f}, {pk.rs1L.sum():+,.0f} on {len(pk)} | {luck(g)} |")
