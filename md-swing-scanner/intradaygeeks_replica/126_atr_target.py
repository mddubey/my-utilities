"""ATR-scaled target (user, 2026-10-09: 'criminal to expect a calm stock to give 2%'; no candle favoured -- find what works,
fit the schedule later). Spec fixed before running. Population: script 124's X (stack + Nifty > 200d + gap -0.25..+0.5),
candles 09:15 and 10:15, reported equally and together. Target = k x daily ATR14% (yday), k = 0.25 / 0.35 / 0.5; stop = candle
high; two versions: no R:R condition | only if target >= 2 x stop. Reference: fixed 1%. Exit 5 candles / day's last candle,
stop first; re-walked on h1_cache. Fixed Rs1,000 risk, charges Rs85 per Rs1 lakh of position. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "125_stop_cap_target_grid.py").read().split("res = []")[0])
res = []
for t, g in X.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    for ix, r in g.iterrows():
        k = pd.Timestamp(f"{r.date} {r.hour}")
        if k not in h.index: continue
        i = h.index.get_loc(k)
        for lab, tp in (("fixed 1%", 1.0), ("0.25 x ATR", 0.25 * r.atrp), ("0.35 x ATR", 0.35 * r.atrp), ("0.5 x ATR", 0.5 * r.atrp)):
            pnl, o = walk(h, i, r.entry, r.high, tp)
            res.append(dict(ix=ix, tgt=lab, tp=tp, ret=pnl / r.entry * 100, out=o))
R = pd.DataFrame(res).merge(X[["stop", "yr", "date", "hour", "atrp"]], left_on="ix", right_index=True)
R["pos"] = 1000 / (R.stop / 100); R["rs"] = R.ret / 100 * R.pos - 85 * R.pos / 1e5
print(f"median ATR% {X.atrp.median():.2f} -> targets at median: 0.25x {0.25*X.atrp.median():.2f}%, 0.35x {0.35*X.atrp.median():.2f}%, 0.5x {0.5*X.atrp.median():.2f}%")
for HR in ("09:15", "10:15", "both"):
    RR = R if HR == "both" else R[R.hour == HR]
    print(f"\n## candle {HR}\n| target | R:R condition | setups | days | median target % | target / stall / stop % | Rs/trade @ Rs1k risk | 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|")
    for lab in ("fixed 1%", "0.25 x ATR", "0.35 x ATR", "0.5 x ATR"):
        for cn, cond in (("none", lambda d: d.tp > 0), ("target >= 2x stop", lambda d: d.tp >= 2 * d.stop)):
            g = RR[RR.tgt == lab]; g = g[cond(g)]; o = g.out
            if len(g) == 0: continue
            y = " / ".join(f"{g[g.yr == k].rs.mean():+.0f}" if (g.yr == k).sum() >= 20 else "-" for k in ("2024", "2025", "2026"))
            print(f"| {lab} | {cn} | {len(g):,} | {g.date.nunique()} | {g.tp.median():.2f} | {(o=='target').mean()*100:.0f} / {(o=='stall').mean()*100:.0f} / {(o=='stop').mean()*100:.0f} | {g.rs.mean():+.0f} | {y} |")
